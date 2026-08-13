#!/usr/bin/env python3
"""Connect the sheet pins on r2.kicad_sch, which until now joined nothing.

Every child sheet has had its hierarchical interface since the work package that
drew it, and `sheet_pins.set_sheet_pins` has been putting matching pins on the
root's sheet symbols all along -- but nothing on the root ever joined one sheet's
pin to another's. So `epd`'s `EPDC_D0P` and `fpga_io`'s `EPDC_D0P` were two
different nets with one node each, and the netlist showed them as
`/epd/EPDC_D0P` and `/fpga_io/EPDC_D0P`. 232 `isolated_pin_label` violations were
all saying the same thing.

**Labels, not wires.** 187 sheet pins across 13 boxes in four columns cannot be
joined with wires legibly -- it would be several hundred crossings. A local label
on the root sheet is a net on the root sheet, so two sheet pins carrying the same
label text are the same net, and the drawing stays readable. This is the ordinary
way to close a hierarchy of this size. `global_label` would also work and is
worse: it would push all 109 names into every sheet's namespace.

Each pin gets a short stub and a label at its end. Sheet pins all sit on the
right edge of their box at rotation 0, so every stub runs right into the gutter
before the next column, and the tool asserts both of those facts rather than
assuming them.

**This tool owns the root's wires and labels.** It deletes every top-level
`(wire ...)`, `(label ...)` and `(junction ...)` before re-emitting, so it is
re-runnable, and a hand edit of those three element types on the root will not
survive it. Sheet boxes, positions and pins are never touched -- those belong to
`sheet_pins.py` and `layout_root.py`.

A name with only one pin is left labelled but unjoined, which is correct: when
the sheet that owns the other end is drawn, its pin gets the same label and the
net closes with no edit here. Those are expected only where a whole sheet is
still a stub, so the list is checked against DANGLING_OK and anything new is
reported as a finding.
"""
import pathlib
import re
import sys
import uuid
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ROOT = HERE.parent / "r2.kicad_sch"
STUB = 5.08
CHAR_W = 1.27          # generous per-character bound for 1.27 mm stroke text
PAGE_RIGHT = 410.0     # A3 is 420 wide; the frame's inner edge is about here

# Names that legitimately have only one sheet pin today, and what they are
# waiting for. Anything dangling and *not* here means an interface was declared
# on one side and forgotten on the other -- which is exactly the class of mistake
# a hierarchy this size hides well.
DANGLING_OK = {
    **{n: "WP7 dpi_in: the SoM's parallel RGB output. fpga_io owns the FPGA "
          "pins and exports them; nothing drives them yet."
       for n in [f"DPI_{c}{b}" for c in "RGB" for b in range(2, 8)]
       + ["DPI_PCLK", "DPI_DE", "DPI_HS", "DPI_VS"]},
    **{n: "WP8 som: the SoM is the CSR SPI master and writes the config NOR. "
          "fpga_config exports the FPGA end."
       for n in ("FPGA_SCLK", "FPGA_MOSI", "FPGA_MISO", "FPGA_CS", "NOR_CS")},
    **{n: "WP8 som: MCU-to-SoM housekeeping, declared on mcu since WP3."
       for n in ("MCU_RXD", "MCU_TXD", "SOM_IRQ#", "SOM_RESET#", "SOM_WAKE#")},
    **{n: "WP8 som: USB 2.0 from J1 on battery to the SoM's OTG port."
       for n in ("USB_DP", "USB_DM")},
}


def sheet_blocks(text: str):
    """-> [(start, end, name, x, y, w, h, [(pin, shape, px, py, rot)])]"""
    out = []
    for m in re.finditer(r'\(sheet\n\t\t\(at ([-\d.]+) ([-\d.]+)\)\n'
                         r'\t\t\(size ([-\d.]+) ([-\d.]+)\)', text):
        a = m.start()
        b = text.index("\n\t)\n", a) + 4
        blk = text[a:b]
        name = re.search(r'\(property "Sheetname" "([^"]*)"', blk).group(1)
        pins = [(p, s, float(px), float(py), int(r)) for p, s, px, py, r
                in re.findall(r'\(pin "([^"]+)" (\w+)\n\t\t\t'
                              r'\(at ([-\d.]+) ([-\d.]+) (\d+)\)', blk)]
        out.append((a, b, name, *(float(v) for v in m.groups()), pins))
    return out


def strip_owned(text: str) -> tuple[str, int]:
    """Remove every top-level wire, label and junction. -> (text, count)"""
    n = 0
    for token in ("wire", "label", "junction"):
        pat = re.compile(r"\n\t\(" + token + r"[\s\n]")
        while True:
            m = pat.search(text)
            if not m:
                break
            s = text.index("(", m.start())
            depth, j, in_str = 0, s, False
            while True:
                c = text[j]
                if c == '"' and text[j - 1] != "\\":
                    in_str = not in_str
                elif not in_str:
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                        if depth == 0:
                            break
                j += 1
            text = text[:m.start()] + text[j + 1:]
            n += 1
    return text, n


def main() -> int:
    text = ROOT.read_text()
    sheets = sheet_blocks(text)
    assert sheets, "no sheet symbols found on the root"

    # Column geometry, so a label can be checked against the next box along.
    right_edges = sorted({x + w for _, _, _, x, _, w, _, _ in sheets})
    left_edges = sorted({x for _, _, _, x, _, _, _, _ in sheets})

    by_name = defaultdict(list)
    for *_, name, x, y, w, h, pins in [(a, b, n, x, y, w, hh, p)
                                       for a, b, n, x, y, w, hh, p in sheets]:
        for pin, shape, px, py, rot in pins:
            by_name[pin].append((name, shape, px, py, rot, x + w))

    text, removed = strip_owned(text)

    problems, emitted = [], []
    for pin, places in sorted(by_name.items()):
        for name, shape, px, py, rot, edge in places:
            if rot != 0:
                problems.append(f"{name}.{pin}: sheet pin rotation is {rot}, "
                                f"this tool only handles pins on the right edge")
                continue
            if abs(px - edge) > 0.01:
                problems.append(f"{name}.{pin}: pin x={px} is not the box's "
                                f"right edge {edge}")
                continue
            end = px + STUB
            reach = end + CHAR_W * len(pin)
            # the first left edge strictly right of this box
            nxt = next((l for l in left_edges if l > px + 0.01), PAGE_RIGHT)
            if reach > nxt - 1.0:
                problems.append(f"{name}.{pin}: label reaches x={reach:.1f}, "
                                f"into the box/edge at {nxt}")
                continue
            emitted.append((end, py, pin))

    if problems:
        for p in problems:
            print(f"  FAIL  {p}")
        return 1

    parts = []
    for end, py, pin in emitted:
        parts.append(
            "\t(wire\n\t\t(pts\n"
            f"\t\t\t(xy {round(end - STUB, 4)} {round(py, 4)}) "
            f"(xy {round(end, 4)} {round(py, 4)})\n"
            "\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f'\t\t(uuid "{uuid.uuid4()}")\n\t)\n')
        parts.append(
            f'\t(label "{pin}"\n\t\t(at {round(end, 4)} {round(py, 4)} 0)\n'
            "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            "\t\t\t(justify left bottom)\n\t\t)\n"
            f'\t\t(uuid "{uuid.uuid4()}")\n\t)\n')

    assert text.endswith(")\n")
    ROOT.write_text(text[:-2] + "\n" + "".join(parts) + ")\n")

    joined = {k: v for k, v in by_name.items() if len(v) > 1}
    solo = {k: v for k, v in by_name.items() if len(v) == 1}
    print(f"root: removed {removed} old wire/label/junction blocks, "
          f"wrote {len(emitted)} stubs + labels")
    print(f"  {len(by_name)} distinct names on {sum(map(len, by_name.values()))}"
          f" sheet pins")
    print(f"  joined across sheets : {len(joined)}")
    print(f"  still one-sided      : {len(solo)}")

    surprises = sorted(set(solo) - set(DANGLING_OK))
    stale = sorted(set(DANGLING_OK) & set(joined))
    for n in surprises:
        sh = solo[n][0][0]
        print(f"  FINDING  {n} is declared only on {sh} and nothing else "
              f"references it")
    for n in stale:
        print(f"  note     {n} is in DANGLING_OK but is now joined; the entry "
              f"can go")
    if not surprises:
        reasons = defaultdict(list)
        for n in sorted(solo):
            reasons[DANGLING_OK[n]].append(n)
        for why, names in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
            print(f"\n  {len(names)} waiting on -- {why}")
            print(f"        {' '.join(names)}")
    return 1 if surprises else 0


if __name__ == "__main__":
    sys.exit(main())
