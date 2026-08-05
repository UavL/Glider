#!/usr/bin/env python3
"""Generate pcb/r2-mainboard/r2.kicad_sym — the project's own symbols.

Two symbols are not in KiCad's standard libraries:

  BQ25892RTW  derived from the stock Battery_Management:BQ25895RTW by renaming
              pins 2, 3 and 24. All four of BQ25890/92/95/96 share the RTW
              WQFN-24 footprint and register map; only those three pins differ
              (bq25896.pdf p.5, bq25890.pdf Fig. 7-1 which shows both variants).
              Deriving rather than redrawing keeps the geometry exact.

  MAX17048    drawn from the datasheet pin table (max17048.pdf p.6).

Run once. After that r2.kicad_sym is edited in the KiCad symbol editor.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import _extract_symbol_block  # noqa: E402

SYMS = pathlib.Path(
    "/tmp/claude-1000/-home-lum-Ereader-Projekt-Glider-OG/"
    "24a17396-32d7-4c7d-976a-9df65f78dae8/scratchpad/syms"
)
OUT = HERE.parent / "r2.kicad_sym"

# pin number -> (new name, new electrical type)
# Pin 24 is NC on the BQ25892/96 but DSEL on the BQ25890/95. It is left
# `passive` rather than `no_connect` so the second-source option resistor can
# attach to it without tripping ERC.
BQ25892_RENAME = {
    "2":  ("PSEL", "input"),
    "3":  ("~{PG}", "open_collector"),
    "24": ("NC/DSEL", "passive"),
}


def _pin_blocks(text):
    """Yield (start, end) spans of each top-level (pin ...) block."""
    for m in re.finditer(r"\(pin ", text):
        i = m.start()
        depth, j, in_str = 0, i, False
        while j < len(text):
            c = text[j]
            if c == '"' and text[j - 1] != "\\":
                in_str = not in_str
            elif not in_str:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        yield (i, j + 1)
                        break
            j += 1


def make_bq25892():
    src = (SYMS / "BQ25895RTW.kicad_sym").read_text()
    block = _extract_symbol_block(src, "BQ25895RTW")
    assert block, "BQ25895RTW not found"

    out, last = [], 0
    for a, b in _pin_blocks(block):
        pin = block[a:b]
        num = re.search(r'\(number "([^"]+)"', pin)
        if num and num.group(1) in BQ25892_RENAME:
            name, etype = BQ25892_RENAME[num.group(1)]
            pin = re.sub(r'^\(pin \w+ ', f"(pin {etype} ", pin, count=1)
            pin = re.sub(r'\(name "[^"]*"', f'(name "{name}"', pin, count=1)
        out.append(block[last:a])
        out.append(pin)
        last = b
    out.append(block[last:])
    block = "".join(out)

    block = re.sub(r'^\(symbol\s+"BQ25895RTW"', '(symbol "BQ25892RTW"',
                   block, count=1)
    block = re.sub(r'\(symbol "BQ25895RTW_(\d+_\d+)"',
                   lambda m: f'(symbol "BQ25892RTW_{m.group(1)}"', block)
    block = re.sub(r'(\(property\s+"Value"\s+)"[^"]*"',
                   lambda m: m.group(1) + '"BQ25892RTW"', block, count=1)
    block = re.sub(r'(\(property\s+"Datasheet"\s+)"[^"]*"',
                   lambda m: m.group(1) + '"https://www.ti.com/lit/ds/symlink/bq25892.pdf"',
                   block, count=1)
    block = re.sub(
        r'(\(property\s+"Description"\s+)"[^"]*"',
        lambda m: m.group(1) + '"I2C battery charger with power path, 5A, 1-cell '
                  'Li-Ion, WQFN-24. Pin-compatible with BQ25890/95/96; pins 2, 3, '
                  '24 differ between variants."',
        block, count=1)
    return block


MAX17048 = '''(symbol "MAX17048"
\t(pin_names
\t\t(offset 1.016)
\t)
\t(exclude_from_sim no)
\t(in_bom yes)
\t(on_board yes)
\t(property "Reference" "U"
\t\t(at -7.62 12.7 0)
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t\t(justify left bottom)
\t\t)
\t)
\t(property "Value" "MAX17048"
\t\t(at -7.62 -13.97 0)
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t\t(justify left bottom)
\t\t)
\t)
\t(property "Footprint" "Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm"
\t\t(at 0 0 0)
\t\t(hide yes)
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t)
\t)
\t(property "Datasheet" "https://www.analog.com/media/en/technical-documentation/data-sheets/MAX17048-MAX17049.pdf"
\t\t(at 0 0 0)
\t\t(hide yes)
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t)
\t)
\t(property "Description" "1-cell ModelGauge fuel gauge, I2C addr 0x36, VDD 2.5-4.5 V, no sense resistor, TDFN-8"
\t\t(at 0 0 0)
\t\t(hide yes)
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t)
\t)
\t(property "ki_keywords" "fuel gauge battery monitor ModelGauge I2C"
\t\t(at 0 0 0)
\t\t(hide yes)
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t)
\t)
\t(symbol "MAX17048_0_1"
\t\t(rectangle
\t\t\t(start -7.62 10.16)
\t\t\t(end 7.62 -10.16)
\t\t\t(stroke
\t\t\t\t(width 0.254)
\t\t\t\t(type default)
\t\t\t)
\t\t\t(fill
\t\t\t\t(type background)
\t\t\t)
\t\t)
\t)
\t(symbol "MAX17048_1_1"
{PINS}\t)
)'''

# (number, name, x, y, rot, etype)  -- from max17048.pdf p.6 Pin/Bump Descriptions
MAX_PINS = [
    ("3", "VDD",      0.0,  12.7, 270, "power_in"),
    ("4", "GND",      0.0, -12.7,  90, "power_in"),
    ("2", "CELL",  -10.16,   5.08,  0, "passive"),
    ("1", "CTG",   -10.16,  -5.08,  0, "passive"),
    ("8", "SDA",    10.16,   5.08, 180, "bidirectional"),
    ("7", "SCL",    10.16,   2.54, 180, "input"),
    ("5", "~{ALRT}", 10.16, -2.54, 180, "open_collector"),
    ("6", "QSTRT",  10.16,  -5.08, 180, "input"),
    ("9", "EP",      0.0, -12.7,   90, "passive"),
]


def make_max17048():
    pins = []
    for num, name, x, y, rot, etype in MAX_PINS:
        pins.append(
            f"\t\t(pin {etype} line\n"
            f"\t\t\t(at {x} {y} {rot})\n"
            f"\t\t\t(length 2.54)\n"
            f'\t\t\t(name "{name}"\n\t\t\t\t(effects\n\t\t\t\t\t(font\n'
            f"\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)\n"
            f'\t\t\t(number "{num}"\n\t\t\t\t(effects\n\t\t\t\t\t(font\n'
            f"\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)\n"
            f"\t\t)\n"
        )
    return MAX17048.replace("{PINS}", "".join(pins))


def make_usblc6():
    """Flatten the stock USBLC6-2SC6 into this project's library.

    KiCad's copy is a derived symbol (`extends USBLC6-2P6`). A schematic that
    embeds the flattened form no longer byte-matches the stock library, which
    ERC reports as `lib_symbol_mismatch`. Owning the flattened symbol here
    makes the cache and the library agree.
    """
    from schgen import _flatten
    child = _extract_symbol_block(
        (SYMS / "USBLC6-2SC6.kicad_sym").read_text(), "USBLC6-2SC6")
    parent = _extract_symbol_block(
        (SYMS / "USBLC6-2P6.kicad_sym").read_text(), "USBLC6-2P6")
    return _flatten(parent, child, "USBLC6-2P6", "USBLC6-2SC6")


def main():
    blocks = [make_bq25892(), make_max17048(), make_usblc6()]
    body = "\n".join(
        "\n".join("\t" + ln if ln else "" for ln in b.splitlines()) for b in blocks
    )
    OUT.write_text(
        "(kicad_symbol_lib\n\t(version 20241209)\n"
        '\t(generator "schgen")\n\t(generator_version "10.0")\n'
        f"{body}\n)\n"
    )
    print(f"wrote {OUT} ({len(blocks)} symbols)")


if __name__ == "__main__":
    main()
