#!/usr/bin/env python3
"""Patch battery.kicad_sch: cell connector -> Molex Pico-Lock, plus solder pads.

`battery.kicad_sch` is a reviewed sheet (WP1, review 1 answered in
docs/battery.md §10), so it is edited surgically here rather than regenerated.
Documents each edit and refuses to run twice.

**Why.** docs/battery.md §10.9 chose `JST-PH` with reservations: it carries the
2 A this design needs but stands ~6.0 mm off the board, and in an e-reader every
millimetre of that is thickness the whole device inherits. §9.1 then found a
second problem when the cell was chosen -- the `PL706090` ships with a **JST
1.25 mm** plug rated **1 A**, against ~1.5 A peak discharge and up to ~2 A into
the cell while fast-charging. So the pack's own connector was the weak link
regardless of what the board carried.

**What changes.**

  J2   JST-PH 3P, ~6.0 mm tall, 2 A
       -> Molex Pico-Lock 504050-0391: 1.5 mm pitch, 3 circuits, right-angle
          SMT, **3.5 A** per contact, 150 V, -40..+105 C, gold, positive lock,
          **2.00 mm mated height**.
  J25  new -- three bare copper pads on the same three nets, for soldering the
       cell's leads directly. Not an either/or with J2: same nets, fit either
       or both.

Right-angle rather than vertical on purpose: the leads then exit parallel to the
board instead of standing up, which is what actually costs thickness once the
cell (7.0 mm) and the SoM (5 mm) already set the stack.

**This still requires re-terminating the pack.** Any >=2 A answer does -- the
1.25 mm plug it ships with is the limit no matter what the board offers. The
pads exist partly so that re-termination is optional.

Not verified from a datasheet: the 3.5 A / 150 V / 2.00 mm figures are from
Molex's published summary via distributor listings (Newark, RS, element14).
Molex's own spec PDF timed out from this machine. Check before fab.

No LCSC code -- Molex parts are thin there and this one did not turn up. Newark
`98AC8179`, RS `187-9994`. Same position as the LM3630A: prototype from a
Western distributor, carry the gap as a production-BOM risk.
"""
from __future__ import annotations

import pathlib
import re
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
SCH = HERE.parent / "battery.kicad_sch"

PICOLOCK_FP = ("Connector_Molex:Molex_Pico-Lock_504050-0391"
               "_1x03-1MP_P1.50mm_Horizontal")
PADS_FP = "r2:SolderPads_1x03_P3.50mm_Wire"

# J2 sits at (299.72, 74.93); its pins land at x=294.64, y=72.39/74.93/77.47.
# The band from y=129 to y=202 in this x range is empty, so J25 goes at +85.09,
# clear of the GND drop at x=290.83 that spans y=77.47..91.44.
DY_J25 = 85.09
PAD_X = 226 * 1.27          # 287.02 -- the stub column, all on the 1.27 grid
P1_Y = 124 * 1.27           # 157.48  +VBAT
P2_Y = 126 * 1.27           # 160.02  CHG_TS
P3_Y = 128 * 1.27           # 162.56  GND
VBAT_Y = 120 * 1.27         # 152.40
GND_Y = 132 * 1.27          # 167.64
PIN_X = 232 * 1.27          # 294.64 -- J25's pins, same column as J2's


def uid() -> str:
    return str(uuid.uuid4())


def sym_span(text: str, ref: str) -> tuple[int, int]:
    for m in re.finditer(r"\n\t\(symbol\n", text):
        s = m.start()
        e = text.index("\n\t)\n", s) + 4
        if re.search(r'\(property "Reference" "%s"' % re.escape(ref),
                     text[s:e]):
            return s, e
    raise KeyError(ref)


def value_span(text: str, value: str) -> tuple[int, int]:
    """First top-level symbol whose Value is `value` -- used for power symbols."""
    for m in re.finditer(r"\n\t\(symbol\n", text):
        s = m.start()
        e = text.index("\n\t)\n", s) + 4
        b = text[s:e]
        if re.search(r'\(property "Value" "%s"' % re.escape(value), b) and \
                re.search(r'\(property "Reference" "#PWR', b):
            return s, e
    raise KeyError(value)


def edit_sym(text, ref, fn):
    s, e = sym_span(text, ref)
    return text[:s] + fn(text[s:e]) + text[e:]


def move(blk: str, dx: float, dy: float) -> str:
    def sub(m):
        return "%s%s %s%s" % (m.group(1), round(float(m.group(2)) + dx, 4),
                              round(float(m.group(3)) + dy, 4), m.group(4))
    return re.sub(r"(\(at )([-\d.]+) ([-\d.]+)((?: [-\d.]+)?\))", sub, blk)


def set_prop(blk: str, name: str, value: str) -> str:
    return re.sub(r'(\(property "%s" ")[^"]*(")' % re.escape(name),
                  lambda m: m.group(1) + value + m.group(2), blk, count=1)


def rename(blk: str, old: str, new: str) -> str:
    blk = set_prop(blk, "Reference", new)
    return blk.replace('(reference "%s")' % old, '(reference "%s")' % new)


def fresh_uuids(blk: str) -> str:
    return re.sub(r'\(uuid "[0-9a-f-]{36}"\)',
                  lambda m: '(uuid "%s")' % uid(), blk)


def wire(x1, y1, x2, y2) -> str:
    return ("\n\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n"
            "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            '\t\t(uuid "%s")\n\t)\n' % (x1, y1, x2, y2, uid()))


def label(name, x, y, rot=0, justify="left") -> str:
    return ('\n\t(label "%s"\n\t\t(at %s %s %s)\n\t\t(effects\n\t\t\t(font\n'
            "\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify %s bottom)\n"
            '\t\t)\n\t\t(uuid "%s")\n\t)\n' % (name, x, y, rot, justify, uid()))


def note(s, x, y) -> str:
    return ('\n\t(text "%s"\n\t\t(exclude_from_sim no)\n\t\t(at %s %s 0)\n'
            "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
            % (s, x, y, uid()))


def add(text: str, chunk: str) -> str:
    assert text.endswith(")\n")
    return text[:-2] + chunk + ")\n"


# Placed below y=215.9, which is where this sheet's content ends in this
# column -- the first attempt started at 176.53 and printed straight through
# the existing TS note and the PWR_FLAG row.
NOTE_Y = 176 * 1.27          # 223.52
NOTE = [
    "Cell attachment -- J2 or J25, same three nets, fit either or both.",
    "J2  Pico-Lock 504050-0391: 3.5 A/contact, 2.00 mm mated, positive lock,",
    "    right-angle. Replaces a JST-PH that was 2 A and ~6.0 mm tall.",
    "J25 bare copper pads, for soldering the cell's leads directly.",
    "*** The PL706090 ships with a JST 1.25 mm plug rated 1 A against ~2 A of",
    "*** charge current, so the pack must be re-terminated. battery.md §9.1.",
]


def main() -> int:
    t = SCH.read_text()
    assert "504050-0391" not in t, "already patched"
    assert "J25" not in t, "J25 already exists"

    # --- 1. J2: JST-PH -> Pico-Lock -------------------------------------- #
    def to_picolock(blk: str) -> str:
        blk = set_prop(blk, "Value", "Pico-Lock 504050-0391")
        blk = set_prop(blk, "Footprint", PICOLOCK_FP)
        return set_prop(blk, "Description",
                        "Cell connector: Molex Pico-Lock 1.5 mm, 3 circuits, "
                        "right-angle SMT. 3.5 A/contact vs ~2 A of charge "
                        "current, 2.00 mm mated height vs the JST-PH's ~6.0. "
                        "1 BAT+, 2 NTC, 3 BAT-. Pack must be re-terminated -- "
                        "its own 1.25 mm plug is rated 1 A. battery.md §9.1")
    t = edit_sym(t, "J2", to_picolock)

    # --- 2. J25: copy J2's block, move it down, re-badge it --------------- #
    s, e = sym_span(t, "J2")
    j25 = fresh_uuids(move(t[s:e], 0, DY_J25))
    j25 = rename(j25, "J2", "J25")
    j25 = set_prop(j25, "Value", "SolderPads 3x")
    j25 = set_prop(j25, "Footprint", PADS_FP)
    j25 = set_prop(j25, "Description",
                   "Three bare copper pads for soldering the cell's leads "
                   "directly, in parallel with J2 and on the same nets. No "
                   "part to populate -- the 'component' is copper. 1 BAT+, "
                   "2 NTC, 3 BAT-. battery.md §9.1")
    t = add(t, j25)

    # --- 3. power symbols for J25's two rails ----------------------------- #
    s, e = value_span(t, "+VBAT")
    vb = t[s:e]
    old_ref = re.search(r'\(property "Reference" "(#PWR\d+)"', vb).group(1)
    at = re.search(r"\(at ([\d.]+) ([\d.]+)", vb)
    vb = fresh_uuids(move(vb, PAD_X - float(at.group(1)),
                          VBAT_Y - float(at.group(2))))
    t = add(t, rename(vb, old_ref, "#PWR1110"))

    s, e = value_span(t, "GND")
    gd = t[s:e]
    old_ref = re.search(r'\(property "Reference" "(#PWR\d+)"', gd).group(1)
    at = re.search(r"\(at ([\d.]+) ([\d.]+)", gd)
    gd = fresh_uuids(move(gd, PAD_X - float(at.group(1)),
                          GND_Y - float(at.group(2))))
    t = add(t, rename(gd, old_ref, "#PWR1111"))

    # --- 4. stubs from J25's pins to their nets --------------------------- #
    t = add(t, wire(PIN_X, P1_Y, PAD_X, P1_Y))      # BAT+
    t = add(t, wire(PAD_X, P1_Y, PAD_X, VBAT_Y))
    t = add(t, wire(PIN_X, P2_Y, PAD_X, P2_Y))      # NTC
    t = add(t, label("CHG_TS", PAD_X, P2_Y, 0, "right"))
    t = add(t, wire(PIN_X, P3_Y, PAD_X, P3_Y))      # BAT-
    t = add(t, wire(PAD_X, P3_Y, PAD_X, GND_Y))

    y = NOTE_Y
    for line in NOTE:
        t = add(t, note(line, 236.22, y))
        y += 3.81

    SCH.write_text(t)
    print("battery.kicad_sch patched:")
    print("  J2  -> Molex Pico-Lock 504050-0391 (3.5 A, 2.00 mm, right-angle)")
    print(f"  J25 -> {PADS_FP}, 3 solder pads on +VBAT / CHG_TS / GND")
    return 0


if __name__ == "__main__":
    sys.exit(main())
