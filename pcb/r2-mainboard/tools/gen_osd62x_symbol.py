#!/usr/bin/env python3
"""Rebuild the `OSD6254-1G-IPM` symbol in library/Reflow.kicad_sym as eleven functional units.

Input: datasheets/SiC OSD62x-PM/osd62x_pm_pinout.json, from tools/parse_osd62x_pinout.py -- the
datasheet's ball map and ball description, checked against each other and against Octavo's own
Eagle library (500/500). Nothing here is typed from the PDF.

The owner imported SamacSys's symbol from Mouser (2026-09-11): one unit, 500 `passive` pins, names
mangled where the datasheet wraps a line (`MCU__UART0_RTSN`) and `VSS_1`... numbered. This script
replaces that block in place and keeps its name, so `Reflow:OSD6254-1G-IPM` instances stay linked,
and keeps every pin NUMBER (the ball names), so nothing already wired moves to another ball. The
vendor original survives untouched as library/OSD6254-1G-IPM.kicad_sym.

Rules are docs/osd62x-symbol-guide.md: pin number = ball; pin name = the datasheet's name verbatim;
electrical types per its section 3.3; the eleven units of section 4; no hidden pins; and no two
pins in a unit at one position (the owner's rule -- no stacking). Every one is asserted below
before the file is written. Run it again and it replaces the block again; the rest of
Reflow.kicad_sym is left byte-for-byte alone.
"""
import collections, json, math, pathlib, re, sys

HERE   = pathlib.Path(__file__).resolve().parent.parent
PINOUT = HERE / 'datasheets/SiC OSD62x-PM/osd62x_pm_pinout.json'
LIB    = HERE / 'library/Reflow.kicad_sym'
FPFILE = HERE / 'library/Reflow.pretty/BGA500C50P28X18_1400X900X130.kicad_mod'
NAME      = 'OSD6254-1G-IPM'
FOOTPRINT = 'Reflow:BGA500C50P28X18_1400X900X130'
LEN, PITCH, NAME_OFS = 5.08, 2.54, 1.016
CHAR = 1.05                      # mm per character of 1.27 mm KiCad text, generous
GAP = None                       # an empty row between groups

INPUTS  = {'USB0_VBUS', 'USB1_VBUS', 'MCU_PORZ', 'MCU_RESETZ', 'RESET_REQZ', 'EXTINTN',
           'MCU_OSC0_XI', 'WKUP_LFOSC0_XI', 'TCK', 'TDI', 'TMS', 'TRSTN'}
OUTPUTS = {'PORZ_OUT', 'RESETSTATZ', 'MCU_RESETSTATZ', 'PMIC_LPM_EN0',
           'MCU_OSC0_XO', 'WKUP_LFOSC0_XO', 'TDO'}

def etype(n):
    if n in ('NC', 'DDR_RSVD0') or n.startswith('AM62X_RSVD'):         return 'no_connect'
    if n == 'VSS' or re.match(r'^(VDD|DDR_VPP$|VPP$)', n):               return 'power_in'
    if n in INPUTS or n.startswith('VMON_'):                             return 'input'
    if n in OUTPUTS:                                                     return 'output'
    return 'bidirectional'

def key(b): return ('ABCDEFGHJKLMNPRTUV'.index(b[0]), int(b[1:]))

def build_units(pins):
    by = collections.defaultdict(list)
    for b, p in pins.items(): by[p['name']].append(b)
    for n in by: by[n].sort(key=key)
    def col(*groups):                      # names -> balls, a GAP row between groups
        out = []
        for g in groups:
            if out: out.append(GAP)
            for n in g:
                assert n in by, f'no ball named {n}'
                out += by[n]
        return out
    R = lambda pre, xs: [f'{pre}{x}' for x in xs]
    vss, nc = by['VSS'], by['NC']
    rsvd = [f'AM62X_RSVD{i}' for i in range(9)] + ['DDR_RSVD0']
    return [
     ('PWR_CORE',
      col(['VDD_CORE'], ['VDD_CANUART', 'VDDA_CORE_CSIRX0', 'VDDA_CORE_USB']),
      col(['VDDR_CORE'], ['VDDS_DDR'], ['DDR_VPP'])),
     ('PWR_IO',
      col(R('VDDSHV', ['0', '1', '2', '3', '4', '5', '6', '_MCU', '_CANUART'])),
      col(['VDDA_1P8_OLDI0', 'VDDA_1P8_CSIRX0', 'VDDA_1P8_USB', 'VDDA_PLL0', 'VDDA_PLL1',
           'VDDA_PLL2', 'VDDA_MCU', 'VDDA_TEMP', 'VDDS_OSC0'], ['VDDA_3P3_USB'], ['VPP'],
          ['VMON_VSYS', 'VMON_1P8_SOC', 'VMON_3P3_SOC'])),
     ('GND', vss[:52], vss[52:]),
     # R2's DPI bus in bus order -- DATA0-5 = DPI_B2-B7, DATA6-11 = G2-G7, DATA12-15 + GPMC0_AD8/9
     # = R2-R7 -- in one right-hand column, as the PHYTEC VIDEO unit did: every signal leaves.
     ('VIDEO', [],
      col(R('VOUT0_DATA', range(0, 6)), R('VOUT0_DATA', range(6, 12)),
          R('VOUT0_DATA', range(12, 16)) + ['GPMC0_AD8', 'GPMC0_AD9'],
          ['VOUT0_PCLK', 'VOUT0_DE', 'VOUT0_HSYNC', 'VOUT0_VSYNC'])),
     ('BOOT_GPMC',
      col(R('GPMC0_AD', [0, 1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13, 14, 15])),
      col(['GPMC0_CLK', 'GPMC0_ADVN_ALE', 'GPMC0_OEN_REN', 'GPMC0_WEN', 'GPMC0_WPN', 'GPMC0_DIR',
           'GPMC0_BE0N_CLE', 'GPMC0_BE1N'], R('GPMC0_CSN', range(4)), ['GPMC0_WAIT0', 'GPMC0_WAIT1'])),
     ('SYSTEM',
      col(['MCU_PORZ', 'MCU_RESETZ', 'RESET_REQZ', 'EXTINTN'],
          ['MCU_OSC0_XI', 'MCU_OSC0_XO', 'WKUP_LFOSC0_XI', 'WKUP_LFOSC0_XO'],
          ['EXT_REFCLK1', 'WKUP_CLKOUT0']),
      col(['PORZ_OUT', 'RESETSTATZ', 'MCU_RESETSTATZ', 'PMIC_LPM_EN0', 'MCU_ERRORN'],
          ['TCK', 'TDI', 'TMS', 'TRSTN', 'TDO', 'EMU0', 'EMU1'])),
     ('SERIAL',                                                   # MAIN domain | MCU + WKUP domains
      col(R('UART0_', ['RXD', 'TXD', 'CTSN', 'RTSN']), R('SPI0_', ['CLK', 'D0', 'D1', 'CS0', 'CS1']),
          ['I2C0_SCL', 'I2C0_SDA', 'I2C1_SCL', 'I2C1_SDA'], ['MCAN0_RX', 'MCAN0_TX'],
          R('MCASP0_', ['ACLKX', 'AFSX', 'ACLKR', 'AFSR', 'AXR0', 'AXR1', 'AXR2', 'AXR3'])),
      col(R('MCU_UART0_', ['RXD', 'TXD', 'CTSN', 'RTSN']), R('MCU_SPI0_', ['CLK', 'D0', 'D1', 'CS0', 'CS1']),
          ['MCU_I2C0_SCL', 'MCU_I2C0_SDA'], ['MCU_MCAN0_RX', 'MCU_MCAN0_TX', 'MCU_MCAN1_RX', 'MCU_MCAN1_TX'],
          R('WKUP_UART0_', ['RXD', 'TXD', 'CTSN', 'RTSN']), ['WKUP_I2C0_SCL', 'WKUP_I2C0_SDA'])),
     ('STORAGE',
      col(['MMC0_CLK', 'MMC0_CMD'] + R('MMC0_DAT', range(8)),
          ['MMC1_CLK', 'MMC1_CMD'] + R('MMC1_DAT', range(4)) + ['MMC1_SDCD', 'MMC1_SDWP']),
      col(['MMC2_CLK', 'MMC2_CMD'] + R('MMC2_DAT', range(4)) + ['MMC2_SDCD', 'MMC2_SDWP'],
          ['OSPI0_CLK', 'OSPI0_DQS', 'OSPI0_LBCLKO'] + R('OSPI0_CSN', range(4)) + R('OSPI0_D', range(8)))),
     ('USB',
      col(['USB0_DP', 'USB0_DM', 'USB0_VBUS', 'USB0_DRVVBUS']),
      col(['USB1_DP', 'USB1_DM', 'USB1_VBUS', 'USB1_DRVVBUS'])),
     ('UNUSED_HS',                                                # R2 uses none of these
      col([f'OLDI0_A{i}{s}' for i in range(8) for s in 'PN'] + ['OLDI0_CLK0P', 'OLDI0_CLK0N', 'OLDI0_CLK1P', 'OLDI0_CLK1N'],
          ['CSI0_RXCLKP', 'CSI0_RXCLKN'] + [f'CSI0_RX{s}{i}' for i in range(4) for s in 'PN']),
      col([f'RGMII1_{s}' for s in ['RXC', 'RX_CTL', 'RD0', 'RD1', 'RD2', 'RD3', 'TXC', 'TX_CTL', 'TD0', 'TD1', 'TD2', 'TD3']],
          [f'RGMII2_{s}' for s in ['RXC', 'RX_CTL', 'RD0', 'RD1', 'RD2', 'RD3', 'TXC', 'TX_CTL', 'TD0', 'TD1', 'TD2', 'TD3']],
          ['MDIO0_MDC', 'MDIO0_MDIO'])),
     ('NC_RSVD', col(rsvd) + [GAP] + nc[:41], nc[41:]),
    ]

def esc(s): return s.replace('\\', '\\\\').replace('"', '\\"')
def fnt(ind): return f'{ind}(effects\n{ind}\t(font\n{ind}\t\t(size 1.27 1.27)\n{ind}\t)\n{ind})\n'

def pin(t, x, y, rot, name, num):
    return (f'\t\t\t(pin {t} line\n\t\t\t\t(at {x:g} {y:g} {rot})\n\t\t\t\t(length {LEN:g})\n'
            f'\t\t\t\t(name "{esc(name)}"\n' + fnt('\t\t\t\t\t') + '\t\t\t\t)\n'
            f'\t\t\t\t(number "{esc(num)}"\n' + fnt('\t\t\t\t\t') + '\t\t\t\t)\n\t\t\t)\n')

def geometry(left, right, pins):
    rows = max(len(left), len(right))
    # Every unit is TOP-aligned: first pin row at y = 0, the body growing downward. KiCad keeps one
    # position per field for all units, so a centred layout put Reference/Value on the pins of
    # the taller units (seen in the 2026-09-11 render); top-aligned, one spot above clears them all.
    top = 0
    lmax = max([len(pins[b]['name']) for b in left if b] or [0])
    rmax = max([len(pins[b]['name']) for b in right if b] or [0])
    w = (lmax + rmax) * CHAR + 2 * NAME_OFS + (2 * PITCH if lmax and rmax else PITCH)
    w = max(15.24, math.ceil(w / (2 * PITCH)) * 2 * PITCH)   # multiple of 5.08 -> half on grid
    return rows, top, w / 2

def unit_block(n, uname, left, right, pins):
    rows, top, half = geometry(left, right, pins)
    out = [f'\t\t(symbol "{NAME}_{n}_1"\n\t\t\t(unit_name "{uname}")\n'
           f'\t\t\t(rectangle\n\t\t\t\t(start {-half:g} {top + PITCH:g})\n'
           f'\t\t\t\t(end {half:g} {top - rows * PITCH:g})\n'
           '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n'
           '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)\n']
    for side, xs, rot in ((left, -half - LEN, 0), (right, half + LEN, 180)):
        for i, b in enumerate(side):
            if b: out.append(pin(etype(pins[b]['name']), xs, top - i * PITCH, rot, pins[b]['name'], b))
    out.append('\t\t)\n')
    return ''.join(out), rows, 2 * half

def splice(text, block):
    m = re.search(r'\n\t\(symbol "%s"\n' % re.escape(NAME), text)
    assert m, f'{NAME} not found in {LIB.name}'
    s, depth, j, ins = m.start() + 1, 0, m.start() + 1, False
    while True:
        c = text[j]
        if c == '"' and text[j - 1] != '\\': ins = not ins
        elif not ins:
            if c == '(': depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0: break
        j += 1
    return text[:s], text[s:j + 2], text[j + 2:]

def main():
    pins = json.load(open(PINOUT))['pins']
    assert len(pins) == 500
    text = LIB.read_text(encoding='utf-8')
    pre, old, post = splice(text, '')
    keep = dict(re.findall(r'\(property "(Height|Mouser Part Number|Mouser Price/Stock|Manufacturer_Name|Manufacturer_Part_Number)" "([^"]*)"', old))

    units = build_units(pins)
    bodies, report, where = [], [], {}
    for n, (uname, left, right) in enumerate(units, 1):
        blk, rows, width = unit_block(n, uname, left, right, pins)
        bodies.append(blk); report.append((n, uname, sum(1 for b in left + right if b), rows, width))
        for b in left + right:
            if b:
                assert b not in where, f'{b} placed twice'
                where[b] = uname
    u1_rows, u1_top, _ = geometry(units[0][1], units[0][2], pins)

    props = [('Reference', 'U', False, 3 * PITCH),          # both above the body, which starts
             ('Value', NAME, False, 2 * PITCH),              # at y = +2.54 in every unit
             ('Footprint', FOOTPRINT, True, 0), ('Datasheet', 'https://octavosystems.com/docs/osd62-pm-datasheet/', True, 0),
             ('Description', 'Octavo OSD62x-PM system-in-package: TI AM6254 + 1 GB DDR4 + passives, 9 x 14 mm '
              '500-ball 0.5 mm BGA. Eleven functional units; pin names verbatim from datasheet Rev. 2.0 '
              'Tables 5-6/5-7, numbers are the balls. Generated by tools/gen_osd62x_symbol.py from '
              'datasheets/SiC OSD62x-PM/osd62x_pm_pinout.json -- see docs/osd62x-symbol-guide.md.', True, 0),
             ('ki_keywords', 'Octavo OSD62x-PM OSD6254 AM62x AM6254 SiP DDR4 BGA-500', True, 0)]
    props += [(k, v, True, 0) for k, v in keep.items()]
    hdr = [f'\t(symbol "{NAME}"\n\t\t(pin_names\n\t\t\t(offset {NAME_OFS:g})\n\t\t)\n'
           '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(in_pos_files yes)\n'
           '\t\t(duplicate_pin_numbers_are_jumpers no)\n']
    for k, v, hide, y in props:
        hdr.append(f'\t\t(property "{k}" "{esc(v)}"\n\t\t\t(at 0 {y:g} 0)\n'
                   + ('\t\t\t(hide yes)\n' if hide else '') + fnt('\t\t\t') + '\t\t)\n')
    block = ''.join(hdr) + ''.join(bodies) + '\t\t(embedded_fonts no)\n\t)\n'

    # ---- every rule, asserted on the text actually about to be written ----------------------
    P = re.findall(r'\(symbol "%s_(\d+)_1"|\(pin (\w+) line\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*\(length [\d.]+\)(\s*\(hide yes\))?\s*\(name "([^"]*)".*?\(number "([^"]*)"' % re.escape(NAME), block, re.S)
    unit, got, pos = None, {}, collections.defaultdict(set)
    for u, t, x, y, rot, hidden, nm, num in P:
        if u: unit = int(u); continue
        assert not hidden, f'{num} is hidden'
        assert num not in got, f'pin number {num} appears twice'
        assert (x, y) not in pos[unit], f'unit {unit}: two pins at ({x}, {y}) -- {num}'
        pos[unit].add((x, y))
        for v in (float(x), float(y)):
            assert abs(v / PITCH - round(v / PITCH)) < 1e-6, f'{num} off the 2.54 grid: {x},{y}'
        got[num] = (t, nm, unit)
    fp = set(re.findall(r'\(pad\s+"?([A-Z]+\d+)"?\s', FPFILE.read_text()))
    assert set(got) == set(pins), f'numbers differ from the datasheet: {sorted(set(pins) ^ set(got))[:8]}'
    assert set(got) == fp, f'numbers differ from the footprint pads: {sorted(fp ^ set(got))[:8]}'
    assert all(got[b][1] == pins[b]['name'] for b in pins), 'a pin name differs from the datasheet'
    assert all(got[b][0] == etype(pins[b]['name']) for b in pins), 'an electrical type is off-rule'
    video = {b for b in pins if where[b] == 'VIDEO'}
    want = {b for b, p in pins.items() if p['name'].startswith('VOUT0_') or p['name'] in ('GPMC0_AD8', 'GPMC0_AD9')}
    assert video == want and len(video) == 22, 'VIDEO is not exactly the 22 DPI balls'

    new = pre + block + post
    assert new.replace(block, '') == pre + post       # everything else untouched
    LIB.write_text(new, encoding='utf-8')

    print(f'{NAME}: {len(got)} pins in {len(units)} units, written into {LIB.relative_to(HERE)}')
    print(f'  {"#":>2}  {"unit":<10} {"pins":>4} {"rows":>4} {"width mm":>9}')
    for n, u, c, r, w in report: print(f'  {n:>2}  {u:<10} {c:>4} {r:>4} {w:>9.2f}')
    print('  types:', ', '.join(f'{k}={v}' for k, v in sorted(collections.Counter(t for t, _, _ in got.values()).items())))
    print('  checks: numbers = datasheet = footprint pads; names verbatim; types by rule; no hidden pin;'
          ' no two pins at one position in any unit; all pins on the 2.54 grid; VIDEO = the 22 DPI balls;'
          ' rest of the library untouched')
    return 0

if __name__ == '__main__':
    sys.exit(main())
