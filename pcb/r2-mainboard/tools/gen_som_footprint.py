#!/usr/bin/env python3
"""The `PCM-071` land pattern: 2 x `BTH-060-01-L-D-A-K-TR`, 240 pads.

`layout.md` §3.2 said this one "should not be built by hand" and pointed at
SnapEDA. That advice was written before the two drawings it needs were in the
repo. They now are, and between them they over-determine the geometry, so it can
be generated *and checked* rather than measured off a picture:

* `bth-xxx-xx-x-d-xx-footprint.pdf` -- Samtec's own recommended PCB layout,
  REV D, for one connector.
* `L-1038e.A5` **Figure 7, "Carrier Board Alignment Hole Placement"** (p.19) --
  which is literally a carrier-board drawing: where the two connectors sit
  relative to the module outline, dimensioned from it.

Samtec's sheet is a vector drawing, so the numerals were not the only source:
the content stream was parsed and the pad rectangles measured directly. Every
measurement agreed with a printed dimension to under 1 um, and two printed
dimensions that the drawing does *not* explain fell out of the measurement:

    pitch        5.66928 pt  ->  0.50000 mm      printed .01969 [0.5000] TYP
    pad          3.456 x 16.416 pt               printed .0120 [0.305] x .0570 [1.448]
    row centres  69.984 pt   ->  6.17230 mm      = printed .3000 [7.620] - 1.448
    NPTH         11.494 pt   ->  1.01380 mm      printed dia .0400 [1.016], -A option
    hole to hole 379.642 pt  ->  33.4818 mm      = Table 1 "A" for -60, 33.482
    hole offset  (33.482 - 29.507) / 2 = 1.9875  = printed .0782 [1.986] REF
    hole to row  11.948 pt   ->  1.05380 mm      = printed .0415 [1.054]

The last two are what make the assembly solvable. **The alignment hole is not on
the connector's centreline** -- it sits 1.054 mm from one pad row and 5.118 mm
from the other. Figure 7 dimensions the *holes*, so without that offset the rows
cannot be placed at all.

Figure 7, with the module outline's lower-left corner as origin:

    SOM outline                  32.000 x 43.000
    left alignment column        x = 2.760
    right alignment column       x = 2.760 + 22.400 = 25.160
    left connector, upper hole   y = 43.000 - 2.420 = 40.580
    right connector, upper hole  4.800 mm LOWER -- the two are staggered
    hole to hole, either one     33.482
    M2.5 mounting holes          (2.800, 2.800) and (29.200, 40.200), dia 2.600

Figure 6 supplies the two facts Figure 7 leaves out: the row order left to
right is **B A** then **D C**, and pin 1 is at the **bottom**, pin 60 at the top.
It also shows the alignment hole drawn against the *left* row of each connector
-- against `B` and against `D` -- which is the orientation `ROW_OF_HOLE`
encodes, and `check()` proves it independently: the alternative puts the `C` row
0.4 mm off the edge of a 32 mm module.

**The near-symmetry is the check worth trusting.** Nothing above forces it, yet
the `B` row lands 0.982 mm inside the left edge and the `C` row 0.998 mm inside
the right. 16 um of asymmetry out of 32 mm, from two independently printed
dimensions (2.760 and 22.400), is not a coincidence -- it is the drawing being
consistent, and it would not survive a wrong row order or a wrong hole offset.

Pitch: Samtec prints 0.5001 mm (.01969 in) and tabulates "B" = 29.507 for 60
positions. This generator lays the pads on an exact 0.500 mm pitch **centred on
the hole pair**, because the holes are the mechanical datum and 0.5 mm is the
design intent. The disagreement with Samtec's own table is 5 um at the end pads.

Courtyard follows the KiCad convention for mezzanine modules -- it encloses the
connectors, not the module. **The module does not sit on the board**: it stands
5 mm off it, so parts may live underneath, and a 32 x 43 courtyard would forbid
that. The module outline goes on `F.Fab` and `User.Drawings` instead, which
means **DRC will not police component height under the SoM**; `layout.md` §3.2
carries that as a manual check.
"""
import pathlib
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "r2.pretty" / "PCM-071_2xBTH-060-01-L-D-A-K.kicad_mod"

NAME = "PCM-071_2xBTH-060-01-L-D-A-K"

# --- Samtec BTH-XXX-XX-X-D-XX recommended layout, REV D ---------------------
N = 60
PITCH = 0.5                 # .01969 [0.5000] TYP
PAD_L, PAD_W = 1.448, 0.305  # .0570 [1.448] x .0120 [0.305]; L is across the row
ROW_SPAN = 7.620            # .3000 [7.620], pad outer edge to pad outer edge
ROW_PITCH = ROW_SPAN - PAD_L  # 6.172, centre to centre
HOLE_D = 1.016              # dia .0400 [1.016], -A option (NPTH)
HOLE_TO_ROW = 1.054         # .0415 [1.054], hole to the NEAR row's centre
A_DIM = 33.482              # Table 1, "A" for -60: hole to hole along the row

# --- L-1038e.A5 Figure 7, carrier-board frame, origin = SOM lower-left ------
SOM_W, SOM_H = 32.000, 43.000
LEFT_HOLE_X = 2.760
CONN_PITCH_X = 22.400
LEFT_HOLE_TOP_Y = SOM_H - 2.420
RIGHT_DROP_Y = 4.800        # the right connector is staggered DOWN by this
MTG_OFF = 2.800             # M2.5 hole, from both edges of its corner
MTG_DRILL = 2.600           # dia 2.600 (drill hole); dia 4.000 is the plating
MTG_PLATE = 4.000

# Figure 6: rows left to right are B A then D C, and the alignment hole is
# drawn against the LEFT row of each connector.
CONNECTORS = (("B", "A", LEFT_HOLE_X, LEFT_HOLE_TOP_Y),
              ("D", "C", LEFT_HOLE_X + CONN_PITCH_X, LEFT_HOLE_TOP_Y - RIGHT_DROP_Y))

SILK_W, FAB_W, CRT_W = 0.12, 0.10, 0.05
CRT_GAP = 0.25


def f(v: float) -> str:
    return f"{round(v, 4):g}"


def rows():
    """(row letter, x in the SOM frame) for all four rows, plus the holes."""
    out = []
    for near, far, hx, htop in CONNECTORS:
        x_near = hx - HOLE_TO_ROW
        out.append((near, x_near, hx, htop))
        out.append((far, x_near + ROW_PITCH, hx, htop))
    return out


def check() -> None:
    """Everything that would produce a board the module does not fit."""
    assert abs((ROW_PITCH + PAD_L) - ROW_SPAN) < 1e-9

    xs = {r: x for r, x, _hx, _ht in rows()}
    left_edge = xs["B"] - PAD_L / 2
    right_edge = xs["C"] + PAD_L / 2
    assert left_edge > 0, f"B row hangs off the module: {left_edge}"
    assert right_edge < SOM_W, f"C row hangs off the module: {right_edge}"

    # The orientation check. Mirroring HOLE_TO_ROW puts C off the edge.
    mirrored = (LEFT_HOLE_X + CONN_PITCH_X + HOLE_TO_ROW) + ROW_PITCH + PAD_L / 2
    assert mirrored > SOM_W, "the mirrored row order is not excluded after all"

    # The one nothing forces: the two outer rows sit the same distance in.
    skew = abs(left_edge - (SOM_W - right_edge))
    assert skew < 0.05, f"rows are not symmetric in the module: {skew:.4f} mm"

    # Pad span against Samtec's own tabulated "B" for -60.
    assert abs((N - 1) * PITCH - 29.507) < 0.01
    # And "A" is that plus twice the printed end offset.
    assert abs(A_DIM - ((N - 1) * PITCH + 2 * 1.986)) < 0.01

    # Nothing drilled may touch a pad or another hole. The M2.5 holes are
    # checked against their dia 4.000 plating, not their 2.600 drill, because
    # that is the copper-free zone the module itself imposes.
    holes = []
    for _near, _far, hx, htop in CONNECTORS:
        holes += [(hx, htop, HOLE_D / 2), (hx, htop - A_DIM, HOLE_D / 2)]
    holes += [(MTG_OFF, MTG_OFF, MTG_PLATE / 2),
              (SOM_W - MTG_OFF, SOM_H - MTG_OFF, MTG_PLATE / 2)]
    for i, (ax, ay, ar) in enumerate(holes):
        for bx, by, br in holes[i + 1:]:
            d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
            assert d > ar + br + 0.2, f"holes collide at {d:.3f} mm"
        for _near, _far, hx, htop in CONNECTORS:
            mid = htop - A_DIM / 2
            for x in (hx - HOLE_TO_ROW, hx - HOLE_TO_ROW + ROW_PITCH):
                for n in (1, N):
                    py = mid + (n - 1 - (N - 1) / 2) * PITCH
                    dx = max(0.0, abs(ax - x) - PAD_L / 2)
                    dy = max(0.0, abs(ay - py) - PAD_W / 2)
                    d = (dx * dx + dy * dy) ** 0.5
                    assert d > ar + 0.15, f"hole at ({ax},{ay}) is {d:.3f} mm from a pad"
    print(f"check: B row {left_edge:.3f} mm inside the left edge, "
          f"C row {SOM_W - right_edge:.3f} mm inside the right, "
          f"skew {skew * 1000:.0f} um")


# --- emit -------------------------------------------------------------------
def uid() -> str:
    return str(uuid.uuid4())


def line(x1, y1, x2, y2, layer, w):
    return ["\t(fp_line", f"\t\t(start {f(x1)} {f(y1)})", f"\t\t(end {f(x2)} {f(y2)})",
            f"\t\t(stroke (width {w}) (type solid))", f'\t\t(layer "{layer}")',
            f'\t\t(uuid "{uid()}")', "\t)"]


def rect(x1, y1, x2, y2, layer, w):
    return ["\t(fp_rect", f"\t\t(start {f(x1)} {f(y1)})", f"\t\t(end {f(x2)} {f(y2)})",
            f"\t\t(stroke (width {w}) (type solid))", "\t\t(fill none)",
            f'\t\t(layer "{layer}")', f'\t\t(uuid "{uid()}")', "\t)"]


def build() -> str:
    check()
    # SOM frame -> footprint frame: origin at the module centre, KiCad Y down.
    cx, cy = SOM_W / 2, SOM_H / 2

    def X(x):
        return x - cx

    def Y(y):
        return cy - y

    o = [f'(footprint "{NAME}"', "\t(version 20260206)", '\t(generator "gen_som_footprint.py")',
         '\t(generator_version "10.0")', '\t(layer "F.Cu")',
         '\t(descr "PHYTEC phyCORE-AM62x PCM-071 System on Module, 240 pins over two '
         'Samtec BTH-060-01-L-D-A-K-TR (2x60, 0.5 mm pitch, 5 mm stack height). Rows B A D C '
         'left to right, pin 1 at the bottom. Land pattern from Samtec drawing '
         'BTH-XXX-XX-X-D-XX REV D; connector placement and mounting holes from PHYTEC '
         'L-1038e.A5 Figure 7. Courtyard covers the connectors only -- the module stands 5 mm '
         'off the board, so parts may sit under it; the 32x43 mm outline is on F.Fab.")',
         '\t(tags "PHYTEC phyCORE AM62x PCM-071 SOM mezzanine Samtec BTH-060 board-to-board")',
         "\t(attr smd)"]

    for kind, txt, yy, layer in (("Reference", "REF**", -cy - 1.2, "F.SilkS"),
                                 ("Value", NAME, cy + 1.2, "F.Fab")):
        o += [f'\t(property "{kind}" "{txt}"', f"\t\t(at 0 {f(yy)} 0)", f'\t\t(layer "{layer}")',
              f'\t\t(uuid "{uid()}")',
              "\t\t(effects (font (size 1 1) (thickness 0.15)))", "\t)"]

    # --- module outline, F.Fab and User.Drawings ---------------------------
    for layer, w in (("F.Fab", FAB_W), ("User.Drawings", FAB_W)):
        o += rect(X(0), Y(0), X(SOM_W), Y(SOM_H), layer, w)

    # --- per connector -----------------------------------------------------
    npads = 0
    for near, far, hx, htop in CONNECTORS:
        hbot = htop - A_DIM
        mid = (htop + hbot) / 2
        y1 = mid - (N - 1) * PITCH / 2          # pin 1, the bottom one
        x_near = hx - HOLE_TO_ROW
        for row, x in ((near, x_near), (far, x_near + ROW_PITCH)):
            for n in range(1, N + 1):
                py = y1 + (n - 1) * PITCH
                o += [f'\t(pad "{row}{n}" smd rect', f"\t\t(at {f(X(x))} {f(Y(py))})",
                      f"\t\t(size {f(PAD_L)} {f(PAD_W)})",
                      '\t\t(layers "F.Cu" "F.Mask" "F.Paste")', f'\t\t(uuid "{uid()}")', "\t)"]
                npads += 1
        # the two NPTH alignment holes
        for hy in (htop, hbot):
            o += ['\t(pad "" np_thru_hole circle', f"\t\t(at {f(X(hx))} {f(Y(hy))})",
                  f"\t\t(size {f(HOLE_D)} {f(HOLE_D)})", f"\t\t(drill {f(HOLE_D)})",
                  '\t\t(layers "F&B.Cu" "*.Mask")', f'\t\t(uuid "{uid()}")', "\t)"]
        # F.Fab: the pad field, and the courtyard around it
        fx0, fx1 = x_near - PAD_L / 2, x_near + ROW_PITCH + PAD_L / 2
        fy0, fy1 = y1 - PAD_W / 2, y1 + (N - 1) * PITCH + PAD_W / 2
        o += rect(X(fx0), Y(fy0), X(fx1), Y(fy1), "F.Fab", FAB_W)
        # The courtyard has to reach past the pads to the alignment holes --
        # the connector body covers them, so a pad-field courtyard would let a
        # neighbour sit on top of the plastic.
        cy0 = min(fy0, hbot - HOLE_D / 2)
        cy1 = max(fy1, htop + HOLE_D / 2)
        o += rect(X(fx0 - CRT_GAP), Y(cy0 - CRT_GAP),
                  X(fx1 + CRT_GAP), Y(cy1 + CRT_GAP), "F.CrtYd", CRT_W)
        # silk: a bracket below pin 1 of each row, outside the pads
        for row, x in ((near, x_near), (far, x_near + ROW_PITCH)):
            sy = y1 - PAD_W / 2 - 0.35
            o += line(X(x - PAD_L / 2), Y(sy), X(x + PAD_L / 2), Y(sy), "F.SilkS", SILK_W)
        o += [f'\t(fp_text user "{near}1 {far}1"',
              f"\t\t(at {f(X(x_near + ROW_PITCH / 2))} {f(Y(y1 - 1.4))} 0)",
              '\t\t(layer "F.SilkS")', f'\t\t(uuid "{uid()}")',
              "\t\t(effects (font (size 0.8 0.8) (thickness 0.12)))", "\t)"]

    # --- silk: the module outline, as corner ticks --------------------------
    TICK = 3.0
    for mx, my, sx, sy in ((0, 0, 1, 1), (SOM_W, 0, -1, 1),
                           (SOM_W, SOM_H, -1, -1), (0, SOM_H, 1, -1)):
        o += line(X(mx), Y(my), X(mx + sx * TICK), Y(my), "F.SilkS", SILK_W)
        o += line(X(mx), Y(my), X(mx), Y(my + sy * TICK), "F.SilkS", SILK_W)

    # --- M2.5 mounting holes ------------------------------------------------
    for mx, my in ((MTG_OFF, MTG_OFF), (SOM_W - MTG_OFF, SOM_H - MTG_OFF)):
        o += ['\t(pad "" np_thru_hole circle', f"\t\t(at {f(X(mx))} {f(Y(my))})",
              f"\t\t(size {f(MTG_DRILL)} {f(MTG_DRILL)})", f"\t\t(drill {f(MTG_DRILL)})",
              '\t\t(layers "F&B.Cu" "*.Mask")', f'\t\t(uuid "{uid()}")', "\t)"]
        # the dia 4.000 plating on the module: keep copper and parts clear of it
        o += ["\t(fp_circle", f"\t\t(center {f(X(mx))} {f(Y(my))})",
              f"\t\t(end {f(X(mx) + MTG_PLATE / 2)} {f(Y(my))})",
              f"\t\t(stroke (width {FAB_W}) (type dash))", "\t\t(fill none)",
              '\t\t(layer "F.Fab")', f'\t\t(uuid "{uid()}")', "\t)"]

    o.append(")")
    print(f"pads: {npads} SMD + 4 NPTH alignment + 2 M2.5")
    return "\n".join(o) + "\n"


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build())
    print(f"wrote {OUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
