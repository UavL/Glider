#!/usr/bin/env python3
"""Give the two `BTH-060` receptacles a reference, a BOM line and a CPL row.

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

So the footprint keeps all 240 pads under `X2`, and the two connectors get
references of their own that exist to be **placed** rather than to carry nets.

**A first attempt made these `on_board no`, and that was wrong.** It fixed
purchasing and left assembly broken, which is the half that matters if you want
the board to arrive with the connectors already on it. A CPL has one row per
reference: `X2` alone produces a single placement at a single centroid, for a
footprint that two separate parts occupy 22.4 mm apart. JLCPCB additionally
rejects a CPL designator that is not in the BOM. The board would come back with
240 bare pads.

So `J26`/`J27` are **`on_board yes`** with `r2:BTH-060-01-L-D-A-K_AssemblyOnly`
-- a body outline with **no pads** -- and `X2`'s own footprint is marked
`exclude_from_pos_files`. The result is exactly what an assembler needs:

| Ref | Footprint | In the BOM | In the CPL | Carries nets |
| --- | --- | --- | --- | --- |
| `X2` | 240 pads | the module, hand-fitted | **no** -- excluded | **yes**, all of them |
| `J26`, `J27` | body outline, no pads | `C3646540` x2 | **yes**, one row each | no |
| `MK20` | none, `on_board no` | the M2.5 kit | no | no |

`tools/check_pcb_connectors.py` asserts `J26`/`J27` sit at `X2` +/- (11.200,
2.400) once `r2.kicad_pcb` exists, which is a **stronger** guarantee than the
single footprint gave -- verified rather than merely structural.

`BOM_ITEM` in `r2.kicad_sym` is a pin-less rectangle, so none of these three can
perturb the netlist whatever `on_board` says.

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

MARKER = "r2:BTH-060-01-L-D-A-K_AssemblyOnly"

# (ref, value, footprint or None, properties). A footprint means the reference
# reaches the PCB and therefore the position file; None means purchase-only.
ITEMS = [
    ("J26", "BTH-060-01-L-D-A-K-TR", MARKER, {
        "LCSC": "C3646540", "MPN": "BTH-060-01-L-D-A-K-TR", "Manufacturer": "Samtec",
        "BOM Comments": ("Board-side receptacle for the PCM-071, 2 per board, SOLDERED BY THE "
                         "ASSEMBLER. Its pads are in r2:PCM-071_2xBTH-060-01-L-D-A-K under X2; "
                         "this reference carries the CPL row and the BOM match, and its own "
                         "footprint has no pads. Place at X2 + (-11.200, +2.400) -- checked by "
                         "tools/check_pcb_connectors.py. LCSC stock was 60 on 2026-08-20; "
                         "C3644612 is the same connector without the -K option. som.md "
                         "section 10.")}),
    ("J27", "BTH-060-01-L-D-A-K-TR", MARKER, {
        "LCSC": "C3646540", "MPN": "BTH-060-01-L-D-A-K-TR", "Manufacturer": "Samtec",
        "BOM Comments": "The second of the two. Place at X2 + (+11.200, -2.400). See J26."}),
    ("MK20", "PCM-071 mounting kit", None, {
        "MPN": "2x M2.5x5 F-F standoff, 4x M2.5x4 screw, 4x M2.5 washer",
        "BOM Comments": ("PHYTEC's own recommendation, L-1038e.A5 section 4.3. Not optional: the "
                         "standoffs set the 5 mm stacking height the BTH-060 pair is specified "
                         "for, so without them the connector solder joints carry the module's "
                         "mechanical load. Holes are in the footprint at (2.8, 2.8) and "
                         "(29.2, 40.2) relative to the module outline.")}),
]


def main() -> int:
    t = SCH.read_text()
    for ref, _v, _f, _p in ITEMS:
        assert f'"{ref}"' not in t, f"already patched ({ref})"
    assert '"BOM_ITEM"' in (PROJ / "r2.kicad_sym").read_text(), \
        "BOM_ITEM is not in r2.kicad_sym"

    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["som"], root_uuid, "r2", paper="A3", pwr_base=1250)
    s.lib.add_file("r2", PROJ / "r2.kicad_sym")

    s.text(X - 17.78, Y0 - 12.7,
           "J26/J27 place the two BTH-060 receptacles; their pads are X2's. som.md §10",
           size=1.27)
    for i, (ref, val, fp, props) in enumerate(ITEMS):
        s.place("r2:BOM_ITEM", ref, val, X, Y0 + i * DY, footprint=fp or "", extra=props,
                ref_at=(X, Y0 + i * DY - 6.35), val_at=(X, Y0 + i * DY + 6.35))
    s.check_grid()
    body = s.render()

    # schgen writes every placed symbol as `on_board yes`. Only MK20 stays off
    # the board -- J26/J27 must reach the PCB so that each gets a CPL row, which
    # is the entire point of this patch.
    #
    # Split on the lib_id rather than regexing across it: property order inside
    # a placed symbol is not fixed, and a greedy match would run into the next
    # symbol's block.
    off = {r for r, _v, fp, _props in ITEMS if fp is None}
    blocks = body.split('(lib_id "r2:BOM_ITEM")')
    done = set()
    for i, blk in enumerate(blocks[1:], 1):
        m = re.search(r'\(property "Reference" "([^"]+)"', blk)
        if m and m.group(1) in off:
            blk, k = re.subn(r"\(on_board yes\)", "(on_board no)", blk, count=1)
            assert k == 1, f"no (on_board yes) in {m.group(1)}'s block"
            blocks[i] = blk
            done.add(m.group(1))
    assert done == off, f"on_board rewrite reached {done}, wanted {off}"
    body = '(lib_id "r2:BOM_ITEM")'.join(blocks)

    SCH.write_text(splice(t, body))
    print(f"som: {len(ITEMS)} items placed ({', '.join(r for r, _, _, _ in ITEMS)}); "
          f"J26/J27 on_board=yes with the assembly-marker footprint, MK20 on_board=no")
    print("     no sheet-pin change, so wire_root.py is not needed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
