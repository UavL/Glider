#!/usr/bin/env python3
"""Assert the ground plane is cut away beneath `U9` and `U26`.

`layout.md` §7.1 / `epd-port.md` §11.1: both are inverting buck-boosts whose
pin 2 is labelled `GND` but sits at -VGL (about -20 V) and -VN (about -15 V).
Copper pour reaching under either part destroys it.

`check_pcb.py` already refuses a *zone* on `-VGL`/`-VN`. This checks the other
half -- that no *filled* `GND` copper, on any layer, covers the island -- by
sampling a grid across each island and testing point-in-polygon against every
filled polygon KiCad actually produced. It needs a board whose zones have been
filled (`kicad-cli pcb drc --refill-zones --save-board`).
"""
import sys

import board
import sexp


def filled_polys(tree, net="GND"):
    out = []
    for z in sexp.find_all(tree, "zone"):
        if str(sexp.get(z, "net", "")) != net and str(sexp.get(z, "net_name", "")) != net:
            continue
        for fp in sexp.find_all(z, "filled_polygon"):
            pts = sexp.find(fp, "pts")
            if pts is None:
                continue
            poly = [(float(p[1]), float(p[2])) for p in sexp.find_all(pts, "xy")]
            if len(poly) > 2:
                out.append((str(sexp.get(fp, "layer", "?")), poly))
    return out


def inside(pt, poly):
    x, y = pt
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-18) + xi:
            c = not c
        j = i
    return c


def main(path, margin=1.5):
    b = board.Board(path)
    polys = filled_polys(b.tree)
    print("filled GND polygons: %d on layers %s"
          % (len(polys), sorted({l for l, _ in polys})))
    if not polys:
        print("FAIL: no filled GND copper found -- run kicad-cli pcb drc "
              "--refill-zones --save-board first")
        return 1
    bad = 0
    for ref, net, _why in (("U9", "-VGL", ""), ("U26", "-VN", "")):
        fp = b.footprints[ref]
        x0, y0, x1, y1 = fp.courtyard_box(margin)
        hits = tot = 0
        yy = y0 + 0.15
        while yy < y1 - 0.15:
            xx = x0 + 0.15
            while xx < x1 - 0.15:
                tot += 1
                if any(inside((xx, yy), p) for _, p in polys):
                    hits += 1
                xx += 0.25
            yy += 0.25
        ok = hits == 0
        bad += 0 if ok else 1
        print("%-4s %-5s island (%.2f, %.2f)-(%.2f, %.2f): %d/%d sample points "
              "carry GND copper -> %s"
              % (ref, net, x0, y0, x1, y1, hits, tot,
                 "CUT AWAY, correct" if ok else "*** PLANE UNDER THE PART ***"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "../../r2_claude.kicad_pcb"))
