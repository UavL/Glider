#!/usr/bin/env python3
"""Retire FL_PWM2 and return PB7 to the spare pool.

Why it existed: R1 drove the frontlight *through the panel connector* -- FL_PWM1,
FL_PWM2, FL_EN and +5V2_FL all left the board on J6, because the driver lived on
the panel/adapter side.  R2 ported that pin-for-pin, then WP6 (2026-08-17) moved
the driver onto the board as U53 (LM3630A), which dims per channel over I2C and
takes a *single* hardware PWM input.  FL_PWM2 has driven nothing since; it only
survived as a stub to J6.42 on a frozen sheet.  patch_j6_40pin.py removed that.

Why not rename it FL_INT#: FL_INT# does not exist any more.  frontlight.md 9.1
(2026-08-23) withdrew it because U53.B2 is an interior pad of a 0.4 mm-pitch
DSBGA-12 and cannot be escaped at any manufacturable width; mcu.md 209 released
PB12 back to the pool at the same time.  Independently, PB7 is EXTI7 and PC7
(KEY_PREV#) already holds EXTI7, so PB7 could not have served as the interrupt
input either.

Spare pins on mcu.kicad_sch carry no wire and no label -- PB12 is drawn that way
-- so this deletes the stubs rather than relabelling them.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MCU, ROOT = HERE / "mcu.kicad_sch", HERE / "r2.kicad_sch"


def drop_wire_at(text, pt):
    x, y = pt
    for m in re.finditer(r'\t\(wire\n\t\t\(pts\n\t\t\t\(xy ([\d.-]+) ([\d.-]+)\) \(xy ([\d.-]+) ([\d.-]+)\)\n(?:.*?\n)*?\t\)\n', text):
        a = (round(float(m.group(1)), 2), round(float(m.group(2)), 2))
        b = (round(float(m.group(3)), 2), round(float(m.group(4)), 2))
        if a == pt or b == pt:
            return text[:m.start()] + text[m.end():], True
    return text, False


def drop_labelish(text, kind, name, pt):
    x, y = pt
    pat = re.compile(r'\t\(%s "%s"\n(?:\t\t\(shape \w+\)\n)?\t\t\(at %s %s [\d.-]+\)\n(?:.*?\n)*?\t\)\n'
                     % (kind, re.escape(name), re.escape(f"{x:g}"), re.escape(f"{y:g}")))
    m = pat.search(text)
    if not m:
        return text, False
    return text[:m.start()] + text[m.end():], True


def main():
    log = []

    t = MCU.read_text(encoding="utf-8")
    if "FL_PWM2" not in t:
        print("mcu.kicad_sch: already retired")
    else:
        for pt in ((190.5, 172.72), (358.14, 102.87), (365.76, 102.87)):
            t, ok = drop_wire_at(t, pt)
            if ok:
                log.append(f"mcu: wire at {pt}")
        for kind, pt in (("label", (190.5, 172.72)), ("label", (358.14, 102.87)),
                         ("hierarchical_label", (365.76, 102.87))):
            t, ok = drop_labelish(t, kind, "FL_PWM2", pt)
            if not ok:
                sys.exit(f"mcu.kicad_sch: {kind} FL_PWM2 not found at {pt}")
            log.append(f"mcu: {kind} at {pt}")
        if "FL_PWM2" in t:
            sys.exit("mcu.kicad_sch: FL_PWM2 still present after the deletions")
        # a bare spare pin is an ERC error; PB12 carries a no-connect flag, so PB7 gets one too
        if "(at 180.34 172.72)" not in t:
            nc = ('\t(no_connect\n\t\t(at 180.34 172.72)\n'
                  '\t\t(uuid "3f7b1c02-9e44-4a1d-8c6e-5b2f0a7d1e93")\n\t)\n')
            anchor = t.index("\t(no_connect\n")
            t = t[:anchor] + nc + t[anchor:]
            log.append("mcu: no-connect flag on PB7 (180.34, 172.72)")
        MCU.write_text(t, encoding="utf-8")

    r = ROOT.read_text(encoding="utf-8")
    if "FL_PWM2" not in r:
        print("r2.kicad_sch: already retired")
    else:
        r, ok = drop_wire_at(r, (281.94, 66.04))
        if ok:
            log.append("root: wire at (281.94, 66.04)")
        r, ok = drop_labelish(r, "label", "FL_PWM2", (281.94, 66.04))
        if not ok:
            sys.exit("r2.kicad_sch: label FL_PWM2 not found")
        log.append("root: label at (281.94, 66.04)")
        # the sheet pin on the mcu sheet symbol
        anchor = r.find('(pin "FL_PWM2" ')
        depth, k = 0, anchor
        while k < len(r):
            if r[k] == "(":
                depth += 1
            elif r[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        ls = r.rfind("\n", 0, anchor) + 1
        le = k + 1
        if r[le:le + 1] == "\n":
            le += 1
        r = r[:ls] + r[le:]
        log.append("root: mcu sheet pin FL_PWM2")
        if "FL_PWM2" in r:
            sys.exit("r2.kicad_sch: FL_PWM2 still present after the deletions")
        ROOT.write_text(r, encoding="utf-8")

    for line in log:
        print("  removed", line)
    print("PB7 (U20.61) is now an unlabelled spare, drawn like PB12.")


if __name__ == "__main__":
    main()
