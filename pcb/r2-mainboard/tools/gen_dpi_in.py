#!/usr/bin/env python3
"""Generate dpi_in.kicad_sch — R2 work package 7.

Implements docs/som.md §2. One part: unit 2 of the `PCM-071`, the module's
parallel RGB output, fanning 22 pins into the 22 hierarchical labels `fpga_io`
has been exporting since WP5. This sheet closes the largest block of dangling
root nets in the project.

**The bit mapping is the whole content of this sheet, and it is the one thing
worth checking twice**, because getting it wrong produces a board that works
perfectly and shows wrong colours -- or, since Glider converts RGB to greyscale,
subtly wrong grey levels that look like a dithering bug.

    AM62x TRM Fig. 12-471, 18-bit mode:  data[17:12]=red  [11:6]=green  [5:0]=blue
    Caster constraint.ucf comments:      DPI_PIXEL[0]=B2 ... [5]=B7
                                         DPI_PIXEL[6]=G2 ... [11]=G7
                                         DPI_PIXEL[12]=R2 ... [17]=R7

Both ends therefore agree that `VOUT0_DATA<n>` is Caster's `DPI_PIXEL[n]`, and
the channel/bit is a pure function of n:

    channel = "BGR"[n // 6]        bit = 2 + n % 6

The `2 +` is not arbitrary: RGB666 keeps the top six bits of each 8-bit channel,
so the least significant surviving bit is bit 2. That is what the UCF's comment
column names and what the DSS presents.

`X1 D2` and `D4` are the exception to "read the name": in Tables 7-10 they are
`X_GPMC0_AD8/BOOTMODE_8` and `X_GPMC0_AD9/BOOTMODE_9`, and only Table 31 reveals
that the module also drives them as `VOUT0_DATA16`/`DATA17`. They are asserted
by pin number below, and `check_pinout.py` will re-assert it against the
manual's own JSON.

Nothing on this sheet may load `DPI_R6`/`DPI_R7` -- they are the module's boot
straps (docs/som.md §2). There are no components here at all, which is the
easiest way to satisfy that, and a note on the sheet says why so a later
reviewer does not add the "missing" termination.

Run once. After the sheet has been opened and saved in Eeschema it is edited in
place, not regenerated.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402
from sheet_pins import set_sheet_pins  # noqa: E402
from gen_som import CONN, MPN, LCSC  # noqa: E402

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
KICAD_CLI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/bin/kicad-cli"

# Both must be multiples of the 1.27 mm grid, or every pin on the part lands
# off-grid and ERC reports 22 `endpoint_off_grid` warnings. 130.0 was the
# first choice and was wrong by 0.36 mm; schgen.check_grid() now catches it.
UX, UY = 127.0, 130.81     # J26's unit 2 origin (100 x 1.27, 103 x 1.27)
# J27's unit 2 is two pins, so it goes above rather than below -- the note block
# starts at UY + 40.64 and a box under J26 would sit in it.
BOX_Y = {"J26": UY, "J27": 62.23}
LABEL_X = 190.5            # the hierarchical-label column
CHANNEL = "BGR"            # data[5:0] blue, [11:6] green, [17:12] red

# The four sync/clock signals, by X1 pin. Named from the SOM's side in the
# manual and from Caster's side in the UCF; both are recorded so the rename is
# visible rather than implied.
SYNC = {
    "A7":  ("X_VOUT0_PCLK",  "DPI_PCLK"),
    "A15": ("X_VOUT0_DE",    "DPI_DE"),
    "A6":  ("X_VOUT0_HSYNC", "DPI_HS"),
    "A5":  ("X_VOUT0_VSYNC", "DPI_VS"),
}
# The two data bits the pinout tables do not call video (docs/som.md §2).
BOOTMODE_PINS = {"D2": 16, "D4": 17}

NOTE = [
    "dpi_in -- the SoM's 18-bit RGB666 output into Caster. 22 signals, no parts.",
    "",
    "Bit mapping, from AM62x TRM Fig. 12-471 and Caster constraint.ucf:",
    "  VOUT0_DATA<n> = DPI_PIXEL[n];  channel = BGR[n/6], bit = 2 + n%6.",
    "  RGB666 keeps the top six bits of each channel, so bit 2 is the LSB.",
    "",
    "X1 D2/D4 are named X_GPMC0_AD8/AD9 in the pinout tables. Table 31 is what",
    "shows the module also drives them as VOUT0_DATA16/DATA17.",
    "",
    "*** D2 and D4 are also BOOTMODE_8 and BOOTMODE_9, the primary boot mode",
    "*** selection, strapped high by 100K on the module. Nothing on this board",
    "*** may load DPI_R6 or DPI_R7 -- no pull-up, pull-down or termination.",
    "*** The absence of components here is deliberate. See docs/som.md 2.",
]


def dpi_name(n: int) -> str:
    return f"DPI_{CHANNEL[n // 6]}{2 + n % 6}"


def pin_map(pins: dict) -> list[tuple[str, str, str]]:
    """-> [(x1_pin, som_signal, r2_net)] in the symbol's own pin order."""
    out = []
    for x1, row in pins.items():
        name = row["name"]
        if x1 in SYNC:
            out.append((x1, *SYNC[x1]))
        elif x1 in BOOTMODE_PINS:
            out.append((x1, name, dpi_name(BOOTMODE_PINS[x1])))
        elif name.startswith("X_VOUT0_DATA"):
            out.append((x1, name, dpi_name(int(name[len("X_VOUT0_DATA"):]))))
    return sorted(out, key=lambda r: (r[0][0], int(r[0][1:])))


def verify(rows: list, pins: dict) -> None:
    nets = [r[2] for r in rows]
    want = {f"DPI_{c}{b}" for c in "RGB" for b in range(2, 8)} | set(
        v for _, v in SYNC.values())
    assert len(rows) == 22, f"{len(rows)} DPI pins, expected 22"
    assert set(nets) == want, f"net set mismatch: {sorted(set(nets) ^ want)}"
    assert len(set(nets)) == 22, "a net name is used twice"
    # every claimed pin really is that pin in the manual's own table
    for x1, som, _ in rows:
        assert pins[x1]["name"] == som, \
            f"{x1}: symbol says {som!r}, manual says {pins[x1]['name']!r}"
    # the two strap pins land on the two red MSBs, not anywhere else
    assert dict((r[0], r[2]) for r in rows if r[0] in BOOTMODE_PINS) == \
        {"D2": "DPI_R6", "D4": "DPI_R7"}, "BOOTMODE pins are not R6/R7"


def build(rows: list) -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    sh = Sheet(
        sheets["dpi_in"], root_uuid, "r2", paper="A3",
        title="Glider-R2 / Reflow mainboard",
        rev="A", date="2026-08-15",
        comments=(
            "dpi_in — J26/J27 unit 2: 18-bit RGB666 parallel video into Caster",
            "See docs/som.md §2. Pin numbers from datasheets/som_pinout.json.",
        ),
        pwr_base=700,
    )
    sh.lib.add_file("r2", PROJ / "r2.kicad_sym")

    # Two boxes, because the DPI group straddles both connectors: 20 of its 22
    # signals are on the module's A/B columns and two -- D2 and D4, the GPMC
    # pins Table 31 reveals as VOUT0_DATA16/17 -- are on C/D. A two-pin box
    # looks odd and is honest; those pins really are on the other receptacle.
    # Unit 2 is one right-hand column, so its box height follows directly from
    # how many of the 22 signals this connector carries. A fixed ref_at offset
    # put J27B's designator off the top of the frame, since its box is two pins
    # tall against J26B's twenty.
    def half_height(ref: str) -> float:
        n = sum(1 for r in rows if (r[0][0] in "AB") == (ref == "J26"))
        return (n - 1) * 2.54 / 2 + 2.54

    units = {}
    for ref, (lib, rows_, fp, what) in CONN.items():
        x, y = UX, BOX_Y[ref]
        hh = half_height(ref)
        units[ref] = sh.place(
            lib, ref, MPN, x, y, 0, unit=2, footprint=fp,
            extra={"LCSC": LCSC, "MPN": MPN, "Manufacturer": "Samtec"},
            ref_at=(x - 27.94, y - hh - 5.08), val_at=(x - 27.94, y - hh - 2.54),
            justify="left",
            description=f"Samtec {MPN} carrying {what} of the PCM-071. Unit 2 of 4: "
                        f"VOUT0 parallel video. Units 1/3/4 are on som.kicad_sch.")

    for x1, _som, net in rows:
        ref = "J26" if x1[0] in "AB" else "J27"
        px, py = units[ref].pin(x1)
        sh.wire((px, py), (LABEL_X, py))
        sh.hlabel(LABEL_X, py, net, shape="output")

    y = UY + 40.64
    for line in NOTE:
        sh.text(63.5, y, line, 1.27)
        y += 3.81
    assert y <= 265.0, f"the note block ends at y={y:.1f}, into the title block"
    return sh.render()


def main() -> int:
    pins = json.loads(PINOUT.read_text())
    rows = pin_map(pins)
    verify(rows, pins)

    out = PROJ / "dpi_in.kicad_sch"
    out.write_text(build(rows))
    subprocess.run([str(KICAD_CLI), "sch", "upgrade", str(out)],
                   check=True, capture_output=True)
    set_sheet_pins(PROJ / "r2.kicad_sch", "dpi_in",
                   sorted((r[2], "output") for r in rows))

    n26 = sum(1 for r in rows if r[0][0] in "AB")
    print(f"wrote {out.name}: 22 DPI signals, {n26} on J26 and {22 - n26} on J27, "
          f"0 components")
    for x1, som, net in rows:
        print(f"  {x1:4s} {som:26s} -> {net}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
