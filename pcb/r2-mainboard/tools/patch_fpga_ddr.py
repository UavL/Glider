#!/usr/bin/env python3
"""Give the FPGA's core rails a home, and write down what the ported sheet hides.

`tools/port_r1.py fpga_ddr` copies R1's DDR sheet across unchanged (49 local nets,
netlist-identical). Three things still have to happen, and none of them are
mechanical.

1. UNIT 6 OF THE FPGA SYMBOL LANDS HERE.  `pcb_common:XC6SLX-FTG256` is split
   into six units. R2 already places 1+2 on `fpga_io` (banks 0/1) and 3+5 on
   `fpga_config` (bank 2 + config), and the port puts 4 here (bank 3 / MCB3).
   Unit 6 is the 42 power pins -- 26 GND, 8 VCCAUX, 8 VCCINT -- and R1 draws it
   on its own `power.kicad_sch`. R2's power sheet is reviewed, committed, and has
   no FPGA on it at all, so unit 6 needs somewhere else to live or ERC reports
   `missing_unit` / `missing_power_pin` forever, and eight VCCINT balls silently
   go unconnected on the board.

   It comes here rather than to `fpga_config` because `fpga_config` has already
   been patched twice and its A4 page is full to y=195; `fpga_ddr` was ported onto
   A3 (see port_r1.PAPER) specifically to make room. The whole block sits at
   x>=296, clear of the ported content, which stops at x=276.86.

   The 12 decoupling capacitors that go with it move too, +300 like the rest of
   WP5. They are relocated, not re-invented: same values, same footprints as R1's
   C18-C25/C57-C59/C68.

2. ONE CAPACITOR IS ADDED, AND IT IS THE ONLY BOM CHANGE ON THIS SHEET.
   UG393 (v1.3) Table 2-1, p.14, row `FT(G)256 LX16` gives the required PCB
   decoupling per device as (100 uF, 4.7 uF, 0.47 uF) triples:

       VCCINT   0 / 5 / 1        VCCO bank 0   1 / 1 / 1
       VCCAUX   1 / 1 / 2        VCCO bank 1   1 / 1 / 2
                                 VCCO bank 2   1 / 1 / 1
                                 VCCO bank 3   1 / 1 / 2

   R1 fits four 4.7 uF on VCCINT where the table asks for five, so `C509` is the
   fifth. It is a 0402 and it costs nothing; the alternative is to argue from a
   PDS impedance simulation nobody here has run.

   Everything else in that table either matches or is a judgement call that R1's
   working board already settles -- written up in docs/fpga.md rather than
   changed, because Table 2-1 note 3 explicitly permits trading the 100 uF parts
   for more 4.7 uF ones, and R1 has taken that trade with 22 uF 0603s.

3. FOUR FACTS GET WRITTEN ON THE PAGE.  Each one is invisible in the netlist and
   expensive to rediscover:

   - `DRAM_ADDR13`/`DRAM_ADDR14` go to balls T3/T7, which the fitted 1 Gb part
     does not have. The symbol is `MT41K256M16HA` (4 Gb, A[14:0]); the Value is
     `MT41K64M16TW` (1 Gb, A[12:0], Micron 1Gb_DDR3L Rev L Figure 7 p.18 shows
     T3/T7/M7 as NC), and `top.v:22` declares `output wire [12:0] DDR_A`. So both
     nets are inert at both ends. They stay wired: T3/T7 are the density-expansion
     balls, so leaving them routed makes a 2 Gb or 4 Gb part a gateware-only
     change, and with bitgen's `-g UnusedPin:PullDown` the two unconstrained FPGA
     balls sit at a weak low into an unbonded ball, drawing nothing.
   - `DDR_ZIO` (M5) must stay unconnected -- it is the MCB's calibration probe,
     not a spare pin, and `C3_CALIB_SOFT_IP = "TRUE"` makes it mandatory.
   - `DRAM_CSB` is tied low and reaches no FPGA pin, because the MCB has no chip
     select: `constraint.ucf` has no `DDR_CS_N` and `top.v` no such port.
   - The bank is 1.5 V, not R1's 1.35 V. `DDR_RESET_N` is constrained `LVCMOS15`
     and every other bank-3 net `SSTL15_II`/`DIFF_SSTL15_II`; DS162 Table 7 gives
     SSTL15 a 1.425-1.575 V VCCO and lists no SSTL135 at all.

4. ONE ERC ITEM R1 LEAVES OPEN IS CLOSED.  Ball `B3` (`IO_L83P_3`) is the one
   spare bank-3 pin R1 leaves bare while flagging `M5` and `N4`, so it gets the
   no-connect flag that docs/mcu.md §3.2 makes the convention for a spare.

   The other two are deliberately left alone, because trying to close them makes
   the report worse rather than better:

   - `+DRAM_VREF` comes out of a resistor divider, so nothing on the net is a
     power *output* and ERC reports `power_pin_not_driven`. A `PWR_FLAG` silences
     it -- and immediately raises *two* `pin_to_pin` violations instead, because
     the FPGA's VREF balls `A3`/`M3` are dual-purpose IO and the symbol types them
     `Bidirectional`, which ERC will not have on a net with a power output. This
     was tried and reverted. The warning as it stands is also the more useful
     statement: this rail genuinely has no active driver.
   - `+1V5` reports the same thing, and its flag would belong on
     `power.kicad_sch` where U15 generates the rail -- a reviewed sheet. R1
     reports the identical violation on `+1V35`, so nothing regressed.

   Both are recorded in docs/fpga.md as expected output rather than hidden.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Placed, Sheet, sheet_uuids  # noqa: E402

PROJ = HERE.parent
SCH = PROJ / "fpga_ddr.kicad_sch"
KI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/share/kicad/symbols"

U6 = (335.28, 100.33)      # unit 6 origin; left pins x=314.96, right x=355.6
STUB = 7.62                # pin -> bus run
CAP_PITCH = 12.7

# R1's C18-C25 / C57-C59 / C68, +300. Order is R1's left-to-right.
VCCINT_CAPS = [("C318", "22uF/6.3V", "0603"), ("C320", "22uF/6.3V", "0603"),
               ("C322", "4.7uF/6.3V", "0402"), ("C324", "4.7uF/6.3V", "0402"),
               ("C357", "4.7uF/6.3V", "0402"), ("C359", "4.7uF/6.3V", "0402"),
               ("C509", "4.7uF/6.3V", "0402"),   # new: UG393 Table 2-1 wants 5
               ("C368", "470nF/25V", "0402")]
VCCAUX_CAPS = [("C319", "22uF/6.3V", "0603"), ("C321", "22uF/6.3V", "0603"),
               ("C323", "4.7uF/6.3V", "0402"), ("C325", "470nF/25V", "0402"),
               ("C358", "470nF/25V", "0402")]
FP = {"0402": "Capacitor_SMD:C_0402_1005Metric",
      "0603": "Capacitor_SMD:C_0603_1608Metric"}

NOTES = [
    "FPGA core rails. Unit 6 of U41 is 26 GND + 8 VCCAUX + 8 VCCINT; R1 draws",
    "it on power.kicad_sch, which in R2 has no FPGA. C509 is the fifth 4.7uF",
    "on VCCINT that UG393 Table 2-1 (FTG256 LX16) wants and R1 does not fit.",
    "",
    "Bank 3 VCCO is 1.5 V, not R1's 1.35 V: the UCF constrains DDR_RESET_N as",
    "LVCMOS15 and the rest of the bank SSTL15_II, and DS162 Table 7 specifies",
    "SSTL15 over 1.425-1.575 V only. VREF = R104/R105 = 1.500/2 = 0.750 V.",
    "",
    "DRAM_ADDR13/14 reach U52 balls T3/T7, which the fitted 1 Gb MT41K64M16",
    "does not bond (Micron 1Gb_DDR3L Rev L Fig 7 p.18) and top.v never drives",
    "(DDR_A is [12:0]). Kept routed: T3/T7 are the density-expansion balls, so",
    "a 2 Gb or 4 Gb part stays a gateware-only change.",
    "",
    "M5 (DDR_ZIO) is reserved for MCB calibration, not spare -- leave it open.",
    "DRAM_CSB is tied low by R101 and reaches no FPGA pin: the MCB has no chip",
    "select (no DDR_CS_N in constraint.ucf, no such port in top.v).",
]
NOTES_X = 296.0
NOTES_TOP = 201.0           # clears the VCCAUX row's GND label, which ends at 196.9
LINE_PITCH = 3.175          # 1.27 mm text, so this is tight but still legible
PARA_GAP = 1.905
# Measured off the A3 render at 260 dpi: the title block's top border is at
# y = 253.0. Every previous pass at this sheet family put text through it, so the
# layout asserts instead of trusting the arithmetic.
TITLE_BLOCK_TOP = 251.0


def _unit4_origin() -> tuple[float, float]:
    """Where the port put unit 4, read from the file rather than assumed."""
    t = SCH.read_text()
    for m in re.finditer(r"\n\t\(symbol\n", t):
        s = m.start()
        blk = t[s:t.index("\n\t)\n", s) + 3]
        if ('(property "Reference" "U41"' in blk
                and re.search(r"\(unit 4\)", blk)):
            at = re.search(r"\(at ([-\d.]+) ([-\d.]+) (\d+)\)", blk)
            assert at.group(3) == "0", f"unit 4 is rotated {at.group(3)}"
            return (float(at.group(1)), float(at.group(2)))
    raise AssertionError("U41 unit 4 not found on fpga_ddr")


def build() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["fpga_ddr"], root_uuid, "r2", paper="A3", pwr_base=520)
    s.lib.add_dir("Device", KI / "Device.kicad_symdir")
    s.lib.add_dir("power", KI / "power.kicad_symdir")
    s.lib.add_dir("symbols", PROJ.parent / "pcb_common/symbols.kicad_sym")

    u = s.place("symbols:XC6SLX-FTG256", "U41", "XC6SLX-FTG256", *U6, unit=6,
                footprint="footprints:Xilinx_FTG256",
                description="Unit 6: core and auxiliary supply pins.",
                ref_at=(U6[0], U6[1] - 33.02), val_at=(U6[0], U6[1] + 33.02))

    # Each rail gets its own bus x so that no two of them are ever collinear.
    # GND left/right are the inner pair because they carry the most pins.
    for name, side, bus_x, rail, cap_y in (
            ("VCCAUX", -1, U6[0] - 20.32 - 2 * STUB, "+3V3", None),
            ("VCCINT", +1, U6[0] + 20.32 + 2 * STUB, "+1V2_FPGA", None),
    ):
        pts = sorted(u.pins_named(name), key=lambda p: p[1])
        assert len(pts) == 8, f"{name}: expected 8 pins, got {len(pts)}"
        for px, py in pts:
            s.wire((px, py), (bus_x, py))
            s.junction(bus_x, py)
        # The vertical run is what makes the eight stubs one net. Without it the
        # junction dots are decoration and seven of the eight balls float --
        # ERC does say so, but only as `pin_not_connected` among many.
        s.wire((bus_x, pts[0][1]), (bus_x, pts[-1][1]))
        s.wire((bus_x, pts[0][1]), (bus_x, pts[0][1] - 6.35))
        s.power(rail, bus_x, pts[0][1] - 6.35)

    gnd = sorted(u.pins_named("GND"), key=lambda p: (p[0], p[1]))
    assert len(gnd) == 26, f"GND: expected 26 pins, got {len(gnd)}"
    for side in (-1, +1):
        col = [p for p in gnd if (p[0] < U6[0]) == (side < 0)]
        assert len(col) == 13, f"GND side {side}: {len(col)}"
        bus_x = U6[0] + side * (20.32 + STUB)
        for px, py in col:
            s.wire((px, py), (bus_x, py))
            s.junction(bus_x, py)
        s.wire((bus_x, col[0][1]), (bus_x, col[-1][1]))
        s.wire((bus_x, col[-1][1]), (bus_x, col[-1][1] + 6.35))
        s.power("GND", bus_x, col[-1][1] + 6.35)

    # ---- decoupling: one row per rail, rail bus above, GND bus below ------- #
    rail_ref = 560          # above the pwr_base block s.power() is drawing from
    for caps, rail, row_y in ((VCCINT_CAPS, "+1V2_FPGA", 152.4),
                              (VCCAUX_CAPS, "+3V3", 179.07)):
        x0 = 302.26
        top_y, bot_y = row_y - 8.89, row_y + 8.89
        for i, (ref, val, pkg) in enumerate(caps):
            cx = x0 + i * CAP_PITCH
            c = s.place("Device:C", ref, val, cx, row_y, footprint=FP[pkg],
                        ref_at=(cx + 2.54, row_y - 1.27),
                        val_at=(cx + 2.54, row_y + 3.81), justify="left")
            hi, lo = c.pin("1"), c.pin("2")
            s.wire(hi, (cx, top_y))
            s.wire(lo, (cx, bot_y))
            s.junction(cx, top_y)
            s.junction(cx, bot_y)
        xe = x0 + (len(caps) - 1) * CAP_PITCH
        s.wire((x0, top_y), (xe, top_y))
        s.wire((x0, bot_y), (xe, bot_y))
        s.wire((xe, bot_y), (xe, bot_y + 5.08))
        s.power("GND", xe, bot_y + 5.08)
        # The rail stub goes up from the left end, and its caption goes *beside*
        # the stem rather than above it. Above is s.power()'s default and it puts
        # the second row's "+3V3" exactly on the first row's ground bus -- the
        # rows are 26.67 mm apart and symbol-plus-caption needs 8.89 either side.
        s.wire((x0, top_y), (x0, top_y - 5.08))
        s.place("symbols:+V", f"#PWR{rail_ref}", rail, x0, top_y - 5.08,
                ref_at=(x0, top_y - 5.08), val_at=(x0 + 2.54, top_y - 3.81),
                hide_ref=True, justify="left")
        rail_ref += 1

    # ---- the one spare bank-3 ball R1 leaves unflagged --------------------- #
    u4 = Placed(s.lib.get("symbols:XC6SLX-FTG256"), *_unit4_origin(), 0, "U41")
    s.nc(*u4.pin("B3"))

    y = NOTES_TOP
    for line in NOTES:
        if line:
            s.text(NOTES_X, y, line, size=1.27)
            y += LINE_PITCH
        else:
            y += PARA_GAP
    assert y <= TITLE_BLOCK_TOP, (
        f"the note block ends at y={y:.1f}, past the title block at "
        f"{TITLE_BLOCK_TOP}. Shorten NOTES or tighten LINE_PITCH.")
    return s.render()


def splice(target: str, new: str) -> str:
    """Merge `new`'s lib_symbols into `target` and append its element blocks."""
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
    assert '(paper "A3")' in t, "run tools/port_r1.py fpga_ddr first (needs A3)"
    assert "(unit 6)" not in t, "already patched (unit 6 present)"
    assert '"C509"' not in t, "already patched (C509 present)"

    SCH.write_text(splice(t, build()))
    print("patched fpga_ddr.kicad_sch: U41 unit 6 + 13 caps (C509 new) + notes")


if __name__ == "__main__":
    main()
