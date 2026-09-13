#!/usr/bin/env python3
"""Step 5 on `sic`: the PMIC `U1501`, its passives, and the two load switches.

Everything here is `docs/sic.md` §3 (the PMIC pin table), §4 (the load switches) and §2 (the
inductor and the output capacitors). Connections are made by net name -- each pin gets a short stub
and a label or a rail symbol -- rather than by routing wires across a dense page. That is normal for
a power IC and it is what keeps this script auditable: the netlist is the thing that matters and it
is checked afterwards, pin by pin, against the table in `docs/sic.md` §3.

Every stub ends *at* its rail symbol or label -- there is no vertical riser. A riser would run
from one pin's stub end to the next pin's, 2.54 mm away, and silently merge the two nets; that bug
was made and caught here on 2026-09-12 by reading the netlist back. `guard()` below now refuses to
write if any generated wire touches an anchor that belongs to a different net.

Choices worth knowing:

  * `PVIN_LDO1` and `PVIN_LDO2` come from **`+1V8_SIC`** (BUCK2), not from the battery: `PVIN_LDO1`
    may not exceed VSYS and LDO1's bypass mode needs <= 3.4 V, and no 3.3 V source satisfies both on
    a cell that sags to 3.0 V (`docs/sic.md` §1). `VLDO1` therefore drives nothing but its 2.2 uF.
  * `EN/PB/VSENSE` gets its 10 k to `+VSYS_SIC` -- First Supply Detection starts the PMIC; the
    optional MCU override is a DNP 0 R the owner can fit later (§3).
  * `GPO1` and `GPIO` are disabled in the NVM, so they get no-connect flags rather than being left
    to float silently.
  * The three switch nodes are named `B1_SW`/`B2_SW`/`B3_SW` so they can be given the `SW_NODE`
    netclass, the way `/power/1V2_SW` already is.
  * Signals that leave the sheet (`MCU_PORZ`, `RESETSTATZ`, `EXTINTN`, `PMIC_LPM_EN0`, `I2C0_*`,
    `MCU_EN_SOC`) are **hierarchical** labels. Their sheet pins on the root and the wiring to `mcu`
    are step 9 of `docs/sic-capture-guide.md`.
"""
import pathlib, re, subprocess, sys, uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / 'tools'))
sys.path.insert(0, '/home/lum/.claude/plugins/cache/kicad-happy/kicad-happy/2.1.0/skills/kicad/scripts')
import schgen                                                              # noqa: E402
from sexp_parser import parse_file, find_all, find_first                   # noqa: E402

SIC = HERE / 'sic.kicad_sch'
SHEET_UUID = '767172a6-43e9-4684-bdc5-5dc2ecddbb44'
KICAD = pathlib.Path('/home/lum/Apps/kicad-10.0.4/share/kicad/symbols')
C402, C603, C805, C1206 = ('Capacitor_SMD:C_0402_1005Metric', 'Capacitor_SMD:C_0603_1608Metric',
                           'Capacitor_SMD:C_0805_2012Metric', 'Capacitor_SMD:C_1206_3216Metric')
R402 = 'Resistor_SMD:R_0402_1005Metric'
IND = 'Inductor_SMD:L_1008_2520Metric'
PMIC_AT = (351.79, 76.2)          # 277 x 1.27: every pin lands on the grid
STUB = 5.08

# pin -> what it connects to.  ('rail', name) places a rail symbol, ('lbl', name) a local label,
# ('hlbl', name, shape) a hierarchical one, ('nc',) a no-connect flag.
PINCONN = {
    '13': ('rail', '+VSYS_SIC'), '4': ('rail', '+VSYS_SIC'), '5': ('rail', '+VSYS_SIC'),
    '30': ('rail', '+VSYS_SIC'), '26': ('rail', '+VSYS_SIC'), '22': ('rail', '+VSYS_SIC'),
    '6': ('rail', '+1V8_SIC'), '20': ('rail', '+1V8_SIC'),
    '25': ('lbl', 'PMIC_EN'), '31': ('hlbl', 'PMIC_LPM_EN0', 'input'),
    '28': ('hlbl', 'RESETSTATZ', 'input'), '12': ('lbl', 'PMIC_VSEL'),
    '9': ('hlbl', 'I2C0_SDA', 'bidirectional'), '10': ('hlbl', 'I2C0_SCL', 'input'),
    '2': ('lbl', 'B1_SW'), '3': ('lbl', 'B1_SW'), '1': ('rail', '+0V75_SIC'),
    '29': ('lbl', 'B2_SW'), '32': ('rail', '+1V8_SIC'),
    '27': ('lbl', 'B3_SW'), '24': ('rail', '+1V2_SIC'),
    '7': ('lbl', 'VLDO1_UNUSED'), '19': ('rail', '+0V85_SIC'), '21': ('rail', '+1V8A_SIC'),
    '23': ('rail', '+2V5_SIC'),
    '8': ('nc',), '16': ('nc',),
    '17': ('lbl', 'PMIC_GPO2'), '11': ('hlbl', 'EXTINTN', 'output'),
    '18': ('hlbl', 'MCU_PORZ', 'output'), '14': ('lbl', 'VDD1P8'),
    '15': ('gnd',), '33': ('gnd',),
}
# pull resistors: (ref, value, net, rail)
PULLS = [('R1500', '10k', 'PMIC_EN', '+VSYS_SIC'), ('R1501', '10k', 'PMIC_LPM_EN0', '+3V3_SIC'),
         ('R1502', '10k', 'PMIC_VSEL', '+3V3_SIC'), ('R1503', '10k', 'EXTINTN', '+3V3_SIC'),
         ('R1504', '10k', 'MCU_PORZ', '+1V8A_SIC'), ('R1505', '4.7k', 'I2C0_SDA', '+3V3_SIC'),
         ('R1506', '4.7k', 'I2C0_SCL', '+3V3_SIC'), ('R1507', '10k', 'PMIC_GPO2', '+VSYS_SIC')]
# capacitors hung between a net and GND: (ref, value, fp, net-or-rail, is_rail)
CAPS = [('C1530', '2.2uF/16V', C603, 'VLDO1_UNUSED', False), ('C1531', '2.2uF/16V', C603, 'VDD1P8', False),
        ('C1532', '2.2uF/16V', C603, '+VSYS_SIC', True), ('C1533', '4.7uF/16V', C805, '+VSYS_SIC', True),
        ('C1534', '10uF/16V', C805, '+VSYS_SIC', True), ('C1535', '10uF/16V', C805, '+VSYS_SIC', True),
        ('C1536', '10uF/16V', C805, '+VSYS_SIC', True), ('C1537', '22uF/16V', C1206, '+VSYS_SIC', True),
        ('C1538', '22uF/16V', C1206, '+VSYS_SIC', True),
        ('C1539', '47uF/6.3V', C1206, '+0V75_SIC', True), ('C1540', '10uF/10V', C805, '+0V75_SIC', True),
        ('C1541', '47uF/6.3V', C1206, '+1V8_SIC', True), ('C1542', '10uF/10V', C805, '+1V8_SIC', True),
        ('C1543', '47uF/6.3V', C1206, '+1V2_SIC', True), ('C1544', '10uF/10V', C805, '+1V2_SIC', True),
        ('C1545', '10uF/10V', C805, '+0V85_SIC', True), ('C1546', '10uF/10V', C805, '+1V8A_SIC', True),
        ('C1547', '10uF/10V', C805, '+2V5_SIC', True), ('C1548', '1000pF/50V', C402, 'U1502_CT', False)]
# inductors: (ref, switch node, rail)
INDS = [('L1500', 'B1_SW', '+0V75_SIC'), ('L1501', 'B2_SW', '+1V8_SIC'), ('L1502', 'B3_SW', '+1V2_SIC')]


def u():
    return str(uuid.uuid4())


def wire(a, b):
    return ('\t(wire\n\t\t(pts\n'
            f'\t\t\t(xy {a[0]:g} {a[1]:g}) (xy {b[0]:g} {b[1]:g})\n'
            '\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            f'\t\t(uuid "{u()}")\n\t)\n')


def label(p, text, rot=0, just='left'):
    return (f'\t(label "{text}"\n\t\t(at {p[0]:g} {p[1]:g} {rot})\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            f'\t\t\t(justify {just} bottom)\n\t\t)\n\t\t(uuid "{u()}")\n\t)\n')


def hlabel(p, text, shape, rot=0, just='left'):
    return (f'\t(hierarchical_label "{text}"\n\t\t(shape {shape})\n'
            f'\t\t(at {p[0]:g} {p[1]:g} {rot})\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            f'\t\t\t(justify {just})\n\t\t)\n\t\t(uuid "{u()}")\n\t)\n')


def nc(p):
    return f'\t(no_connect\n\t\t(at {p[0]:g} {p[1]:g})\n\t\t(uuid "{u()}")\n\t)\n'


def prop(n, v, px, py, hide, rot=0):
    h = '\n\t\t\t(hide yes)' if hide else ''
    return (f'\t\t(property "{n}" "{v}"\n\t\t\t(at {px:g} {py:g} {rot}){h}\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')


def symbol(lib_id, ref, value, x, y, root, fp='', rot=0, hide_ref=False, extra=()):
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
    lib.add_dir('Device', KICAD / 'Device.kicad_symdir')
    lib.add_file('Reflow', HERE / 'library/Reflow.kicad_sym')
    lib.add_file('r2', HERE / 'r2.kicad_sym')
    pmic = lib.get('Reflow:TPS6521903')
    cap = lib.get('Device:C'); res = lib.get('Device:R'); ind = lib.get('Device:L')
    sw = lib.get('r2:TPS22965DSG')
    dy_c = abs(cap.pins['1'].y - cap.pins['2'].y) / 2
    dy_r = abs(res.pins['1'].y - res.pins['2'].y) / 2
    dy_l = abs(ind.pins['1'].y - ind.pins['2'].y) / 2

    text = SIC.read_text(encoding='utf-8')
    root = re.search(r'\(uuid "([^"]+)"\)', text).group(1)
    assert 'U1501' not in text, 'the PMIC is already on this sheet'

    add = []
    anchors = []          # (point, net) -- every place a net is named or terminated
    segs = []             # (a, b, net)

    def anchor(pt, net):
        anchors.append(((round(pt[0], 3), round(pt[1], 3)), net))

    def seg(a, b, net):
        segs.append(((round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3)), net))
        add.append(wire(a, b))

    P = schgen.Placed(pmic, *PMIC_AT, 0, 'U1501')
    add.append(symbol('Reflow:TPS6521903', 'U1501', 'TPS6521903RHBR', *PMIC_AT, root,
                      fp='Package_DFN_QFN:Texas_RHB0032E_VQFN-32-1EP_5x5mm_P0.5mm'
                         '_EP3.45x3.45mm_ThermalVias',
                      extra=(('MPN', 'TPS6521903RHBR'), ('LCSC', 'C18716455'))))

    npwr = 1800
    for i, (num, conn) in enumerate(sorted(PINCONN.items(), key=lambda kv: int(kv[0]))):
        px, py = P.pin(num)
        if conn[0] == 'nc':
            add.append(nc((px, py)))
            continue
        side = 'left' if px < PMIC_AT[0] - 1 else ('right' if px > PMIC_AT[0] + 1 else 'bottom')
        length = STUB + (i % 3) * 3.81                 # stagger, so the rail graphics do not stack
        end = ((px - length, py) if side == 'left' else
               (px + length, py) if side == 'right' else (px, py + length))
        net = conn[1] if conn[0] != 'gnd' else 'GND'
        seg((px, py), end, net)
        anchor(end, net)
        anchor((px, py), net)
        if conn[0] == 'rail':
            npwr += 1
            add.append(symbol('symbols:+V', f'#PWR{npwr}', conn[1], *end, root, hide_ref=True))
        elif conn[0] == 'gnd':
            npwr += 1
            add.append(symbol('power:GND', f'#PWR{npwr}', 'GND', *end, root, hide_ref=True))
        elif conn[0] == 'lbl':
            add.append(label(end, conn[1], 0 if side != 'left' else 180,
                             'left' if side != 'left' else 'right'))
        else:
            add.append(hlabel(end, conn[1], conn[2], 0 if side != 'left' else 180,
                              'left' if side != 'left' else 'right'))

    def two_terminal(lib_id, ref, val, fp, x, y, dy, top, bottom, extra=()):
        """A vertical part with `top` and `bottom` each ('rail'|'gnd'|'lbl', net)."""
        nonlocal npwr
        add.append(symbol(lib_id, ref, val, x, y, root, fp=fp, extra=extra))
        for kind_net, ypin, sign in ((top, y - dy, -1), (bottom, y + dy, +1)):
            kind, net = kind_net
            end = (x, ypin + sign * 2.54)
            seg((x, ypin), end, net)
            anchor((x, ypin), net); anchor(end, net)
            if kind == 'rail':
                npwr += 1
                add.append(symbol('symbols:+V', f'#PWR{npwr}', net, *end, root, hide_ref=True))
            elif kind == 'gnd':
                npwr += 1
                add.append(symbol('power:GND', f'#PWR{npwr}', 'GND', *end, root, hide_ref=True))
            else:
                add.append(label(end, net, 0, 'left'))

    for i, (ref, val, net, rail) in enumerate(PULLS):
        two_terminal('Device:R', ref, val, R402, 299.72, 38.1 + i * 15.24, dy_r,
                     ('rail', rail), ('lbl', net))
    for i, (ref, val, fp, net, is_rail) in enumerate(CAPS):
        two_terminal('Device:C', ref, val, fp, 25.4 + (i % 10) * 17.78, 261.62 + (i // 10) * 22.86,
                     dy_c, ('rail' if is_rail else 'lbl', net), ('gnd', 'GND'))
    for i, (ref, node, rail) in enumerate(INDS):
        two_terminal('Device:L', ref, '0.47uH/4.9A', IND, 394.97, 45.72 + i * 20.32, dy_l,
                     ('lbl', node), ('rail', rail),
                     extra=(('MPN', 'DFE252012F-R47M'), ('LCSC', 'C703140')))
    two_terminal('Device:R', 'R1508', '100k', R402, 299.72, 220.98, dy_r,
                 ('lbl', 'MCU_EN_SOC'), ('gnd', 'GND'))

    for ref, val, vin, vout, on_net, at in (
            ('U1502', 'TPS22965DSGR', '+3V3_DCDC', '+3V3_SIC', 'PMIC_GPO2', (360.68, 151.13)),
            ('U1503', 'TPS22965DSGR', '+VSYS', '+VSYS_SIC', 'MCU_EN_SOC', (360.68, 191.77))):
        S = schgen.Placed(sw, *at, 0, ref)
        add.append(symbol('r2:TPS22965DSG', ref, val, *at, root,
                          fp='Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm_ThermalVias',
                          extra=(('MPN', 'TPS22965DSGR'), ('LCSC', 'C122837'))))
        for k, pin_no in enumerate(('1', '2', '4')):            # VIN, VIN, VBIAS
            px, py = S.pin(pin_no)
            end = (px - STUB - k * 3.81, py)
            seg((px, py), end, vin); anchor((px, py), vin); anchor(end, vin)
            npwr += 1
            add.append(symbol('symbols:+V', f'#PWR{npwr}', vin, *end, root, hide_ref=True))
        for k, pin_no in enumerate(('7', '8')):                 # VOUT
            px, py = S.pin(pin_no)
            end = (px + STUB + k * 3.81, py)
            seg((px, py), end, vout); anchor((px, py), vout); anchor(end, vout)
            npwr += 1
            add.append(symbol('symbols:+V', f'#PWR{npwr}', vout, *end, root, hide_ref=True))
        px, py = S.pin('3')                                     # ON
        end = (px - STUB, py)
        seg((px, py), end, on_net); anchor((px, py), on_net); anchor(end, on_net)
        if ref == 'U1503':
            add.append(hlabel(end, on_net, 'input', 180, 'right'))
        else:
            add.append(label(end, on_net, 180, 'right'))
        px, py = S.pin('6')                                     # CT
        if ref == 'U1502':
            end = (px + STUB, py)
            seg((px, py), end, 'U1502_CT'); anchor((px, py), 'U1502_CT'); anchor(end, 'U1502_CT')
            add.append(label(end, 'U1502_CT', 0, 'left'))
        else:
            add.append(nc((px, py)))                            # the BRK fits no CT here either
        for pin_no in ('5', '9'):                               # GND, EP
            px, py = S.pin(pin_no)
            end = (px, py + 2.54)
            seg((px, py), end, 'GND'); anchor((px, py), 'GND'); anchor(end, 'GND')
            npwr += 1
            add.append(symbol('power:GND', f'#PWR{npwr}', 'GND', *end, root, hide_ref=True))

    # ---- the guard --------------------------------------------------------------------------
    # v1 of this script checked only its own geometry and shorted PMIC_GPO2 to +1V8A_SIC by ending
    # a stub on the decoupling row's rail trunk, which an earlier script had drawn. So the sheet's
    # existing wires and anchors are loaded and checked against too.
    ex = parse_file(str(SIC))
    def _walk(n):
        if isinstance(n, list):
            yield n
            for c in n:
                yield from _walk(c)
    exnodes = list(_walk(ex))
    for w in [n for n in exnodes if n and n[0] == 'wire']:
        xy = [(round(float(q[1]), 3), round(float(q[2]), 3))
              for q in find_all(find_first(w, 'pts'), 'xy')]
        segs.append((xy[0], xy[1], '(existing)'))
    for l in [n for n in exnodes if n and n[0] in ('label', 'hierarchical_label')]:
        at = find_first(l, 'at')
        anchors.append(((round(float(at[1]), 3), round(float(at[2]), 3)), '(existing)'))
    for sy in [n for n in exnodes if n and n[0] == 'symbol' and find_first(n, 'lib_id')]:
        lid = find_first(sy, 'lib_id')[1].strip('"')
        if lid.startswith(('power:', 'symbols:')):
            at = find_first(sy, 'at')
            anchors.append(((round(float(at[1]), 3), round(float(at[2]), 3)), '(existing)'))

    for a, b, net in segs:
        if net == '(existing)':
            continue
        for pt in (a, b):
            for v in pt:
                assert abs(round(v / 1.27) * 1.27 - v) < 1e-4, f'off-grid endpoint {pt} on {net}'

    bypt = {}
    for pt, net in anchors:
        if pt in bypt and bypt[pt] != net:
            sys.exit(f'two nets meet at {pt}: {bypt[pt]} and {net}')
        bypt[pt] = net
    # an existing anchor may legitimately share a point only with the same net, which we cannot
    # know here -- so any coincidence with existing drawing is reported and must be looked at
    for a, b, net in segs:
        for pt, other in bypt.items():
            if other == net:
                continue
            if a[0] == b[0] == pt[0] and min(a[1], b[1]) - 1e-6 <= pt[1] <= max(a[1], b[1]) + 1e-6:
                sys.exit(f'wire {net} {a}->{b} passes through {other} anchor at {pt}')
            if a[1] == b[1] == pt[1] and min(a[0], b[0]) - 1e-6 <= pt[0] <= max(a[0], b[0]) + 1e-6:
                sys.exit(f'wire {net} {a}->{b} passes through {other} anchor at {pt}')

    tail = text.rstrip()
    SIC.write_text(text[:len(tail) - 1] + ''.join(add) + text[len(tail) - 1:], encoding='utf-8')
    print(f'  U1501 TPS6521903 at {PMIC_AT}, all 33 pins connected')
    print(f'  {len(PULLS) + 1} resistors, {len(CAPS)} capacitors, {len(INDS)} inductors')
    print('  U1502 (+3V3_DCDC -> +3V3_SIC, ON = PMIC_GPO2, CT = 1000 pF), '
          'U1503 (+VSYS -> +VSYS_SIC, ON = MCU_EN_SOC)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
