#!/usr/bin/env python3
"""Move the DDR bank rail from 1.35 V to 1.5 V, and rename it everywhere.

Decided by the hardware owner 2026-08-12, during WP5, on evidence that only
arrived when the Spartan-6 and Micron datasheets were finally obtained.

WHY
---
Caster's `constraint.ucf` constrains all 48 DDR pins as `SSTL15_II` /
`DIFF_SSTL15_II` / `LVCMOS15`.  `ds162.pdf` Table 7 specifies `SSTL15_II` over
VCCO **1.425-1.575 V** with VREF **0.69-0.81 V**.  This sheet produced 1.344 V,
which is 81 mV below the VCCO minimum, and a half-rail VREF of 0.672 V, which is
below the VREF minimum.  Spartan-6 offers no 1.35 V I/O standard to relabel the
gateware to: `SSTL135` appears nowhere in `ds162.pdf` or `ug381.pdf`, and the
nearest 1.5 V-class standards (`LVCMOS15`, `HSTL_*`) still stop at 1.4 V.

R1 runs the same way and works, but it is a different layout, the assistant
cannot test either board, and an out-of-spec DDR bus fails as rare corruption
rather than as a clean stop.

`mt41k64m16.pdf` p.1 makes the fix available: "VDD = VDDQ = +1.35V (1.283V to
1.45V)" and "Backward compatible to VDD = VDDQ = 1.5V +/-0.075V".  At 1.5 V the
two windows are *identical* -- DDR3 1.5 V +/-0.075 = 1.425-1.575 V, and
`SSTL15_II` VCCO = 1.425-1.575 V -- which is no coincidence, since SSTL15 exists
to drive DDR3.  1.5 V is also what the MIG core was generated against
(`MT41J64M16XX-125`, a 1.5 V part).

Cost, now a measured figure rather than an estimate: `mt41k64m16.pdf` gives
`IDD6` room-temperature self-refresh as 8 mA (Rev. G) / 12 mA (Rev. J), and the
die revision is not selectable when buying from LCSC.  At the 12 mA worst case
the rail goes from 16.1 mW to 18.0 mW -- **about 1.9 mW** -- which buys full
datasheet compliance on a board with no planned respin.

WHAT CHANGES
------------
1. `power.kicad_sch`: `R33` 124 k -> **150 k**, giving
   0.600 x (1 + 150/100) = **1.500 V** exactly from `U15`'s 0.600 V reference
   (`tps62a01.pdf`).  150 k is a standard 1 % value.  `R34` stays 100 k.
2. The rail is renamed `+1V35_DCDC` -> `+1V5_DCDC` and `+1V35` -> `+1V5`,
   keeping the sheet's convention that a converter output carries `_DCDC` and
   the plain name comes back from the shunt on `power_mon`.
3. `PG_1V35` -> `PG_1V5` across `power`, `mcu` and the root sheet's pins.

Every occurrence is a plain quoted string in a `(label`, `(hierarchical_label`,
`(pin`, `(text` or `(property "Value"` -- checked before writing this.  No
`lib_id` or `lib_symbols` entry carries the old name, so the rename cannot
strand a symbol reference.  Replacements are done on the fully-quoted forms so
that `"+1V35"` can never match inside `"+1V35_DCDC"`.

The DRAM part does not change: `MT41K64M16TW` simply runs in its 1.5 V
compatible mode.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

# (file, [(old, new, expected_count), ...])
EDITS = [
    ("power.kicad_sch", [
        ('(property "Value" "+1V35_DCDC"', '(property "Value" "+1V5_DCDC"', 2),
        ('(label "PG_1V35"',               '(label "PG_1V5"',               2),
        ('(hierarchical_label "PG_1V35"',  '(hierarchical_label "PG_1V5"',  1),
        ('(text "+1V35_DCDC  —  DDR3L and the FPGA\'s DDR bank VCCO"',
         '(text "+1V5_DCDC  —  DDR3L at 1.5 V and the FPGA\'s DDR bank VCCO"', 1),
    ]),
    ("power_mon.kicad_sch", [
        ('(property "Value" "+1V35_DCDC"', '(property "Value" "+1V5_DCDC"', 1),
        ('(property "Value" "+1V35"',      '(property "Value" "+1V5"',      1),
    ]),
    ("mcu.kicad_sch", [
        ('(label "PG_1V35"',              '(label "PG_1V5"',              2),
        ('(hierarchical_label "PG_1V35"', '(hierarchical_label "PG_1V5"', 1),
    ]),
    ("r2.kicad_sch", [
        ('(pin "PG_1V35"', '(pin "PG_1V5"', 2),
    ]),
]


def set_r33(text):
    """R33 124k -> 150k, addressed via its own symbol block so no other 124k moves."""
    for m in re.finditer(r'\n\t\(symbol\n', text):
        s = m.start()
        e = text.index('\n\t)\n', s) + 3
        blk = text[s:e]
        if re.search(r'\(property "Reference" "R33"', blk):
            new, n = re.subn(r'(\(property "Value" ")124k/1%(")',
                             lambda mm: mm.group(1) + "150k/1%" + mm.group(2),
                             blk, count=1)
            assert n == 1, "R33 is not 124k/1% -- already patched or changed"
            return text[:s] + new + text[e:]
    raise KeyError("R33")


def main():
    if not any("1V35" in (ROOT / f).read_text() for f, _ in EDITS):
        sys.exit("already patched (no 1V35 remains)")

    for fname, subs in EDITS:
        p = ROOT / fname
        t = p.read_text()
        for old, new, count in subs:
            n = t.count(old)
            assert n == count, "%s: expected %d x %r, found %d" % (fname, count, old, n)
            t = t.replace(old, new)
        if fname == "power.kicad_sch":
            t = set_r33(t)
        assert "1V35" not in t, "%s: 1V35 survived" % fname
        p.write_text(t)
        print("patched %-22s (%d substitutions%s)"
              % (fname, sum(c for _, _, c in subs),
                 ", R33 -> 150k" if fname == "power.kicad_sch" else ""))


if __name__ == "__main__":
    main()
