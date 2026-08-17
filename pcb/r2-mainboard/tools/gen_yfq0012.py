#!/usr/bin/env python3
"""Generate r2.pretty/Texas_YFQ0012_DSBGA-12_1.91x1.39mm_Layout3x4_P0.4mm.kicad_mod

The LM3630A's package (TI YFQ0012, 12-bump DSBGA). KiCad 10 has no match:

  Texas_DSBGA-12_1.36x1.86mm_Layout3x4_P0.5mm   right grid, WRONG PITCH (0.5)
  Maxim_WLP-12_2.008x1.608mm_Layout4x3_P0.4mm   right pitch, wrong pad names
                                                (A1..C4, we need A1..D3)

**The pitch is 0.4 mm and this is only legible in the drawing, not the text.**
lm3630a.pdf p.50 (YFQ0012xxx, TMD12XXX Rev B) gives D and E as text but prints
the pitch only as "0.4 TYP" inside the graphic, in both directions. Rendered at
300 dpi and read. Inferring it from the body size would have given 0.5 mm --
3 x 0.5 = 1.5 against D = 1.91 looks plausible until you check the other axis --
and a wrong BGA land pattern is not reworkable.

Geometry, all from that drawing:

  D  = 1.94 max / 1.88 min  -> 1.91 nominal, spans the 4 rows A..D
  E  = 1.42 max / 1.36 min  -> 1.39 nominal, spans the 3 columns 1..3
  pitch                      0.4 mm TYP, both axes
  ball                       12x dia 0.28 / 0.25
  LAND PATTERN RECOMMENDATION  12x dia 0.24 / 0.21

The land is specified as *copper*, so these are non-solder-mask-defined pads and
the mask opening is left to the board's own expansion rule. Orientation follows
the datasheet's §5 "Top View" pin table exactly -- rows A..D run down, columns
1..3 run across, A1 top-left:

      col 1     col 2     col 3
  A   SDA       SCL       SW
  B   HWEN      INTN      GND
  C   PWM       SEL       IN
  D   OVP       ILED2     ILED1
"""
from __future__ import annotations

import pathlib
import uuid

OUT = (pathlib.Path(__file__).resolve().parent.parent / "r2.pretty"
       / "Texas_YFQ0012_DSBGA-12_1.91x1.39mm_Layout3x4_P0.4mm.kicad_mod")

NAME = "Texas_YFQ0012_DSBGA-12_1.91x1.39mm_Layout3x4_P0.4mm"
PITCH = 0.4
PAD_D = 0.24            # land pattern recommendation, max of 0.24/0.21
ROWS = "ABCD"           # 4, down the page, spanning D = 1.91
COLS = "123"            # 3, across the page, spanning E = 1.39
BODY_X, BODY_Y = 1.39 / 2, 1.91 / 2      # 0.695, 0.955
CRT_X, CRT_Y = BODY_X + 0.25, BODY_Y + 0.25


def f(v: float) -> str:
    return f"{v:g}"


def build() -> str:
    o = [
        f'(footprint "{NAME}"',
        "\t(version 20240108)",
        '\t(generator "gen_yfq0012.py")',
        '\t(layer "F.Cu")',
        '\t(descr "Texas Instruments YFQ0012, 12-bump DSBGA, 1.91x1.39mm body, '
        '0.4mm pitch, 4 rows A-D x 3 columns 1-3. LM3630A. Land pattern from '
        'lm3630a.pdf drawing TMD12XXX Rev B (p.50): 12x dia 0.24/0.21 copper '
        'land, pitch 0.4 TYP both axes. Pitch is printed only in the graphic, '
        'not in the datasheet text.")',
        '\t(tags "DSBGA WLCSP YFQ0012 LM3630A wafer level chip scale")',
        "\t(attr smd)",
    ]

    # --- pads: A1 top-left, rows down, columns across ---------------------
    for ri, r in enumerate(ROWS):
        y = (ri - (len(ROWS) - 1) / 2) * PITCH        # -0.6 -0.2 +0.2 +0.6
        for ci, c in enumerate(COLS):
            x = (ci - (len(COLS) - 1) / 2) * PITCH    # -0.4  0.0 +0.4
            o += [
                f'\t(pad "{r}{c}" smd circle',
                f"\t\t(at {f(x)} {f(y)})",
                f"\t\t(size {f(PAD_D)} {f(PAD_D)})",
                '\t\t(layers "F.Cu" "F.Paste" "F.Mask")',
                f'\t\t(uuid "{uuid.uuid4()}")',
                "\t)",
            ]

    # --- fab body outline --------------------------------------------------
    for a, b in (((-BODY_X, -BODY_Y), (BODY_X, -BODY_Y)),
                 ((BODY_X, -BODY_Y), (BODY_X, BODY_Y)),
                 ((BODY_X, BODY_Y), (-BODY_X, BODY_Y)),
                 ((-BODY_X, BODY_Y), (-BODY_X, -BODY_Y))):
        o += [
            "\t(fp_line",
            f"\t\t(start {f(a[0])} {f(a[1])})",
            f"\t\t(end {f(b[0])} {f(b[1])})",
            '\t\t(stroke (width 0.1) (type solid))',
            '\t\t(layer "F.Fab")',
            f'\t\t(uuid "{uuid.uuid4()}")',
            "\t)",
        ]

    # --- A1 marker: silk dot outside the courtyard, on the A1 side ---------
    o += [
        "\t(fp_circle",
        f"\t\t(center {f(-BODY_X - 0.25)} {f(-BODY_Y - 0.25)})",
        f"\t\t(end {f(-BODY_X - 0.15)} {f(-BODY_Y - 0.25)})",
        '\t\t(stroke (width 0.1) (type solid))',
        "\t\t(fill solid)",
        '\t\t(layer "F.SilkS")',
        f'\t\t(uuid "{uuid.uuid4()}")',
        "\t)",
    ]

    # --- courtyard ---------------------------------------------------------
    o += [
        "\t(fp_rect",
        f"\t\t(start {f(-CRT_X)} {f(-CRT_Y)})",
        f"\t\t(end {f(CRT_X)} {f(CRT_Y)})",
        '\t\t(stroke (width 0.05) (type solid))',
        "\t\t(fill none)",
        '\t\t(layer "F.CrtYd")',
        f'\t\t(uuid "{uuid.uuid4()}")',
        "\t)",
    ]

    # --- reference / value -------------------------------------------------
    for layer, kind, txt, yy in (("F.SilkS", "reference", "REF**", -CRT_Y - 0.6),
                                 ("F.Fab", "value", NAME, CRT_Y + 0.6)):
        o += [
            f'\t(fp_text {kind} "{txt}"',
            f"\t\t(at 0 {f(yy)} 0)",
            f'\t\t(layer "{layer}")',
            f'\t\t(uuid "{uuid.uuid4()}")',
            "\t\t(effects (font (size 0.5 0.5) (thickness 0.08)))",
            "\t)",
        ]
    o.append(")")
    return "\n".join(o) + "\n"


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build())
    print(f"wrote {OUT.name}: 12 pads A1-D3, {PITCH} mm pitch, "
          f"dia {PAD_D} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
