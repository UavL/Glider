#!/usr/bin/env python3
"""The SiP's decoupling bank on `sic` -- the rest of step 4.

Values and counts are `docs/sic.md` §2, which takes them from Octavo's Table 4-3:

    +0V75_SIC  10 uF + 6 x 100 nF     the core group is one net, so note 1 applies
    +0V85_SIC  3 x 100 nF             VDDR_CORE
    +1V2_SIC   3 x 100 nF             VDDS_DDR
    +2V5_SIC   100 nF                 DDR_VPP
    +1V8A_SIC  4.7 uF + 2 x 1 uF + 2 x 100 nF   OLDI0 1 uF, CSIRX0 4.7 uF, + 1 uF, + 100 nF each
    +3V3_SIC   10 uF + 10 x 100 nF    one per VDDSHV ball pair (9) + VDDA_3P3_USB, plus bulk

Each rail gets one row: a rail trunk above, a ground trunk below, the capacitors between them.
That is electrically what the SiP needs -- which capacitor sits at which ball is a layout question
(`docs/sic.md` §12), not a schematic one. Placed in the space freed by the A4 -> A3 change, clear
of the owner's drawing, with every new segment collision-checked first.
"""
import pathlib, re, subprocess, sys, uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / 'tools'))
sys.path.insert(0, '/home/lum/.claude/plugins/cache/kicad-happy/kicad-happy/2.1.0/skills/kicad/scripts')
import schgen                                                              # noqa: E402
from sexp_parser import parse_file, find_all, find_first                   # noqa: E402

SIC = HERE / 'sic.kicad_sch'
# KiCad 10 keeps the stock libraries as directories of one file per symbol
KICAD_SYMS = pathlib.Path('/home/lum/Apps/kicad-10.0.4/share/kicad/symbols/Device.kicad_symdir')
PITCH = 12.7                       # capacitor to capacitor
SHEET_UUID = '767172a6-43e9-4684-bdc5-5dc2ecddbb44'

# (rail, y of the row, [(value, footprint-size), ...])
C402 = 'Capacitor_SMD:C_0402_1005Metric'
C603 = 'Capacitor_SMD:C_0603_1608Metric'
C805 = 'Capacitor_SMD:C_0805_2012Metric'
ROWS = [
    ('+0V75_SIC', 190.5, 25.4,  [('10uF/10V', C805)] + [('100nF/16V', C402)] * 6),
    ('+0V85_SIC', 190.5, 139.7, [('100nF/16V', C402)] * 3),
    ('+1V2_SIC',  190.5, 190.5, [('100nF/16V', C402)] * 3),
    ('+2V5_SIC',  190.5, 241.3, [('100nF/16V', C402)]),
    ('+1V8A_SIC', 190.5, 266.7, [('4.7uF/10V', C805), ('1uF/16V', C402), ('1uF/16V', C402),
                                 ('100nF/16V', C402), ('100nF/16V', C402)]),
    ('+3V3_SIC',  231.14, 25.4, [('10uF/10V', C805)] + [('100nF/16V', C402)] * 10),
]


def u():
    return str(uuid.uuid4())


def wire(a, b):
    return ('\t(wire\n\t\t(pts\n'
            f'\t\t\t(xy {a[0]:g} {a[1]:g}) (xy {b[0]:g} {b[1]:g})\n'
            '\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            f'\t\t(uuid "{u()}")\n\t)\n')


def junction(p):
    return (f'\t(junction\n\t\t(at {p[0]:g} {p[1]:g})\n\t\t(diameter 0)\n'
            f'\t\t(color 0 0 0 0)\n\t\t(uuid "{u()}")\n\t)\n')


def prop(n, v, px, py, hide, rot=0):
    h = '\n\t\t\t(hide yes)' if hide else ''
    return (f'\t\t(property "{n}" "{v}"\n\t\t\t(at {px:g} {py:g} {rot}){h}\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')


def symbol(lib_id, ref, value, x, y, root, extra=(), fp='', rot=0, hide_ref=False):
    s = ['\t(symbol\n', f'\t\t(lib_id "{lib_id}")\n', f'\t\t(at {x:g} {y:g} {rot})\n',
         '\t\t(unit 1)\n',
         '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n',
         f'\t\t(uuid "{u()}")\n',
         prop('Reference', ref, x + 2.54, y - 1.27, hide_ref),
         prop('Value', value, x + 2.54, y + 1.27, False),
         prop('Footprint', fp, x, y, True), prop('Datasheet', '', x, y, True),
         prop('Description', '', x, y, True)]
    for k, v in extra:
        s.append(prop(k, v, x, y, True))
    s.append('\t\t(instances\n\t\t\t(project "r2"\n'
             f'\t\t\t\t(path "/{root}/{SHEET_UUID}"\n'
             f'\t\t\t\t\t(reference "{ref}")\n\t\t\t\t\t(unit 1)\n'
             '\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')
    return ''.join(s)


def main():
    run = [n for n in ('kicad', 'eeschema', 'pcbnew') if
           subprocess.run(['pgrep', '-x', n], capture_output=True).returncode == 0]
    if run:
        sys.exit(f'{", ".join(run)} running -- close KiCad first (CLAUDE.md).')

    lib = schgen.SymbolLib()
    lib.add_dir('Device', KICAD_SYMS)
    cap = lib.get('Device:C')
    p1, p2 = cap.pins['1'], cap.pins['2']
    dy = abs(p1.y - p2.y) / 2                      # pin offset from the symbol origin

    text = SIC.read_text(encoding='utf-8')
    root = re.search(r'\(uuid "([^"]+)"\)', text).group(1)
    assert 'C1500' not in text, 'the decoupling bank is already there'

    d = parse_file(str(SIC))
    def walk(n):
        if isinstance(n, list):
            yield n
            for c in n:
                yield from walk(c)
    old = []
    for w in [n for n in walk(d) if n and n[0] == 'wire']:
        xy = [(round(float(p[1]), 3), round(float(p[2]), 3))
              for p in find_all(find_first(w, 'pts'), 'xy')]
        old.append((xy[0], xy[1]))
    used = []
    for s in [n for n in walk(d) if n and n[0] == 'symbol' and find_first(n, 'lib_id')]:
        at = find_first(s, 'at')
        used.append((float(at[1]), float(at[2])))

    def clear(x, y, r=7.0):
        for ux, uy in used:
            if abs(ux - x) < r and abs(uy - y) < r:
                return False
        for (ax, ay), (bx, by) in old:
            if min(ax, bx) - r < x < max(ax, bx) + r and min(ay, by) - r < y < max(ay, by) + r:
                return False
        return True

    add, n, ncap = [], 1500, 0
    for rail, y, x0, caps in ROWS:
        rail_y, gnd_y = y - 10.16, y + 10.16
        xs = [x0 + i * PITCH for i in range(len(caps))]
        for x in xs:
            assert clear(x, y), f'{rail} row would land on existing drawing at ({x}, {y})'
        add.append(wire((xs[0], rail_y), (xs[-1], rail_y)))
        add.append(wire((xs[0], gnd_y), (xs[-1], gnd_y)))
        for i, ((val, fp), x) in enumerate(zip(caps, xs)):
            ref = f'C{n}'; n += 1; ncap += 1
            add.append(symbol('Device:C', ref, val, x, y, root, fp=fp))
            add.append(wire((x, y - dy), (x, rail_y)))
            add.append(wire((x, y + dy), (x, gnd_y)))
            if 0 < i < len(xs) - 1 or (i == 0 and len(xs) > 1):
                add.append(junction((x, rail_y))); add.append(junction((x, gnd_y)))
        # rail and ground symbols at the left end of each trunk
        add.append(symbol('symbols:+V', f'#PWR16{n-1500:02d}', rail, xs[0], rail_y - 2.54, root,
                          hide_ref=True))
        add.append(wire((xs[0], rail_y - 2.54), (xs[0], rail_y)))
        add.append(symbol('power:GND', f'#PWR17{n-1500:02d}', 'GND', xs[0], gnd_y + 2.54, root,
                          hide_ref=True))
        add.append(wire((xs[0], gnd_y), (xs[0], gnd_y + 2.54)))

    tail = text.rstrip()
    assert tail.endswith(')')
    SIC.write_text(text[:len(tail) - 1] + ''.join(add) + text[len(tail) - 1:], encoding='utf-8')
    print(f'  {ncap} capacitors C1500..C{n-1} in {len(ROWS)} rail rows')
    for rail, y, x0, caps in ROWS:
        print(f'    {rail:<11} {len(caps):>2} x  ({", ".join(sorted({v for v, _ in caps}))})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
