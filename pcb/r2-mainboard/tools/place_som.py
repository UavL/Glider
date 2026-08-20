#!/usr/bin/env python3
"""Snap `J26`/`J27` onto `X2` exactly, then group all three so they move as one.

Put `X2` wherever you want the module. Run this. The two receptacles land on
their exact offsets and the three become a KiCad group, so from then on you drag
the SoM, not three parts that have to agree with each other.

**Why this is a tool and not an instruction.** The two connectors are 22.400 mm
apart *and* staggered 4.800 mm (PHYTEC's `PCM-071_1573-1.dxf`), and both offsets
are exact negatives of each other about `X2`'s origin. That symmetry is the
trap: an error of the wrong kind does not shift a connector slightly, it puts
`J26` where `J27` belongs. The module still seats -- the alignment holes line up
either way -- and every one of 240 nets is on the wrong receptacle. Nothing in
KiCad checks this, and it is invisible in the 3D view.

The offsets, in `X2`'s own frame:

    J26   (-11.200, -2.400)
    J27   (+11.200, +2.400)

**The rotation convention was settled from measurement, not reasoning.** KiCad's
`at` angle is counter-clockwise *as displayed*, and the file's y axis points
down, so a positive angle is mathematically clockwise:

    x' = px + dx*cos + dy*sin
    y' = py - dx*sin + dy*cos

Both signs were checked against a drill export of the real board -- `J26`'s
alignment holes are asymmetric in x, so they distinguish the two conventions.
`tools/check_pcb_connectors.py` carries the full note; it had this backwards
until 2026-08-21 and reported a hand-placed pair that was 0.9 mm out as 22 mm
out, which is what prompted writing this.

Safe to re-run. Backs up the board, refuses to run while KiCad is open (it
rewrites the file on exit), and verifies its own result by re-running the
geometry check.
"""
from __future__ import annotations

import math
import pathlib
import re
import shutil
import subprocess
import sys
import uuid as _uuid
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent
PCB = PROJ / "r2.kicad_pcb"

ANCHOR = "X2"
OFFSETS = {"J26": (-11.200, -2.400), "J27": (+11.200, +2.400)}
GROUP_NAME = "SoM: X2 + J26 + J27"


def fp_blocks(text: str) -> dict:
    """reference -> (start, end) of its top-level `(footprint ...)` block."""
    out = {}
    for m in re.finditer(r"\n\t\(footprint ", text):
        i = m.start() + 1
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
        if ref:
            out[ref.group(1)] = (i, j + 1)
    return out


def at_of(blk: str):
    m = re.search(r"\n\t\t\(at ([\d.-]+) ([\d.-]+)(?: ([\d.-]+))?\)", blk)
    assert m, "footprint has no (at ...)"
    return float(m.group(1)), float(m.group(2)), float(m.group(3) or 0.0)


def uuid_of(blk: str) -> str:
    m = re.search(r'\n\t\t\(uuid "([0-9a-f-]+)"\)', blk)
    assert m, "footprint has no uuid"
    return m.group(1)


def place(px, py, rot, dx, dy):
    r = math.radians(rot)
    c, s = math.cos(r), math.sin(r)
    return px + dx * c + dy * s, py - dx * s + dy * c


def set_at(blk: str, x, y, rot) -> str:
    return re.sub(r"(\n\t\t\(at )[\d.-]+ [\d.-]+(?: [\d.-]+)?(\))",
                  lambda m: f"{m.group(1)}{x:g} {y:g} {rot:g}{m.group(2)}",
                  blk, count=1)


def main() -> int:
    if not PCB.exists():
        print(f"{PCB.name} does not exist yet."); return 1
    # `pgrep -f <pattern>` matches this script's own command line as often as
    # KiCad's, so check the process NAME and KiCad's own lock files instead.
    running = subprocess.run(["pgrep", "-x", "kicad"], capture_output=True).returncode == 0
    locks = list(PROJ.glob("~*.lck"))
    if running or locks:
        why = "KiCad is running" if running else f"lock files present: {[l.name for l in locks]}"
        print(f"FAIL: {why}. It rewrites the board on exit, so close it first.")
        return 1

    text = PCB.read_text()
    blocks = fp_blocks(text)
    missing = [r for r in (ANCHOR, *OFFSETS) if r not in blocks]
    if missing:
        print(f"FAIL: not on the board: {', '.join(missing)}"); return 1

    ai, aj = blocks[ANCHOR]
    ax, ay, arot = at_of(text[ai:aj])
    print(f"{ANCHOR} is at ({ax:g}, {ay:g}) rotated {arot:g}°\n")

    # --- move the two receptacles ------------------------------------------
    edits = []
    for ref, (dx, dy) in OFFSETS.items():
        i, j = blocks[ref]
        blk = text[i:j]
        ox, oy, orot = at_of(blk)
        tx, ty = place(ax, ay, arot, dx, dy)
        moved = math.hypot(tx - ox, ty - oy)
        edits.append((i, j, set_at(blk, tx, ty, arot)))
        print(f"  {ref}: ({ox:g}, {oy:g}) @{orot:g}°  ->  "
              f"({tx:g}, {ty:g}) @{arot:g}°   moved {moved * 1000:.0f} µm")

    # --- X2 must stay out of the position file -----------------------------
    ax_blk = text[ai:aj]
    if "exclude_from_pos_files" not in ax_blk:
        if re.search(r"\n\t\t\(attr [^)]*\)", ax_blk):
            new = re.sub(r"(\n\t\t\(attr )([^)]*)(\))",
                         r"\1\2 exclude_from_pos_files\3", ax_blk, count=1)
        else:
            new = ax_blk.replace(f'\n\t\t(at {ax:g}',
                                 '\n\t\t(attr exclude_from_pos_files allow_missing_courtyard)'
                                 f'\n\t\t(at {ax:g}', 1)
        edits.append((ai, aj, new))
        print(f"\n  {ANCHOR}: added exclude_from_pos_files "
              "(KiCad drops a flag-only attr on import)")

    for i, j, blk in sorted(edits, reverse=True):
        text = text[:i] + blk + text[j:]

    # --- group them, so they move together from now on ---------------------
    if GROUP_NAME not in text:
        members = [uuid_of(text[slice(*fp_blocks(text)[r])])
                   for r in (ANCHOR, *OFFSETS)]
        grp = (f'\n\t(group "{GROUP_NAME}"\n\t\t(uuid "{_uuid.uuid4()}")\n'
               "\t\t(members\n"
               + "".join(f'\t\t\t"{u}"\n' for u in members)
               + "\t\t)\n\t)")
        k = text.rstrip().rfind(")")
        text = text[:k] + grp + "\n" + text[k:]
        print(f"\n  grouped: {ANCHOR} + {' + '.join(OFFSETS)} now move as one")
    else:
        print(f"\n  already grouped")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(PCB, PCB.with_suffix(f".kicad_pcb.bak-{stamp}"))
    PCB.write_text(text)
    print(f"  backed up -> {PCB.name}.bak-{stamp}")

    # --- prove it -----------------------------------------------------------
    print()
    r = subprocess.run([sys.executable, str(HERE / "check_pcb_connectors.py")],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stderr.write(r.stderr)
        print("\nFAIL: the check does not agree — board left in place, "
              "restore the .bak if needed.")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
