#!/usr/bin/env python3
"""Three follow-ups on `sic`, from the owner's review on 2026-09-13.

1.  **`VMON_VSYS` looked unconnected** -- it was a label with nothing on the other end, which is
    indistinguishable on the page from a mistake. Its divider is built now (`docs/sic.md` §7):
    `+VSYS_SIC` -- 100 k -- tap -- 16.9 k -- GND. The PMIC's power-fail comparator trips at
    0.45 V, so the tap reaches it at 0.45 x (100 + 16.9) / 16.9 = **3.11 V** at the cell.
    (`VDDA_3P3_USB` was never unconnected: ball N7 sits on `+3V3_SIC` through the owner's own
    trunk, as does `VMON_3P3_SOC` on B15.)

2.  **Capacitors re-valued onto lines the board already buys.** Nothing here is a new requirement;
    each part keeps or exceeds the rating the datasheet asks for, and every rail involved is at or
    below 4.4 V:
        2.2 uF/16V 0603 x3  -> 4.7 uF/10V 0805   (datasheet says "2.2 uF or greater")
        4.7 uF/16V 0805     -> 4.7 uF/10V 0805
        10 uF/16V 0805 x3   -> 10 uF/10V 0805
        22 uF/16V 1206 x2   -> 22 uF/10V 0805    (17 already on the board)
        1000pF/50V          -> 1nF/50V           (same part, the board spells it 1nF)
    That removes five unique BOM lines and one whole footprint (1206) from this page.

3.  **Placement notes on the page.** A schematic cannot say which ball a capacitor belongs to --
    only which net -- so the intent from Octavo's Table 4-3 is written next to each row as text,
    and repeated in `docs/sic.md` §12 for the layout.
"""
import pathlib, re, subprocess, sys, uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / 'tools'))
import schgen                                                              # noqa: E402

SIC = HERE / 'sic.kicad_sch'
SH = '767172a6-43e9-4684-bdc5-5dc2ecddbb44'
R402 = 'Resistor_SMD:R_0402_1005Metric'

REVALUE = {                      # ref -> (new value, new footprint)
    'C1530': ('4.7uF/10V', 'Capacitor_SMD:C_0805_2012Metric'),
    'C1531': ('4.7uF/10V', 'Capacitor_SMD:C_0805_2012Metric'),
    'C1532': ('4.7uF/10V', 'Capacitor_SMD:C_0805_2012Metric'),
    'C1533': ('4.7uF/10V', 'Capacitor_SMD:C_0805_2012Metric'),
    'C1534': ('10uF/10V', 'Capacitor_SMD:C_0805_2012Metric'),
    'C1535': ('10uF/10V', 'Capacitor_SMD:C_0805_2012Metric'),
    'C1536': ('10uF/10V', 'Capacitor_SMD:C_0805_2012Metric'),
    'C1537': ('22uF/10V', 'Capacitor_SMD:C_0805_2012Metric'),
    'C1538': ('22uF/10V', 'Capacitor_SMD:C_0805_2012Metric'),
    'C1548': ('1nF/50V', 'Capacitor_SMD:C_0402_1005Metric'),
}
NOTES = [   # (x, y, text) -- placement intent, Octavo Table 4-3 / docs/sic.md §2
    (25.4, 173.99, 'Decoupling, docs/sic.md §2 - the net is what the schematic fixes; these notes '
                   'say where each part goes on the board (Octavo Table 4-3)'),
    (25.4, 176.53, '+0V75_SIC: 10 uF bulk + one 100 nF per VDD_CORE cluster (G13..K16, 18 balls)'),
    (139.7, 176.53, '+0V85_SIC: 3 x 100 nF at VDDR_CORE (H17..K18)'),
    (190.5, 176.53, '+1V2_SIC: 3 x 100 nF at VDDS_DDR (K10..M11)'),
    (241.3, 176.53, '+2V5_SIC: 100 nF at DDR_VPP N10'),
    (266.7, 176.53, '+1V8A_SIC: 4.7 uF at CSIRX0 P13, 1 uF at OLDI0 P11, 1 uF bulk, '
                    '100 nF at PLL0/1/2 + MCU'),
    (25.4, 214.63, '+3V3_SIC: 10 uF bulk + one 100 nF per VDDSHV ball pair (9 pairs) '
                   '+ 100 nF at VDDA_3P3_USB N7'),
    (287.02, 30.48, 'PMIC input bank and output capacitors - keep the 22 uF/10 uF pair at PVIN, '
                    'the 47 uF + 10 uF at each buck output, close to U1501'),
    (287.02, 231.14, 'VMON_VSYS divider: trips the PMIC power-fail comparator (0.45 V) '
                     'at 0.45 x (100k+16k9)/16k9 = 3.11 V at the cell'),
]


def u():
    return str(uuid.uuid4())


def wire(a, b):
    return ('\t(wire\n\t\t(pts\n'
            f'\t\t\t(xy {a[0]:g} {a[1]:g}) (xy {b[0]:g} {b[1]:g})\n'
            '\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            f'\t\t(uuid "{u()}")\n\t)\n')


def text(x, y, s):
    return (f'\t(text "{s}"\n\t\t(exclude_from_sim yes)\n\t\t(at {x:g} {y:g} 0)\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.016 1.016)\n\t\t\t)\n'
            '\t\t\t(justify left bottom)\n\t\t)\n'
            f'\t\t(uuid "{u()}")\n\t)\n')


def label(p, t):
    return (f'\t(label "{t}"\n\t\t(at {p[0]:g} {p[1]:g} 0)\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            '\t\t\t(justify left bottom)\n\t\t)\n'
            f'\t\t(uuid "{u()}")\n\t)\n')


def prop(n, v, x, y, hide):
    h = '\n\t\t\t(hide yes)' if hide else ''
    return (f'\t\t(property "{n}" "{v}"\n\t\t\t(at {x:g} {y:g} 0){h}\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')


def symbol(lib_id, ref, value, x, y, root, fp='', hide_ref=False):
    return ('\t(symbol\n' f'\t\t(lib_id "{lib_id}")\n' f'\t\t(at {x:g} {y:g} 0)\n\t\t(unit 1)\n'
            '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n'
            f'\t\t(uuid "{u()}")\n'
            + prop('Reference', ref, x + 2.54, y - 1.27, hide_ref)
            + prop('Value', value, x + 2.54, y + 1.27, False)
            + prop('Footprint', fp, x, y, True) + prop('Datasheet', '', x, y, True)
            + prop('Description', '', x, y, True)
            + '\t\t(instances\n\t\t\t(project "r2"\n' f'\t\t\t\t(path "/{root}/{SH}"\n'
            f'\t\t\t\t\t(reference "{ref}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')


def main():
    run = [n for n in ('kicad', 'eeschema', 'pcbnew') if
           subprocess.run(['pgrep', '-x', n], capture_output=True).returncode == 0]
    if run:
        sys.exit(f'{", ".join(run)} running -- close KiCad first (CLAUDE.md).')

    text_all = SIC.read_text(encoding='utf-8')
    root = re.search(r'\(uuid "([^"]+)"\)', text_all).group(1)
    assert 'R1509' not in text_all, 'already applied'

    # ---- 2. re-value ---------------------------------------------------------------------------
    n_rv = 0
    for ref, (val, fp) in REVALUE.items():
        m = re.search(r'(\t\(symbol\n\t\t\(lib_id "Device:C"\)(?:(?!\n\t\(symbol).)*?'
                      r'\(property "Reference" "' + ref + r'".*?)(\n\t\)\n)', text_all, re.S)
        assert m, f'{ref} not found'
        blk = m.group(1)
        blk = re.sub(r'(\(property "Value" ")[^"]*(")', rf'\g<1>{val}\g<2>', blk, count=1)
        blk = re.sub(r'(\(property "Footprint" ")[^"]*(")', rf'\g<1>{fp}\g<2>', blk, count=1)
        text_all = text_all[:m.start(1)] + blk + text_all[m.end(1):]
        n_rv += 1

    # ---- 1. the VMON_VSYS divider --------------------------------------------------------------
    lib = schgen.SymbolLib()
    lib.add_dir('Device', pathlib.Path('/home/lum/Apps/kicad-10.0.4/share/kicad/symbols/'
                                       'Device.kicad_symdir'))
    res = lib.get('Device:R')
    dy = abs(res.pins['1'].y - res.pins['2'].y) / 2
    X, Y_TOP, Y_BOT = 299.72, 243.84, 259.08
    add = [symbol('Device:R', 'R1509', '100k/1%', X, Y_TOP, root, fp=R402),
           symbol('Device:R', 'R1510', '16.9k/1%', X, Y_BOT, root, fp=R402),
           wire((X, Y_TOP - dy), (X, Y_TOP - dy - 2.54)),
           symbol('symbols:+V', '#PWR1960', '+VSYS_SIC', X, Y_TOP - dy - 2.54, root, hide_ref=True),
           wire((X, Y_TOP + dy), (X, Y_BOT - dy)),                    # the tap
           label((X, Y_TOP + dy + 3.81), 'VMON_VSYS'),
           wire((X, Y_BOT + dy), (X, Y_BOT + dy + 2.54)),
           symbol('power:GND', '#PWR1961', 'GND', X, Y_BOT + dy + 2.54, root, hide_ref=True)]
    for x, y, s in NOTES:
        add.append(text(x, y, s.replace('"', "'")))

    for a in add:
        for m in re.finditer(r'\(xy ([-\d.]+) ([-\d.]+)\)', a):
            for v in (float(m.group(1)), float(m.group(2))):
                assert abs(round(v / 1.27) * 1.27 - v) < 1e-4, f'off-grid {v}'

    tail = text_all.rstrip()
    SIC.write_text(text_all[:len(tail) - 1] + ''.join(add) + text_all[len(tail) - 1:],
                   encoding='utf-8')
    print(f'  {n_rv} capacitors re-valued onto existing BOM lines')
    print(f'  R1509 100k/1% + R1510 16.9k/1%: +VSYS_SIC -> VMON_VSYS -> GND, trips at 3.11 V')
    print(f'  {len(NOTES)} placement notes added to the page')
    return 0


if __name__ == '__main__':
    sys.exit(main())
