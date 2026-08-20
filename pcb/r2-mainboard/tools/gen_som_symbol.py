#!/usr/bin/env python3
"""Build the 240-pin `PCM-071` symbol into r2.kicad_sym, from the manual.

Input is `datasheets/som_pinout.json`, which `parse_som_pinout.py` extracts from
Tables 7-10 of `L-1038e.A5` and verifies (60 rows per column, every processor
ball well-formed, no ball claimed twice). Nothing here is typed from the PDF by
hand -- 240 pins is exactly the size where transcription puts two or three
silent errors into a part whose every pin is invisible to ERC.

**Units are by function, not by the manual's four columns.** The columns are a
physical division -- two Samtec `BTH-060` connectors, two columns each -- but
the DPI group alone spans columns A, B *and* D, so a column-shaped symbol could
not put the video pins on `dpi_in` and the rest on `som`. Same shape as the
FPGA's six units across three sheets.

    unit 1  POWER    VIN x3, VBAT, SoC_VDDSHV5_SDIO, 45 x GND        50   som
    unit 2  VIDEO    VOUT0_* plus D2/D4, which are GPMC pins the      22   dpi_in
                     module also drives as VOUT0_DATA16/17
    unit 3  CTRL     SPI0, UART0, MMC1, USB0, I2C, reset/status,      ~43  som
                     and the MCU/WKUP-domain groups that SOM_WAKE#
                     will have to come from
    unit 4  NC       everything R2 does not use                      ~125 som

**One symbol and one footprint, not two of each.** The two `BTH-060` patterns
have a fixed relative position set by the module. Drawing them as two
independent parts would let a layout move one relative to the other and destroy
the board with no DRC complaint; a single footprint carrying both patterns makes
that geometry unbreakable. The footprint itself is a Stage-D artifact and does
not exist yet -- the property names it so the link is ready.

Electrical types come from the manual's own Type column (`I`, `O`, `I/O`,
`OD-O`, `OD-I/O`, `A/I`, `PWR_I`, `PWR_IO`), with two deliberate departures
recorded in TYPE_MAP.

Run it again and it replaces the existing `PCM-071` block in place, so the
symbol stays regenerable while the rest of r2.kicad_sym is hand-edited.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent

def _find(name):
    """Locate a datasheet-derived file under datasheets/, at any depth."""
    direct = PROJ / "datasheets" / name
    if direct.exists():
        return direct
    for p in sorted((PROJ / "datasheets").rglob(name)):
        return p
    return direct  # keep the canonical path in the error message


PINOUT = _find("som_pinout.json")
OUT = PROJ / "r2.kicad_sym"
NAME = "PCM-071"

PITCH = 2.54
LEN = 5.08

# The manual's Type column -> KiCad electrical type.
#
# Two departures, both deliberate:
#   * `PWR_IO` on B1 is `power_out`. Table 12 is explicit that
#     SoC_VDDSHV5_SDIO *delivers* 0.33 W (100 mA) -- it is the module supplying
#     the SD I/O rail to us, not us supplying it. Typing it `power_in` would
#     make the microSD's supply look like a board rail and would need a
#     PWR_FLAG to silence ERC, which would then hide a genuinely undriven rail.
#   * `A/I` (USB VBUS sense, through a resistor/diode network on the module) is
#     `input` rather than `passive`, so ERC still notices if nothing drives it.
TYPE_MAP = {
    "PWR_I": "power_in",
    "PWR_IO": "power_out",
    "I": "input",
    "O": "output",
    "I/O": "bidirectional",
    "OD-O": "open_collector",
    "OD-I/O": "open_collector",
    "A/I": "input",
    "": "passive",
    "-": "power_in",          # every "-" row in Tables 7-10 is GND
}

UNIT_NAMES = {1: "POWER", 2: "VIDEO", 3: "CTRL", 4: "NC"}

# unit 2: the DPI link. VOUT0_DATA16/17 are named as GPMC/BOOTMODE pins in the
# pinout tables and only Table 31 reveals them as video, so they are listed
# explicitly rather than matched by name.
VIDEO_EXTRA = {"D2", "D4"}

# unit 3: what som.kicad_sch wires, plus the always-on groups SOM_WAKE# may have
# to come from. Prefixes are matched after stripping the leading `X_`.
CTRL_PREFIXES = (
    "SPI0_", "UART0_", "MMC1_", "USB0_", "I2C0_", "I2C1_",
    "MCU_UART0_", "WKUP_UART0_", "WKUP_I2C0_", "MCU_I2C0_", "MCU_SPI0_",
    # MCAN is in the MCU always-on domain and a reader can never want CAN, so
    # this is where SOM_WAKE#/SOM_IRQ# land -- A58 = MCU_GPIO0_14 and
    # A57 = MCU_GPIO0_13. Keeping all four on the wired unit means the two
    # spares are visible if the chosen pin turns out not to wake DeepSleep.
    "MCU_MCAN0_", "MCU_MCAN1_",
)
CTRL_EXACT = {
    "X_PMIC_EN", "X_nRESET_IN", "X_PGOOD", "X_PORz_OUT", "X_RESETSTATz",
    "X_RESET_REQz", "X_MCU_RESETz", "X_MCU_RESETSTATz",
}


def key(pin: str) -> tuple[str, int]:
    return (pin[0], int(pin[1:]))


def assign_units(pins: dict) -> dict[str, int]:
    unit = {}
    for pin, row in pins.items():
        name = row["name"]
        bare = name[2:] if name.startswith("X_") else name
        if name in ("GND", "VIN", "VBAT") or name.startswith("SoC_"):
            unit[pin] = 1
        elif bare.startswith("VOUT") or pin in VIDEO_EXTRA:
            unit[pin] = 2
        elif name in CTRL_EXACT or bare.startswith(CTRL_PREFIXES):
            unit[pin] = 3
        else:
            unit[pin] = 4
    return unit


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def pin_block(etype: str, x: float, y: float, rot: int, name: str, number: str,
              hide: bool = False) -> str:
    return (
        f"\t\t\t(pin {etype} line\n"
        f"\t\t\t\t(at {x:g} {y:g} {rot})\n"
        f"\t\t\t\t(length {LEN:g})\n"
        + ("\t\t\t\t(hide yes)\n" if hide else "")
        + f'\t\t\t\t(name "{esc(name)}"\n'
        "\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n"
        "\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n"
        f'\t\t\t\t(number "{esc(number)}"\n'
        "\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n"
        "\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)\n"
    )


def unit_block(n: int, left: list, right: list, pins: dict, width: float) -> str:
    """One `(symbol "NAME_n_1" ...)` with a body rectangle and its pins."""
    rows = max(len(left), len(right))
    half_h = (rows - 1) * PITCH / 2 + PITCH
    half_w = width / 2
    out = [f'\t\t(symbol "{NAME}_{n}_1"\n'
           "\t\t\t(rectangle\n"
           f"\t\t\t\t(start {-half_w:g} {half_h:g})\n"
           f"\t\t\t\t(end {half_w:g} {-half_h:g})\n"
           "\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n"
           "\t\t\t\t)\n\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n"
           "\t\t\t)\n"]
    top = (rows - 1) * PITCH / 2
    for i, pin in enumerate(left):
        r = pins[pin]
        out.append(pin_block(TYPE_MAP[r["type"]], -half_w - LEN, top - i * PITCH,
                             0, r["name"], pin))
    for i, pin in enumerate(right):
        r = pins[pin]
        out.append(pin_block(TYPE_MAP[r["type"]], half_w + LEN, top - i * PITCH,
                             180, r["name"], pin))
    out.append("\t\t)\n")
    return "".join(out)


def build(pins: dict) -> str:
    unit = assign_units(pins)
    by_unit: dict[int, list[str]] = {}
    for pin, u in unit.items():
        by_unit.setdefault(u, []).append(pin)
    for u in by_unit:
        by_unit[u].sort(key=key)

    hdr = [
        f'\t(symbol "{NAME}"\n',
        "\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)\n",
        "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n",
    ]
    props = [
        ("Reference", "X", False),
        ("Value", NAME, False),
        ("Footprint", "r2:PCM-071_2xBTH-060-01-L-D-A-K", True),
        ("Datasheet", "L-1038e.A5_phyCORE-AM62x_HW Manual.pdf", True),
        ("Description",
         "PHYTEC phyCORE-AM62x SOM, connectorised. 240 pins on X1 columns A-D "
         "over two Samtec BTH-060-01-L-D-A-K-TR. Generated by "
         "tools/gen_som_symbol.py from datasheets/som_pinout.json.", True),
        ("ki_keywords", "SOM module AM62x phyCORE PHYTEC ARM Cortex-A53", True),
    ]
    for i, (k, v, hide) in enumerate(props):
        y = 6.35 if i == 0 else (-6.35 if i == 1 else 0)
        hdr.append(f'\t\t(property "{k}" "{esc(v)}"\n\t\t\t(at 0 {y:g} 0)\n'
                   + ("\t\t\t(hide yes)\n" if hide else "")
                   + "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                     "\t\t\t\t)\n\t\t\t)\n\t\t)\n")

    body = []
    for u in sorted(by_unit):
        ps = by_unit[u]
        if u == 1:
            # supplies left, the 45 grounds right
            left = [p for p in ps if pins[p]["name"] != "GND"]
            right = [p for p in ps if pins[p]["name"] == "GND"]
            width = 45.72
        elif u == 2:
            # every DPI signal leaves the module, so one right-hand column --
            # dpi_in then reads as 22 pins fanning into 22 labels, with no
            # traffic on the left of the page.
            left, right = [], ps
            width = 50.8
        else:
            half = (len(ps) + 1) // 2
            left, right = ps[:half], ps[half:]
            width = 60.96
        body.append(unit_block(u, left, right, pins, width))

    return "".join(hdr) + "".join(body) + "\t)\n"


def splice(text: str, block: str) -> str:
    """Replace an existing PCM-071 block, or append before the closing paren."""
    m = re.search(r'\n\t\(symbol "%s"\n' % re.escape(NAME), text)
    if m:
        s = m.start() + 1
        depth, j, ins = 0, s, False
        while True:
            c = text[j]
            if c == '"' and text[j - 1] != "\\":
                ins = not ins
            elif not ins:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        return text[:s] + block + text[j + 2:]
    assert text.rstrip().endswith(")")
    i = text.rstrip().rfind(")")
    return text[:i] + block + ")\n"


def main() -> int:
    pins = json.loads(PINOUT.read_text())
    assert len(pins) == 240, f"expected 240 pins, som_pinout.json has {len(pins)}"
    unknown = sorted({r["type"] for r in pins.values()} - set(TYPE_MAP))
    assert not unknown, f"no KiCad type mapped for manual types {unknown}"

    block = build(pins)
    OUT.write_text(splice(OUT.read_text(), block))

    # report, and assert the symbol really carries all 240 numbers exactly once
    got = re.findall(r'\(number "([^"]+)"', block)
    assert sorted(got, key=key) == sorted(pins, key=key), \
        f"symbol has {len(got)} pin numbers for {len(pins)} pins"
    unit = assign_units(pins)
    print(f"{NAME}: {len(got)} pins, all 240 present exactly once")
    for u in sorted(UNIT_NAMES):
        members = [p for p, v in unit.items() if v == u]
        print(f"  unit {u} {UNIT_NAMES[u]:6s} {len(members):3d} pins")
    from collections import Counter
    c = Counter(TYPE_MAP[r["type"]] for r in pins.values())
    print("  electrical types: "
          + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
