#!/usr/bin/env python3
"""Apply the fixes from the first review of `mcu.kicad_sch`.

The sheet has been hand-edited and saved in Eeschema, so it -- not
`gen_mcu.py` -- is the source of truth. This script patches the file in place,
item by item, and refuses to run twice.

What it changes, and why (long form in `docs/mcu.md` §12):

1. `C42` (100 nF on `VBAT`, pin 6) is deleted.  The reviewer asked whether it is
   one capacitor too many, and it is.  `stm32g0b1.pdf` Figure 15 (p.65) is the
   whole of ST's decoupling scheme and it shows **no** capacitor on `VBAT` --
   only "1 x 100 nF + 1 x 4.7 uF" on `VDD/VDDA` and "100 nF + 1 uF" on `VREF+`.
   There is no coin cell here, so `VBAT` (pin 6) is strapped to the same
   `+3V3_AON` net as `VDD/VDDA` (pin 8), two pins away, and the netlist confirms
   both land on it.  `C40` 4.7 uF + `C41` 100 nF already are the figure's pair;
   `C42` was a third capacitor on a net that is already correctly decoupled.

2. `SW21`/`SW22`, the page-turn buttons, move from `TS-1187A-B-A-B` (LCSC
   C318884) to Panasonic `EVQPLHA15` (LCSC C79172).  Same 1.6 N force and
   1.5 mm travel, so the feel is unchanged, but the cycle rating goes from
   **100 000 to 500 000**.  At a plausible ~200 page turns a day the old part is
   rated for about 1.4 years; these two switches are the most-actuated parts on
   the board.  KiCad 10 carries the land pattern
   (`SW_SPST_Panasonic_EVQPL_3PL_5PL_PT_A15`), whose pads 1/2 are the SPST
   terminals and pads 0 the mechanical anchors, in a 5.5 x 5.4 mm envelope
   consistent with the 4.9 x 4.9 mm J-lead body LCSC lists.

   `SW20` stays a `TS-1187A`: it is the power button, pressed rarely, and it is
   a JLC Basic part.

3. `Description` fields are filled in for the parts the review turned on, so the
   sheet carries its own justification: the two decoupling groups cite Figure
   15, `FB20` records the 190 mOhm DCR that makes it legal in series with
   `VREF+` (Table 21 caps that pin at min(VDD + 0.4, 4.0) V), and `Y20` says in
   as many words that it is the LSE and that no HSE is fitted -- the 8 MHz the
   reviewer found is `fOSC_IN` typ in Table 42 and the caption of Figure 20,
   both of which describe the HSE.

Nothing else changes.  In particular the button topology is untouched: the
hardware owner chose to keep `SW20` as the power button (2026-08-12), since it
is the only ship-mode exit that does not need either a cable or a live I2C host.
"""
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
SCH = HERE.parent / "mcu.kicad_sch"


# --------------------------------------------------------------------------- #
# primitives (same shapes as patch_power_review1.py)
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


def retext(text, old, new):
    pat = r'\(text "%s"' % re.escape(old)
    assert re.search(pat, text), "note %r not found" % old
    return re.sub(pat, lambda m: '(text "%s"' % new, text, count=1)


# --------------------------------------------------------------------------- #

EVQPL_FP = "Button_Switch_SMD:SW_SPST_Panasonic_EVQPL_3PL_5PL_PT_A15"

D_KEY = ("Page-turn tact switch — 1.6 N, 1.5 mm travel, 500 k cycles, "
         "4.9×4.9 mm J-lead (Panasonic EVQPLHA15, LCSC C79172). Chosen for "
         "cycle life: the 100 k-cycle TS-1187A is ~1.4 years at 200 turns/day")
D_PWRBTN = ("Power button — shorts CHG_QON# to GND galvanically, the only "
            "ship-mode exit needing neither a cable nor a live I²C host "
            "(bq25890.pdf §9.2.10.2). 1.6 N, 100 k cycles is ample for a "
            "rarely-pressed key (XKB TS-1187A-B-A-B, LCSC C318884, JLC Basic)")
D_FB = ("Ferrite bead 120 Ω @ 100 MHz, DCR 190 mΩ, 550 mA, 0402 (Murata "
        "BLM15AG121SN1D, LCSC C85812). Isolates VREF+ from the digital rail. "
        "The low DCR is the load-bearing spec: stm32g0b1.pdf Table 21 caps "
        "VREF+ at min(VDD + 0.4, 4.0) V, so nothing with real series "
        "impedance may sit here — a resistor would be a hazard, this is "
        "<0.2 mV at 1 mA. Not required by Figure 15; see docs/mcu.md §12.2")
D_C40 = ("4.7 µF bulk for VDD/VDDA (pin 8) and VBAT (pin 6), which share "
         "+3V3_AON — stm32g0b1.pdf Figure 15 p.65: 1 × 100 nF + 1 × 4.7 µF")
D_C41 = ("100 nF decoupling at VDD/VDDA pin 8 — stm32g0b1.pdf Figure 15 p.65. "
         "With C40 this is the whole of ST's scheme for this pin pair; no "
         "separate VBAT capacitor is called for")
D_C43 = "1 µF on VREF+ — stm32g0b1.pdf Figure 15 p.65 (100 nF + 1 µF)"
D_C44 = "100 nF on VREF+ — stm32g0b1.pdf Figure 15 p.65 (100 nF + 1 µF)"
D_Y20 = ("32.768 kHz LSE crystal for the RTC (Epson FC-135, LCSC C32346, JLC "
         "Basic). This is the LSE, not the HSE: no HSE is fitted, and the "
         "8 MHz in stm32g0b1.pdf Table 42 / Figure 20 is fOSC_IN typ for the "
         "HSE. LSE spec is Table 43 p.85; tSU 2 s. CL unconfirmed — see §9")
D_CL = ("LSE load capacitor for Y20 — 18 pF assumes a 12.5 pF crystal and "
        "~3 pF stray (docs/mcu.md §5.4). Y20's actual CL is unconfirmed; "
        "AN2867 is the selection reference named by Table 43")


def main():
    t = SCH.read_text()
    assert '"C42"' in t, "already patched (C42 is gone)"

    # -- 1. delete the redundant VBAT capacitor ------------------------------- #
    # C42 hangs off the +3V3_AON rail wire (25.40,45.72)-(76.20,45.72) at
    # x = 50.80 and drops to its own GND symbol.  The rail is a single wire, so
    # removing the stub cannot break it.
    t = drop_junction(t, 50.8, 45.72)          # rail tap
    t = drop_wire(t, 50.8, 53.34, 50.8, 60.96)  # C42.2 down to GND
    t = drop_sym(t, "#PWR305")                  # that GND symbol
    t = drop_sym(t, "C42")
    assert '"C42"' not in t and '"#PWR305"' not in t

    # the block note no longer needs to imply per-pin decoupling
    t = retext(t, "VDD/VDDA (8)        VBAT (6)",
               "VDD/VDDA (8) + VBAT (6) - one net")

    # -- 2. page-turn buttons: 100 k -> 500 k cycles -------------------------- #
    for ref in ("SW21", "SW22"):
        t = edit_sym(t, ref, lambda b: set_prop(
            set_prop(set_prop(b, "Footprint", EVQPL_FP),
                     "LCSC", "C79172"),
            "Description", D_KEY))
    t = edit_sym(t, "SW20", lambda b: set_prop(b, "Description", D_PWRBTN))

    # -- 3. record why the reviewed parts are what they are ------------------- #
    for ref, desc in (("FB20", D_FB), ("C40", D_C40), ("C41", D_C41),
                      ("C43", D_C43), ("C44", D_C44), ("Y20", D_Y20),
                      ("C46", D_CL), ("C47", D_CL)):
        t = edit_sym(t, ref, lambda b, d=desc: set_prop(b, "Description", d))

    SCH.write_text(t)
    print("patched %s" % SCH.name)


if __name__ == "__main__":
    main()
