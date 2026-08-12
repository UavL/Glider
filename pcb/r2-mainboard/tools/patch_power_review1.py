#!/usr/bin/env python3
"""Apply the fixes from the first review of `power.kicad_sch`.

The sheet has been hand-edited and saved in Eeschema, so it -- not
`gen_power.py` -- is the source of truth. This script therefore patches the file
in place, item by item, and refuses to run twice.

What it changes, and why (long form in `docs/power.md` §10):

1. `U11` (TPS22965 load switch) and its two support caps `C23` (CT) and `C24`
   (VBIAS) are deleted, and `MCU_EN_5V` now drives `U12.EN` directly with `R20`
   as its pull-down.

   `docs/power.md` §2.2 justified `U11` with "a boost passes its input through
   when disabled".  That is wrong for this part.  `tps61022.pdf` p.1 lists
   "True disconnection between input and output during shutdown" as a headline
   feature, §7.3.2 repeats it ("In the shutdown mode ... The output is
   disconnected from input power supply"), and §6.5 backs it with
   `IVOUT_LKG` = 1 µA typ / 3 µA max measured with `VOUT` forced to 5.5 V while
   `VIN` = 0 V, i.e. the isolation blocks in both directions.  §2.2 had misread
   §7.3.5, which describes pass-through while the device is *enabled*.

   `C22` stays as `+VSYS` bulk and `C25` becomes the boost's input capacitor
   (§8.2.2.5 asks for 10 µF; 22 µF is above that).  `VSYS_SW` disappears: the
   boost runs from `+VSYS` directly, and the `+5V` rail now has the same
   enable-plus-pull-down shape as the other three.

2. Inductor `Value` fields carried "/6A", which no inductor on this sheet is
   rated for.  Checked on LCSC 2026-08-11:
     C3224227  DFE322512F-1R0M  1 µH   1210  Isat 4.8 A  Irms 3.8 A  32 mΩ
     C703140   DFE252012F-R47M  470 nH 1008  Isat 7.4 A  Irms 4.9 A  23 mΩ
   The `Value` strings now carry Irms, the continuous rating, and the full
   figures go in `Description`.

3. `C32`/`C34` were 22 µF/6.3 V while the reviewer's own `Description` on `C32`
   quoted TI's 10 V part.  `tps62a01.pdf` Table 8-2 specifies 10 V, so the
   values follow the datasheet.

4. `Description` fields: the reviewer pasted TI's Table 8-2 rows onto `C31`,
   `C32` and `L12`.  Those name Murata parts that LCSC does not stock, so they
   would mislead the BOM pass.  They are replaced by the electrical description
   plus, where the part *is* decided and stocked, its MPN and LCSC code, and
   mirrored onto the matching parts of the twin +1V35 circuit.
"""
import pathlib
import re
import uuid

HERE = pathlib.Path(__file__).resolve().parent
SCH = HERE.parent / "power.kicad_sch"


def uid():
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# primitives (same shapes as patch_battery_review1.py)
# --------------------------------------------------------------------------- #

def sym_span(text, ref):
    """Byte span of the top-level `(symbol ...)` block whose Reference is `ref`.

    The span runs from the newline that precedes `\t(symbol` to the closing
    `\t)` *inclusive*, but stops short of the newline that follows it -- that
    newline is the next block's leading newline.  Including it would make
    consecutive spans overlap by one byte, and deleting a block would then eat
    the following block's `\n\t(symbol` marker.
    """
    for m in re.finditer(r'\n\t\(symbol\n', text):
        s = m.start()
        e = text.index('\n\t)\n', s) + 3
        if re.search(r'\(property "Reference" "%s"' % re.escape(ref), text[s:e]):
            return s, e
    raise KeyError(ref)


def edit_sym(text, ref, fn):
    s, e = sym_span(text, ref)
    return text[:s] + fn(text[s:e]) + text[e:]


def drop_sym(text, ref):
    s, e = sym_span(text, ref)
    return text[:s] + text[e:]


def set_prop(blk, name, value):
    """Set an existing property's value."""
    pat = r'(\(property "%s" ")[^"]*(")' % re.escape(name)
    assert re.search(pat, blk), "no %s property" % name
    return re.sub(pat, lambda m: m.group(1) + value + m.group(2), blk, count=1)


def wire(x1, y1, x2, y2):
    return ('\n\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n'
            '\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            '\t\t(uuid "%s")\n\t)\n' % (x1, y1, x2, y2, uid()))


def drop_wire(text, x1, y1, x2, y2):
    """Delete the wire with exactly these endpoints, in either order."""
    for a, b, c, d in ((x1, y1, x2, y2), (x2, y2, x1, y1)):
        pat = (r'\n\t\(wire\n\t\t\(pts\n\t\t\t\(xy %s %s\) \(xy %s %s\)\n'
               r'\t\t\)\n\t\t\(stroke\n\t\t\t\(width 0\)\n\t\t\t\(type default\)\n'
               r'\t\t\)\n\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
               % tuple(re.escape(str(v)) for v in (a, b, c, d)))
        new, n = re.subn(pat, '\n', text, count=1)
        if n == 1:
            return new
    raise AssertionError("wire (%s,%s)-(%s,%s) not found" % (x1, y1, x2, y2))


def drop_junction(text, x, y):
    pat = (r'\n\t\(junction\n\t\t\(at %s %s\)\n\t\t\(diameter 0\)\n'
           r'\t\t\(color 0 0 0 0\)\n\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
           % (re.escape(str(x)), re.escape(str(y))))
    new, n = re.subn(pat, '\n', text, count=1)
    assert n == 1, "junction (%s,%s) not found" % (x, y)
    return new


def drop_label(text, name, x, y):
    pat = (r'\n\t\(label "%s"\n\t\t\(at %s %s [-\d.]+\)\n\t\t\(effects\n.*?'
           r'\n\t\t\)\n\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
           % (re.escape(name), re.escape(str(x)), re.escape(str(y))))
    new, n = re.subn(pat, '\n', text, count=1, flags=re.S)
    assert n == 1, "label %s at (%s,%s) not found" % (name, x, y)
    return new


def add(text, chunk):
    """Append a top-level element just before the closing paren of the file."""
    assert text.endswith(')\n')
    return text[:-2] + chunk + ')\n'


def retext(text, old, new):
    pat = r'\(text "%s"' % re.escape(old)
    assert re.search(pat, text), "note %r not found" % old
    return re.sub(pat, '(text "%s"' % new, text, count=1)


# --------------------------------------------------------------------------- #

L_1UH = ("1 µH power inductor, 1210 — Isat 4.8 A / Irms 3.8 A / 32 mΩ "
         "(Murata DFE322512F-1R0M, LCSC C3224227)")
L_R47 = ("470 nH power inductor, 1008 — Isat 7.4 A / Irms 4.9 A / 23 mΩ "
         "(Murata DFE252012F-R47M, LCSC C703140)")
C_4U7 = "4.7 µF 10 V X7R 0805 — TPS62A02 input cap, tps62a01.pdf Table 8-2"
C_22U = "22 µF 10 V X7R/X5R 0805 — TPS62A02 output cap, tps62a01.pdf Table 8-3"


def main():
    t = SCH.read_text()
    assert '"U11"' in t, "already patched (U11 is gone)"

    # -- 1. delete the load switch and rewire the boost's enable -------------- #

    # every wire that touched U11, C23 or C24
    for w in ((146.05, 58.42, 146.05, 62.23),   # C24 top to +VSYS
              (146.05, 69.85, 146.05, 74.93),   # C24 bottom to GND
              (161.29, 58.42, 161.29, 66.04),   # VBIAS feed, vertical
              (161.29, 66.04, 165.1, 66.04),    # VBIAS feed, horizontal
              (165.1, 58.42, 165.1, 60.96),     # U11 pin 2 (VIN)
              (165.1, 68.58, 165.1, 95.25),     # U11 pin 3 (ON)
              (165.1, 95.25, 146.05, 95.25),    # MCU_EN_5V run, replaced below
              (175.26, 73.66, 175.26, 77.47),   # U11 pin 5 (GND)
              (180.34, 73.66, 180.34, 77.47),   # U11 pin 9 (EP)
              (175.26, 77.47, 180.34, 77.47),   # GND/EP join
              (177.8, 77.47, 177.8, 82.55),     # down to the GND symbol
              (190.5, 58.42, 190.5, 60.96),     # U11 pin 8 (VOUT)
              (190.5, 68.58, 196.85, 68.58),    # U11 pin 6 (CT)
              (196.85, 68.58, 196.85, 71.12),   # C23 top
              (196.85, 78.74, 196.85, 83.82),   # C23 bottom to GND
              (222.25, 58.42, 222.25, 71.12)):  # old EN feed off the rail
        t = drop_wire(t, *w)

    for j in ((146.05, 58.42), (161.29, 58.42), (165.1, 58.42),
              (177.8, 77.47), (190.5, 58.42), (222.25, 58.42)):
        t = drop_junction(t, *j)

    # VSYS_SW no longer exists -- the boost runs from +VSYS
    t = drop_label(t, "VSYS_SW", 203.2, 58.42)

    for ref in ("U11", "C23", "C24", "#PWR207", "#PWR210", "#PWR211"):
        t = drop_sym(t, ref)

    # close the gap the switch left in the +VSYS rail
    t = add(t, wire(165.1, 58.42, 190.5, 58.42))

    # MCU_EN_5V keeps R20 and its GND where they are and now runs across to
    # U12's EN pin, joining the existing (222.25,71.12)-(231.14,71.12) stub.
    t = add(t, wire(146.05, 95.25, 215.9, 95.25))
    t = add(t, wire(215.9, 95.25, 215.9, 71.12))
    t = add(t, wire(215.9, 71.12, 222.25, 71.12))

    # the on-sheet note that explained the pair
    t = retext(t, "U11 is the real disconnect; U12's EN follows its own switched input,",
               "TPS61022 truly disconnects VOUT from VIN in shutdown (datasheet")
    t = retext(t, "so one GPIO owns the pair and 'off' is unambiguous.",
               "Features, 7.3.2), so no series load switch is needed.")

    # -- 2. honest inductor ratings ------------------------------------------ #
    for ref in ("L10", "L12", "L13"):
        t = edit_sym(t, ref, lambda b: set_prop(
            set_prop(b, "Value", "1uH/3.8A"), "Description", L_1UH))
    t = edit_sym(t, "L11", lambda b: set_prop(
        set_prop(b, "Value", "0.47uH/4.9A"), "Description", L_R47))

    # -- 3. buck output caps follow the datasheet's 10 V ---------------------- #
    for ref in ("C32", "C34"):
        t = edit_sym(t, ref, lambda b: set_prop(
            set_prop(b, "Value", "22uF/10V"), "Description", C_22U))
    for ref in ("C31", "C33"):
        t = edit_sym(t, ref, lambda b: set_prop(b, "Description", C_4U7))

    SCH.write_text(t)
    print("power.kicad_sch patched")


if __name__ == "__main__":
    main()
