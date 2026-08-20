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
OUT_DIR = HERE.parent / "r2.pretty"

# One footprint per physical connector, plus one for the module's mechanical
# presence. The single 240-pad footprint this replaced is why som.md §10 exists:
# a position file has one row per reference, so it could never place two parts.
MODULE_NAME = "PCM-071_Module"
CONNECTORS = {
    # name: (near row = left, far row = right, centroid in the module frame)
    "BTH-060-01-L-D-A-K_AB": ("B", "A", (4.800, 23.900)),
    "BTH-060-01-L-D-A-K_CD": ("D", "C", (27.200, 19.100)),
}

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
HOLE_END_OFF = 1.991              # Samtec's own KiCad footprint; the drawing
                                  # prints .0782 [1.986] REF, 5 um away and REF
HOLE_TO_ROW = 1.054               # .0415, from the NEAR row's centre; Samtec's
                                  # footprint puts it 2.032 off the centreline,
                                  # which is 3.086 - 1.054 exactly
MASK_MARGIN = 0.102               # Samtec sets this on every pad. It makes the
                                  # mask openings 0.509 on a 0.5 pitch, i.e. one
                                  # gang opening per row with no webs -- which is
                                  # deliberate at this pitch, and better stated
                                  # here than left to the board's global margin
                                  # (a 0.093 web would be under JLC's 0.1 minimum
                                  # and removed anyway, but silently).

# Figure 6: rows left to right are B A then D C; the alignment hole sits against
# the LEFT row of each connector.
ROWS = (("B", "A"), ("D", "C"))

SILK_W, FAB_W, CRT_W = 0.12, 0.10, 0.05
CRT_GAP = 0.25


def f(v: float) -> str:
    return f"{round(v, 4):g}"


def check() -> None:
    """Everything that would produce a board the module does not fit."""
    assert abs((ROW_PITCH + PAD_L) - ROW_SPAN) < 1e-9
    assert abs(SPAN - 29.500) < 1e-9

    xs = {}
    for near, far, (cx, _cy) in CONNECTORS.values():
        xs[near], xs[far] = cx - ROW_PITCH / 2, cx + ROW_PITCH / 2

    left_edge = xs["B"] - PAD_L / 2
    right_edge = xs["C"] + PAD_L / 2
    assert left_edge > 0, f"B row hangs off the module: {left_edge}"
    assert right_edge < SOM_W, f"C row hangs off the module: {right_edge}"

    # The DXF's centrelines are symmetric about the module midline, so the two
    # outer rows must be too. Nothing in Samtec's drawing forces this.
    skew = abs(left_edge - (SOM_W - right_edge))
    assert skew < 0.001, f"rows are not symmetric in the module: {skew:.4f} mm"

    cxs = [c for _n, _f, (c, _y) in CONNECTORS.values()]
    cys = [y for _n, _f, (_c, y) in CONNECTORS.values()]
    assert abs((cxs[1] - cxs[0]) - 22.400) < 1e-9, "connector spacing"
    assert abs((cys[0] - cys[1]) - 4.800) < 1e-9, "connector stagger"
    # the centroids must be what the DXF's pad columns average to
    for (cx, cy), y1 in zip([c for _n, _f, c in CONNECTORS.values()], PIN1_Y):
        assert abs(cy - (y1 + SPAN / 2)) < 1e-9, f"centroid {cy} vs pads at {y1}"

    # Nothing drilled may touch a pad or another hole. M2.5 is checked against
    # its 4.000 plating, not its 2.600 drill: that is the copper-free zone.
    holes = []
    for near, _far, (cx, cy) in CONNECTORS.values():
        hx = cx - ROW_PITCH / 2 + HOLE_TO_ROW
        holes += [(hx, cy - SPAN / 2 - HOLE_END_OFF, HOLE_D / 2),
                  (hx, cy + SPAN / 2 + HOLE_END_OFF, HOLE_D / 2)]
    holes += [(mx, my, MTG_PLATE / 2) for mx, my in MTG]
    for i, (ax, ay, ar) in enumerate(holes):
        for bx, by, br in holes[i + 1:]:
            d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
            assert d > ar + br + 0.2, f"holes collide at {d:.3f} mm"
        for near, far, (cx, cy) in CONNECTORS.values():
            for x in (cx - ROW_PITCH / 2, cx + ROW_PITCH / 2):
                for py in (cy - SPAN / 2, cy + SPAN / 2):
                    dx = max(0.0, abs(ax - x) - PAD_L / 2)
                    dy = max(0.0, abs(ay - py) - PAD_W / 2)
                    d = (dx * dx + dy * dy) ** 0.5
                    assert d > ar + 0.15, f"hole ({ax},{ay}) is {d:.3f} mm from a pad"

    print(f"check: B and C rows both {left_edge:.3f} mm inside the module edges "
          f"(skew {skew * 1000:.1f} um); 22.400 spacing and 4.800 stagger hold")


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


def head(name: str, descr: str, tags: str, attr: str) -> list:
    o = [f'(footprint "{name}"', "\t(version 20260206)",
         '\t(generator "gen_som_footprint.py")', '\t(generator_version "10.0")',
         '\t(layer "F.Cu")', f'\t(descr "{descr}")', f'\t(tags "{tags}")',
         f"\t(attr {attr})"]
    return o


def props(name: str, half_h: float) -> list:
    o = []
    for kind, txt, yy, layer in (("Reference", "REF**", -half_h - 1.4, "F.SilkS"),
                                 ("Value", name, half_h + 1.4, "F.Fab")):
        o += [f'\t(property "{kind}" "{txt}"', f"\t\t(at 0 {f(yy)} 0)",
              f'\t\t(layer "{layer}")', f'\t\t(uuid "{uid()}")',
              "\t\t(effects (font (size 1 1) (thickness 0.15)))", "\t)"]
    return o


def build_connector(name: str, near: str, far: str, centroid) -> str:
    """One receptacle: 120 pads named as the module names them, plus 2 NPTH.

    Local frame, origin at the connector's centroid, KiCad Y down. The near row
    is on the left and the far row on the right, which is Figure 6's B A / D C
    order, and the alignment hole sits 1.054 mm inboard of the near row.
    """
    cx, cy = centroid
    xl, xr = -ROW_PITCH / 2, ROW_PITCH / 2
    hx = xl + HOLE_TO_ROW
    half_h = SPAN / 2 + PAD_W / 2

    o = head(name,
             f"Samtec BTH-060-01-L-D-A-K-TR, 2x60 0.5 mm board-to-board receptacle. "
             f"Carries rows {near} and {far} of the PHYTEC PCM-071; pads are named as "
             f"L-1038e.A5 Tables 7-10 name them, NOT Samtec's 1-120. Land pattern from "
             f"Samtec drawing BTH-XXX-XX-X-D-XX REV D and their own KiCad footprint; "
             f"placement from PHYTEC PCM-071_1573-1.dxf. Two of these take the module. "
             f"Must sit at X2 + ({cx - SOM_W / 2:+.3f}, {SOM_H / 2 - cy:+.3f}) -- checked by "
             f"tools/check_pcb_connectors.py. See som.md section 11.",
             "Samtec BTH-060 board-to-board mezzanine 0.5mm PCM-071 phyCORE AM62x",
             "smd")
    o += props(name, half_h)

    npads = 0
    for row, x in ((near, xl), (far, xr)):
        for n in range(1, N + 1):
            # pin 1 at the bottom: local y = +SPAN/2 down to -SPAN/2
            py = SPAN / 2 - (n - 1) * PITCH
            o += [f'\t(pad "{row}{n}" smd rect', f"\t\t(at {f(x)} {f(py)})",
                  f"\t\t(size {f(PAD_L)} {f(PAD_W)})",
                  '\t\t(layers "F.Cu" "F.Mask" "F.Paste")',
                  f"\t\t(solder_mask_margin {f(MASK_MARGIN)})",
                  f'\t\t(uuid "{uid()}")', "\t)"]
            npads += 1
    for hy in (SPAN / 2 + HOLE_END_OFF, -SPAN / 2 - HOLE_END_OFF):
        o += ['\t(pad "" np_thru_hole circle', f"\t\t(at {f(hx)} {f(hy)})",
              f"\t\t(size {f(HOLE_D)} {f(HOLE_D)})", f"\t\t(drill {f(HOLE_D)})",
              '\t\t(layers "F&B.Cu" "*.Mask")', f'\t\t(uuid "{uid()}")', "\t)"]

    # Samtec's own F.Fab body, 35.0 x 5.969, rotated vertical.
    o += rect(-2.9845, -17.5, 2.9845, 17.5, "F.Fab", FAB_W)
    # courtyard reaches past the pads to the holes -- the body covers them
    o += rect(-ROW_PITCH / 2 - PAD_L / 2 - CRT_GAP, -17.5 - CRT_GAP,
              ROW_PITCH / 2 + PAD_L / 2 + CRT_GAP, 17.5 + CRT_GAP, "F.CrtYd", CRT_W)
    # pin-1 bracket below each row, clear of the pads
    sy = SPAN / 2 + PAD_W / 2 + 0.35
    for x in (xl, xr):
        o += line(x - PAD_L / 2, sy, x + PAD_L / 2, sy, "F.SilkS", SILK_W)
    o += [f'\t(fp_text user "{near}1 {far}1"', f"\t\t(at 0 {f(sy + 1.1)} 0)",
          '\t\t(layer "F.SilkS")', f'\t\t(uuid "{uid()}")',
          "\t\t(effects (font (size 0.8 0.8) (thickness 0.12)))", "\t)"]
    o.append(")")
    print(f"  {name}: {npads} pads {near}1-{near}{N} / {far}1-{far}{N} + 2 NPTH")
    return "\n".join(o) + "\n"


def build_module() -> str:
    """`X2`: the module's outline and mounting holes. No pads, no nets.

    The `PCM-071` is a plug-in module fitted by hand after assembly, so it is not
    a placeable part -- `exclude_from_pos_files` keeps it out of the CPL, where a
    designator with no BOM match would be rejected. What it *is* good for is
    layout: the 32 x 43 outline says where the module sits and the two M2.5 holes
    say where the standoffs go, and both are positional facts the connectors
    alone do not carry.
    """
    cx0, cy0 = SOM_W / 2, SOM_H / 2

    def X(x):
        return x - cx0

    def Y(y):
        return cy0 - y

    o = head(MODULE_NAME,
             "PHYTEC phyCORE-AM62x PCM-071, module outline and M2.5 mounting holes. "
             "NO PADS -- the 240 contacts belong to J26/J27, the two BTH-060 receptacles. "
             "The module is fitted by hand after assembly, so this is excluded from the "
             "position file. Outline and hole positions from PCM-071_1573-1.dxf "
             "(BOARD_OUTLINE 32.000 x 43.000; holes at 2.800/2.800 and 29.200/40.200, "
             "2.600 drill, 4.000 plating). Stands 5 mm off the board on two M2.5 F-F "
             "standoffs. See som.md section 11.",
             "PHYTEC phyCORE AM62x PCM-071 SOM module outline mechanical mounting",
             "exclude_from_pos_files")
    o += props(MODULE_NAME, cy0)

    for layer in ("F.Fab", "User.Drawings"):
        o += rect(X(0), Y(0), X(SOM_W), Y(SOM_H), layer, FAB_W)
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
    # where the connectors must land, so a person placing by eye has a target
    for name, (_n, _fr, (mx, my)) in CONNECTORS.items():
        o += rect(X(mx) - 2.9845, Y(my) - 17.5, X(mx) + 2.9845, Y(my) + 17.5,
                  "User.Drawings", FAB_W)
    o.append(")")
    print(f"  {MODULE_NAME}: outline {SOM_W} x {SOM_H}, 2 M2.5 NPTH, 0 pads")
    return "\n".join(o) + "\n"


def main() -> int:
    check()
    OUT_DIR.mkdir(exist_ok=True)
    old = OUT_DIR / "PCM-071_2xBTH-060-01-L-D-A-K.kicad_mod"
    if old.exists():
        old.unlink()
        print(f"  removed {old.name} -- superseded by the two-connector split")
    for name, (near, far, centroid) in CONNECTORS.items():
        (OUT_DIR / f"{name}.kicad_mod").write_text(
            build_connector(name, near, far, centroid))
    (OUT_DIR / f"{MODULE_NAME}.kicad_mod").write_text(build_module())
    return 0


if __name__ == "__main__":
    sys.exit(main())
