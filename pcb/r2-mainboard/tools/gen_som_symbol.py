#!/usr/bin/env python3
"""Build the two 120-pin `BTH-060` connector symbols into r2.kicad_sym.

Input is `datasheets/som_pinout.json`, which `parse_som_pinout.py` extracts from
Tables 7-10 of `L-1038e.A5` and verifies (60 rows per column, every processor
ball well-formed, no ball claimed twice). Nothing here is typed from the PDF by
hand -- 240 pins is exactly the size where transcription puts two or three
silent errors into a part whose every pin is invisible to ERC.

**One symbol per physical connector, chosen by the owner 2026-08-20.** Earlier
revisions built a single 240-pin `PCM-071` symbol on a single footprint carrying
both land patterns. That was defensible -- it made the two connectors'
22.400 mm spacing and 4.800 mm stagger structurally unbreakable -- but it does
not say what the board is, and it left the receptacles with no BOM line and no
position-file row, so an assembled board would have come back with 240 bare
pads. `docs/som.md` §10 has the whole story. The board has two connectors, so
the schematic now has two symbols:

    BTH-060_AB   rows A + B   module connector at x = 4.800   J26
    BTH-060_CD   rows C + D   module connector at x = 27.200  J27

**This is a repartition, not a renumber, and that is what makes it safe.** Pin
numbers stay `A1`-`A60` / `B1`-`B60` / `C1`-`C60` / `D1`-`D60`, exactly as
`L-1038e.A5` Tables 7-10 print them -- *not* Samtec's `1`-`120` alternating
numbering. Names, electrical types and unit assignment are untouched. Only which
symbol a pin belongs to changes, so there is no mapping table anywhere and
nothing to get wrong. The matching footprints name their pads the same way.

**Units stay by function, not by the manual's columns**, because the DPI group
spans columns A, B *and* D -- so it straddles both connectors and a
column-shaped unit could not put the video pins on `dpi_in` and the rest on
`som`. Each symbol therefore carries the same four units over its own 120 pins:

                    POWER  VIDEO  CTRL   NC   total   sheets
    BTH-060_AB  J26    30     20    12    58     120   som (1,3,4) + dpi_in (2)
    BTH-060_CD  J27    20      2    41    57     120   som (1,3,4) + dpi_in (2)

`J27`'s VIDEO unit is two pins -- `D2`/`D4`, the GPMC pins that Table 31 reveals
as `VOUT0_DATA16/17`. A two-pin box on `dpi_in` looks odd and is honest: those
pins really are on the other connector.

The `PCM-071` module itself is no longer a symbol with pins. It survives as
`X2`, a mechanical footprint (outline plus the two M2.5 holes, no pads) and a
BOM line -- `gen_som.py` places it, `gen_som_footprint.py` draws it.

Electrical types come from the manual's own Type column (`I`, `O`, `I/O`,
`OD-O`, `OD-I/O`, `A/I`, `PWR_I`, `PWR_IO`), with two deliberate departures
recorded in TYPE_MAP.

Run it again and it replaces the existing blocks in place, so the symbols stay
regenerable while the rest of r2.kicad_sym is hand-edited.
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
# One symbol per physical connector. The value is the same Samtec part for
# both; the symbol name records which of the module's four columns it carries.
CONNECTORS = {
    "BTH-060_AB": ("AB", "r2:BTH-060-01-L-D-A-K_AB",
                   "rows A and B, the connector at module x = 4.800"),
    "BTH-060_CD": ("CD", "r2:BTH-060-01-L-D-A-K_CD",
                   "rows C and D, the connector at module x = 27.200"),
}
MPN = "BTH-060-01-L-D-A-K-TR"

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


def unit_block(n: int, left: list, right: list, pins: dict, width: float,
               name: str) -> str:
    """One `(symbol "<name>_n_1" ...)` with a body rectangle and its pins."""
    rows = max(len(left), len(right))
    half_h = (rows - 1) * PITCH / 2 + PITCH
    half_w = width / 2
    out = [f'\t\t(symbol "{name}_{n}_1"\n'
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


def build(pins: dict, name: str, rows: str, footprint: str, what: str) -> str:
    """One connector symbol, over just the pins in `rows` (e.g. "AB")."""
    mine = {p: r for p, r in pins.items() if p[0] in rows}
    assert len(mine) == 120, f"{name} got {len(mine)} pins, expected 120"

    unit = assign_units(pins)          # assigned over all 240, then filtered,
    by_unit: dict[int, list[str]] = {}  # so a pin's unit never depends on which
    for pin in mine:                   # symbol it landed in
        by_unit.setdefault(unit[pin], []).append(pin)
    for u in by_unit:
        by_unit[u].sort(key=key)

    hdr = [
        f'\t(symbol "{name}"\n',
        "\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)\n",
        "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n",
    ]
    props = [
        ("Reference", "J", False),
        ("Value", MPN, False),
        ("Footprint", footprint, True),
        ("Datasheet", "L-1038e.A5_phyCORE-AM62x_HW Manual.pdf", True),
        ("Description",
         f"Samtec BTH-060-01-L-D-A-K-TR, 2x60 0.5 mm board-to-board receptacle. "
         f"Carries {what} of the PHYTEC phyCORE-AM62x PCM-071. Pin numbers are the "
         f"module's own (L-1038e.A5 Tables 7-10), not Samtec's 1-120. Two of these "
         f"take the module; X2 is its outline and mounting holes. Generated by "
         f"tools/gen_som_symbol.py from datasheets/som_pinout.json.", True),
        ("ki_keywords",
         "Samtec BTH-060 board-to-board mezzanine SOM AM62x phyCORE PCM-071", True),
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
            # supplies left, the grounds right
            left = [p for p in ps if pins[p]["name"] != "GND"]
            right = [p for p in ps if pins[p]["name"] == "GND"]
            width = 45.72
        elif u == 2:
            # every DPI signal leaves the module, so one right-hand column --
            # dpi_in then reads as pins fanning into labels, with no traffic on
            # the left of the page.
            left, right = [], ps
            width = 50.8
        else:
            half = (len(ps) + 1) // 2
            left, right = ps[:half], ps[half:]
            width = 60.96
        body.append(unit_block(u, left, right, pins, width, name))

    return "".join(hdr) + "".join(body) + "\t)\n"


def splice(text: str, block: str, name: str) -> str:
    """Replace an existing block of this name, or append before the closing paren."""
    m = re.search(r'\n\t\(symbol "%s"\n' % re.escape(name), text)
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

    unit = assign_units(pins)
    text = OUT.read_text()
    seen: list[str] = []

    for name, (rows, footprint, what) in CONNECTORS.items():
        block = build(pins, name, rows, footprint, what)
        text = splice(text, block, name)

        got = re.findall(r'\(number "([^"]+)"', block)
        mine = sorted((p for p in pins if p[0] in rows), key=key)
        assert sorted(got, key=key) == mine, \
            f"{name} has {len(got)} pin numbers for {len(mine)} pins"
        seen += got

        print(f"{name}: {len(got)} pins, rows {rows[0]} + {rows[1]}")
        for u in sorted(UNIT_NAMES):
            n = sum(1 for p in got if unit[p] == u)
            print(f"  unit {u} {UNIT_NAMES[u]:6s} {n:3d} pins")

    # The whole point of the split: between them the two symbols carry every
    # module pin exactly once. A pin lost here is a pin that silently stops
    # existing, and ERC cannot see it.
    assert sorted(seen, key=key) == sorted(pins, key=key), \
        f"the two symbols carry {len(seen)} pins for {len(pins)} module pins"

    # And nothing may have drifted between the symbols and the pinout table.
    for pin in pins:
        assert pin[0] in "ABCD", f"pin {pin} is in no column"

    OUT.write_text(text)
    print(f"\nboth symbols carry all {len(pins)} pins exactly once, "
          f"numbered as L-1038e.A5 prints them")
    from collections import Counter
    c = Counter(TYPE_MAP[r["type"]] for r in pins.values())
    print("electrical types: "
          + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
