#!/usr/bin/env python3
"""Step 4 corrections on `sic` (page 15) + the reference and PMIC-page fixes.

Surgical: every edit is an anchored replacement or an append. The owner drew this sheet in
Eeschema, so nothing is regenerated (CLAUDE.md).

What it does and why -- all of it audited from the netlist, not guessed:

1.  `sic` A4 -> A3. The owner's content already spans x 30..258, y 23..168 of an A4; the PMIC,
    its passives, the two load switches and the decoupling bank do not fit. Every other large
    sheet here (mcu, power, battery, io_expansion, dpi_in) is A3.
2.  **One reference for the SiP.** The 11 units answer to five names -- `IC1500`, `U1500`,
    `U1501`, `U1` and `U1403` -- so KiCad sees five parts, each claiming the 500-ball footprint,
    and the netlist export warns about annotation. Units live on pages 6/14/15/16, so the lowest
    page wins (CLAUDE.md): **`U600`**. This also frees `U1501` for the PMIC, which is what
    `docs/sic.md` §3 calls it.
3.  **`+1V8A_SIC` split from `+1V8_SIC`.** The nine `VDDA_*` analog pins and `VMON_1P8_SOC` were
    on one net. LDO3 exists precisely to give the PLLs, the oscillator and the analog blocks a
    quiet 1.8 V separate from BUCK2's digital 1.8 V (`docs/sic.md` §2). The two trunks are already
    separate on the page, so this is one symbol's Value.
4.  **`VMON_VSYS` taken off `+3V3_SIC`.** It was wired to the 3.3 V trunk; it is the PMIC's
    power-fail comparator input and must see the battery through the 100k/16.9k divider
    (`docs/sic.md` §7). Left on 3.3 V it would read a constant 3.3 V and never trip. The stub is
    cut and labelled; the divider itself belongs to step 8.
5.  **`VDDSHV0..6`, `_MCU`, `_CANUART` (18 pins) -> `+3V3_SIC`.** They were floating. They are one
    contiguous column on unit 2, so one trunk and one rail symbol.
6.  **`VDDA_CORE_CSIRX0` and `VDDA_CORE_USB` -> `+0V75_SIC`.** Floating; `docs/sic.md` §2 puts
    both in the core group.
7.  **`VPP` gets a no-connect flag.** `docs/sic.md` §2: "floating or grounded except while
    programming eFuses". The flag makes that explicit and keeps ERC quiet.
8.  **The PMIC leaves `power.kicad_sch`.** It was placed there as `U2`, which also copied its
    embedded datasheet into that sheet and grew the file from 186 kB to 5.1 MB. Removed with its
    `lib_symbols` entry; it is re-placed on `sic` as `U1501` by the stage-b script.
"""
import pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent.parent
SIC, NC, IOX, PWR = (HERE / f for f in ('sic.kicad_sch', 'nc.kicad_sch',
                                        'io_expansion.kicad_sch', 'power.kicad_sch'))
SIP_LIB = 'Reflow:OSD6254-1G-IPM'
REF = 'U600'


def running():
    return [n for n in ('kicad', 'eeschema', 'pcbnew', 'symbol_editor')
            if subprocess.run(['pgrep', '-x', n], capture_output=True).returncode == 0]


def sym_blocks(text, lib_id):
    """(start, end) of every top-level (symbol ...) block whose lib_id matches."""
    out = []
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
        if f'(lib_id "{lib_id}")' in blk:
            out.append((s, j + 1))
    return out


def retarget(path, lib_id, ref):
    """Give every instance of `lib_id` on this sheet the same reference."""
    text = path.read_text(encoding='utf-8')
    n = 0
    for s, e in reversed(sym_blocks(text, lib_id)):
        blk = text[s:e]
        old = re.search(r'\(property "Reference" "([^"]*)"', blk).group(1)
        if old != ref:
            n += 1
        blk = re.sub(r'(\(property "Reference" ")[^"]*(")', rf'\g<1>{ref}\g<2>', blk, count=1)
        blk = re.sub(r'(\(reference ")[^"]*(")', rf'\g<1>{ref}\g<2>', blk)
        text = text[:s] + blk + text[e:]
    path.write_text(text, encoding='utf-8')
    return n


def main():
    if running():
        sys.exit(f'{", ".join(running())} running -- close KiCad first (CLAUDE.md).')
    report = []

    # ---- 2. one reference for the SiP, everywhere it is placed --------------------------------
    for path in (SIC, NC, IOX):
        n = retarget(path, SIP_LIB, REF)
        report.append(f'{path.name}: {n} SiP unit(s) re-referenced to {REF}')

    sic = SIC.read_text(encoding='utf-8')

    # ---- 1. A4 -> A3 --------------------------------------------------------------------------
    assert '(paper "A4")' in sic
    sic = sic.replace('(paper "A4")', '(paper "A3")', 1)
    report.append('sic: paper A4 -> A3')

    # ---- 3. the analog 1.8 V rail gets its own name -------------------------------------------
    # the symbol at (139.7, 96.52) is the one whose trunk carries the nine VDDA_* pins
    m = re.search(r'\(symbol\n\t\t\(lib_id "power:\+1V5"\)\n\t\t\(at 139\.7 96\.52 0\)', sic)
    assert m, 'the +1V8 symbol at (139.7, 96.52) moved -- re-run the connectivity audit'
    s, e = sym_blocks(sic, 'power:+1V5')[0], None
    for a, b in sym_blocks(sic, 'power:+1V5'):
        if '(at 139.7 96.52 0)' in sic[a:b]:
            blk = sic[a:b]
            assert '"+1V8_SIC"' in blk
            sic = sic[:a] + blk.replace('"+1V8_SIC"', '"+1V8A_SIC"') + sic[b:]
            report.append('sic: analog rail renamed +1V8_SIC -> +1V8A_SIC (LDO3, docs/sic.md §2)')
            break
    else:
        sys.exit('could not find the analog +1V8 rail symbol')

    SIC.write_text(sic, encoding='utf-8')

    # ---- 8. the PMIC leaves the power sheet ---------------------------------------------------
    pwr = PWR.read_text(encoding='utf-8')
    before = len(pwr)
    blocks = sym_blocks(pwr, 'Reflow:TPS6521903')
    for a, b in reversed(blocks):
        pwr = pwr[:a] + pwr[b:]
    # its lib_symbols entry carries the embedded datasheet -- that is the 5 MB
    m = re.search(r'\n\t\t\(symbol "Reflow:TPS6521903"', pwr)
    if m:
        s, depth, j, ins = m.start() + 1, 0, m.start() + 1, False
        while True:
            c = pwr[j]
            if c == '"' and pwr[j - 1] != '\\':
                ins = not ins
            elif not ins:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        pwr = pwr[:s] + pwr[j + 2:]
    PWR.write_text(pwr, encoding='utf-8')
    report.append(f'power: removed {len(blocks)} PMIC instance(s) and its lib_symbols entry '
                  f'({before/1e6:.1f} MB -> {len(pwr)/1e6:.1f} MB)')

    print('\n'.join('  ' + r for r in report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
