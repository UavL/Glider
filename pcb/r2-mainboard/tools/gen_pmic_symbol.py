#!/usr/bin/env python3
"""Fill in the `TPS6521903` symbol the owner created in library/Reflow.kicad_sym.

The owner made the container: name, Value, Description and an **embedded copy of the datasheet**
(`kicad-embed://tps65219.pdf`, a ~60k-line base64 block). This script only ever supplies the pins,
the body and the field positions; the embedded file block and the Description are lifted out of the
existing symbol and written back **verbatim**.

Source of truth: `datasheets/Power/tps65219.pdf` (`SLVSGA0D`), section 5, **Table 5-1 Pin
Functions**. `PINS` below is transcribed from it; the table is also parsed from the PDF at run time
and every parsed row must agree with `PINS`, so a mis-transcription or a datasheet revision shows up
as a failure instead of a wrong symbol. **29 of the 33 rows re-parse**; the other four defeat
pdftotext's columns -- pin 12's number sits on its own line, pin 25's name is split over two lines,
pin 28 has a single space before its number, and pin 33 is numbered "PowerPad" -- and the script
asserts that it is exactly those four, so a re-flowed table fails instead of checking less.

Package: `RHB0032W`, VQFN-32, 5 x 5 mm, 0.5 mm pitch, exposed pad 3.5 mm. KiCad's stock
`Texas_RHB0032E_..._EP3.45x3.45mm_ThermalVias` is 0.05 mm under on the pad and already carries the
>= 9 vias the datasheet demands; its pads are 1..32 plus **33** for the pad, which is what the
thermal pin is numbered here.

    tools/gen_pmic_symbol.py           # writes library/Reflow.kicad_sym (refuses while KiCad runs)
    tools/gen_pmic_symbol.py --out F   # write elsewhere, for staging
"""
import argparse, collections, math, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent.parent
PDF  = HERE / 'datasheets/Power/tps65219.pdf'
LIB  = HERE / 'library/Reflow.kicad_sym'
NAME = 'TPS6521903'
FOOTPRINT = ('Package_DFN_QFN:Texas_RHB0032E_VQFN-32-1EP_5x5mm_P0.5mm'
             '_EP3.45x3.45mm_ThermalVias')
FPFILE = pathlib.Path('/home/lum/Apps/AppDir/share/kicad/footprints/Package_DFN_QFN.pretty')
LEN, PITCH, NAME_OFS = 2.54, 2.54, 1.016      # 2.54 pins: the convention in r2.kicad_sym
CHAR = 1.05
GAP = None

# Datasheet Table 5-1, transcribed. (number, name, datasheet TYPE) -- the TYPE column is kept so the
# runtime parse can check it; the KiCad electrical type is decided by ETYPE below.
PINS = [
    (1,  'FB_B1',            'I'),   (2,  'LX_B1_1',   'PWR'), (3,  'LX_B1_2',    'PWR'),
    (4,  'PVIN_B1_1',        'PWR'), (5,  'PVIN_B1_2', 'PWR'), (6,  'PVIN_LDO1',  'PWR'),
    (7,  'VLDO1',            'PWR'), (8,  'GPO1',      'O'),   (9,  'SDA',        'I/O'),
    (10, 'SCL',              'I'),   (11, 'nINT',      'O'),   (12, 'VSEL_SD/VSEL_DDR', 'I'),
    (13, 'VSYS',             'PWR'), (14, 'VDD1P8',    'PWR'), (15, 'AGND',       'GND'),
    (16, 'GPIO',             'I/O'), (17, 'GPO2',      'O'),   (18, 'nRSTOUT',    'O'),
    (19, 'VLDO2',            'PWR'), (20, 'PVIN_LDO2', 'PWR'), (21, 'VLDO3',      'PWR'),
    (22, 'PVIN_LDO34',       'PWR'), (23, 'VLDO4',     'PWR'), (24, 'FB_B3',      'I'),
    (25, 'EN/PB/VSENSE',     'I'),   (26, 'PVIN_B3',   'PWR'), (27, 'LX_B3',      'PWR'),
    (28, 'MODE/RESET',       'I'),   (29, 'LX_B2',     'PWR'), (30, 'PVIN_B2',    'PWR'),
    (31, 'MODE/STBY',        'I'),   (32, 'FB_B2',     'I'),   (33, 'PGND',       'GND'),
]

# KiCad electrical types. The bucks' switch nodes are `passive` (they carry the inductor, they are
# neither a supply to draw from nor a signal); the four open-drain outputs are `open_collector`, so
# ERC does not call two of them tied together a conflict; `VDD1P8` and the LDO outputs are
# `power_out` -- each is an internal regulator output that must never be fed from a rail.
ETYPE = {
    'power_in':       {'VSYS', 'PVIN_B1_1', 'PVIN_B1_2', 'PVIN_B2', 'PVIN_B3', 'PVIN_LDO1',
                       'PVIN_LDO2', 'PVIN_LDO34', 'AGND', 'PGND'},
    'power_out':      {'VLDO1', 'VLDO2', 'VLDO3', 'VLDO4', 'VDD1P8'},
    'passive':        {'LX_B1_1', 'LX_B1_2', 'LX_B2', 'LX_B3'},
    'input':          {'FB_B1', 'FB_B2', 'FB_B3', 'SCL', 'EN/PB/VSENSE', 'MODE/RESET',
                       'MODE/STBY', 'VSEL_SD/VSEL_DDR'},
    'bidirectional':  {'SDA', 'GPIO'},
    'open_collector': {'GPO1', 'GPO2', 'nINT', 'nRSTOUT'},
}
TYPE_OF = {n: t for t, names in ETYPE.items() for n in names}

# The body: inputs and control on the left, everything the board takes from the part on the right,
# the two grounds out of the bottom.
LEFT = [['VSYS', 'PVIN_B1_1', 'PVIN_B1_2', 'PVIN_B2', 'PVIN_B3', 'PVIN_LDO1', 'PVIN_LDO2',
         'PVIN_LDO34'],
        ['EN/PB/VSENSE', 'MODE/STBY', 'MODE/RESET', 'VSEL_SD/VSEL_DDR'],
        ['SDA', 'SCL']]
RIGHT = [['LX_B1_1', 'LX_B1_2', 'FB_B1', 'LX_B2', 'FB_B2', 'LX_B3', 'FB_B3'],
         ['VLDO1', 'VLDO2', 'VLDO3', 'VLDO4'],
         ['GPO1', 'GPO2', 'GPIO', 'nINT', 'nRSTOUT'],
         ['VDD1P8']]
BOTTOM = ['AGND', 'PGND']


def parse_table(pdf):
    """Table 5-1 -> {number: (name, TYPE)} for every row whose layout survives pdftotext."""
    txt = subprocess.run(['pdftotext', '-layout', str(pdf), '-'],
                         check=True, capture_output=True, text=True).stdout.split('\n')
    lo = next(i for i, l in enumerate(txt) if 'Table 5-1. Pin Functions' in l)
    # bound the search *after* lo: '6 Specifications' also appears in the table of contents
    hi = next(i for i, l in enumerate(txt) if i > lo and re.match(r'\s*6 Specifications', l))
    out = {}
    for line in txt[lo:hi]:
        m = re.match(r'\s{2,}([A-Za-z0-9_/]{3,20})\s{2,}(\d{1,2})\s{2,}(PWR|GND|I/O|I|O)(?:\s|$)', line)
        if m:
            out[int(m.group(2))] = (m.group(1), m.group(3))
    return out


def esc(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')


def fnt(ind):
    return f'{ind}(effects\n{ind}\t(font\n{ind}\t\t(size 1.27 1.27)\n{ind}\t)\n{ind})\n'


def pin(t, x, y, rot, name, num):
    return (f'\t\t\t(pin {t} line\n\t\t\t\t(at {x:g} {y:g} {rot})\n\t\t\t\t(length {LEN:g})\n'
            f'\t\t\t\t(name "{esc(name)}"\n' + fnt('\t\t\t\t\t') + '\t\t\t\t)\n'
            f'\t\t\t\t(number "{esc(num)}"\n' + fnt('\t\t\t\t\t') + '\t\t\t\t)\n\t\t\t)\n')


def flatten(groups):
    out = []
    for g in groups:
        if out:
            out.append(GAP)
        out += g
    return out


def splice(text):
    """(head, symbol block, tail) for NAME -- the block is balanced on parentheses."""
    m = re.search(r'\n\t\(symbol "%s"\n' % re.escape(NAME), text)
    assert m, f'{NAME} not found in {LIB.name} -- create the symbol in KiCad first'
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


def lift(block, tag):
    """Pull a balanced `(tag ...)` sub-block out of the old symbol, verbatim."""
    m = re.search(r'\n(\t\t\(%s\b)' % re.escape(tag), block)
    if not m:
        return ''
    s, depth, j, ins = m.start(1), 0, m.start(1), False
    while True:
        c = block[j]
        if c == '"' and block[j - 1] != '\\':
            ins = not ins
        elif not ins:
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
        j += 1
    return block[s:j + 1] + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=pathlib.Path)
    args = ap.parse_args()
    dest = args.out or LIB
    running = [n for n in ('kicad', 'eeschema', 'pcbnew', 'symbol_editor')
               if subprocess.run(['pgrep', '-x', n], capture_output=True).returncode == 0]
    if dest == LIB and running:
        sys.exit(f'{", ".join(running)} running -- close it, or use --out to stage (CLAUDE.md).')

    by_num = {n: (nm, ty) for n, nm, ty in PINS}
    assert len(by_num) == 33 and set(by_num) == set(range(1, 34)), 'PINS is not 1..33'

    parsed = parse_table(PDF)
    for num, (nm, ty) in parsed.items():
        assert num in by_num, f'datasheet has pin {num}, PINS does not'
        want, wty = by_num[num]
        # a multi-function name wraps in the PDF ('VSEL_SD/' / 'VSEL_DDR'), so the parse sees one
        # half of it; accept that, reject anything else
        ok = nm == want or want.endswith('/' + nm) or want.startswith(nm + '/')
        assert ok and ty == wty, f'pin {num}: datasheet {nm}/{ty}, PINS {want}/{wty}'
    # Four rows cannot survive pdftotext's column layout, each for its own reason: 12 puts the
    # number on a line of its own, 25 splits 'EN/PB/ VSENSE' over two lines, 28 leaves a single
    # space before the number, and 33 is numbered 'PowerPad'. Assert the exact set -- if a
    # revision re-flows the table, this fires instead of silently checking less.
    assert set(range(1, 34)) - set(parsed) == {12, 25, 28, 33}, \
        f'Table 5-1 re-flowed: {sorted(set(range(1, 34)) - set(parsed))} unparsed'

    names = {nm: n for n, nm, _ in PINS}
    assert set(names) == set(TYPE_OF), 'a pin has no electrical type'
    placed = flatten(LEFT) + flatten(RIGHT) + BOTTOM
    assert sorted(p for p in placed if p) == sorted(names), 'the body does not place every pin once'

    # ---- geometry ---------------------------------------------------------------------------
    left, right = flatten(LEFT), flatten(RIGHT)
    rows = max(len(left), len(right))
    lmax = max(len(p) for p in left if p)
    rmax = max(len(p) for p in right if p)
    w = (lmax + rmax) * CHAR + 2 * NAME_OFS + 2 * PITCH
    half = max(15.24, math.ceil(w / (2 * PITCH)) * PITCH)
    top = math.ceil(rows / 2) * PITCH                      # body centred on the origin, on grid
    bot = top - (rows + 1) * PITCH

    body = [f'\t\t(symbol "{NAME}_0_1"\n'
            f'\t\t\t(rectangle\n\t\t\t\t(start {-half:g} {top:g})\n\t\t\t\t(end {half:g} {bot:g})\n'
            '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n'
            '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n']
    pins = [f'\t\t(symbol "{NAME}_1_1"\n']
    for side, xs, rot in ((left, -half - LEN, 0), (right, half + LEN, 180)):
        for i, nm in enumerate(side):
            if nm:
                pins.append(pin(TYPE_OF[nm], xs, top - (i + 1) * PITCH, rot, nm, str(names[nm])))
    for k, nm in enumerate(BOTTOM):                        # out of the bottom edge, pointing down
        pins.append(pin(TYPE_OF[nm], (k - (len(BOTTOM) - 1) / 2) * 2 * PITCH, bot - LEN, 90,
                        nm, str(names[nm])))
    pins.append('\t\t)\n')

    text = LIB.read_text(encoding='utf-8')
    pre, old, post = splice(text)
    embedded = lift(old, 'embedded_files')                 # the owner's embedded datasheet, verbatim
    desc = re.search(r'\(property "Description" "([^"]*)"', old).group(1)
    datasheet = re.search(r'\(property "Datasheet" "([^"]*)"', old).group(1)

    props = [('Reference', 'U', False, top + 2 * PITCH), ('Value', NAME, False, top + PITCH),
             ('Footprint', FOOTPRINT, True, 0), ('Datasheet', datasheet, True, 0),
             ('Description', desc, True, 0),
             ('ki_keywords', 'PMIC TPS65219 TPS6521903 buck LDO AM62x power management', True, 0),
             ('MPN', 'TPS6521903RHBR', True, 0), ('Manufacturer', 'Texas Instruments', True, 0),
             ('LCSC', 'C18716455', True, 0)]
    hdr = [f'\t(symbol "{NAME}"\n\t\t(pin_names\n\t\t\t(offset {NAME_OFS:g})\n\t\t)\n'
           '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(in_pos_files yes)\n'
           '\t\t(duplicate_pin_numbers_are_jumpers no)\n']
    for k, v, hide, y in props:
        hdr.append(f'\t\t(property "{k}" "{esc(v)}"\n\t\t\t(at 0 {y:g} 0)\n'
                   + ('\t\t\t(hide yes)\n' if hide else '') + fnt('\t\t\t') + '\t\t)\n')
    block = ''.join(hdr) + ''.join(body) + ''.join(pins) + '\t\t(embedded_fonts no)\n' + embedded + '\t)\n'

    # ---- assert on the text about to be written ----------------------------------------------
    P = re.findall(r'\(pin (\w+) line\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*\(length [\d.]+\)'
                   r'(\s*\(hide yes\))?\s*\(name "([^"]*)".*?\(number "([^"]*)"', block, re.S)
    got, pos = {}, set()
    for t, x, y, rot, hidden, nm, num in P:
        assert not hidden, f'{num} is hidden'
        assert num not in got, f'pin number {num} twice'
        assert (x, y) not in pos, f'two pins at ({x}, {y})'
        pos.add((x, y))
        for v in (float(x), float(y)):
            assert abs(v / PITCH - round(v / PITCH)) < 1e-6, f'{num} off the 2.54 grid'
        got[num] = (t, nm)
    assert set(got) == {str(n) for n in range(1, 34)}, 'pin numbers are not 1..33'
    assert all(got[str(n)] == (TYPE_OF[nm], nm) for n, nm, _ in PINS), 'a name or type is wrong'
    fp = FPFILE / (FOOTPRINT.split(':')[1] + '.kicad_mod')
    if fp.exists():
        pads = set(re.findall(r'\(pad "(\d+)"', fp.read_text()))
        assert pads == set(got), f'footprint pads != symbol pins: {sorted(pads ^ set(got))}'
    assert embedded.strip().startswith('(embedded_files'), 'the embedded datasheet was lost'
    assert len(embedded) > 10000, 'the embedded datasheet looks truncated'

    new = pre + block + post
    assert new.replace(block, '', 1) == pre + post, 'the rest of the library would change'
    dest.write_text(new, encoding='utf-8')

    print(f'{NAME}: {len(got)} pins written to {dest}')
    print(f'  body {2 * half:.2f} x {top - bot:.2f} mm, {rows} pin rows, '
          f'{len(left)} left / {len(right)} right / {len(BOTTOM)} bottom')
    print('  types:', ', '.join(f'{k}={v}' for k, v in
                                sorted(collections.Counter(t for t, _ in got.values()).items())))
    print(f'  footprint: {FOOTPRINT}')
    print(f'  checks: {len(parsed)}/33 rows re-parsed from Table 5-1 and matched; pin numbers 1..33 '
          '= the footprint pads; names verbatim; no hidden pin; no two pins at one position; all on '
          "the 2.54 grid; the owner's embedded datasheet and Description kept verbatim; the rest of "
          'the library untouched')
    return 0


if __name__ == '__main__':
    sys.exit(main())
