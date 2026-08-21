#!/usr/bin/env python3
"""Add the ground pours, the two HV island cut-outs and the stitching vias."""
import argparse
import math
import sys

import board
import edit
import place
import plane


def free_for_via(b, x, y, clear=0.55):
    """True when a stitching via at (x, y) clears every pad and courtyard."""
    for fp in b.footprints.values():
        bx0, by0, bx1, by1 = fp.courtyard_box(0.2)
        if bx0 <= x <= bx1 and by0 <= y <= by1:
            return False
        for p in fp.pads:
            px, py = fp.pad_xy(p)
            pw, ph = fp.pad_size(p)
            if abs(px - x) < pw / 2 + clear and abs(py - y) < ph / 2 + clear:
                return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcb", default="../../r2_claude.kicad_pcb")
    ap.add_argument("--pitch", type=float, default=5.0)
    a = ap.parse_args()

    b = board.Board(a.pcb)
    ed = edit.BoardEditor(b)
    # start from bare copper so the script is re-runnable
    ed.text, stripped = edit.strip_routing(ed.text)
    if any(stripped.values()):
        print("cleared previous pours/vias: %s" % stripped)
    x0, y0, x1, y1 = place.BOARD
    inset = 0.5
    poly = plane.rect(x0 + inset, y0 + inset, x1 - inset, y1 - inset)

    # 1. the pours
    for layer in ("F.Cu", "In1.Cu", "B.Cu"):
        ed.add_before_close(plane.gnd_zone(layer, poly, "GND_%s" % layer))

    # 2. the two islands, before anything can pour into them
    islands = []
    for ref, net, why in plane.HV_ISLANDS:
        fp = b.footprints[ref]
        bx0, by0, bx1, by1 = fp.courtyard_box(plane.ISLAND_MARGIN)
        islands.append((bx0, by0, bx1, by1))
        ed.add_before_close(plane.keepout_zone(
            plane.rect(bx0, by0, bx1, by1),
            "HV island %s (%s) - no plane beneath: %s" % (ref, net, why)))
        print("HV island %-4s %-5s  (%.2f, %.2f) - (%.2f, %.2f)"
              % (ref, net, bx0, by0, bx1, by1))

    # 3. stitching vias on a grid, skipping pads, courtyards and the islands
    n = 0
    yy = y0 + 3.0
    while yy < y1 - 3.0:
        xx = x0 + 3.0
        while xx < x1 - 3.0:
            if (free_for_via(b, xx, yy)
                    and not any(ix0 <= xx <= ix1 and iy0 <= yy <= iy1
                                for ix0, iy0, ix1, iy1 in islands)):
                ed.add_before_close(plane.via(xx, yy))
                n += 1
            xx += a.pitch
        yy += a.pitch
    print("stitching vias placed: %d" % n)

    ed.save(a.pcb)
    print("wrote %s" % a.pcb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
