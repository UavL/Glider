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
    pat = re.compile(r'^327.{17}(.{6})-(.{4}).*?X([+-]\d+)Y([+-]\d+)')
    for line in open(path):
        m = pat.match(line)
        if not m:
            continue
        ref = m.group(1).strip()
        pin = m.group(2).strip()
        x = int(m.group(3)) * MM
        y = -int(m.group(4)) * MM
        out.setdefault((ref, pin), []).append((x, y))
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
            d = min(max(abs(tx - ox), abs(ty - oy)) for tx, ty in cand)
            checked += 1
            if d > worst:
                worst, worst_at = d, (key, (ox, oy), fp.rot, fp.layer)
    print("pads compared     : %d" % checked)
    print("not in IPC export : %d (NPTH/mechanical carry no net record)" % missing)
    print("worst error       : %.6f mm" % worst)
    if worst_at:
        print("  at %s ours=%s rot=%s layer=%s" % worst_at)
    # IPC-D-356 rounds to 0.0001 in = 2.54 um, so under ~3 um is exact
    ok = worst < 0.003
    print("VERDICT           :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
