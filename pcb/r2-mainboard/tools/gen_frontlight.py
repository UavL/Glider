#!/usr/bin/env python3
"""Generate frontlight.kicad_sch — R2 work package 6, redrawn 2026-08-17.

Implements docs/frontlight.md. This replaces the 2026-08-15 sheet completely.

**What changed and why.** The old sheet boosted `+VSYS_FL` to a 4.99 V rail
called `+5V2_FL` and let the panel regulate its own LED current, which is what
R1 did -- R1 drove an adapter board. The chosen panel (GDEP103TC2-FT11) has a
*bonded* frontlight whose tail is `LED1+/LED1-/LED2+/LED2-`: bare anodes and
cathodes with nothing regulating them. A voltage rail of any value is the wrong
answer, so `+5V2_FL`, `U53`'s TPS61022 and its feedback divider are all gone and
this sheet is a real two-channel constant-current driver.

`U53` is an LM3630A: boost to 40 V, two independently controlled current sinks
at 5-28.5 mA, adaptive headroom (V_HR 160-240 mV), 256-step exponential dimming
over I2C plus a PWM input. docs/frontlight.md §3 has why, including why a third
LGS6302B5 -- the obvious reuse, already on the BOM -- fails: 89.3 % duty at a
flat cell against a D_MAX of 90 % typ with no minimum.

**SEL must strap to IN, not GND.** Grounded, the LM3630A answers at 7-bit 0x36,
which is where max17048.pdf fixes the fuel gauge. Two devices on one address
takes down the always-on bus and the charger with it. R509 makes 0x38.

Sheet geometry notes, because they are load-bearing rather than cosmetic:

  * Every coordinate is a multiple of 1.27. UX/UY are 118 and 63 grid steps.
    `check_grid()` runs at render time; gen_dpi_in.py once put all 22 of its
    wires off-grid by choosing a round-looking origin.
  * Each resistor's drop sits in a column that no horizontal wire spans, and
    the symbol's pin order was chosen to make that possible -- HWEN is the
    lowest left pin so its pull-down falls into empty space instead of across
    SCL/SDA. See patch_lm3630a_symbol.py.

Run once. After the sheet has been opened and saved in Eeschema it is edited in
place, not regenerated.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402
from sheet_pins import set_sheet_pins  # noqa: E402

PROJ = HERE.parent
KICAD_CLI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/bin/kicad-cli"
KI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/share/kicad/symbols"
TI = "https://www.ti.com/lit/ds/symlink/"

R_FP = "Resistor_SMD:R_0402_1005Metric"
C_FP = "Capacitor_SMD:C_0402_1005Metric"
C6_FP = "Capacitor_SMD:C_0603_1608Metric"
C8_FP = "Capacitor_SMD:C_0805_2012Metric"
L_FP = "Inductor_SMD:L_Changjiang_FNR4030S"
D_FP = "footprints:D_SOD-323_Alt"
J_FP = "footprints:HC-FPC-05-09-8RLTAG"
U_FP = "r2:Texas_YFQ0012_DSBGA-12_1.91x1.39mm_Layout3x4_P0.4mm"

G = 1.27
UX, UY = 118 * G, 63 * G           # 149.86, 80.01 -- both on grid

NOTE = [
    "frontlight -- the panel's bonded LED film. See docs/frontlight.md.",
    "",
    "The tail is LED1+/LED1-/LED2+/LED2- on an 8-pin FPC: bare anodes and",
    "cathodes, nothing regulating them. So this is a constant-CURRENT driver,",
    "not a rail. LED1 is cool, LED2 is warm; 27 V, ~9 LEDs in series each.",
    "",
    "*** R509 straps SEL to IN so the I2C address is 0x38. Grounded, SEL",
    "*** gives 0x36 -- the same address as U2, the MAX17048 fuel gauge, whose",
    "*** address is fixed. That would take down the whole always-on bus.",
    "",
    "Brightness is 256 exponential steps per channel over I2C; FL_PWM1 is the",
    "hardware dim input. FL_PWM2 is no longer used and returns to the MCU",
    "spare pool. FL_EN still both enables the driver and reaches J6.43.",
    "",
    "1 MHz / 10 uH: at a flat cell with both channels at full scale the peak",
    "inductor current is 771 mA against a 1 A limit. 500 kHz leaves 10 %.",
]


def build() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    sh = Sheet(
        sheets["frontlight"], root_uuid, "r2", paper="A4",
        title="Glider-R2 / Reflow mainboard",
        rev="A", date="2026-08-17",
        comments=(
            "frontlight — LM3630A dual-channel LED driver, +VSYS_FL to the "
            "panel's bonded frontlight",
            "See docs/frontlight.md. SEL straps to IN: I2C 0x38, not 0x36.",
        ),
        pwr_base=1000,
    )
    for n in ("Device", "power", "Connector_Generic"):
        sh.lib.add_dir(n, KI / f"{n}.kicad_symdir")
    sh.lib.add_file("symbols", PROJ.parent / "pcb_common" / "symbols.kicad_sym")
    sh.lib.add_file("r2", PROJ / "r2.kicad_sym")

    def R(ref, val, x, y, rot=0, descr="", ref_at=None, val_at=None):
        return sh.place("Device:R", ref, val, x, y, rot, footprint=R_FP,
                        ref_at=ref_at or (x + 2.54, y - 1.27),
                        val_at=val_at or (x + 2.54, y + 2.032),
                        justify="left", description=descr)

    def C(ref, val, x, y, fp=C_FP, descr="", lcsc=None):
        return sh.place("Device:C", ref, val, x, y, 0, footprint=fp,
                        ref_at=(x + 2.54, y - 1.27), val_at=(x + 2.54, y + 2.032),
                        justify="left", description=descr,
                        extra={"LCSC": lcsc} if lcsc else None)

    u = sh.place("r2:LM3630A", "U53", "LM3630A", UX, UY, 0, footprint=U_FP,
                 datasheet=TI + "lm3630a.pdf",
                 extra={"LCSC": "C2678552", "DigiKey": "296-46302-1-ND"},
                 ref_at=(UX - 10.16, UY + 20.32),
                 val_at=(UX - 10.16, UY + 22.86), justify="left",
                 description="Dual-string white LED driver. 2 x 9 series LEDs "
                             "at 27 V, cool + warm, independently dimmed. "
                             "OVP set to the 32 V option. LCSC stock is 0; "
                             "board 1 orders from DigiKey.")

    P = {n: u.pin(n) for n in ("SW", "IN", "SEL", "SCL", "SDA", "PWM",
                               "HWEN", "OVP", "ILED1", "ILED2", "~{INTN}",
                               "GND")}
    CHAIN_Y = 45 * G                       # 57.15 -- the L/D row above the IC
    RAIL_X = 73 * G                        # 92.71 -- +VSYS_FL comes down here
    IN_X = 100 * G                         # 127.00 -- the IN/SEL drop column

    # --- input rail -------------------------------------------------------
    sh.power("+VSYS_FL", RAIL_X, CHAIN_Y - 6.35)
    sh.wire((RAIL_X, CHAIN_Y - 6.35), (RAIL_X, CHAIN_Y))
    sh.wire((RAIL_X, CHAIN_Y), (IN_X, CHAIN_Y))
    # 12 grid steps apart, not 7: at 7 the two value strings printed on top of
    # each other ("4.7uF/10V100nF/16V") in the first render.
    for ref, val, fp, x, lcsc, descr in (
            ("C514", "4.7uF/10V", C6_FP, 76 * G, None,
             "input bypass. lm3630a.pdf pin C3 asks for 2.2 uF or greater; "
             "4.7 uF derates into that band at 4 V"),
            ("C516", "100nF/16V", C_FP, 88 * G, None,
             "local HF bypass at IN")):
        c = C(ref, val, x, CHAIN_Y + 8.89, fp=fp, descr=descr, lcsc=lcsc)
        sh.wire((x, CHAIN_Y), c.pin("1"))
        sh.junction(x, CHAIN_Y)
        sh.wire(c.pin("2"), (x, CHAIN_Y + 17.78))
        sh.power("GND", x, CHAIN_Y + 17.78)

    # --- inductor: rail -> SW --------------------------------------------
    l33 = sh.place("Device:L", "L33", "10uH 2.4A Isat", 105 * G, CHAIN_Y, 90,
                   footprint=L_FP, extra={"LCSC": "C167879"},
                   ref_at=(105 * G - 2.54, CHAIN_Y - 3.81),
                   val_at=(105 * G - 2.54, CHAIN_Y - 1.27), justify="right",
                   description="FNR4030S100MT. Isat 2.4 A against a 771 mA "
                               "peak at the flat cell; DCR 130 mohm. Same "
                               "Changjiang family as L5.")
    la, lb = l33.pin("1"), l33.pin("2")
    l_left, l_right = (la, lb) if la[0] < lb[0] else (lb, la)
    sh.wire((IN_X, CHAIN_Y), l_left)
    sh.junction(IN_X, CHAIN_Y)

    # SW: L33's right end drops straight onto the pin -- same x by construction
    assert abs(l_right[0] - P["SW"][0]) < 1e-4, (
        f"L33 right pin x={l_right[0]} must equal SW x={P['SW'][0]}")
    sh.wire(l_right, P["SW"])
    sh.junction(*l_right)

    # --- diode: SW -> LED anode ------------------------------------------
    # Device:D is already horizontal at rot 0 (unlike Device:L, which is
    # vertical), and at rot 0 its cathode is on the left. 180 puts the anode
    # on the SW side, which is the direction a boost needs.
    # Text sits above the chain row and to the right of L33's, which is
    # justified right and so runs the other way. prop_angle=0 keeps it upright:
    # at rot 180 KiCad would otherwise print it mirrored.
    d34 = sh.place("Device:D", "D34", "1N5819WS", 114 * G, CHAIN_Y, 180,
                   footprint=D_FP, extra={"LCSC": "C488405"},
                   ref_at=(114 * G, CHAIN_Y - 11.43),
                   val_at=(114 * G, CHAIN_Y - 8.89), justify="left",
                   prop_angle=0,
                   description="40 V Schottky, already on the BOM as D2/D15. "
                               "The step current through it each cycle is why "
                               "it sits hard against SW -- lm3630a.pdf pin A3.")
    da, dk = d34.pin("A"), d34.pin("K")
    assert da[0] < dk[0], (
        f"D34 is backwards: anode x={da[0]} must be left of cathode x={dk[0]}")
    sh.wire(l_right, da)

    # Lanes on the right, each with its own column so no two collide:
    #   OVP 167.64 | C515 175.26 | labels 182.88 | R508 drop 177.8 (below)
    OUT_X = 144 * G                        # 182.88 -- the FL_LEDA label
    OVP_X = 132 * G                        # 167.64 -- OVP's own lane
    C515_X = 138 * G                       # 175.26
    sh.wire(dk, (OUT_X, CHAIN_Y))

    c515 = C("C515", "2.2uF/50V", C515_X, CHAIN_Y + 8.89, fp=C8_FP,
             descr="output. lm3630a.pdf asks for 1 uF; a 2.2 uF/50 V part "
                   "derates to about that at 28.5 V of DC bias")
    sh.wire((C515_X, CHAIN_Y), c515.pin("1"))
    sh.junction(C515_X, CHAIN_Y)
    # short drop: at +17.78 the GND symbol landed 2.5 mm from the ILED1 wire
    # and their text ran together
    sh.wire(c515.pin("2"), (C515_X, CHAIN_Y + 12.7))
    sh.power("GND", C515_X, CHAIN_Y + 12.7)

    # OVP senses the output capacitor's positive terminal
    sh.wire(P["OVP"], (OVP_X, P["OVP"][1]))
    sh.wire((OVP_X, P["OVP"][1]), (OVP_X, CHAIN_Y))
    sh.junction(OVP_X, CHAIN_Y)
    sh.label(OUT_X, CHAIN_Y, "FL_LEDA")

    # --- IN and SEL -------------------------------------------------------
    sh.wire((IN_X, CHAIN_Y), (IN_X, P["IN"][1]))
    sh.wire((IN_X, P["IN"][1]), P["IN"])
    sh.junction(IN_X, P["IN"][1])

    # SEL rises to the rail in its own column at 121.92, left of where the IN
    # wire starts, so the two verticals never meet.
    SEL_X = 96 * G                         # 121.92
    r509 = R("R509", "0R", 102 * G, P["SEL"][1], rot=90,
             ref_at=(102 * G - 3.81, P["SEL"][1] - 7.62),
             val_at=(102 * G - 3.81, P["SEL"][1] - 10.16),
             descr="SEL -> IN: I2C address 0x38. Grounded SEL is 0x36, which "
                   "collides with U2 (MAX17048), whose address is fixed. "
                   "Drawn as a link so the alternative stays a stuffing option.")
    ra, rb = r509.pin("1"), r509.pin("2")
    r_left, r_right = (ra, rb) if ra[0] < rb[0] else (rb, ra)
    sh.wire(P["SEL"], r_right)
    sh.wire(r_left, (SEL_X, P["SEL"][1]))
    sh.wire((SEL_X, P["SEL"][1]), (SEL_X, CHAIN_Y))
    sh.junction(SEL_X, CHAIN_Y)

    # --- control signals --------------------------------------------------
    HLX = 92 * G                           # 116.84
    for name, shape, x in (("SCL_AON", "bidirectional", HLX),
                           ("SDA_AON", "bidirectional", HLX),
                           ("FL_PWM1", "input", HLX),
                           ("FL_EN", "input", HLX)):
        key = {"SCL_AON": "SCL", "SDA_AON": "SDA",
               "FL_PWM1": "PWM", "FL_EN": "HWEN"}[name]
        y = P[key][1]
        sh.wire(P[key], (x, y))
        sh.hlabel(x, y, name, shape=shape, rot=180)

    # HWEN is the lowest left pin, so its pull-down drops into empty space
    en_y = P["HWEN"][1]
    r507 = R("R507", "100k", IN_X, en_y + 8.89,
             descr="HWEN pull-down: the driver stays off until firmware "
                   "asserts FL_EN, the pattern every MCU_EN_* rail uses")
    sh.wire((IN_X, en_y), r507.pin("1"))
    sh.junction(IN_X, en_y)
    sh.wire(r507.pin("2"), (IN_X, en_y + 17.78))
    sh.power("GND", IN_X, en_y + 17.78)

    # --- IC ground --------------------------------------------------------
    sh.wire(P["GND"], (P["GND"][0], P["GND"][1] + 6.35))
    sh.power("GND", P["GND"][0], P["GND"][1] + 6.35)

    # --- current sinks ----------------------------------------------------
    for key, net in (("ILED1", "FL_LED1K"), ("ILED2", "FL_LED2K")):
        y = P[key][1]
        sh.wire(P[key], (OUT_X, y))
        sh.label(OUT_X, y, net)

    # --- INTN --------------------------------------------------------------
    # R508 drops *downward* to +3V3. Drawn upward it has to cross both ILED
    # wires, which share this band; below INTN the page is empty.
    int_y = P["~{INTN}"][1]
    PU_X = 140 * G                         # 177.80
    sh.wire(P["~{INTN}"], (OUT_X, int_y))
    r508 = R("R508", "10k", PU_X, int_y + 8.89,
             descr="INTN is open drain; the fault interrupt needs a pull-up")
    sh.wire((PU_X, int_y), r508.pin("1"))
    sh.junction(PU_X, int_y)
    sh.wire(r508.pin("2"), (PU_X, int_y + 17.78))
    sh.power("+3V3", PU_X, int_y + 17.78)
    sh.hlabel(OUT_X, int_y, "FL_INT#", shape="output", rot=0)

    # --- J24, the frontlight tail ----------------------------------------
    # Placed well below the driver: beside it, its four labels landed on top
    # of R508 and the sink labels.
    JY = 96 * G                            # 121.92
    j = sh.place("Connector_Generic:Conn_01x08", "J24",
                 "HC-FPC-05-09-8RLTAG", 158 * G, JY, 0, footprint=J_FP,
                 extra={"LCSC": "C5213749"},
                 ref_at=(158 * G + 2.54, JY - 12.7),
                 val_at=(158 * G + 2.54, JY - 10.16), justify="left",
                 description="Frontlight FPC, 8-pin 0.5 mm. Pinout from "
                             "GDEP103TC2-FT11.pdf p.2, in the mechanical "
                             "drawing's title block. 500 mA / 50 V per contact "
                             "against 28.5 mA at 28.5 V.")
    JL_X = 146 * G                         # 185.42
    for pin, net in (("1", "FL_LEDA"), ("2", "FL_LED1K"),
                     ("5", "FL_LEDA"), ("6", "FL_LED2K")):
        px, py = j.pin(pin)
        sh.wire((px, py), (JL_X, py))
        sh.label(JL_X, py, net, justify="right")
    for pin in ("3", "4", "7", "8"):
        sh.nc(*j.pin(pin))

    y = 106 * G
    for line in NOTE:
        sh.text(20.32, y, line, 1.27)
        y += 3.81
    assert y <= 200.0, f"note block runs to y={y:.1f}, past the page"
    return sh.render()


def main() -> int:
    out = PROJ / "frontlight.kicad_sch"
    out.write_text(build())
    subprocess.run([str(KICAD_CLI), "sch", "upgrade", str(out)],
                   check=True, capture_output=True)
    set_sheet_pins(PROJ / "r2.kicad_sch", "frontlight", [
        ("FL_EN", "input"),
        ("FL_PWM1", "input"),
        ("SCL_AON", "bidirectional"),
        ("SDA_AON", "bidirectional"),
        ("FL_INT#", "output"),
    ])
    print(f"wrote {out.name}: U53 LM3630A, L33, D34, J24, "
          f"R507-R509, C514-C516")
    return 0


if __name__ == "__main__":
    sys.exit(main())
