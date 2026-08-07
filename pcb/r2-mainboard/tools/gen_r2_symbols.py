#!/usr/bin/env python3
"""Generate pcb/r2-mainboard/r2.kicad_sym — the project's own symbols.

Two symbols are not in KiCad's standard libraries:

  BQ25892RTW  derived from the stock Battery_Management:BQ25895RTW by renaming
              pins 2, 3 and 24. All four of BQ25890/92/95/96 share the RTW
              WQFN-24 footprint and register map; only those three pins differ
              (bq25896.pdf p.5, bq25890.pdf Fig. 7-1 which shows both variants).
              Deriving rather than redrawing keeps the geometry exact.

  MAX17048    drawn from the datasheet pin table (max17048.pdf p.6).

  TPS7A0233DBV, TPS22965DSG, TPS63802DLA, TPS62A02DRL
              the power sheet's regulators, drawn from their datasheet pin
              tables. TPS61022 is *not* here -- KiCad's Converter_DCDC has it
              already, with the correct RWU0007A footprint.

  SY8120, MT9700
              lifted verbatim from R1's epd_power.kicad_sch embedded
              lib_symbols. Both are used by R1 but neither is in pcb_common at
              the pinned commit, so in R1 they survive only as definitions
              embedded in the sheet -- the library link is dead there. Lifting
              them into r2.kicad_sym gives R2 a live link to a version-
              controlled copy. Note SY8120 is the *symbol* R1 reuses for the
              LGS5145; the value on each instance is what names the real part.

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


# --------------------------------------------------------------------------
# Power-sheet regulators. KiCad 10 ships none of these except TPS61022, which
# the power sheet uses straight from Converter_DCDC. Every pin number, name and
# electrical type below is read off the datasheet's Pin Functions table; the
# page is cited per part.
# --------------------------------------------------------------------------

IC_TEMPLATE = '''(symbol "{name}"
\t(pin_names
\t\t(offset 1.016)
\t)
\t(exclude_from_sim no)
\t(in_bom yes)
\t(on_board yes)
{props}\t(symbol "{name}_0_1"
\t\t(rectangle
\t\t\t(start {bx0} {by0})
\t\t\t(end {bx1} {by1})
\t\t\t(stroke
\t\t\t\t(width 0.254)
\t\t\t\t(type default)
\t\t\t)
\t\t\t(fill
\t\t\t\t(type background)
\t\t\t)
\t\t)
\t)
\t(symbol "{name}_1_1"
{pins}\t)
)'''


def _prop(name, value, x, y, hide=True, justify=None):
    h = "\n\t\t(hide yes)" if hide else ""
    j = f"\n\t\t\t(justify {justify})" if justify else ""
    return (f'\t(property "{name}" "{value}"\n'
            f"\t\t(at {x} {y} 0){h}\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)"
            f"{j}\n\t\t)\n\t)\n")


def make_ic(name, footprint, datasheet, description, keywords, box, pins,
            ref_at, val_at):
    """Build a plain rectangular IC symbol from a pin table."""
    bx0, by0, bx1, by1 = box
    props = (
        _prop("Reference", "U", ref_at[0], ref_at[1], hide=False,
              justify="left bottom")
        + _prop("Value", name, val_at[0], val_at[1], hide=False,
                justify="left bottom")
        + _prop("Footprint", footprint, 0, 0)
        + _prop("Datasheet", datasheet, 0, 0)
        + _prop("Description", description, 0, 0)
        + _prop("ki_keywords", keywords, 0, 0)
    )
    body = []
    for num, pname, x, y, rot, etype in pins:
        body.append(
            f"\t\t(pin {etype} line\n"
            f"\t\t\t(at {x} {y} {rot})\n"
            f"\t\t\t(length 2.54)\n"
            f'\t\t\t(name "{pname}"\n\t\t\t\t(effects\n\t\t\t\t\t(font\n'
            f"\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)\n"
            f'\t\t\t(number "{num}"\n\t\t\t\t(effects\n\t\t\t\t\t(font\n'
            f"\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)\n"
            f"\t\t)\n"
        )
    return IC_TEMPLATE.format(name=name, props=props, pins="".join(body),
                              bx0=bx0, by0=by0, bx1=bx1, by1=by1)


# tps7a02.pdf p.3 Table 5-1 (DBV column). NC is pin 4 and is genuinely
# unbonded, so it is `no_connect` — ERC then insists on a no-connect flag.
TPS7A0233 = dict(
    name="TPS7A0233DBV",
    footprint="Package_TO_SOT_SMD:SOT-23-5",
    datasheet="https://www.ti.com/lit/ds/symlink/tps7a02.pdf",
    description="200mA LDO, 25nA quiescent, fixed 3.3V, SOT-23-5",
    keywords="LDO regulator low quiescent nanopower",
    box=(-7.62, 5.08, 7.62, -5.08),
    ref_at=(-7.62, 7.62), val_at=(-7.62, -7.62),
    pins=[
        ("1", "IN",  -10.16,  2.54,   0, "power_in"),
        ("3", "EN",  -10.16, -2.54,   0, "input"),
        ("5", "OUT",  10.16,  2.54, 180, "power_out"),
        ("4", "NC",   10.16, -2.54, 180, "no_connect"),
        ("2", "GND",   0.0,  -7.62,  90, "power_in"),
    ],
)

# tps22965.pdf p.4 Pin Functions. VIN is pins 1+2 and VOUT is pins 7+8 -- the
# datasheet requires both halves be connected. Pad 9 is the thermal pad, which
# the KiCad footprint numbers, so it needs a pin here or it stays unrouted.
# Only one half of each doubled pin carries its real electrical type: two pins
# typed power_output wired together is an ERC error, so pins 2 and 8 are
# passive. Same net, same silicon, no loss of checking.
TPS22965 = dict(
    name="TPS22965DSG",
    footprint="Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm",
    datasheet="https://www.ti.com/lit/ds/symlink/tps22965.pdf",
    description="5.5V 6A load switch, 16mOhm, adjustable slew rate, WSON-8",
    keywords="load switch power distribution",
    box=(-10.16, 7.62, 10.16, -7.62),
    ref_at=(-10.16, 10.16), val_at=(-10.16, -10.16),
    pins=[
        ("1", "VIN",   -12.7,   5.08,   0, "power_in"),
        ("2", "VIN",   -12.7,   2.54,   0, "passive"),
        ("4", "VBIAS", -12.7,  -2.54,   0, "power_in"),
        ("3", "ON",    -12.7,  -5.08,   0, "input"),
        ("7", "VOUT",   12.7,   5.08, 180, "power_out"),
        ("8", "VOUT",   12.7,   2.54, 180, "passive"),
        ("6", "CT",     12.7,  -5.08, 180, "passive"),
        ("5", "GND",    -2.54, -10.16, 90, "power_in"),
        ("9", "EP",      2.54, -10.16, 90, "passive"),
    ],
)

# tps63802.pdf p.4 Table 7-1. VSON-HR has no exposed pad -- the KiCad
# VSON-HR-8 footprint confirms the family numbers no ninth pad.
TPS63802 = dict(
    name="TPS63802DLA",
    footprint="r2:Texas_DLA0010A_VSON-HR-10_2x3mm_P0.5mm",
    datasheet="https://www.ti.com/lit/ds/symlink/tps63802.pdf",
    description="2A buck-boost, 1.3-5.5V in, 1.8-5.2V out, 11uA Iq, "
                "true shutdown with load disconnect, VSON-HR-10",
    keywords="buck boost converter regulator",
    box=(-10.16, 10.16, 10.16, -10.16),
    ref_at=(-10.16, 12.7), val_at=(-10.16, -12.7),
    # L1/L2 sit on top, 7.62 mm apart, so the inductor drops straight across
    # them with two vertical wires and no jogs.
    pins=[
        ("10", "VIN",  -12.7,   5.08,   0, "power_in"),
        ("1",  "EN",   -12.7,  -2.54,   0, "input"),
        ("2",  "MODE", -12.7,  -5.08,   0, "input"),
        ("9",  "L1",    -3.81, 12.7,  270, "passive"),
        ("7",  "L2",     3.81, 12.7,  270, "passive"),
        ("6",  "VOUT",  12.7,   5.08, 180, "power_out"),
        ("4",  "FB",    12.7,  -2.54, 180, "input"),
        ("5",  "PG",    12.7,  -5.08, 180, "open_collector"),
        ("8",  "GND",   -2.54, -12.7,  90, "power_in"),
        ("3",  "AGND",   2.54, -12.7,  90, "power_in"),
    ],
)

# tps62a01.pdf p.4 Table 5-1, SOT563-6 (DRL) column. Used for both the 1.2 V
# and the 1.35 V rail; the 2 A part is TPS62A02, same pinout as TPS62A01.
TPS62A02 = dict(
    name="TPS62A02DRL",
    footprint="Package_TO_SOT_SMD:SOT-563",
    datasheet="https://www.ti.com/lit/ds/symlink/tps62a01.pdf",
    description="2A synchronous buck, 2.5-5.5V in, 0.6V ref, power save mode, "
                "power good, SOT-563",
    keywords="buck step-down converter regulator",
    box=(-7.62, 5.08, 7.62, -5.08),
    ref_at=(-7.62, 7.62), val_at=(-7.62, -7.62),
    pins=[
        ("3", "VIN", -10.16,  2.54,   0, "power_in"),
        ("4", "EN",  -10.16,  0.0,    0, "input"),
        ("2", "SW",   10.16,  2.54, 180, "output"),
        ("5", "FB",   10.16,  0.0,  180, "input"),
        ("6", "PG",   10.16, -2.54, 180, "open_collector"),
        ("1", "GND",   0.0,  -7.62,  90, "power_in"),
    ],
)


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



R1_EPD_POWER = pathlib.Path(__file__).resolve().parents[2] / "mainboard" / "epd_power.kicad_sch"


def lift_from_r1(name: str) -> str:
    """Copy a symbol definition verbatim out of R1's embedded lib_symbols.

    R1 is read-only: this only ever reads it. The block comes back with one
    extra level of indentation (it lives inside `lib_symbols`), so strip it.
    """
    text = R1_EPD_POWER.read_text()
    lib = text[text.index("(lib_symbols"):]
    # entries inside lib_symbols are keyed by full lib_id, and the sub-units
    # by "<lib_id>_0_1" etc.; strip the library prefix everywhere so the
    # symbol stands alone in r2.kicad_sym.
    block = _extract_symbol_block(lib, f"symbols:{name}")
    if block is None:
        raise KeyError(f"{name!r} not found in {R1_EPD_POWER}")
    block = block.replace(f'"symbols:{name}', f'"{name}')
    lines = [ln[1:] if ln.startswith("\t") else ln for ln in block.splitlines()]
    return "\n".join(lines)


def main():
    blocks = [make_bq25892(), make_max17048(), make_usblc6()]
    blocks += [lift_from_r1(n) for n in ("SY8120", "MT9700")]
    for spec in (TPS7A0233, TPS22965, TPS63802, TPS62A02):
        spec = dict(spec)
        blocks.append(make_ic(spec.pop("name"), **spec))
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
