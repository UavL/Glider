#!/usr/bin/env python3
"""Route everything that is not GND, shortest nets first.

Order is deliberate. Short local connections claim their space before the long
hauls have to detour round them, which is the cheap version of what a human
does by routing the tight neighbourhoods first.
"""
import argparse
import math
import sys
import time
from collections import defaultdict

import board
import edit
import place
import plane
import route

WIDTH = 0.15          # mm, every routed net; see the caveat in the report
PLANE_NETS = {"GND"}


def track_sexp(layer, a, b, width, net):
    import uuid
    return ('\n\t(segment\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(width %s)\n'
            '\t\t(layer "%s")\n\t\t(net "%s")\n\t\t(uuid "%s")\n\t)\n'
            % (a[0], a[1], b[0], b[1], width, layer, net, uuid.uuid4()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcb", default="../../r2_claude.kicad_pcb")
    ap.add_argument("--limit", type=int, default=0, help="route only N nets")
    ap.add_argument("--budget", type=float, default=0.0, help="seconds")
    a = ap.parse_args()

    b = board.Board(a.pcb)
    r = route.Router(b, place.BOARD)

    # terminals per net
    nets = defaultdict(list)
    for fp in b.footprints.values():
        for p in fp.pads:
            if p.net and p.net not in PLANE_NETS:
                nets[p.net].append((fp, p))
    nets = {n: v for n, v in nets.items() if len(v) >= 2}

    r.stamp_pads()
    # the HV islands forbid pour, not tracks, so they are not stamped here;
    # what must stay clear is the plane, and In1.Cu is never routed on.
    existing = []
    import sexp
    for v in sexp.find_all(b.tree, "via"):
        at = sexp.find(v, "at")
        existing.append((float(at[1]), float(at[2]), str(sexp.get(v, "net", ""))))
    r.stamp_existing_vias(existing)
    print("grid %d x %d x %d layers, %d nets to route"
          % (r.nx, r.ny, len(route.LAYERS), len(nets)))

    def span(v):
        xs = [f.pad_xy(p)[0] for f, p in v]
        ys = [f.pad_xy(p)[1] for f, p in v]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    order = sorted(nets.items(), key=lambda kv: span(kv[1]))
    if a.limit:
        order = order[:a.limit]

    t0 = time.time()
    ok = part = fail = 0
    edges_done = edges_left = 0
    for i, (net, terms) in enumerate(order):
        cells, snap = [], {}
        for f, p in terms:
            c = r._pad_cells(f, p, r.nid(net), shrink=WIDTH / 2)
            if not c:
                continue
            cells.append(c)
            centre = f.pad_xy(p)
            for k in c:
                snap[k] = centre
        if len(cells) < 2:
            continue
        d, left = r.route_net(net, cells, WIDTH)
        edges_done += d
        edges_left += left
        if left == 0:
            ok += 1
        elif d:
            part += 1
        else:
            fail += 1
        if i % 25 == 0 or i == len(order) - 1:
            print("  %4d/%d  %-24s ok=%d partial=%d failed=%d  edges %d/%d  %.0fs"
                  % (i + 1, len(order), net[:24], ok, part, fail,
                     edges_done, edges_done + edges_left, time.time() - t0),
                  flush=True)
        if a.budget and time.time() - t0 > a.budget:
            print("  budget reached, stopping after %d nets" % (i + 1))
            break

    ed = edit.BoardEditor(b)
    for layer, p0, p1, w, net in r.tracks:
        ed.add_before_close(track_sexp(layer, p0, p1, w, net))
    for (x, y, net) in r.vias:
        ed.add_before_close(plane.via(x, y, 0.45, 0.3, net))
    ed.save(a.pcb)
    print("\nnets fully routed : %d" % ok)
    print("nets partial      : %d" % part)
    print("nets failed       : %d" % fail)
    print("edges routed      : %d of %d" % (edges_done, edges_done + edges_left))
    print("tracks/vias added : %d / %d" % (len(r.tracks), len(r.vias)))
    print("wrote %s" % a.pcb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
