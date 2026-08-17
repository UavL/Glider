#!/usr/bin/env python3
"""Generate r2.pretty/SolderPads_1x03_P3.50mm_Wire.kicad_mod

Three bare copper pads for soldering the cell's leads straight to the board, as
an alternative to `J2` (Molex Pico-Lock). Both live on the same three nets --
`+VBAT`, `CHG_TS`, `GND` -- so fitting either, or both, is electrically the
same. docs/battery.md §9.1.

Why this exists at all: `battery.md` §10.9 wanted a connector for bring-up, when
the cell gets unplugged often, and pads for the thinner, more reliable joint
once the design settles. The `PL706090`'s own JST 1.25 mm plug is rated 1 A
against ~2 A of charge current, so the pads are also the escape hatch if
re-terminating the pack turns out badly.

Geometry, chosen for a stranded lead rather than a part:

  pad        2.0 x 3.0 mm, 3.5 mm pitch -- room to lay a tinned 22-24 AWG
             conductor along the pad and reflow it with an iron
  no paste   these are hand-soldered. A stencil aperture over a 6 mm^2 pad
             leaves a solder bump that gets in the way of laying a wire flat.
  mask       normal expansion; the pads are NSMD like everything else here
  silk       "+", "T", "-" so the polarity is readable with the cell in hand.
             Getting BAT+ and BAT- backwards on a 5 Ah pack is not a small
             mistake, and the connector's polarisation does not protect these.

Pad 2 is the thermistor, not a second power pin: `battery.md` §10.2 established
that no register disables the charger's TS comparator, so the NTC is mandatory
hardware and the pads have to carry it.
"""
from __future__ import annotations

import pathlib
import uuid

OUT = (pathlib.Path(__file__).resolve().parent.parent / "r2.pretty"
       / "SolderPads_1x03_P3.50mm_Wire.kicad_mod")
NAME = "SolderPads_1x03_P3.50mm_Wire"

PITCH = 3.5
PAD_W, PAD_H = 2.0, 3.0
LABELS = ("+", "T", "-")
CRT = 0.25


def f(v: float) -> str:
    return f"{v:g}"


def build() -> str:
    span = PITCH * 2 + PAD_W                      # 9.0
    hx, hy = span / 2 + CRT, PAD_H / 2 + CRT
    o = [
        f'(footprint "{NAME}"',
        "\t(version 20240108)",
        '\t(generator "gen_solderpads.py")',
        '\t(layer "F.Cu")',
        '\t(descr "Three bare copper pads for soldering a battery lead '
        'directly: 2.0x3.0 mm on 3.5 mm pitch, no paste, hand-solder only. '
        'Pad 1 BAT+, pad 2 NTC/thermistor, pad 3 BAT-. Alternative to the '
        'Pico-Lock J2 on the same nets -- see docs/battery.md §9.1.")',
        '\t(tags "solder pad wire battery hand-solder")',
        "\t(attr exclude_from_pos_files)",
    ]
    for i, (lbl, dx) in enumerate(zip(LABELS, (-PITCH, 0.0, PITCH)), start=1):
        # no F.Paste: hand-soldered, and a stencil aperture here just leaves a
        # bump under the wire
        o += [
            f'\t(pad "{i}" smd rect',
            f"\t\t(at {f(dx)} 0)",
            f"\t\t(size {f(PAD_W)} {f(PAD_H)})",
            '\t\t(layers "F.Cu" "F.Mask")',
            f'\t\t(uuid "{uuid.uuid4()}")',
            "\t)",
            f'\t(fp_text user "{lbl}"',
            f"\t\t(at {f(dx)} {f(-PAD_H / 2 - 0.9)} 0)",
            '\t\t(layer "F.SilkS")',
            f'\t\t(uuid "{uuid.uuid4()}")',
            "\t\t(effects (font (size 0.8 0.8) (thickness 0.15)))",
            "\t)",
        ]
    o += [
        "\t(fp_rect",
        f"\t\t(start {f(-hx)} {f(-hy)})",
        f"\t\t(end {f(hx)} {f(hy)})",
        '\t\t(stroke (width 0.05) (type solid))',
        "\t\t(fill none)",
        '\t\t(layer "F.CrtYd")',
        f'\t\t(uuid "{uuid.uuid4()}")',
        "\t)",
    ]
    for layer, kind, txt, yy in (("F.SilkS", "reference", "REF**", -hy - 1.9),
                                 ("F.Fab", "value", NAME, hy + 0.9)):
        o += [
            f'\t(fp_text {kind} "{txt}"',
            f"\t\t(at 0 {f(yy)} 0)",
            f'\t\t(layer "{layer}")',
            f'\t\t(uuid "{uuid.uuid4()}")',
            "\t\t(effects (font (size 0.7 0.7) (thickness 0.12)))",
            "\t)",
        ]
    o.append(")")
    return "\n".join(o) + "\n"


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build())
    print(f"wrote {OUT.name}: 3 pads {PAD_W}x{PAD_H} mm, {PITCH} mm pitch, "
          f"no paste")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
