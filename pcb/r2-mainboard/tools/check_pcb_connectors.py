#!/usr/bin/env python3
"""Assert `J26`/`J27` sit exactly on the two connectors inside `X2`'s footprint.

Run before every fabrication order, once `r2.kicad_pcb` exists.

`X2` carries all 240 pads; `J26` and `J27` carry no pads at all and exist so
that each physical receptacle gets its own row in the position file (`som.md`
§10). That split is what makes the board assemblable -- and it is also the one
thing about it that can silently go wrong, because nothing in KiCad ties the
three footprints together. Drag `J26` 2 mm and the board still passes DRC, the
BOM is still right, and the assembler puts a 120-pin 0.5 mm connector 2 mm off
its pads.

So the relationship is checked instead of trusted:

    J26 = X2 + (-11.200, -2.400)
    J27 = X2 + (+11.200, +2.400)

which is PHYTEC's 22.400 mm connector spacing and 4.800 mm stagger
(`PCM-071_1573-1.dxf`), split symmetrically about the module's centre. **This is
a stronger guarantee than the single-footprint arrangement it replaced**, which
was structurally unbreakable but also unverifiable -- there was nothing to check
because there was nothing that could differ.

Also checked, because each has bitten a real board somewhere:

* all three are on the **same side** -- a mirrored `J26` places the connector
  on the back of the board;
* rotations agree, so the CPL angles are consistent;
* `X2` is `exclude_from_pos_files` and `J26`/`J27` are not, which is the whole
  BOM/CPL bargain;
* `J26`/`J27` really have **no pads**, since pads here would collide with `X2`'s.

Exit status is 0 when everything holds and 1 otherwise, so it can gate a
release script.
"""
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PCB = HERE.parent / "r2.kicad_pcb"

EXPECT = {"J26": (-11.200, -2.400), "J27": (+11.200, +2.400)}
TOL = 0.001          # mm; these are generated numbers, not measured ones
ANCHOR = "X2"


def footprints(text: str):
    """-> {reference: {at, layer, attrs, npads}}"""
    out = {}
    for m in re.finditer(r'\n\t\(footprint ', text):
        i = m.start() + 2
        d, j = 0, i
        while True:
            if text[j] == "(":
                d += 1
            elif text[j] == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        blk = text[i:j + 1]
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
        at = re.search(r'\n\t\t\(at ([\d.-]+) ([\d.-]+)(?: ([\d.-]+))?\)', blk)
        lay = re.search(r'\n\t\t\(layer "([^"]+)"\)', blk)
        if not (ref and at):
            continue
        out[ref.group(1)] = {
            "at": (float(at.group(1)), float(at.group(2))),
            "rot": float(at.group(3) or 0.0),
            "layer": lay.group(1) if lay else "?",
            "attr": re.search(r'\n\t\t\(attr ([^)]*)\)', blk),
            "npads": len(re.findall(r'\n\t\t\(pad ', blk)),
        }
        out[ref.group(1)]["attr"] = (out[ref.group(1)]["attr"].group(1)
                                     if out[ref.group(1)]["attr"] else "")
    return out


def main() -> int:
    if not PCB.exists():
        print(f"{PCB.name} does not exist yet -- Stage D has not started. "
              "Nothing to check, and that is not a failure.")
        return 0

    fps = footprints(PCB.read_text())
    bad = []

    missing = [r for r in (ANCHOR, *EXPECT) if r not in fps]
    if missing:
        print(f"FAIL: not on the board: {', '.join(missing)}")
        return 1

    a = fps[ANCHOR]
    ax, ay = a["at"]
    ar = math.radians(a["rot"])
    cos, sin = math.cos(ar), math.sin(ar)

    for ref, (dx, dy) in EXPECT.items():
        f = fps[ref]
        # the offset is defined in X2's frame, so rotate it with X2
        ex = ax + dx * cos - dy * sin
        ey = ay + dx * sin + dy * cos
        gx, gy = f["at"]
        err = math.hypot(gx - ex, gy - ey)
        ok = err <= TOL
        print(f"  {ref}: at ({gx:.3f}, {gy:.3f})  expected ({ex:.3f}, {ey:.3f})  "
              f"error {err * 1000:.1f} um  {'OK' if ok else 'FAIL'}")
        if not ok:
            bad.append(f"{ref} is {err:.3f} mm from where it belongs")
        if f["layer"] != a["layer"]:
            bad.append(f"{ref} is on {f['layer']} and {ANCHOR} is on {a['layer']}")
        if abs((f["rot"] - a["rot"] + 180) % 360 - 180) > 0.01:
            bad.append(f"{ref} is rotated {f['rot']}, {ANCHOR} is {a['rot']}")
        if f["npads"]:
            bad.append(f"{ref} has {f['npads']} pads; it must have none "
                       f"(they would collide with {ANCHOR}'s)")
        if "exclude_from_pos_files" in f["attr"]:
            bad.append(f"{ref} is excluded from the position file, so it gets no "
                       f"CPL row and the connector never gets placed")

    if "exclude_from_pos_files" not in a["attr"]:
        bad.append(f"{ANCHOR} is NOT excluded from the position file -- it will "
                   f"appear as a CPL designator with no BOM match, which JLCPCB "
                   f"rejects")
    if fps[ANCHOR]["npads"] != 246:
        bad.append(f"{ANCHOR} has {fps[ANCHOR]['npads']} pads, expected 246 "
                   f"(240 SMD + 4 alignment + 2 M2.5)")

    if bad:
        print("\nFAIL:")
        for b in bad:
            print(f"  - {b}")
        return 1
    print("\nOK: both receptacles are on their pads, same side, same rotation, "
          "and the BOM/CPL split is intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
