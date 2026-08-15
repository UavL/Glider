#!/usr/bin/env python3
"""Re-pack the sheet symbols on r2.kicad_sch so their boxes do not overlap.

`set_sheet_pins` grows a sheet's box to fit its pins, and the boxes were first
placed by hand on an empty hierarchy where every sheet was the same small size.
As sheets gain interface nets they outgrow that grid -- `mcu` (41 pins) and
`epd` (36) both did. This keeps each sheet in the column it was put in and only
re-stacks it vertically, so the hand-made left-to-right arrangement survives.

Positions only. Nothing else on the root sheet is touched.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ROOT = HERE.parent / "r2.kicad_sch"
TOP = 30.48
GAP = 12.7


def boxes(text: str):
    """-> [(name, x, y, w, h)] for every sheet symbol on the root."""
    out = []
    for m in re.finditer(
            r'\(sheet\n\t\t\(at ([-\d.]+) ([-\d.]+)\)\n\t\t\(size ([-\d.]+) ([-\d.]+)\)',
            text):
        x, y, w, h = (float(v) for v in m.groups())
        blk_end = text.index("\n\t)\n", m.start())
        name = re.search(r'\(property "Sheetname" "([^"]*)"',
                         text[m.start():blk_end]).group(1)
        out.append((name, x, y, w, h))
    return out


def overlaps(text: str):
    """-> [(name_a, name_b)] for every pair of sheet boxes that intersect.

    This is the check that catches the worst bug this hierarchy can have, and
    **ERC is silent on it.** `set_sheet_pins` grows a box to fit its pins; if
    the taller box reaches the sheet below, `wire_root`'s stubs and labels land
    inside the neighbour's box and the two sheets' nets merge. WP5 lost seven
    FPGA balls to `VCOM_MEA_EN` and friends that way, and WP7 repeated it
    exactly -- `dpi_in` grew from 25.4 mm to 63.5 mm, swallowed `epd`, and
    shorted seven `DPI_*` nets to the panel bus. Both times the schematic
    stayed perfectly legal.
    """
    bs = boxes(text)
    bad = []
    for i, (n1, x1, y1, w1, h1) in enumerate(bs):
        for n2, x2, y2, w2, h2 in bs[i + 1:]:
            if x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + h2 and y2 < y1 + h1:
                bad.append((n1, n2))
    return bad


def assert_no_overlap(text: str) -> None:
    bad = overlaps(text)
    if bad:
        pairs = ", ".join(f"{a} <-> {b}" for a, b in bad)
        raise AssertionError(
            f"sheet boxes overlap on the root: {pairs}. Their pins would share "
            f"coordinates and their nets would silently merge. Run "
            f"tools/layout_root.py before wiring.")


def main():
    text = ROOT.read_text()
    sheets = []
    for m in re.finditer(
            r'\(sheet\n\t\t\(at ([-\d.]+) ([-\d.]+)\)\n\t\t\(size ([-\d.]+) ([-\d.]+)\)',
            text):
        x, y, w, h = (float(v) for v in m.groups())
        blk_end = text.index('\n\t)\n', m.start())
        name = re.search(r'\(property "Sheetname" "([^"]*)"',
                         text[m.start():blk_end]).group(1)
        sheets.append({"m": m, "x": x, "y": y, "w": w, "h": h, "name": name})

    cols = {}
    for s in sheets:
        cols.setdefault(s["x"], []).append(s)

    moves = []
    for x in sorted(cols):
        y = TOP
        for s in sorted(cols[x], key=lambda s: s["y"]):
            if abs(s["y"] - y) > 0.01:
                moves.append((s["name"], s["y"], y))
            s["new_y"] = y
            y += s["h"] + GAP

    # Rewrite back-to-front so earlier spans stay valid. Each sheet's pins and
    # its Sheetname/Sheetfile captions are positioned absolutely, so they all
    # shift by the same delta.
    for s in sorted(sheets, key=lambda s: -s["m"].start()):
        dy = s["new_y"] - s["y"]
        if abs(dy) < 0.01:
            continue
        a = s["m"].start()
        b = text.index('\n\t)\n', a) + 4
        blk = text[a:b]
        # `(at x y)` for the box and its captions, `(at x y rot)` for each
        # sheet pin -- both have to move, or the pins are left behind and two
        # sheets' pins can land on the same point.
        blk = re.sub(r'(\(at ([-\d.]+) )([-\d.]+)((?: [-\d.]+)?\))',
                     lambda m: f"{m.group(1)}{round(float(m.group(3)) + dy, 4)}{m.group(4)}",
                     blk)
        text = text[:a] + blk + text[b:]

    assert_no_overlap(text)
    ROOT.write_text(text)
    if moves:
        for name, old, new in moves:
            print(f"  {name:<13} y {old:7.2f} -> {new:7.2f}")
    else:
        print("  nothing to move")


if __name__ == "__main__":
    main()
