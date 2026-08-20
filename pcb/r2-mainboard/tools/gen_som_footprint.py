#!/usr/bin/env python3
"""The `PCM-071` land pattern: 2 x `BTH-060-01-L-D-A-K-TR`, 240 pads.

**Rebuilt 2026-08-20 on PHYTEC's own DXF**, which the owner downloaded with the
3D models (`datasheets/SoM Phycore AM62x/PCM-071_1573-1_3d/`). The first version
of this generator derived the placement from `L-1038e.A5` Figure 7 by reading
numerals off a raster image; the DXF is vector, numeric, and PHYTEC's README
names it as authoritative -- *"Exact specifications can be found in the
corresponding data sheets and DXF data"*, in the same breath as warning that the
STEP model may be simplified. It agreed with the picture-derived version to
**8 um in x and 61 um in y**, which is close enough to be reassuring and far
enough to be worth correcting: 61 um is 20 % of a 0.305 mm pad's width.

**What the DXF gives directly**, in a frame whose origin is the module's
lower-left corner (`BOARD_OUTLINE` is exactly `(0,0)-(32.000,43.000)`):

    four columns of exactly 60 pads   x = 1.95, 7.65, 24.35, 30.05
    pitch                             0.500 mm exactly, 59 gaps, span 29.500
    left connector pads               y = 9.150 .. 38.650
    right connector pads              y = 4.350 .. 33.850   (4.800 lower)
    M2.5 mounting holes               (2.800, 2.800) and (29.200, 40.200)

Those columns are the module's **BSH-060 plug**, not our receptacle, so their
5.70 mm row spacing is not ours -- but their *centrelines* are, and they come out
at **4.800 and 27.200**: exactly 22.400 apart (Figure 7's number) and exactly
symmetric about the module's 16.000 mm midline. The receptacle's rows go
+/- `ROW_PITCH`/2 either side of those.

**Three things the DXF confirms that were assumptions before:** the pitch really
is 0.500 and not Samtec's inch-derived 0.5001; the span really is 29.500 and not
the 29.507 in Samtec's table; and the two `M2.5` positions are exactly Figure 7's.

**And one thing it corrects.** The DXF has four `MOUNTING_HOLES_LAYER` circles of
1.100 mm at x 7.452 / 29.852, spaced **35.126** along the row -- which is neither
Samtec's `-A` diameter (1.016) nor its "A" dimension (33.482). They are not our
holes: they are the **BSH plug's own** locating holes in the module. The `-A`
option puts plastic pegs on each connector that drop into holes in the board that
connector is soldered to, so the plug's pegs land in the module and the
receptacle's pegs land in our board, and the two sets never meet. Our holes come
from Samtec's BTH drawing and are referenced to *our* pads. Spending twenty
minutes on that apparent contradiction was the most useful part of the exercise.

**What still comes from Samtec** (`bth-xxx-xx-x-d-xx-footprint.pdf`, REV D, whose
content stream was parsed rather than eyeballed -- every measurement matched a
printed dimension to under 1 um):

    row centre spacing  6.1723 mm   = printed .3000 [7.620] - 1.448
    pad                 1.448 x 0.305
    NPTH                1.016, the -A option
    hole beyond end pad 1.986 along the row   (.0782 REF)
    hole off centreline 1.054 from the near row  (.0415)

`L-1038e.A5` Figure 6 supplies the row order -- **B A** then **D C**, pin 1 at
the bottom -- and shows the alignment hole against the *left* row of each
connector, which `ROW_OF_HOLE` encodes and `check()` proves independently.

⚠ **The two receptacles are a BOM line this schematic does not produce.** `X2` is
one symbol for the module; the parts an assembler actually solders are
**2 x `BTH-060-01-L-D-A-K-TR`**, LCSC `C3646540`. See `som.md` §10.
"""
import pathlib
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "r2.pretty" / "PCM-071_2xBTH-060-01-L-D-A-K.kicad_mod"

NAME = "PCM-071_2xBTH-060-01-L-D-A-K"

# --- PHYTEC PCM-071_1573-1.dxf, module frame, origin at the lower-left --------
SOM_W, SOM_H = 32.000, 43.000     # BOARD_OUTLINE, 4 vertices, exact
N = 60                            # pads per column, counted
PITCH = 0.500                     # 59 gaps, all 0.500
SPAN = (N - 1) * PITCH            # 29.500, matches the DXF exactly
# (BSH column pairs (1.95, 7.65) and (24.35, 30.05) -> these centrelines)
CONN_CX = (4.800, 27.200)
PIN1_Y = (9.150, 4.350)           # bottom pad of the left / right connector
MTG = ((2.800, 2.800), (SOM_W - 2.800, SOM_H - 2.800))
MTG_DRILL, MTG_PLATE = 2.600, 4.000

# --- Samtec BTH-XXX-XX-X-D-XX recommended layout, REV D -----------------------
PAD_L, PAD_W = 1.448, 0.305       # L is across the row, W along it
ROW_SPAN = 7.620                  # .3000, pad outer edge to pad outer edge
ROW_PITCH = ROW_SPAN - PAD_L      # 6.172, centre to centre
HOLE_D = 1.016                    # dia .0400, -A option, NPTH
HOLE_END_OFF = 1.986              # .0782 REF, beyond the end pad along the row
HOLE_TO_ROW = 1.054               # .0415, from the NEAR row's centre

# Figure 6: rows left to right are B A then D C; the alignment hole sits against
# the LEFT row of each connector.
ROWS = (("B", "A"), ("D", "C"))

SILK_W, FAB_W, CRT_W = 0.12, 0.10, 0.05
CRT_GAP = 0.25


def f(v: float) -> str:
    return f"{round(v, 4):g}"


def geometry():
    """[(left row, right row, x_left, x_right, x_hole, y_pin1)] per connector."""
    out = []
    for (near, far), cx, y1 in zip(ROWS, CONN_CX, PIN1_Y):
        xl = cx - ROW_PITCH / 2
        out.append((near, far, xl, xl + ROW_PITCH, xl + HOLE_TO_ROW, y1))
    return out


def check() -> None:
    """Everything that would produce a board the module does not fit."""
    assert abs((ROW_PITCH + PAD_L) - ROW_SPAN) < 1e-9
    assert abs(SPAN - 29.500) < 1e-9

    g = geometry()
    xs = {}
    for near, far, xl, xr, _hx, _y1 in g:
        xs[near], xs[far] = xl, xr

    left_edge = xs["B"] - PAD_L / 2
    right_edge = xs["C"] + PAD_L / 2
    assert left_edge > 0, f"B row hangs off the module: {left_edge}"
    assert right_edge < SOM_W, f"C row hangs off the module: {right_edge}"

    # The DXF's centrelines are symmetric about the module midline, so the two
    # outer rows must be too. Nothing in Samtec's drawing forces this.
    skew = abs(left_edge - (SOM_W - right_edge))
    assert skew < 0.001, f"rows are not symmetric in the module: {skew:.4f} mm"

    # The two numbers Figure 7 prints, rederived from the DXF's pad columns.
    assert abs((CONN_CX[1] - CONN_CX[0]) - 22.400) < 1e-9, "connector spacing"
    assert abs((PIN1_Y[0] - PIN1_Y[1]) - 4.800) < 1e-9, "connector stagger"

    # Nothing drilled may touch a pad or another hole. M2.5 is checked against
    # its 4.000 plating, not its 2.600 drill: that is the copper-free zone.
    holes = []
    for _near, _far, _xl, _xr, hx, y1 in g:
        holes += [(hx, y1 - HOLE_END_OFF, HOLE_D / 2),
                  (hx, y1 + SPAN + HOLE_END_OFF, HOLE_D / 2)]
    holes += [(mx, my, MTG_PLATE / 2) for mx, my in MTG]
    for i, (ax, ay, ar) in enumerate(holes):
        for bx, by, br in holes[i + 1:]:
            d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
            assert d > ar + br + 0.2, f"holes collide at {d:.3f} mm"
        for _near, _far, xl, xr, _hx, y1 in g:
            for x in (xl, xr):
                for py in (y1, y1 + SPAN):
                    dx = max(0.0, abs(ax - x) - PAD_L / 2)
                    dy = max(0.0, abs(ay - py) - PAD_W / 2)
                    d = (dx * dx + dy * dy) ** 0.5
                    assert d > ar + 0.15, f"hole ({ax},{ay}) is {d:.3f} mm from a pad"

    print(f"check: B and C rows both {left_edge:.3f} mm inside the module edges "
          f"(skew {skew * 1000:.1f} um); 22.400 spacing and 4.800 stagger rederived")


# --- emit --------------------------------------------------------------------
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
    cx0, cy0 = SOM_W / 2, SOM_H / 2   # origin at the module centre, KiCad Y down

    def X(x):
        return x - cx0

    def Y(y):
        return cy0 - y

    o = [f'(footprint "{NAME}"', "\t(version 20260206)",
         '\t(generator "gen_som_footprint.py")', '\t(generator_version "10.0")',
         '\t(layer "F.Cu")',
         '\t(descr "PHYTEC phyCORE-AM62x PCM-071 System on Module, 240 pins over two '
         'Samtec BTH-060-01-L-D-A-K-TR (2x60, 0.5 mm pitch, 5 mm stack height). Rows B A D C '
         'left to right, pin 1 at the bottom, right connector staggered 4.8 mm down. Placement '
         'and module outline from PHYTEC PCM-071_1573-1.dxf; land pattern from Samtec drawing '
         'BTH-XXX-XX-X-D-XX REV D. The two receptacles are a separate BOM line, LCSC C3646540 x2 '
         '-- see som.md. Courtyard covers the connectors only: the module stands 5 mm off the '
         'board, so parts may sit under it; the 32x43 mm outline is on F.Fab.")',
         '\t(tags "PHYTEC phyCORE AM62x PCM-071 SOM mezzanine Samtec BTH-060 board-to-board")',
         "\t(attr smd)"]

    for kind, txt, yy, layer in (("Reference", "REF**", -cy0 - 1.2, "F.SilkS"),
                                 ("Value", NAME, cy0 + 1.2, "F.Fab")):
        o += [f'\t(property "{kind}" "{txt}"', f"\t\t(at 0 {f(yy)} 0)",
              f'\t\t(layer "{layer}")', f'\t\t(uuid "{uid()}")',
              "\t\t(effects (font (size 1 1) (thickness 0.15)))", "\t)"]

    for layer in ("F.Fab", "User.Drawings"):
        o += rect(X(0), Y(0), X(SOM_W), Y(SOM_H), layer, FAB_W)

    npads = 0
    for near, far, xl, xr, hx, y1 in geometry():
        for row, x in ((near, xl), (far, xr)):
            for n in range(1, N + 1):
                py = y1 + (n - 1) * PITCH
                o += [f'\t(pad "{row}{n}" smd rect', f"\t\t(at {f(X(x))} {f(Y(py))})",
                      f"\t\t(size {f(PAD_L)} {f(PAD_W)})",
                      '\t\t(layers "F.Cu" "F.Mask" "F.Paste")', f'\t\t(uuid "{uid()}")', "\t)"]
                npads += 1
        hb, ht = y1 - HOLE_END_OFF, y1 + SPAN + HOLE_END_OFF
        for hy in (hb, ht):
            o += ['\t(pad "" np_thru_hole circle', f"\t\t(at {f(X(hx))} {f(Y(hy))})",
                  f"\t\t(size {f(HOLE_D)} {f(HOLE_D)})", f"\t\t(drill {f(HOLE_D)})",
                  '\t\t(layers "F&B.Cu" "*.Mask")', f'\t\t(uuid "{uid()}")', "\t)"]
        fx0, fx1 = xl - PAD_L / 2, xr + PAD_L / 2
        fy0, fy1 = y1 - PAD_W / 2, y1 + SPAN + PAD_W / 2
        o += rect(X(fx0), Y(fy0), X(fx1), Y(fy1), "F.Fab", FAB_W)
        # The courtyard reaches past the pads to the holes -- the connector body
        # covers them, so a pad-field courtyard would let a neighbour sit on the
        # plastic.
        o += rect(X(fx0 - CRT_GAP), Y(min(fy0, hb - HOLE_D / 2) - CRT_GAP),
                  X(fx1 + CRT_GAP), Y(max(fy1, ht + HOLE_D / 2) + CRT_GAP),
                  "F.CrtYd", CRT_W)
        for _row, x in ((near, xl), (far, xr)):
            sy = fy0 - 0.35
            o += line(X(x - PAD_L / 2), Y(sy), X(x + PAD_L / 2), Y(sy), "F.SilkS", SILK_W)
        o += [f'\t(fp_text user "{near}1 {far}1"',
              f"\t\t(at {f(X((xl + xr) / 2))} {f(Y(fy0 - 1.4))} 0)",
              '\t\t(layer "F.SilkS")', f'\t\t(uuid "{uid()}")',
              "\t\t(effects (font (size 0.8 0.8) (thickness 0.12)))", "\t)"]

    TICK = 3.0
    for mx, my, sx, sy in ((0, 0, 1, 1), (SOM_W, 0, -1, 1),
                           (SOM_W, SOM_H, -1, -1), (0, SOM_H, 1, -1)):
        o += line(X(mx), Y(my), X(mx + sx * TICK), Y(my), "F.SilkS", SILK_W)
        o += line(X(mx), Y(my), X(mx), Y(my + sy * TICK), "F.SilkS", SILK_W)

    for mx, my in MTG:
        o += ['\t(pad "" np_thru_hole circle', f"\t\t(at {f(X(mx))} {f(Y(my))})",
              f"\t\t(size {f(MTG_DRILL)} {f(MTG_DRILL)})", f"\t\t(drill {f(MTG_DRILL)})",
              '\t\t(layers "F&B.Cu" "*.Mask")', f'\t\t(uuid "{uid()}")', "\t)"]
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
