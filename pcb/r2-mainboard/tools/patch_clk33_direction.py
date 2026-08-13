#!/usr/bin/env python3
"""FPGA_CLK33 leaves fpga_config; it does not arrive there.

The port carried R1's `GCLK` across as an `input` on both `fpga_io` and
`fpga_config`. That is wrong on one of them: X1 (the 33.33 MHz oscillator) and
its series resistor R409 are drawn on `fpga_config`, so the net is generated
there and exported. `fpga_io` receives it, at ball K11.

Nothing electrical changes -- a hierarchical label's shape is documentation and
an ERC hint, and the netlist is identical either way. It matters because with
both ends declared `input` the net has no declared source, so once the root was
wired ERC had no way to tell a missing oscillator from a working one. Two
`input`s meeting is also the one interface shape combination on this board that
is never legitimate, which is how it was found.

`tools/port_r1.py`'s HIER table is corrected too, so a re-port produces this
directly; this script exists because `fpga_config` is FROZEN and carries the
config NOR, which a re-port would discard.

Three places have to agree or ERC raises `hier_label_mismatch`:
  * both `FPGA_CLK33` hierarchical labels inside `fpga_config.kicad_sch`
  * the `FPGA_CLK33` sheet pin on `fpga_config`'s box on the root
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PROJ = HERE.parent
SHEET = PROJ / "fpga_config.kicad_sch"
ROOT = PROJ / "r2.kicad_sch"


def main():
    t = SHEET.read_text()
    pat = re.compile(r'(\(hierarchical_label "FPGA_CLK33"\n\t\t\(shape )input(\))')
    t, n = pat.subn(r"\1output\2", t)
    assert n == 2, (f"expected 2 FPGA_CLK33 hierarchical labels set to input on "
                    f"fpga_config, changed {n} -- already patched?")
    SHEET.write_text(t)

    r = ROOT.read_text()
    # Only fpga_config's pin: fpga_io's FPGA_CLK33 stays an input.
    for m in re.finditer(r"\(sheet\n", r):
        a = m.start()
        b = r.index("\n\t)\n", a) + 4
        blk = r[a:b]
        if '"Sheetfile" "fpga_config.kicad_sch"' not in blk:
            continue
        blk2, k = re.subn(r'(\(pin "FPGA_CLK33" )input\b', r"\1output", blk)
        assert k == 1, f"fpga_config sheet pin FPGA_CLK33: changed {k}, want 1"
        ROOT.write_text(r[:a] + blk2 + r[b:])
        break
    else:
        raise AssertionError("no fpga_config sheet block on the root")

    print("FPGA_CLK33: fpga_config now exports it (2 labels + 1 sheet pin)")


if __name__ == "__main__":
    main()
