#!/usr/bin/env python3
"""Give the two `BTH-060` receptacles and the mounting hardware a BOM line.

`som.md` §10 found the gap: **`X2` is one symbol for the *module*.** The parts a
PCBA house actually solders to `r2:PCM-071_2xBTH-060-01-L-D-A-K` are two Samtec
`BTH-060-01-L-D-A-K-TR` receptacles, and no symbol in the project generates that
line. A BOM built from this schematic orders the module and arrives with 240
empty pads.

**The one-symbol-one-footprint decision is right and is not what is being
changed here.** `gen_som_symbol.py` states it: the two `BTH-060` patterns have a
fixed relative position set by the module, so *"drawing them as two independent
parts would let a layout move one relative to the other and destroy the board
with no DRC complaint."* That argument still holds -- and PHYTEC's DXF has since
made the cost concrete, because the two connectors are staggered 4.800 mm as
well as spaced 22.400 mm, which is exactly the sort of relationship a human
moves by accident. Two footprints would also have to be remapped pin by pin:
Samtec numbers its pads **1-120 alternating between rows**, while the module's
pinout is A1-A60 / B1-B60 / C1-C60 / D1-D60, so "just use the vendor footprint"
is a 240-line renumbering with no ERC to catch a slip.

So the footprint stays as it is, and the missing BOM lines are added as symbols
that are **`on_board no`** -- present on the schematic and on the order, absent
from the netlist and the PCB. That is the ordinary KiCad way to carry a
purchase-only item, and it is the same mechanism used for screws and standoffs.
`BOM_ITEM` in `r2.kicad_sym` is a pin-less rectangle; with no pins it could not
perturb the netlist even if `on_board` were set wrong.

| Ref | Part | LCSC | Qty | Who fits it |
| --- | --- | --- | --- | --- |
| `J26`, `J27` | `BTH-060-01-L-D-A-K-TR` | `C3646540` | 2 | the PCBA house -- these are soldered |
| `MK20` | M2.5 mounting kit | -- | 1 | you, with the module |

⚠ `C3646540` had **60** in stock on 2026-08-20, i.e. 30 boards, which makes it
the tightest line on the whole BOM. `C3644612` is the same connector without the
`-K` option, 36 more. Re-check before ordering.

The hardware is `L-1038e.A5` §4.3's own recommendation -- 2x M2.5x5 mm F-F
standoffs, 4x M2.5x4 mm screws, 4x M2.5 washers -- kept as **one** line because
that is how such a kit is bought. It is not optional: the standoffs are what set
the 5 mm stacking height the connectors are specified for, so without them the
solder joints carry the mechanical load.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402
from patch_mcu_pg_som import splice  # noqa: E402

PROJ = HERE.parent
SCH = PROJ / "som.kicad_sch"

# Free canvas on `som`: the band x ~190..300, y ~195..260, below the X2C block
# and left of X2D.
#
# ⚠ The first attempt put these at x=62.23 and they landed **on top of `J21`**,
# the microSD connector. The mistake is worth recording because it is easy to
# repeat: scanning a sheet's `(at ...)` values finds symbol *origins*, not
# extents, so a large symbol reads as a single empty-looking point. J21's origin
# is outside the scanned cells; its body is not. **Free space on a dense sheet
# has to be confirmed by rendering the page and looking at it**, which is what
# these coordinates were.
X, Y0, DY = 236.22, 203.2, 20.32

ITEMS = [
    ("J26", "BTH-060-01-L-D-A-K-TR", {
        "LCSC": "C3646540", "MPN": "BTH-060-01-L-D-A-K-TR", "Manufacturer": "Samtec",
        "BOM Comments": ("Board-side receptacle for the PCM-071, 2 per board. Soldered to "
                         "r2:PCM-071_2xBTH-060-01-L-D-A-K, which carries both patterns in one "
                         "footprint -- so this symbol is on_board=no and exists only to put the "
                         "part on the order. LCSC stock was 60 on 2026-08-20; C3644612 is the "
                         "same connector without the -K option. som.md section 10.")}),
    ("J27", "BTH-060-01-L-D-A-K-TR", {
        "LCSC": "C3646540", "MPN": "BTH-060-01-L-D-A-K-TR", "Manufacturer": "Samtec",
        "BOM Comments": "The second of the two. See J26."}),
    ("MK20", "PCM-071 mounting kit", {
        "MPN": "2x M2.5x5 F-F standoff, 4x M2.5x4 screw, 4x M2.5 washer",
        "BOM Comments": ("PHYTEC's own recommendation, L-1038e.A5 section 4.3. Not optional: the "
                         "standoffs set the 5 mm stacking height the BTH-060 pair is specified "
                         "for, so without them the connector solder joints carry the module's "
                         "mechanical load. Holes are in the footprint at (2.8, 2.8) and "
                         "(29.2, 40.2) relative to the module outline.")}),
]


def main() -> int:
    t = SCH.read_text()
    for ref, _v, _p in ITEMS:
        assert f'"{ref}"' not in t, f"already patched ({ref})"
    assert '"BOM_ITEM"' in (PROJ / "r2.kicad_sym").read_text(), \
        "BOM_ITEM is not in r2.kicad_sym"

    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["som"], root_uuid, "r2", paper="A3", pwr_base=1250)
    s.lib.add_file("r2", PROJ / "r2.kicad_sym")

    s.text(X - 17.78, Y0 - 12.7,
           "Purchase-only lines -- not on the board, not in the netlist. som.md §10",
           size=1.27)
    for i, (ref, val, props) in enumerate(ITEMS):
        s.place("r2:BOM_ITEM", ref, val, X, Y0 + i * DY, extra=props,
                ref_at=(X, Y0 + i * DY - 6.35), val_at=(X, Y0 + i * DY + 6.35))
    s.check_grid()
    body = s.render()

    # schgen writes placed symbols as on_board yes; these must not reach the PCB.
    body, n = re.subn(r'(\(lib_id "r2:BOM_ITEM"\)(?:(?!\(lib_id).)*?)\(on_board yes\)',
                      r'\1(on_board no)', body, flags=re.S)
    assert n == len(ITEMS), f"on_board rewrite hit {n} of {len(ITEMS)}"

    SCH.write_text(splice(t, body))
    print(f"som: {len(ITEMS)} purchase-only items placed "
          f"({', '.join(r for r, _, _ in ITEMS)}), all on_board=no")
    print("     no sheet-pin change, so wire_root.py is not needed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
