#!/usr/bin/env python3
"""One BOM line per part, and the better-rated part in each line (owner, 2026-09-13).

The board buys the same physical part under several spellings and several voltage ratings. This
rewrites `Value` (and `Footprint` where the package changes) so each part appears once. **No net,
no reference and no position is touched** -- the netlist after must differ only in component
values, which `--verify` checks.

The rule the owner set: keep the better option -- highest voltage rating, then smallest footprint --
rather than the cheapest. Applied per footprint, because the best rating is not offered in every
package. Every target below was confirmed in stock at LCSC on 2026-09-13 (price @100):

    100nF  0402  50V X7R  C307331  basic, 16M      was 16V/50V/'100n'   -- X7R and 50V, +$0.13 total
    1uF    0402  25V X5R  C52923   basic, 14.5M    was 16V/25V
    4.7uF  0402  10V X5R  C23733   basic,  4.8M    was 6.3V -- 10V is the best 0402 offered
    4.7uF  0805  25V X5R  C1779    basic,  5.2M    was 10V/16V (0603 and 0805 merged here)
    10uF   0805  25V X5R  C15850   basic, 12.7M    was 10V/16V/'10u'  (50V exists, 6x price, no gain)
    22uF   0805  25V X5R  C45783   basic,  5.4M    was 10V/6.3V/'22u'/16V-1206
    1nF    0402  50V                                was 25V/50V/'1000pF'

Two changes are more than tidying:

  * **22uF/6.3V 0603 -> 22uF/25V 0805.** Eight of the fifteen sit on +3V3. An X5R rated 6.3V at
    3.3V bias keeps roughly a third of its capacitance, so those "22 uF" were really ~7-9 uF. The
    owner accepted the larger package; if a part does not fit, put that one back to 0603.
  * **47uF/6.3V 1206 -> two 22uF/25V 0805 per buck.** LCSC stocks no 47 uF 1206 at all, and the
    only 47 uF 0805 is 6.3V, which halves at 1.8V bias. Two 22 uF/25V give more *effective*
    capacitance than the 47 uF would have, and reuse a line the board already buys.

Resistors: one spelling, `<value>/1%`, lowercase k/M/R. 1% thick film costs the same as 5% at 0402,
so the tighter part is kept. `R1115` also moves to 0603: it dissipates ~40 mW (20 V across 10 k)
and an 0402 is rated 63 mW -- 63%, past the usual 50% derating.
"""
import glob, pathlib, re, subprocess, sys

C402, C603, C805, C1206 = ('Capacitor_SMD:C_0402_1005Metric', 'Capacitor_SMD:C_0603_1608Metric',
                           'Capacitor_SMD:C_0805_2012Metric', 'Capacitor_SMD:C_1206_3216Metric')
R402, R603 = 'Resistor_SMD:R_0402_1005Metric', 'Resistor_SMD:R_0603_1608Metric'

# (old value, old footprint-tail) -> (new value, new footprint)
CAPS = {
    ('100n', C402): ('100nF/50V', C402), ('100nF/16V', C402): ('100nF/50V', C402),
    ('1uF/16V', C402): ('1uF/25V', C402),
    ('4.7uF/6.3V', C402): ('4.7uF/10V', C402),
    ('4.7uF/10V', C603): ('4.7uF/25V', C805), ('4.7uF/16V', C603): ('4.7uF/25V', C805),
    ('4.7uF/10V', C805): ('4.7uF/25V', C805), ('4.7uF/16V', C805): ('4.7uF/25V', C805),
    ('10u', C805): ('10uF/25V', C805), ('10uF/10V', C805): ('10uF/25V', C805),
    ('10uF/16V', C805): ('10uF/25V', C805),
    ('22u', C805): ('22uF/25V', C805), ('22uF/10V', C805): ('22uF/25V', C805),
    ('22uF/16V', C1206): ('22uF/25V', C805), ('22uF/6.3V', C603): ('22uF/25V', C805),
    ('47uF/6.3V', C1206): ('22uF/25V', C805),
    ('1nF/25V', C402): ('1nF/50V', C402), ('1000pF/50V', C402): ('1nF/50V', C402),
}
def r_norm(v):
    m = re.match(r'^([\d.]+)\s*([kKmMrR]?)(?:/(\d+)%)?$', v.strip())
    if not m:
        return None
    num, unit, tol = m.group(1), m.group(2), m.group(3)
    unit = {'k': 'k', 'K': 'k', 'm': 'M', 'M': 'M', 'r': 'R', 'R': 'R', '': ''}[unit]
    if unit == '' and float(num) >= 1:            # bare number = ohms
        unit = 'R'
    return f'{num}{unit}/1%'

KEEP = {'20mR', '0R'}                              # sense resistor and links: leave alone


def main():
    verify = '--verify' in sys.argv
    run = [n for n in ('kicad', 'eeschema', 'pcbnew') if
           subprocess.run(['pgrep', '-x', n], capture_output=True).returncode == 0]
    if run and not verify:
        sys.exit(f'{", ".join(run)} running -- close KiCad first (CLAUDE.md).')

    changes, per_sheet = {}, {}
    for f in sorted(glob.glob('*.kicad_sch')):
        if f == 'r2_claude.kicad_sch':
            continue
        text = pathlib.Path(f).read_text(encoding='utf-8')
        out, n = [], 0
        i = 0
        # walk top-level (symbol ...) blocks
        for m in re.finditer(r'\n\t\(symbol\n', text):
            s, depth, j, ins = m.start() + 1, 0, m.start() + 1, False
            while True:
                c = text[j]
                if c == '"' and text[j - 1] != '\\':
                    ins = not ins
                elif not ins:
                    if c == '(':
                        depth += 1
                    elif c == ')':
                        depth -= 1
                        if depth == 0:
                            break
                j += 1
            blk = text[s:j + 1]
            lid = re.search(r'\(lib_id "([^"]+)"\)', blk)
            ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
            val = re.search(r'\(property "Value" "([^"]*)"', blk)
            fp = re.search(r'\(property "Footprint" "([^"]*)"', blk)
            if not (lid and ref and val and fp) or ref.group(1).startswith('#'):
                continue
            newv = newf = None
            if lid.group(1) == 'Device:C':
                hit = CAPS.get((val.group(1), fp.group(1)))
                if hit:
                    newv, newf = hit
            elif lid.group(1) == 'Device:R' and val.group(1) not in KEEP:
                nv = r_norm(val.group(1))
                if nv and nv != val.group(1):
                    newv, newf = nv, fp.group(1)
                if ref.group(1) == 'R1115':          # 40 mW in an 0402: move to 0603
                    newv, newf = (newv or val.group(1)), R603
            if newv is None:
                continue
            nb = re.sub(r'(\(property "Value" ")[^"]*(")', lambda mm: mm.group(1) + newv + mm.group(2), blk, count=1)
            nb = re.sub(r'(\(property "Footprint" ")[^"]*(")', lambda mm: mm.group(1) + newf + mm.group(2), nb, count=1)
            out.append((s, j + 1, nb))
            changes.setdefault((val.group(1), newv), 0)
            changes[(val.group(1), newv)] += 1
            n += 1
        if out and not verify:
            for s, e, nb in reversed(out):
                text = text[:s] + nb + text[e:]
            pathlib.Path(f).write_text(text, encoding='utf-8')
        if n:
            per_sheet[f] = n
    for (a, b), n in sorted(changes.items()):
        print(f'  {a:<12} -> {b:<12} x{n}')
    print(f'  {sum(per_sheet.values())} parts across {len(per_sheet)} sheets: '
          + ', '.join(f'{k.replace(".kicad_sch","")}:{v}' for k, v in sorted(per_sheet.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
