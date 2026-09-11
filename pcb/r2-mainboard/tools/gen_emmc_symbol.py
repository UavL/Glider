#!/usr/bin/env python3
"""Generate the `KLM8G1GETF-B041` eMMC symbol in r2.kicad_sym — three units, 153 pins.

Source of truth: `datasheets/Storage/samsung_emmc.pdf` (Samsung Rev. 1.21, one datasheet for
KLM8G1GETF-B041 8 GB / KLMAG1JETD-B041 16 GB / KLMBG2JETD-B041 32 GB / KLMCG4JETD-B041 64 GB — one
ball map for all four), section 3.1, **[Table 2] 153 Ball Information**. The table is parsed from
the PDF at run time; nothing is typed in from it.

Figure 1 on the same page is *not* parsed. Its text layer puts the row labels and the ball names in
columns that drift by one on some rows (checked 2026-09-12: the offsets put DAT6/DAT7 on B4/B5
where the table says B5/B6), which is the trap `parse_osd62x_pinout.py` hit on the SiP's ball map.
Instead `FIGURE` below is a hand transcription of it, and the parsed table must equal it exactly —
so a future parse that drifts fails here instead of quietly producing a wrong symbol.

The rules are `docs/osd62x-symbol-guide.md`, as for the SiP: pin number = ball, pin name = the
datasheet's name verbatim, no hidden pins, no two pins at one position in a unit, everything on the
2.54 mm grid. Every one is asserted on the text about to be written.

The footprint is KiCad's stock `Package_BGA:LFBGA-153_11.5x13mm_Layout14x14_P0.5mm` (JEDEC MO-276F,
0.24 mm lands). It is not copied into the project: the board already places three stock `Package_BGA`
footprints. Its 153 pads are asserted to be exactly this symbol's 153 pin numbers.

    tools/gen_emmc_symbol.py                 # write r2.kicad_sym in place (refuses if KiCad runs)
    tools/gen_emmc_symbol.py --out FILE      # write the result elsewhere, for staging
"""
import argparse, collections, math, pathlib, re, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent.parent
PDF  = HERE / 'datasheets/Storage/samsung_emmc.pdf'
LIB  = HERE / 'r2.kicad_sym'
FP_CANDIDATES = [
    pathlib.Path('/home/lum/Apps/AppDir/share/kicad/footprints/Package_BGA.pretty'),
    pathlib.Path('/usr/share/kicad/footprints/Package_BGA.pretty'),
]
FP_NAME   = 'LFBGA-153_11.5x13mm_Layout14x14_P0.5mm'
FOOTPRINT = f'Package_BGA:{FP_NAME}'
NAME      = 'KLM8G1GETF-B041'
LEN, PITCH, NAME_OFS = 5.08, 2.54, 1.016
CHAR = 1.05                       # mm per character of 1.27 mm KiCad text, generous
GAP  = None                       # an empty row between groups
ROWS = 'ABCDEFGHJKLMNP'           # JEDEC skips I and O

# Hand transcription of Figure 1 (ball-side down view), section 3.1. Checked against [Table 2] by
# this script; see the module docstring for why the figure is not machine-parsed.
FIGURE = {
    'A3': 'DAT0', 'A4': 'DAT1', 'A5': 'DAT2', 'A6': 'VSS',
    'B2': 'DAT3', 'B3': 'DAT4', 'B4': 'DAT5', 'B5': 'DAT6', 'B6': 'DAT7',
    'C2': 'VDDI', 'C4': 'VSS', 'C6': 'VCCQ',
    'E6': 'VCC', 'E7': 'VSS',
    'F5': 'VCC',
    'G5': 'VSS',
    'H5': 'Data Strobe', 'H10': 'VSS',
    'J5': 'VSS', 'J10': 'VCC',
    'K5': 'RSTN', 'K8': 'VSS', 'K9': 'VCC',
    'M4': 'VCCQ', 'M5': 'CMD', 'M6': 'CLK',
    'N2': 'VSS', 'N4': 'VCCQ', 'N5': 'VSS',
    'P3': 'VCCQ', 'P4': 'VSS', 'P5': 'VCCQ', 'P6': 'VSS',
}

# Section 3.1's own descriptions: CLK is an input, Data Strobe is "generated from eMMC to host",
# CMD and DAT0-7 are bidirectional, RST_n is an input. VDDi is "internal power node to stabilize
# regulator output" — an output of the part's own regulator, so power_out: it drives its capacitor
# and must never be tied to a rail. RFU balls are "do not use for any usage".
TYPES = {'CLK': 'input', 'RSTN': 'input', 'Data_Strobe': 'output', 'CMD': 'bidirectional',
         'VCC': 'power_in', 'VCCQ': 'power_in', 'VSS': 'power_in', 'VDDI': 'power_out',
         'NC': 'no_connect'}


def display(n):
    """KiCad stores pin names without spaces, so the datasheet's `Data Strobe` becomes
    `Data_Strobe` -- write that, rather than leave the substitution to KiCad on load."""
    return n.replace(' ', '_')


def etype(n):
    return TYPES.get(n, 'bidirectional' if n.startswith('DAT') else None) or sys.exit(f'no type for {n}')


def key(b):
    return (ROWS.index(b[0]), int(b[1:]))


def parse_table(pdf):
    """[Table 2] 153 Ball Information -> {ball: name}, the datasheet's names verbatim."""
    txt = subprocess.run(['pdftotext', '-layout', str(pdf), '-'],
                         check=True, capture_output=True, text=True).stdout.split('\n')
    lo = next(i for i, l in enumerate(txt) if '[Table 2]' in l)
    hi = next(i for i, l in enumerate(txt) if 'Figure 1. 153-FBGA' in l)
    names = r'DAT[0-7]|CLK|CMD|RSTN|VCCQ|VCC|VDDI|VSS|Data\s+Strobe'
    out = {}
    for line in txt[lo:hi]:
        m = re.match(rf'\s+([{ROWS}])(\d{{1,2}})\s{{2,}}({names})(?:\s|$)', line)
        if m:
            ball, name = m.group(1) + m.group(2), re.sub(r'\s+', ' ', m.group(3))
            assert ball not in out or out[ball] == name, f'{ball} listed twice, differently'
            out[ball] = name
    return out


def footprint_pads():
    for d in FP_CANDIDATES:
        f = d / f'{FP_NAME}.kicad_mod'
        if f.exists():
            return f, set(re.findall(r'\(pad\s+"([A-Z]+\d+)"\s', f.read_text()))
    sys.exit(f'{FP_NAME}.kicad_mod not found in {[str(d) for d in FP_CANDIDATES]}')


def esc(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')


def fnt(ind):
    return f'{ind}(effects\n{ind}\t(font\n{ind}\t\t(size 1.27 1.27)\n{ind}\t)\n{ind})\n'


def pin(t, x, y, rot, name, num):
    return (f'\t\t\t(pin {t} line\n\t\t\t\t(at {x:g} {y:g} {rot})\n\t\t\t\t(length {LEN:g})\n'
            f'\t\t\t\t(name "{esc(name)}"\n' + fnt('\t\t\t\t\t') + '\t\t\t\t)\n'
            f'\t\t\t\t(number "{esc(num)}"\n' + fnt('\t\t\t\t\t') + '\t\t\t\t)\n\t\t\t)\n')


def geometry(left, right, names):
    rows = max(len(left), len(right))
    lmax = max([len(names[b]) for b in left if b] or [0])
    rmax = max([len(names[b]) for b in right if b] or [0])
    w = (lmax + rmax) * CHAR + 2 * NAME_OFS + (2 * PITCH if lmax and rmax else PITCH)
    w = max(15.24, math.ceil(w / (2 * PITCH)) * 2 * PITCH)
    return rows, 0, w / 2              # top-aligned: one field position serves every unit


def unit_block(n, uname, left, right, names):
    rows, top, half = geometry(left, right, names)
    out = [f'\t\t(symbol "{NAME}_{n}_1"\n\t\t\t(unit_name "{uname}")\n'
           f'\t\t\t(rectangle\n\t\t\t\t(start {-half:g} {top + PITCH:g})\n'
           f'\t\t\t\t(end {half:g} {top - rows * PITCH:g})\n'
           '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n'
           '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)\n']
    for side, xs, rot in ((left, -half - LEN, 0), (right, half + LEN, 180)):
        for i, b in enumerate(side):
            if b:
                out.append(pin(etype(names[b]), xs, top - i * PITCH, rot, names[b], b))
    out.append('\t\t)\n')
    return ''.join(out), rows, 2 * half


def build_units(names):
    by = collections.defaultdict(list)
    for b, n in names.items():
        by[n].append(b)
    for n in by:
        by[n].sort(key=key)

    def col(*groups):
        out = []
        for g in groups:
            if out:
                out.append(GAP)
            for n in g:
                out += by[n]
        return out

    nc = by['NC']
    half = (len(nc) + 1) // 2
    return [
        ('MEM', col(['CLK', 'CMD'], ['Data_Strobe'], ['RSTN']), col([f'DAT{i}' for i in range(8)])),
        ('PWR', col(['VCC'], ['VCCQ'], ['VDDI']), col(['VSS'])),
        ('NC',  nc[:half], nc[half:]),
    ]


def splice(text):
    """(head, old block or '', tail) around the NAME symbol; appends at the end if absent."""
    m = re.search(r'\n\t\(symbol "%s"\n' % re.escape(NAME), text)
    if not m:
        j = text.rstrip().rfind('\n)')             # before the library's closing paren
        assert j > 0, 'cannot find the end of the library'
        return text[:j + 1], '', text[j + 1:]
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
    return text[:s], text[s:j + 2], text[j + 2:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=pathlib.Path, help='write here instead of r2.kicad_sym')
    args = ap.parse_args()
    dest = args.out or LIB
    # Exact process names: `pgrep -f kicad` also matches the shell that invoked this script, if
    # its command line happens to mention KiCad -- a false positive that blocks a legitimate run.
    running = [n for n in ('kicad', 'eeschema', 'pcbnew', 'symbol_editor')
               if subprocess.run(['pgrep', '-x', n], capture_output=True).returncode == 0]
    if dest == LIB and running:
        sys.exit(f'{", ".join(running)} running — close it, or use --out to stage (CLAUDE.md).')

    table = parse_table(PDF)
    assert table == FIGURE, ('the parsed table and the hand-read figure disagree: '
                             f'{sorted(set(table.items()) ^ set(FIGURE.items()))[:8]}')
    assert len(table) == 33, len(table)

    fpfile, pads = footprint_pads()
    assert len(pads) == 153, f'{len(pads)} pads in {fpfile.name}'
    assert set(table) <= pads, f'balls with no land: {sorted(set(table) - pads)}'

    names = {b: display(n) for b, n in table.items()}
    for b in pads - set(table):
        names[b] = 'NC'                            # RFU and unlabelled balls: leave unconnected
    assert len(names) == 153

    units = build_units(names)
    bodies, report, where = [], [], {}
    for n, (uname, left, right) in enumerate(units, 1):
        blk, rows, width = unit_block(n, uname, left, right, names)
        bodies.append(blk)
        report.append((n, uname, sum(1 for b in left + right if b), rows, width))
        for b in left + right:
            if b:
                assert b not in where, f'{b} placed twice'
                where[b] = uname

    props = [('Reference', 'U', False, 3 * PITCH),
             ('Value', NAME, False, 2 * PITCH),
             ('Footprint', FOOTPRINT, True, 0),
             ('Datasheet', 'datasheets/Storage/samsung_emmc.pdf', True, 0),
             ('Description',
              'Samsung KLM8G1GETF-B041 eMMC 5.1, 8 GB, 153-ball FBGA 11.5 x 13 mm, 0.5 mm pitch. '
              'Same ball map as KLMAG1JETD-B041 (16 GB), KLMBG2JETD-B041 (32 GB) and '
              'KLMCG4JETD-B041 (64 GB). Pin numbers are the balls, names verbatim from datasheet '
              'Rev. 1.21 [Table 2] (its `Data Strobe` is `Data_Strobe`: KiCad pin names hold no '
              'spaces); the 120 balls the table does not name are RFU or unused and '
              'carry the name NC -- leave every one unconnected. Generated by '
              'tools/gen_emmc_symbol.py; see docs/sic.md 6.1.', True, 0),
             ('ki_keywords', 'eMMC 5.1 MMC flash Samsung KLM8G1GETF BGA-153 JEDEC', True, 0),
             ('MPN', NAME, True, 0),
             ('Manufacturer', 'Samsung', True, 0),
             ('LCSC', 'C499918', True, 0)]
    hdr = [f'\t(symbol "{NAME}"\n\t\t(pin_names\n\t\t\t(offset {NAME_OFS:g})\n\t\t)\n'
           '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(in_pos_files yes)\n'
           '\t\t(duplicate_pin_numbers_are_jumpers no)\n']
    for k, v, hide, y in props:
        hdr.append(f'\t\t(property "{k}" "{esc(v)}"\n\t\t\t(at 0 {y:g} 0)\n'
                   + ('\t\t\t(hide yes)\n' if hide else '') + fnt('\t\t\t') + '\t\t)\n')
    block = ''.join(hdr) + ''.join(bodies) + '\t\t(embedded_fonts no)\n\t)\n'

    # ---- every rule, asserted on the text about to be written -------------------------------
    P = re.findall(r'\(symbol "%s_(\d+)_1"|\(pin (\w+) line\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*'
                   r'\(length [\d.]+\)(\s*\(hide yes\))?\s*\(name "([^"]*)".*?\(number "([^"]*)"'
                   % re.escape(NAME), block, re.S)
    unit, got, pos = None, {}, collections.defaultdict(set)
    for u, t, x, y, rot, hidden, nm, num in P:
        if u:
            unit = int(u)
            continue
        assert not hidden, f'{num} is hidden'
        assert num not in got, f'pin number {num} appears twice'
        assert (x, y) not in pos[unit], f'unit {unit}: two pins at ({x}, {y}) -- {num}'
        pos[unit].add((x, y))
        for v in (float(x), float(y)):
            assert abs(v / PITCH - round(v / PITCH)) < 1e-6, f'{num} off the 2.54 grid'
        got[num] = (t, nm, unit)
    assert set(got) == pads, f'numbers differ from the footprint pads: {sorted(set(got) ^ pads)[:8]}'
    assert all(got[b][1] == names[b] for b in names), 'a pin name differs from the datasheet'
    assert all(got[b][0] == etype(names[b]) for b in names), 'an electrical type is off-rule'
    bus = {b for b in got if where[b] == 'MEM'}
    assert bus == {b for b, n in names.items()
                   if n.startswith('DAT') or n in ('CLK', 'CMD', 'Data_Strobe', 'RSTN')}, \
        'MEM is not exactly the twelve bus balls'
    assert len({b for b in got if where[b] == 'NC'}) == 120

    text = LIB.read_text(encoding='utf-8')
    pre, old, post = splice(text)
    new = pre + block + post
    assert new.replace(block, '', 1) == pre + post, 'the rest of the library would change'
    if dest != LIB:
        shutil.copystat(LIB, LIB)                  # no-op; keeps the staged path obvious
    dest.write_text(new, encoding='utf-8')

    print(f'{NAME}: {len(got)} pins in {len(units)} units '
          f'({"replaced" if old else "appended"}), written to {dest}')
    print(f'  {"#":>2}  {"unit":<5} {"pins":>4} {"rows":>4} {"width mm":>9}')
    for n, u, c, r, w in report:
        print(f'  {n:>2}  {u:<5} {c:>4} {r:>4} {w:>9.2f}')
    print('  types:', ', '.join(f'{k}={v}' for k, v in
                                sorted(collections.Counter(t for t, _, _ in got.values()).items())))
    print('  checks: [Table 2] parse = the hand-read Figure 1 (33 balls); numbers = the stock '
          f'{FP_NAME} pads (153); names verbatim; types by rule; no hidden pin; no two pins at one '
          'position in a unit; all pins on the 2.54 grid; MEM = the 12 bus balls; NC = 120; the '
          'rest of the library untouched')
    return 0


if __name__ == '__main__':
    sys.exit(main())
