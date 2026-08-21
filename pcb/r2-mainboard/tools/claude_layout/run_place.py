#!/usr/bin/env python3
"""Place `r2_claude.kicad_pcb`: draw the outline, run the placer, write it back.

    python3 run_place.py [--iters N] [--seed N]

Idempotent: it always starts from the region seeding, so re-running with the
same seed reproduces the same board.
"""
import argparse
import pickle
import re
import sys

import board
import edit
import place


def set_outline(text, x0, y0, x1, y1):
    """Replace the Edge.Cuts rectangle. layout.md §6.2 step 6."""
    pat = re.compile(r'(\(gr_rect\n\t\t\(start )[-\d.]+ [-\d.]+(\)\n\t\t\(end )'
                     r'[-\d.]+ [-\d.]+(\))')
    new, n = pat.subn(lambda m: "%s%s %s%s%s %s%s" % (
        m.group(1), x0, y0, m.group(2), x1, y1, m.group(3)), text, count=1)
    assert n == 1, "Edge.Cuts rectangle not found"
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcb", default="../../r2_claude.kicad_pcb")
    ap.add_argument("--iters", type=int, default=1500000)
    ap.add_argument("--seed", type=int, default=20260821)
    ap.add_argument("--dump", default=None)
    a = ap.parse_args()

    b = board.Board(a.pcb)
    p = place.Placer(b, seed=a.seed)
    p.seed_regions()
    p.anneal(iters=a.iters, t0=8.0, t1=0.02)
    p.legalize(rounds=4000)
    p.polish(iters=a.iters // 3, t0=0.6)
    p.legalize(rounds=4000)
    p.polish(iters=a.iters // 4, t0=0.15)
    left = p.legalize(rounds=8000)
    rep = p.report()
    rep["keepout"] = round(sum(p.keepout_overlap(r) for r in p.fps), 3)
    rep["legalize_rounds"] = left
    print("placement: %s" % rep)

    # Order matters: footprint edits are byte spans into the original text,
    # so they must be spliced first. Only then can the whole-document rewrites
    # (strip routing, silk -> fab, outline) run on the result.
    ed = edit.BoardEditor(b)
    for ref, fp in p.fps.items():
        ed.place(ref, fp.x, fp.y, fp.rot)
    out = ed.render()
    out, stripped = edit.strip_routing(out)
    out, nsilk = edit.silk_text_to_fab(out)
    out, nx2 = edit.silk_to_user_drawings(out, {"X2"})
    out = set_outline(out, *place.BOARD)
    with open(a.pcb, "w") as fh:
        fh.write(out)
    print("stripped stale routing            : %s" % stripped)
    print("footprint text -> F.Fab           : %d" % nsilk)
    print("X2 silk -> User.Drawings          : %d" % nx2)
    print("outline                           : %.0f x %.0f mm"
          % (place.BOARD[2] - place.BOARD[0], place.BOARD[3] - place.BOARD[1]))
    print("wrote %s" % a.pcb)

    if a.dump:
        pickle.dump({r: (f.x, f.y, f.rot) for r, f in p.fps.items()},
                    open(a.dump, "wb"))

    print("\nproximity, achieved vs documented vs physical floor:")
    print("  %-6s %-6s %7s %7s %7s  %s" %
          ("part", "anchor", "limit", "floor", "actual", ""))
    bad = 0
    for a_, o, lim, floor, d, ok_doc, ok_phys in sorted(
            p.prox_report(), key=lambda r: -(r[4] - max(r[2], r[3]))):
        if ok_doc:
            note = "OK"
        elif ok_phys:
            note = "at the physical limit (rule is impossible)"
        else:
            note = "OVER"
            bad += 1
        print("  %-6s %-6s %7.1f %7.2f %7.2f  %s" % (a_, o, lim, floor, d, note))
    print("\n%d rule(s) beyond even the physical floor" % bad)
    return 0 if (rep["overlap"] == 0 and rep["outside"] == 0 and bad == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
