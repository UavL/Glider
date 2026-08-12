#!/usr/bin/env python3
"""Apply the fixes from the first review of `battery.kicad_sch`.

The sheet has been hand-edited in Eeschema, so it -- not `gen_battery.py` -- is
the source of truth. This script therefore patches the file in place, item by
item, and refuses to run twice.

What it changes, and why (long form in `docs/battery.md` and
`manual-analysis/Analyse_battery.md`):

1. PSEL is strapped HIGH, not LOW. Low means "adapter" and arms a 3.25 A
   default input limit before firmware exists; high means "USB host" and 500 mA
   (datasheet Table 9-4). The pull-up goes to REGN because REGN is up before
   PSEL is sampled (power-up sequence step 1 vs step 3) while +3V3_AON is not.
2. The charge LED comes out of the MCU's sense path. In series it drops ~1-1.5 V
   at leakage currents, which pushes the STAT "high" level to ~2 V -- below the
   STM32G0's 0.7*VDD = 2.31 V VIH. R4 goes back to being a plain 10 k pull-up
   and the LED gets its own branch.
3. `MAX17048` CELL (pin 2) is wired to +VBAT. It is "not internally connected"
   on the 17048, but the datasheet still says "connect to the positive battery
   terminal", and doing so lets a MAX17049 drop in.
4. I2C pull-ups 10 k -> 2.2 k, so the bus can run at 400 kHz.
"""
import pathlib
import re
import uuid

HERE = pathlib.Path(__file__).resolve().parent
SCH = HERE.parent / "battery.kicad_sch"

SHEET_PATH = "/dee825bf-c2f1-415d-afdf-cf702072a6e8/a6dcf48c-d5d2-42bd-8aa1-b0910921d2ee"


def uid():
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #

def sym_span(text, ref):
    """Byte span of the top-level `(symbol ...)` block whose Reference is `ref`."""
    for m in re.finditer(r'\n\t\(symbol\n', text):
        s = m.start()
        e = text.index('\n\t)\n', s) + 4
        if re.search(r'\(property "Reference" "%s"' % re.escape(ref), text[s:e]):
            return s, e
    raise KeyError(ref)


def edit_sym(text, ref, fn):
    s, e = sym_span(text, ref)
    return text[:s] + fn(text[s:e]) + text[e:]


def move(blk, dx, dy):
    """Shift every `(at x y ...)` in a symbol block. Rotation is left alone."""
    def sub(m):
        return "%s%s %s%s" % (m.group(1), round(float(m.group(2)) + dx, 4),
                              round(float(m.group(3)) + dy, 4), m.group(4))
    return re.sub(r'(\(at )([-\d.]+) ([-\d.]+)((?: [-\d.]+)?\))', sub, blk)


def set_prop(blk, name, value):
    return re.sub(r'(\(property "%s" ")[^"]*(")' % re.escape(name),
                  lambda m: m.group(1) + value + m.group(2), blk, count=1)


def rename(blk, old, new):
    blk = set_prop(blk, "Reference", new)
    return blk.replace('(reference "%s")' % old, '(reference "%s")' % new)


def fresh_uuids(blk):
    return re.sub(r'\(uuid "[0-9a-f-]{36}"\)',
                  lambda m: '(uuid "%s")' % uid(), blk)


def wire(x1, y1, x2, y2):
    return ('\n\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n'
            '\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            '\t\t(uuid "%s")\n\t)\n' % (x1, y1, x2, y2, uid()))


def junction(x, y):
    return ('\n\t(junction\n\t\t(at %s %s)\n\t\t(diameter 0)\n'
            '\t\t(color 0 0 0 0)\n\t\t(uuid "%s")\n\t)\n' % (x, y, uid()))


def label(name, x, y, rot):
    return ('\n\t(label "%s"\n\t\t(at %s %s %s)\n\t\t(effects\n\t\t\t(font\n'
            '\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
            '\t\t)\n\t\t(uuid "%s")\n\t)\n' % (name, x, y, rot, uid()))


def note(s, x, y):
    return ('\n\t(text "%s"\n\t\t(exclude_from_sim no)\n\t\t(at %s %s 0)\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
            % (s, x, y, uid()))


def drop_wire(text, x1, y1, x2, y2):
    pat = (r'\n\t\(wire\n\t\t\(pts\n\t\t\t\(xy %s %s\) \(xy %s %s\)\n'
           r'\t\t\)\n\t\t\(stroke\n\t\t\t\(width 0\)\n\t\t\t\(type default\)\n'
           r'\t\t\)\n\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
           % tuple(re.escape(str(v)) for v in (x1, y1, x2, y2)))
    new, n = re.subn(pat, '\n', text, count=1)
    assert n == 1, "wire (%s,%s)-(%s,%s) not found" % (x1, y1, x2, y2)
    return new


def add(text, chunk):
    """Append a top-level element just before the closing paren of the file."""
    assert text.endswith(')\n')
    return text[:-2] + chunk + ')\n'


# --------------------------------------------------------------------------- #

def main():
    t = SCH.read_text()
    assert '"R38"' not in t, "already patched"

    # -- 1. PSEL high ------------------------------------------------------- #
    # R11 (0 R to GND) becomes the un-fitted adapter option.
    t = edit_sym(t, "R11", lambda b: b.replace('(dnp no)', '(dnp yes)'))

    # R38: 10 k from CHG_PSEL up to REGN, cloned off R5 so it inherits the
    # column's drawing style exactly.
    s, e = sym_span(t, "R5")
    r38 = fresh_uuids(rename(move(t[s:e], 97.79, 0.0), "R5", "R38"))
    t = add(t, r38)
    t = add(t, wire(168.91, 182.88, 168.91, 177.8))
    t = add(t, wire(168.91, 190.5, 168.91, 194.31))
    t = add(t, label("REGN", 168.91, 177.8, 90))
    t = add(t, label("CHG_PSEL", 168.91, 194.31, 90))
    t = t.replace('(text "PSEL low = adapter source"',
                  '(text "PSEL high = USB host source"')
    t = add(t, note("Fit R38 or R11, never both.", 139.7, 200.66))

    # -- 2. charge LED out of the sense path --------------------------------- #
    # R4 slides down into the standard pull-up position; the wires that used to
    # stitch it to D7 and D7 to R37 go away.
    t = drop_wire(t, 50.8, 185.42, 50.8, 186.69)
    t = drop_wire(t, 50.8, 194.31, 50.8, 193.04)
    t = drop_wire(t, 50.8, 203.2, 50.8, 201.93)
    t = drop_wire(t, 45.72, 203.2, 50.8, 203.2)
    t = t.replace('(label "CHG_STAT#"\n\t\t(at 45.72 203.2 90)',
                  '(label "CHG_STAT#"\n\t\t(at 50.8 199.39 90)')
    t = edit_sym(t, "R4", lambda b: move(b, 0.0, 3.81))
    t = add(t, wire(50.8, 179.07, 50.8, 182.88))
    t = add(t, wire(50.8, 190.5, 50.8, 199.39))

    # The indicator becomes its own block in the empty area below the TS
    # divider: +3V3_AON -> R37 -> D7 -> CHG_STAT#.
    t = edit_sym(t, "R37", lambda b: set_prop(
        set_prop(move(b, 157.48, 27.94), "Value", "1k"),
        "Footprint", "Resistor_SMD:R_0402_1005Metric"))
    t = edit_sym(t, "D7", lambda b: set_prop(
        set_prop(move(b, 157.48, 44.45), "Value", "LED green"),
        "Footprint", "LED_SMD:LED_0603_1608Metric"))

    s, e = sym_span(t, "#PWR028")           # +3V3_AON at (50.8, 179.07)
    pwr = fresh_uuids(rename(move(t[s:e], 157.48, 39.37), "#PWR028", "#PWR004"))
    t = add(t, pwr)
    t = add(t, wire(208.28, 218.44, 208.28, 222.25))
    t = add(t, wire(208.28, 237.49, 208.28, 241.3))
    t = add(t, label("CHG_STAT#", 208.28, 241.3, 90))
    t = add(t, note("Charge indicator - lit while STAT is low.", 198.12, 213.36))

    # -- 3. MAX17048 CELL to +VBAT ------------------------------------------ #
    t = re.sub(r'\n\t\(no_connect\n\t\t\(at 341\.63 116\.84\)\n'
               r'\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n', '\n', t, count=1)
    t = add(t, wire(341.63, 116.84, 341.63, 107.95))
    t = add(t, junction(341.63, 107.95))

    # -- 4. I2C pull-ups for 400 kHz ---------------------------------------- #
    for ref in ("R6", "R7"):
        t = edit_sym(t, ref, lambda b: set_prop(b, "Value", "2.2k"))

    SCH.write_text(t)
    print("battery.kicad_sch patched")


if __name__ == "__main__":
    main()
