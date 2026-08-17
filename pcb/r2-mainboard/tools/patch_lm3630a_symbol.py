#!/usr/bin/env python3
"""Add (or refresh) the LM3630A symbol in r2.kicad_sym.

`gen_r2_symbols.py` cannot be re-run -- it reads a scratch directory from the
session that created it -- and its docstring says r2.kicad_sym is edited in the
symbol editor from then on. This script is the `patch_*.py` equivalent for one
symbol: it removes any existing LM3630A block and writes the current one, so it
is idempotent rather than refusing to run twice.

Pinout from lm3630a.pdf §5 (12-bump DSBGA, YFQ0012):

    A1 SDA   A2 SCL    A3 SW
    B1 HWEN  B2 INTN   B3 GND
    C1 PWM   C2 SEL    C3 IN
    D1 OVP   D2 ILED2  D3 ILED1

**Pin *placement* is not cosmetic here.** Two orderings were tried and
discarded because of what they do to the sheet:

  SW on the right      forces the inductor to route around the body, because a
                       boost wants IN -> L -> SW adjacent.
  SEL below HWEN/PWM   forces SEL's strap up to the IN rail to cross the HWEN
                       and PWM wires. Crossing wires are not connected in
                       KiCad, so this is legal and invisible -- which is
                       exactly how the four silent shorts of 2026-08-16
                       happened.

So: the boost input network (SW, IN) sits at the top left with SEL immediately
below IN, and the LED side (OVP, ILED1, ILED2) on the right facing J24.
"""
from __future__ import annotations

import pathlib
import sys

OUT = pathlib.Path(__file__).resolve().parent.parent / "r2.kicad_sym"
FP = "r2:Texas_YFQ0012_DSBGA-12_1.91x1.39mm_Layout3x4_P0.4mm"

# (name, ball, x, y, rot, electrical type)
PINS = [
    ("SW",      "A3", -12.7,  12.70,   0, "passive"),
    ("IN",      "C3", -12.7,   7.62,   0, "power_in"),
    ("SEL",     "C2", -12.7,   5.08,   0, "input"),
    ("HWEN",    "B1", -12.7,   0.00,   0, "input"),
    ("PWM",     "C1", -12.7,  -2.54,   0, "input"),
    ("SCL",     "A2", -12.7,  -7.62,   0, "input"),
    ("SDA",     "A1", -12.7, -10.16,   0, "bidirectional"),
    ("OVP",     "D1",  12.7,  12.70, 180, "input"),
    ("ILED1",   "D3",  12.7,   2.54, 180, "input"),
    ("ILED2",   "D2",  12.7,   0.00, 180, "input"),
    ("~{INTN}", "B2",  12.7, -10.16, 180, "open_collector"),
    ("GND",     "B3",   0.0, -17.78,  90, "power_in"),
]

PROPS = [
    ("Reference", "U", -10.16, 16.51, False),
    ("Value", "LM3630A", -10.16, -19.05, False),
    ("Footprint", FP, 0, 0, True),
    ("Datasheet", "https://www.ti.com/lit/ds/symlink/lm3630a.pdf", 0, 0, True),
    ("Description",
     "Dual-string white LED driver: boost to 40V, two independently "
     "controlled current sinks 5-28.5mA, adaptive headroom, 256-step I2C "
     "exponential dimming plus a PWM input, DSBGA-12", 0, 0, True),
    ("ki_keywords",
     "LED driver backlight frontlight boost dual string WLED e-reader",
     0, 0, True),
]


def _prop(name, val, x, y, hide):
    h = "\n\t\t\t(hide yes)" if hide else ""
    just = "" if hide else "\t\t\t\t(justify left bottom)\n"
    return (f'\t\t(property "{name}" "{val}"\n\t\t\t(at {x} {y} 0)\n'
            f"\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no){h}\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            f"\t\t\t\t)\n{just}\t\t\t)\n\t\t)\n")


def _pin(name, ball, x, y, rot, etype):
    fx = ("\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t"
          "(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n")
    return (f"\t\t\t(pin {etype} line\n\t\t\t\t(at {x} {y} {rot})\n"
            f"\t\t\t\t(length 2.54)\n"
            f'\t\t\t\t(name "{name}"\n{fx}\t\t\t\t)\n'
            f'\t\t\t\t(number "{ball}"\n{fx}\t\t\t\t)\n\t\t\t)\n')


def block() -> str:
    s = ('\t(symbol "LM3630A"\n\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)\n'
         "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
         "\t\t(in_pos_files yes)\n"
         "\t\t(duplicate_pin_numbers_are_jumpers no)\n")
    s += "".join(_prop(*p) for p in PROPS)
    s += ('\t\t(symbol "LM3630A_0_1"\n\t\t\t(rectangle\n'
          "\t\t\t\t(start -10.16 15.24)\n\t\t\t\t(end 10.16 -15.24)\n"
          "\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n"
          "\t\t\t\t\t(type default)\n\t\t\t\t)\n"
          "\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n"
          "\t\t\t)\n\t\t)\n")
    s += ('\t\t(symbol "LM3630A_1_1"\n'
          + "".join(_pin(*p) for p in PINS) + "\t\t)\n\t)\n")
    return s


def main() -> int:
    t = OUT.read_text()
    i = t.find('\t(symbol "LM3630A"')
    if i >= 0:                       # drop the old block, whatever shape it had
        depth, j = 0, i
        while j < len(t):
            if t[j] == "(":
                depth += 1
            elif t[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        t = t[:i] + t[j + 1:].lstrip("\n")
        print("replaced the existing LM3630A block")
    k = t.rstrip().rfind(")")
    OUT.write_text(t[:k] + block() + ")\n")
    print(f"wrote LM3630A into {OUT.name}: {len(PINS)} pins, footprint {FP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
