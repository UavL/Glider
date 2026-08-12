#!/usr/bin/env python3
"""Replace J20 with a combined SWD+JTAG footprint, and claim a pin for INIT_B.

Two changes to `mcu.kicad_sch`, both decided by the hardware owner 2026-08-12.

1. ONE DEBUG FOOTPRINT FOR BOTH TARGETS.  R1 fits `J5`, a 2x6 1.27 mm socket
   carrying FPGA JTAG *and* MCU SWD, and populates it.  R2 had only `J20`, a 1x5
   2.54 mm SWD footprint.  The combined footprint goes here rather than on
   `fpga_config` because `fpga_config` already exports `FPGA_TCK`/`TDI`/`TDO`/
   `TMS` as sheet pins from the port -- so this is four labels added to one sheet
   instead of three local nets reclassified on another.

   Pinout is R1's `J5` order with its pin-10 ground given over to `MCU_NRST`,
   which R1's header does not carry:

       1 FPGA_TCK     2 GND
       3 FPGA_TDI     4 GND
       5 FPGA_TDO     6 GND
       7 FPGA_TMS     8 GND
       9 MCU_SWCLK   10 MCU_NRST
      11 MCU_SWDIO   12 +3V3_AON

   Signal/ground interleaving is kept on the JTAG half, which is the half that
   runs at any speed.  `+3V3_AON` rather than `+3V3` for the adapter's reference:
   both are 3.3 V, but the always-on rail is the one guaranteed to be up when you
   are trying to work out why nothing else is.

   Still not fitted.  It is pads only, as `J20` was.

2. INIT_B REACHES THE MCU.  `PC10` (pin 64) gives up its no-connect flag.  It is
   a plain GPIO -- not one of the four ADC-capable spares, which are worth
   keeping analog -- and `EXTI10` is unused, so the signal can interrupt rather
   than be polled if firmware wants that.

   Why it earns a pin: with the FPGA self-booting from the NOR, a corrupt image
   shows up only as `DONE` never asserting, which is indistinguishable from "the
   NOR never answered".  `INIT_B` low separates the two.  R1 did not need this,
   because the MCU fed the bitstream and therefore knew what it had sent.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402

PROJ = HERE.parent
SCH = PROJ / "mcu.kicad_sch"
KI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/share/kicad/symbols"

ORIGIN = (88.9, 198.12)          # keep R1's/J20's position; the 2x6 is the same height
PC10 = (124.46, 177.8)           # MCU pin 64, carries a no_connect from generation

# Everything belonging to the old 1x5 footprint, enumerated rather than matched by
# a bounding box so that a stray extra element in the region is an error, not a
# silent deletion.
OLD_WIRES = [
    (76.2, 193.04, 76.2, 185.42),      # +3V3_AON stub, upward
    (73.66, 198.12, 73.66, 210.82),    # GND drop
    (83.82, 198.12, 73.66, 198.12),    # pin3 GND
    (83.82, 200.66, 68.58, 200.66),    # pin4 MCU_SWDIO
    (83.82, 195.58, 60.96, 195.58),    # pin2 MCU_SWCLK
    (83.82, 193.04, 76.2, 193.04),     # pin1 +3V3_AON
    (83.82, 203.2, 53.34, 203.2),      # pin5 MCU_NRST
]
OLD_LABELS = [("MCU_SWCLK", 60.96, 195.58), ("MCU_NRST", 53.34, 203.2),
              ("MCU_SWDIO", 68.58, 200.66)]
OLD_PWR = ["#PWR313"]                  # the GND at (73.66, 210.82)


def drop_wire(t, x1, y1, x2, y2):
    for a, b, c, d in ((x1, y1, x2, y2), (x2, y2, x1, y1)):
        pat = (r'\n\t\(wire\n\t\t\(pts\n\t\t\t\(xy %s %s\) \(xy %s %s\)\n\t\t\)\n'
               r'\t\t\(stroke\n\t\t\t\(width 0\)\n\t\t\t\(type default\)\n\t\t\)\n'
               r'\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
               % tuple(re.escape(str(v)) for v in (a, b, c, d)))
        new, n = re.subn(pat, "\n", t, count=1)
        if n:
            return new
    raise AssertionError(f"wire ({x1},{y1})-({x2},{y2}) not found")


def drop_label(t, name, x, y):
    pat = (r'\n\t\(label "%s"\n\t\t\(at %s %s [-\d.]+\)\n\t\t\(effects\n[\s\S]*?'
           r'\n\t\t\)\n\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
           % (re.escape(name), re.escape(str(x)), re.escape(str(y))))
    new, n = re.subn(pat, "\n", t, count=1)
    assert n == 1, f"label {name} at ({x},{y}) not found"
    return new


def drop_symbol(t, ref):
    for m in re.finditer(r"\n\t\(symbol\n", t):
        s = m.start()
        e = t.index("\n\t)\n", s) + 3
        if re.search(r'\(property "Reference" "%s"' % re.escape(ref), t[s:e]):
            return t[:s] + t[e:]
    raise KeyError(ref)


def build() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["mcu"], root_uuid, "r2", paper="A3", pwr_base=350)
    s.lib.add_dir("Connector_Generic", KI / "Connector_Generic.kicad_symdir")
    s.lib.add_dir("power", KI / "power.kicad_symdir")
    s.lib.add_dir("symbols", PROJ.parent / "pcb_common/symbols.kicad_sym")

    j = s.place("Connector_Generic:Conn_02x06_Odd_Even", "J20", "SWD+JTAG (DNP)",
                *ORIGIN, dnp=True,
                footprint="Connector_PinSocket_1.27mm:"
                          "PinSocket_2x06_P1.27mm_Vertical_SMD",
                description="Combined debug footprint, pads only. R1's J5 order "
                            "with pin 10 given to MCU_NRST. Mates a stock 2x6 "
                            "1.27 mm cable.",
                val_at=(ORIGIN[0], ORIGIN[1] + 12.7))

    # odd column, wires left to their labels
    LX = 71.12
    for pin, name, shape in (("1", "FPGA_TCK", "output"), ("3", "FPGA_TDI", "output"),
                             ("5", "FPGA_TDO", "input"), ("7", "FPGA_TMS", "output")):
        px, py = j.pin(pin)
        s.wire((px, py), (LX, py))
        s.hlabel(LX, py, name, shape=shape, rot=180, justify="right")
    for pin, name in (("9", "MCU_SWCLK"), ("11", "MCU_SWDIO")):
        px, py = j.pin(pin)
        s.wire((px, py), (LX, py))
        s.label(LX, py, name, rot=180, justify="right")

    # even column: four grounds onto one bus, then NRST and the reference rail.
    # The NRST and +3V3_AON wires cross the ground bus without a junction, which
    # is not a connection -- the netlist assertion after this run is what proves
    # it, not the picture.
    GB = 101.6
    gp = [j.pin(p) for p in ("2", "4", "6", "8")]
    for px, py in gp:
        s.wire((px, py), (GB, py))
        s.junction(GB, py)
    s.wire((GB, gp[0][1]), (GB, 210.82))
    s.power("GND", GB, 210.82)

    px, py = j.pin("10")
    s.wire((px, py), (119.38, py))
    s.label(119.38, py, "MCU_NRST")
    px, py = j.pin("12")
    s.wire((px, py), (106.68, py))
    # not s.power(): its caption defaults above the symbol, which is exactly
    # where MCU_NRST's label sits. Place it below instead.
    s.place("symbols:+V", "#PWR352", "+3V3_AON", 106.68, py, 0,
            ref_at=(106.68, py), val_at=(106.68, py + 3.81), hide_ref=True)

    # ---- INIT_B on PC10 -------------------------------------------------- #
    s.wire(PC10, (114.3, PC10[1]))
    s.hlabel(114.3, PC10[1], "FPGA_INIT", shape="input", rot=180, justify="right")

    # R1's original note described the 1x5 CN4 order and is now false; it is
    # deleted in main() and these take its place, at its coordinates. Kept short
    # of x=130 so they clear the "Buttons" heading.
    s.text(48.26, 218.44,
           "J20 is pads only, not fitted. One footprint for both targets:", size=1.27)
    s.text(48.26, 222.25,
           "FPGA JTAG + MCU SWD, R1's J5 order, pin 10 given to MCU_NRST.", size=1.27)
    s.text(48.26, 226.06,
           "PC10 carries FPGA_INIT: INIT_B low tells a config error from a", size=1.27)
    s.text(48.26, 229.87,
           "silent NOR when DONE never arrives. EXTI10 is free for it.", size=1.27)
    return s.render()


def splice(target: str, new: str) -> str:
    def libs(text):
        i = text.index("(lib_symbols")
        d, j = 0, i
        while True:
            if text[j] == "(":
                d += 1
            elif text[j] == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        return i, j + 1, text[i:j + 1]

    ti, tj, tbody = libs(target)
    _, nj, nbody = libs(new)
    have = set(re.findall(r'\(symbol "([^"]+:[^"]+)"', tbody))
    add = []
    for m in re.finditer(r'\n\t\t\(symbol "([^"]+:[^"]+)"', nbody):
        if m.group(1) in have:
            continue
        s0 = nbody.index("(", m.start())
        d, k = 0, s0
        while True:
            if nbody[k] == "(":
                d += 1
            elif nbody[k] == ")":
                d -= 1
                if d == 0:
                    break
            k += 1
        add.append("\n\t\t" + nbody[s0:k + 1])
    merged = tbody[:-1].rstrip() + "".join(add) + "\n\t)"
    out = target[:ti] + merged + target[tj:]
    body = new[nj:]
    body = body[:body.rindex("(embedded_fonts")].strip("\n")
    assert out.endswith(")\n")
    return out[:-2] + "\n" + body + "\n)\n"


def main():
    t = SCH.read_text()
    assert "Conn_02x06" not in t, "already patched (2x6 header present)"

    t = drop_symbol(t, "J20")
    for w in OLD_WIRES:
        t = drop_wire(t, *w)
    for lab in OLD_LABELS:
        t = drop_label(t, *lab)
    for ref in OLD_PWR:
        t = drop_symbol(t, ref)

    # the +3V3_AON stub that fed old pin 1
    for m in re.finditer(r"\n\t\(symbol\n", t):
        s0 = m.start()
        e0 = t.index("\n\t)\n", s0) + 3
        blk = t[s0:e0]
        if re.search(r'\(at 76\.2 185\.42 \d+\)', blk) and '"+3V3_AON"' in blk:
            t = t[:s0] + t[e0:]
            break
    else:
        raise AssertionError("+3V3_AON stub at (76.2, 185.42) not found")

    for y in (218.44, 222.25, 226.06):
        pat = re.compile(r'\n\t\(text "[^"]*"\n\t\t\(exclude_from_sim \w+\)\n'
                         r'\t\t\(at 48\.26 %s 0\)\n[\s\S]*?\n\t\)\n' % y)
        t, k = pat.subn("\n", t, count=1)
        assert k == 1, f"stale J20 note line at y={y} not found"

    nc = re.compile(r'\n\t\(no_connect\n\t\t\(at %s %s\)\n\t\t\(uuid "[0-9a-f-]+"\)'
                    r'\n\t\)\n' % PC10)
    t, n = nc.subn("\n", t, count=1)
    assert n == 1, f"no_connect at PC10 {PC10} not found"

    SCH.write_text(splice(t, build()))
    print("patched mcu.kicad_sch: J20 -> 2x6 SWD+JTAG, PC10 claimed for FPGA_INIT")


if __name__ == "__main__":
    main()
