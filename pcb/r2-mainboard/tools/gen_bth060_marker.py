#!/usr/bin/env python3
"""An assembly-only footprint for one `BTH-060` receptacle: no pads, just a body.

**This exists so the board comes back with the connectors already soldered on.**
The problem it solves is not electrical, it is a pick-and-place bookkeeping
problem, and it only becomes visible when you try to order:

`r2:PCM-071_2xBTH-060-01-L-D-A-K` carries all 240 pads under the single
reference `X2`. A CPL (placement) file has **one row per reference**, so `X2`
produces exactly one placement at one centroid -- but there is no single part
that covers all 240 pads. There are two, 22.4 mm apart. So the assembler is told
to place one component where two belong, the `X2` row matches no LCSC part, and
per JLCPCB's upload rules a CPL designator that is not in the BOM is rejected
outright. The board would arrive with 240 bare pads.

The fix keeps the pads where they are and adds two references that exist purely
to be placed:

    X2    240 pads, all the nets      -> excluded from the position file
    J26   this footprint, no pads     -> CPL row at connector 1's centroid
    J27   this footprint, no pads     -> CPL row at connector 2's centroid

`J26`/`J27` carry `C3646540`, so the BOM line and the CPL rows agree and the
machine places a real part at each real centroid. The paste and copper it lands
on come from `X2`, which the assembler never needs to know.

**The offsets are the whole safety argument, so they are checkable rather than
remembered.** Relative to `X2`'s origin (the module's centre):

    J26   (-11.200, -2.400)
    J27   (+11.200, +2.400)

which is the 22.400 mm spacing and 4.800 mm stagger of PHYTEC's DXF, split
symmetrically. `tools/check_pcb_connectors.py` asserts exactly this against
`r2.kicad_pcb` once Stage D exists. That check is *stronger* than the
single-footprint arrangement it replaces, because it is verified rather than
merely structural -- and it is the reason splitting the placement this way does
not reintroduce the hazard `gen_som_symbol.py` warned about.

Body outline is Samtec's own `F.Fab` rectangle from
`SAMTEC_BTH-060-X-X-D-A-K.kicad_mod` -- 35.0 x 5.969 mm -- rotated into this
board's vertical orientation, so pin 1 is at the bottom and rotation 0 is
correct as placed.

⚠ **Two things to confirm before the first PCBA order**, both cheap and both
expensive to get wrong:

1. **Ask JLCPCB to confirm the arrangement.** A designator whose own footprint
   has no pads is a known technique, not an exotic one, but their DFM review
   may query it. A query costs an email; a rejected order costs a week.
2. **Check the CPL rotation.** JLCPCB's pick-and-place does not share KiCad's
   rotation convention for every part (their own guidance calls connectors out
   specifically). Verify `J26`/`J27`'s rotation against Samtec's pin-1 marking
   before uploading, and record the correction if one is needed.
"""
import pathlib
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "r2.pretty" / "BTH-060-01-L-D-A-K_AssemblyOnly.kicad_mod"
NAME = "BTH-060-01-L-D-A-K_AssemblyOnly"

# Samtec's own F.Fab body rectangle, in their horizontal drawing: +/-17.5 x
# +/-2.9845. This board runs the connectors vertically, so the axes swap.
HALF_LONG, HALF_SHORT = 17.5, 2.9845
FAB_W, SILK_W = 0.10, 0.12
# Where each instance must sit relative to X2's origin. Not used by the
# footprint itself -- carried here so check_pcb_connectors.py has one source.
OFFSETS = {"J26": (-11.200, -2.400), "J27": (+11.200, +2.400)}


def f(v: float) -> str:
    return f"{round(v, 4):g}"


def uid() -> str:
    return str(uuid.uuid4())


def build() -> str:
    x, y = HALF_SHORT, HALF_LONG
    o = [f'(footprint "{NAME}"', "\t(version 20260206)",
         '\t(generator "gen_bth060_marker.py")', '\t(generator_version "10.0")',
         '\t(layer "F.Cu")',
         '\t(descr "Samtec BTH-060-01-L-D-A-K-TR, ASSEMBLY MARKER ONLY -- no pads. The pads for '
         'both receptacles live in r2:PCM-071_2xBTH-060-01-L-D-A-K under X2; this footprint exists '
         'so each connector gets its own CPL row and BOM match. Place at X2 + (-11.200, -2.400) '
         'for J26 and X2 + (+11.200, +2.400) for J27, verified by tools/check_pcb_connectors.py. '
         'Body outline is Samtec\'s own F.Fab rectangle, 35.0 x 5.969 mm, rotated vertical with '
         'pin 1 at the bottom. See som.md section 10.")',
         '\t(tags "Samtec BTH-060 assembly marker no-pads CPL placement PCM-071")',
         # smd so it lands in the position file; exclude_from_bom is NOT set --
         # this reference is exactly what the BOM line has to match.
         "\t(attr smd)"]

    for kind, txt, yy, layer in (("Reference", "REF**", -y - 1.4, "F.SilkS"),
                                 ("Value", NAME, y + 1.4, "F.Fab")):
        o += [f'\t(property "{kind}" "{txt}"', f"\t\t(at 0 {f(yy)} 0)",
              f'\t\t(layer "{layer}")', f'\t\t(uuid "{uid()}")',
              "\t\t(effects (font (size 1 1) (thickness 0.15)))", "\t)"]

    for layer, w in (("F.Fab", FAB_W), ("F.SilkS", SILK_W)):
        o += ["\t(fp_rect", f"\t\t(start {f(-x)} {f(-y)})", f"\t\t(end {f(x)} {f(y)})",
              f"\t\t(stroke (width {w}) (type solid))", "\t\t(fill none)",
              f'\t\t(layer "{layer}")', f'\t\t(uuid "{uid()}")', "\t)"]

    # Pin-1 chevron at the bottom, on F.Fab only -- silk here would sit on the
    # pads, and F.SilkS under a 0.5 mm connector is a solder-mask problem.
    o += ["\t(fp_poly", "\t\t(pts",
          f"\t\t\t(xy {f(-x)} {f(y)}) (xy {f(-x + 1.2)} {f(y)}) (xy {f(-x)} {f(y - 1.2)})", "\t\t)",
          f"\t\t(stroke (width {FAB_W}) (type solid))", "\t\t(fill solid)",
          '\t\t(layer "F.Fab")', f'\t\t(uuid "{uid()}")', "\t)"]

    o += [f'\t(fp_text user "pin 1"', f"\t\t(at 0 {f(y - 2.2)} 0)",
          '\t\t(layer "F.Fab")', f'\t\t(uuid "{uid()}")',
          "\t\t(effects (font (size 0.8 0.8) (thickness 0.12)))", "\t)"]

    # No courtyard: this marker sits on top of X2's, and two overlapping
    # courtyards are a DRC error for a collision that does not exist.
    o.append(")")
    return "\n".join(o) + "\n"


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build())
    print(f"wrote {OUT.relative_to(HERE.parent)}: no pads, "
          f"{2 * HALF_SHORT:.4g} x {2 * HALF_LONG:.4g} mm body")
    for r, (dx, dy) in OFFSETS.items():
        print(f"   {r} must be placed at X2 + ({dx:+.3f}, {dy:+.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
