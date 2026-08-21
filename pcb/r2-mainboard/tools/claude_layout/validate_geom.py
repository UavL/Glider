#!/usr/bin/env python3
"""Check our pad-position maths against KiCad's own IPC-D-356 export.

The rotation sign convention is the one thing here that cannot be reasoned out
safely from the file format alone, so it is measured instead: every pad in the
design is compared against the coordinates KiCad itself writes.
"""
import re
import sys

import board

MM = 25.4 / 10000.0


def d356_pads(path):
    """{(ref, pin): (x_mm, y_mm)} from an IPC-D-356 export."""
    out = {}
    # 327 | net name (17) | refdes (6) | '-' | pin (4) | ... | X+nnnnnnY-nnnnnn
    pat = re.compile(r'^327.{17}(.{6})-(.{4}).*?X([+-]\d+)Y([+-]\d+)'
                     r'X(\d+)Y(\d+)')
    for line in open(path):
        m = pat.match(line)
        if not m:
            continue
        ref = m.group(1).strip()
        pin = m.group(2).strip()
        x = int(m.group(3)) * MM
        y = -int(m.group(4)) * MM
        w = int(m.group(5)) * MM
        h = int(m.group(6)) * MM
        out.setdefault((ref, pin), []).append((x, y, w, h))
    return out


def main(pcb, d356):
    b = board.Board(pcb)
    truth = d356_pads(d356)
    # Pad numbers are not unique -- mounting pads share "MP"/"SH"/"" -- so match
    # position multisets per (ref, pin) instead of assuming one pad per key.
    checked = worst = 0
    worst_at = None
    missing = 0
    for fp in b.footprints.values():
        for p in fp.pads:
            key = (fp.ref, p.number)
            cand = truth.get(key)
            if not cand:
                missing += 1
                continue
            ox, oy = fp.pad_xy(p)
            d = min(max(abs(tx - ox), abs(ty - oy))
                    for tx, ty, _tw, _th in cand)
            checked += 1
            if d > worst:
                worst, worst_at = d, (key, (ox, oy), fp.rot, fp.layer)
    # IPC-D-356 gives pad dimensions in the pad's own frame, so it cannot
    # check that we rotate them correctly. This can: in a sane board no two
    # pads of different nets overlap, and a transposed pad rectangle breaks
    # that immediately -- which is how the U26 1.32 x 0.60 / 0.60 x 1.32 mix-up
    # was caught after DRC blamed the router for driving a track through -VN.
    boxes = []
    for fp in b.footprints.values():
        for p in fp.pads:
            if p.kind == "np_thru_hole":
                continue
            x, y = fp.pad_xy(p)
            w, h = fp.pad_size(p)
            boxes.append((x - w / 2, y - h / 2, x + w / 2, y + h / 2,
                          p.net, fp.ref, p.number, fp.layer, p.kind))
    boxes.sort()
    overlaps = 0
    worst_pair = None
    for i, A in enumerate(boxes):
        for B in boxes[i + 1:]:
            if B[0] >= A[2]:
                break
            if A[4] == B[4] or A[4] == "" or B[4] == "":
                continue
            if A[7] != B[7] and A[8] == "smd" and B[8] == "smd":
                continue
            dx = min(A[2], B[2]) - max(A[0], B[0])
            dy = min(A[3], B[3]) - max(A[1], B[1])
            if dx > 1e-6 and dy > 1e-6:
                overlaps += 1
                if worst_pair is None:
                    worst_pair = (A[5], A[6], A[4], B[5], B[6], B[4])
    print("pads compared     : %d" % checked)
    print("different-net pad overlaps: %d %s"
          % (overlaps, worst_pair if worst_pair else ""))
    print("not in IPC export : %d (NPTH/mechanical carry no net record)" % missing)
    print("worst position err: %.6f mm" % worst)
    if worst_at:
        print("  at %s ours=%s rot=%s layer=%s" % worst_at)
    # IPC-D-356 rounds to 0.0001 in = 2.54 um, so under ~3 um is exact
    ok = worst < 0.003 and overlaps == 0
    print("VERDICT           :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
