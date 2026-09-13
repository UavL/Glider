#!/usr/bin/env python3
"""Steps 6 and 7 on `sic`: the 25 MHz crystal and the boot straps. Plus the bulk capacitors that
replace the unstocked 47 uF, and the page grows to A2.

Page size: the owner spread the eleven units out to x = 480, past A3's 420 mm frame, so anything
beyond it would not plot. A2 (594 x 420) holds the present arrangement with room for this work.

**Clock** (`docs/sic.md` §5): `Y1500` = YXC `SX3B25.000F1010F30`, 25 MHz, CL 10 pF, ESR 30 ohm,
3225 4-pad, with 2 x 18 pF C0G. `SPRSP58C` Table 6-22 allows CL 6-12 pF and, at ESR 30 ohm, up to
7 pF of shunt capacitance. Load caps: CL1 = CL2 = 2 x CL = 20 pF nominal, minus ~2 pF of pin and
trace each, so 18 pF -- trim at bring-up. `WKUP_LFOSC0_XI` is grounded and `XO` left open
(`SPRSP58C` Fig. 6-25): the MCU keeps time and the SoC is woken over `SOM_WAKE#`.

**Straps** (`docs/sic.md` §6, from TRM Tables 5-2..5-5): 10 k each, none floating. Fourteen live on
`BOOT_GPMC` here; **bits 8 and 9 are `GPMC0_AD8`/`AD9`, which are also `DPI_R6`/`DPI_R7`** and sit on
the `VIDEO` unit on `dpi_in`, so those two resistors go on page 6 (`R600`/`R601`).

    AD0 AD1 = 1 1, AD2 = 0        PLL config 011 = 25 MHz
    AD3..AD6 = 0 0 0 1            primary boot 1000 = MMCSD  (AD3 = 1 selects eMMC boot instead)
    AD7 = 0                       filesystem, not raw
    AD9 = 1                       MMC port 1 -- the SD card
    AD10..AD12 = 1 0 0            backup boot 001 = USB
    AD13 = 0                      backup config: DFU
    AD8, AD14, AD15 = 0           reserved, tied low

Connections are by label: the units sit far apart on this page, so a stub and a name is clearer --
and far less error-prone -- than a wire across 200 mm of sheet.
"""
import json, pathlib, re, subprocess, sys, uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / 'tools'))
sys.path.insert(0, '/home/lum/.claude/plugins/cache/kicad-happy/kicad-happy/2.1.0/skills/kicad/scripts')
import schgen                                                              # noqa: E402
from sexp_parser import parse_file, find_all, find_first                   # noqa: E402

SIC, DPI = HERE / 'sic.kicad_sch', HERE / 'dpi_in.kicad_sch'
SH_SIC = '767172a6-43e9-4684-bdc5-5dc2ecddbb44'
KICAD = pathlib.Path('/home/lum/Apps/kicad-10.0.4/share/kicad/symbols')
R402 = 'Resistor_SMD:R_0402_1005Metric'
C402 = 'Capacitor_SMD:C_0402_1005Metric'
C805 = 'Capacitor_SMD:C_0805_2012Metric'
XTAL_FP = 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm'

STRAPS = [   # (ball, bit, pull) -- pull 1 = up to +3V3_SIC, 0 = down to GND
    ('G28', 0, 1), ('G27', 1, 1), ('F28', 2, 0), ('F27', 3, 0), ('E28', 4, 0), ('E27', 5, 0),
    ('D28', 6, 1), ('D27', 7, 0), ('K27', 10, 1), ('K28', 11, 0), ('J28', 12, 0), ('J27', 13, 0),
    ('H28', 14, 0), ('H27', 15, 0),
]
BULK = [('C1549', '+0V75_SIC'), ('C1550', '+1V8_SIC'), ('C1551', '+1V2_SIC')]


def u():
    return str(uuid.uuid4())


def wire(a, b):
    return ('\t(wire\n\t\t(pts\n'
            f'\t\t\t(xy {a[0]:g} {a[1]:g}) (xy {b[0]:g} {b[1]:g})\n'
            '\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            f'\t\t(uuid "{u()}")\n\t)\n')


def label(p, t, rot=0, just='left'):
    return (f'\t(label "{t}"\n\t\t(at {p[0]:g} {p[1]:g} {rot})\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            f'\t\t\t(justify {just} bottom)\n\t\t)\n\t\t(uuid "{u()}")\n\t)\n')


def nc(p):
    return f'\t(no_connect\n\t\t(at {p[0]:g} {p[1]:g})\n\t\t(uuid "{u()}")\n\t)\n'


def text(x, y, s, size=1.27):
    return (f'\t(text "{s}"\n\t\t(exclude_from_sim yes)\n\t\t(at {x:g} {y:g} 0)\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n\t\t\t)\n'
            '\t\t\t(justify left bottom)\n\t\t)\n'
            f'\t\t(uuid "{u()}")\n\t)\n')


def prop(n, v, x, y, hide):
    h = '\n\t\t\t(hide yes)' if hide else ''
    return (f'\t\t(property "{n}" "{v}"\n\t\t\t(at {x:g} {y:g} 0){h}\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')


def symbol(lib_id, ref, value, x, y, root, sheet, fp='', rot=0, hide_ref=False, extra=()):
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
             f'\t\t\t\t(path "/{root}/{sheet}"\n'
             f'\t\t\t\t\t(reference "{ref}")\n\t\t\t\t\t(unit 1)\n'
             '\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')
    return ''.join(s)


def main():
    run = [n for n in ('kicad', 'eeschema', 'pcbnew') if
           subprocess.run(['pgrep', '-x', n], capture_output=True).returncode == 0]
    if run:
        sys.exit(f'{", ".join(run)} running -- close KiCad first (CLAUDE.md).')

    lib = schgen.SymbolLib()
    lib.add_file('Reflow', HERE / 'library/Reflow.kicad_sym')
    lib.add_dir('Device', KICAD / 'Device.kicad_symdir')
    sip = lib.get('Reflow:OSD6254-1G-IPM')
    res, cap = lib.get('Device:R'), lib.get('Device:C')
    xtal = lib.get('Device:Crystal_GND24')
    dy_r = abs(res.pins['1'].y - res.pins['2'].y) / 2
    dy_c = abs(cap.pins['1'].y - cap.pins['2'].y) / 2

    text_sic = SIC.read_text(encoding='utf-8')
    assert 'Y1500' not in text_sic, 'already applied'
    root = re.search(r'\(uuid "([^"]+)"\)', text_sic).group(1)
    assert '(paper "A3")' in text_sic
    text_sic = text_sic.replace('(paper "A3")', '(paper "A2")', 1)

    d = parse_file(str(SIC))
    def walk(n):
        if isinstance(n, list):
            yield n
            for c in n:
                yield from walk(c)
    units = {}
    for s in [n for n in walk(d) if n and n[0] == 'symbol' and find_first(n, 'lib_id')]:
        if 'OSD6254' not in find_first(s, 'lib_id')[1]:
            continue
        at = find_first(s, 'at')
        units[int(find_first(s, 'unit')[1])] = (float(at[1]), float(at[2]),
                                                int(float(at[3])) if len(at) > 3 else 0)
    P5 = schgen.Placed(sip, *units[5], 'U600')
    P6 = schgen.Placed(sip, *units[6], 'U600')

    add, anchors, segs = [], [], []

    def seg(a, b, net):
        segs.append((a, b, net)); add.append(wire(a, b))

    def anc(p, net):
        anchors.append((p, net))

    # ---- straps: stub + name at the ball, resistor array in free space -------------------------
    for ball, bit, pull in STRAPS:
        px, py = P5.pin(ball)
        end = (px - 5.08, py)
        seg((px, py), end, f'BOOT{bit}'); anc((px, py), f'BOOT{bit}'); anc(end, f'BOOT{bit}')
        add.append(label(end, f'BOOT{bit}', 180, 'right'))
    add.append(text(287.02, 332.74, 'Boot straps - docs/sic.md 6: PLL 011 = 25 MHz, primary boot '
                                    '1000 = MMCSD, port 1 = SD, backup 001 = USB DFU'))
    add.append(text(287.02, 335.28, 'BOOT3 up instead = eMMC boot (1001); BOOT8/BOOT9 are '
                                    'DPI_R6/R7 and live on dpi_in as R600/R601'))
    npwr, nref = 1970, 1511
    for i, (ball, bit, pull) in enumerate(STRAPS):
        x, y = 292.1 + i * 12.7, 342.9
        ref = f'R{nref}'; nref += 1
        add.append(symbol('Device:R', ref, '10k/1%', x, y, root, SH_SIC, fp=R402))
        top, bot = (x, y - dy_r), (x, y + dy_r)
        if pull:
            seg(top, (x, y - dy_r - 2.54), '+3V3_SIC'); anc(top, '+3V3_SIC')
            anc((x, y - dy_r - 2.54), '+3V3_SIC')
            npwr += 1
            add.append(symbol('symbols:+V', f'#PWR{npwr}', '+3V3_SIC', x, y - dy_r - 2.54, root,
                              SH_SIC, hide_ref=True))
            seg(bot, (x, y + dy_r + 2.54), f'BOOT{bit}'); anc(bot, f'BOOT{bit}')
            anc((x, y + dy_r + 2.54), f'BOOT{bit}')
            add.append(label((x, y + dy_r + 2.54), f'BOOT{bit}', 0, 'left'))
        else:
            seg(top, (x, y - dy_r - 2.54), f'BOOT{bit}'); anc(top, f'BOOT{bit}')
            anc((x, y - dy_r - 2.54), f'BOOT{bit}')
            add.append(label((x, y - dy_r - 2.54), f'BOOT{bit}', 0, 'left'))
            seg(bot, (x, y + dy_r + 2.54), 'GND'); anc(bot, 'GND'); anc((x, y + dy_r + 2.54), 'GND')
            npwr += 1
            add.append(symbol('power:GND', f'#PWR{npwr}', 'GND', x, y + dy_r + 2.54, root, SH_SIC,
                              hide_ref=True))

    # ---- clock ---------------------------------------------------------------------------------
    for ball, net in (('G1', 'OSC_XI'), ('G2', 'OSC_XO')):
        px, py = P6.pin(ball)
        end = (px - 5.08, py)
        seg((px, py), end, net); anc((px, py), net); anc(end, net)
        add.append(label(end, net, 180, 'right'))
    px, py = P6.pin('H1')                                   # WKUP_LFOSC0_XI -> GND
    end = (px - 5.08, py)
    seg((px, py), end, 'GND'); anc((px, py), 'GND'); anc(end, 'GND')
    npwr += 1
    add.append(symbol('power:GND', f'#PWR{npwr}', 'GND', *end, root, SH_SIC, hide_ref=True))
    add.append(nc(P6.pin('H2')))                            # WKUP_LFOSC0_XO left open

    XX, XY = 203.2, 342.9
    X = schgen.Placed(xtal, XX, XY, 0, 'Y1500')
    add.append(symbol('Device:Crystal_GND24', 'Y1500', 'SX3B25.000F1010F30', XX, XY, root, SH_SIC,
                      fp=XTAL_FP, extra=(('MPN', 'SX3B25.000F1010F30'), ('LCSC', 'C2901684'))))
    for pin_no, net in (('1', 'OSC_XI'), ('3', 'OSC_XO')):
        px, py = X.pin(pin_no)
        end = (px + (-7.62 if pin_no == '1' else 7.62), py)
        seg((px, py), end, net); anc((px, py), net); anc(end, net)
        add.append(label(end, net, 180 if pin_no == '1' else 0, 'right' if pin_no == '1' else 'left'))
    gx, gy = X.pin('2')
    seg((gx, gy), (gx, gy + 2.54), 'GND'); anc((gx, gy), 'GND'); anc((gx, gy + 2.54), 'GND')
    npwr += 1
    add.append(symbol('power:GND', f'#PWR{npwr}', 'GND', gx, gy + 2.54, root, SH_SIC, hide_ref=True))
    for ref, net, x in (('C1552', 'OSC_XI', 177.8), ('C1553', 'OSC_XO', 228.6)):
        y = 361.95
        add.append(symbol('Device:C', ref, '18pF/50V', x, y, root, SH_SIC, fp=C402))
        seg((x, y - dy_c), (x, y - dy_c - 2.54), net); anc((x, y - dy_c), net)
        anc((x, y - dy_c - 2.54), net)
        add.append(label((x, y - dy_c - 2.54), net, 0, 'left'))
        seg((x, y + dy_c), (x, y + dy_c + 2.54), 'GND'); anc((x, y + dy_c), 'GND')
        anc((x, y + dy_c + 2.54), 'GND')
        npwr += 1
        add.append(symbol('power:GND', f'#PWR{npwr}', 'GND', x, y + dy_c + 2.54, root, SH_SIC,
                          hide_ref=True))
    add.append(text(177.8, 332.74, 'Y1500 25 MHz, CL 10 pF, ESR 30 ohm - load caps 2 x CL minus '
                                   '~2 pF pin+trace; trim at bring-up (docs/sic.md 5)'))

    # ---- the bulk capacitors that replace the unstocked 47 uF/1206 ------------------------------
    for i, (ref, rail) in enumerate(BULK):
        x, y = 25.4 + i * 17.78, 309.88
        add.append(symbol('Device:C', ref, '22uF/25V', x, y, root, SH_SIC, fp=C805))
        seg((x, y - dy_c), (x, y - dy_c - 2.54), rail); anc((x, y - dy_c), rail)
        anc((x, y - dy_c - 2.54), rail)
        npwr += 1
        add.append(symbol('symbols:+V', f'#PWR{npwr}', rail, x, y - dy_c - 2.54, root, SH_SIC,
                          hide_ref=True))
        seg((x, y + dy_c), (x, y + dy_c + 2.54), 'GND'); anc((x, y + dy_c), 'GND')
        anc((x, y + dy_c + 2.54), 'GND')
        npwr += 1
        add.append(symbol('power:GND', f'#PWR{npwr}', 'GND', x, y + dy_c + 2.54, root, SH_SIC,
                          hide_ref=True))
    add.append(text(25.4, 299.72, 'Second 22 uF per buck output - replaces the 47 uF/1206, which '
                                  'LCSC does not stock (see tools/normalise_passives.py)'))

    # ---- guard: grid, self-collisions, and collisions with what is already on the sheet --------
    for a, b, net in segs:
        for pt in (a, b):
            for v in pt:
                assert abs(round(v / 1.27) * 1.27 - v) < 1e-4, f'off-grid {pt} on {net}'
    ex = parse_file(str(SIC))
    for w in [n for n in walk(ex) if n and n[0] == 'wire']:
        xy = [(round(float(q[1]), 3), round(float(q[2]), 3))
              for q in find_all(find_first(w, 'pts'), 'xy')]
        segs.append((xy[0], xy[1], '(existing)'))
    for l in [n for n in walk(ex) if n and n[0] in ('label', 'hierarchical_label')]:
        at = find_first(l, 'at')
        anchors.append(((round(float(at[1]), 3), round(float(at[2]), 3)), '(existing)'))
    for sy in [n for n in walk(ex) if n and n[0] == 'symbol' and find_first(n, 'lib_id')]:
        if find_first(sy, 'lib_id')[1].strip('"').startswith(('power:', 'symbols:')):
            at = find_first(sy, 'at')
            anchors.append(((round(float(at[1]), 3), round(float(at[2]), 3)), '(existing)'))
    bypt = {}
    for pt, net in anchors:
        pt = (round(pt[0], 3), round(pt[1], 3))
        if pt in bypt and bypt[pt] != net:
            sys.exit(f'two nets meet at {pt}: {bypt[pt]} and {net}')
        bypt[pt] = net
    for a, b, net in segs:
        a = (round(a[0], 3), round(a[1], 3)); b = (round(b[0], 3), round(b[1], 3))
        for pt, other in bypt.items():
            if other == net:
                continue
            if a[0] == b[0] == pt[0] and min(a[1], b[1]) - 1e-6 <= pt[1] <= max(a[1], b[1]) + 1e-6:
                sys.exit(f'wire {net} {a}->{b} passes through {other} at {pt}')
            if a[1] == b[1] == pt[1] and min(a[0], b[0]) - 1e-6 <= pt[0] <= max(a[0], b[0]) + 1e-6:
                sys.exit(f'wire {net} {a}->{b} passes through {other} at {pt}')

    tail = text_sic.rstrip()
    SIC.write_text(text_sic[:len(tail) - 1] + ''.join(add) + text_sic[len(tail) - 1:],
                   encoding='utf-8')
    print(f'  page A3 -> A2 (content reached x=480, past A3\'s 420 mm frame)')
    print(f'  14 strap resistors R1511..R{nref-1} + labels BOOT0..BOOT15 on the BOOT_GPMC unit')
    print(f'  Y1500 + C1552/C1553 18 pF; WKUP_LFOSC0_XI grounded, XO no-connect')
    print(f'  C1549..C1551 22uF/25V, the second bulk cap per buck output')
    return 0


if __name__ == '__main__':
    sys.exit(main())
