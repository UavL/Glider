#!/usr/bin/env python3
"""Generate power.kicad_sch — R2 work package 2.

Implements docs/power.md. Run once; after the sheet has been opened and saved
in Eeschema it is edited in place, not regenerated.

Drawing style follows battery.kicad_sch: rails are power symbols (global in
KiCad, so no hierarchical label is needed for +VSYS / +3V3_AON / *_DCDC),
control and status signals get a local label next to their pin, and the
sheet-interface column at the right ties each of those names to a hierarchical
label. Every switching loop -- input cap, inductor, output cap, feedback
divider -- is drawn as real wire, because its topology is what the layout has
to honour.

Reference designators start at 10/20 so they do not collide with
battery.kicad_sch, which owns U1-U3, C1-C8, R1-R19 and L1.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402

PROJ = HERE.parent
SYMS = pathlib.Path(
    "/tmp/claude-1000/-home-lum-Ereader-Projekt-Glider-OG/"
    "24a17396-32d7-4c7d-976a-9df65f78dae8/scratchpad/syms"
)

R_FP = "Resistor_SMD:R_0402_1005Metric"
C_FP = "Capacitor_SMD:C_0402_1005Metric"
CB_FP = "Capacitor_SMD:C_0805_2012Metric"    # 10 uF and 22 uF bulk
# Placeholders: KiCad has no land pattern for either Murata DFE series, and
# the generic metric chip lands are the right body size. Check both against
# Murata's recommended pattern before layout -- docs/power.md §7.
L_FP = "Inductor_SMD:L_1210_3225Metric"      # DFE322512F, 3.2 x 2.5 mm, 1 uH
L2_FP = "Inductor_SMD:L_1008_2520Metric"     # DFE252012F, 2.5 x 2.0 mm, 0.47 uH

HIER = (("MCU_EN_5V", "input"),
        ("MCU_EN_3V3", "input"),
        ("MCU_EN_FPGA_CORE", "input"),
        ("MCU_EN_DDR", "input"),
        ("PG_3V3", "output"),
        ("PG_1V2", "output"),
        ("PG_1V35", "output"))

TI = "https://www.ti.com/lit/ds/symlink/"


def build():
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    sh = Sheet(
        sheets["power"], root_uuid, "r2", paper="A3",
        title="Glider-R2 / Reflow mainboard",
        rev="A", date="2026-08-06",
        comments=(
            "power — rail tree from +VSYS; every rail below +3V3_AON is gated",
            "See docs/power.md. Values and pin data cite datasheets/.",
        ),
        pwr_base=200,
    )
    for n in ("Device", "power", "Converter_DCDC"):
        sh.lib.add_dir(n, SYMS)
    sh.lib.add_file("symbols", PROJ.parent / "pcb_common" / "symbols.kicad_sym")
    sh.lib.add_file("r2", PROJ / "r2.kicad_sym")

    # Vertical passives carry reference and value clear of the wires above and
    # below. `side` flips them to the left where the space on the right is
    # already taken.
    def _vert(lib_id, ref, val, x, y, fp, dnp, side):
        dx = 2.54 if side == "right" else -2.54
        return sh.place(lib_id, ref, val, x, y, 0, footprint=fp, dnp=dnp,
                        ref_at=(x + dx, y - 1.27), val_at=(x + dx, y + 2.032),
                        justify="left" if side == "right" else "right")

    def RV(ref, val, x, y, dnp=False, fp=R_FP, side="right"):
        return _vert("Device:R", ref, val, x, y, fp, dnp, side)

    def CV(ref, val, x, y, fp=C_FP, dnp=False, side="right"):
        return _vert("Device:C", ref, val, x, y, fp, dnp, side)

    def LH(ref, val, x, y, fp=L_FP):
        return sh.place("Device:L", ref, val, x, y, 90, footprint=fp,
                        ref_at=(x, y - 4.445), val_at=(x, y + 5.08))

    def gnd(x, y):
        sh.power("GND", x, y)

    def note(x, y, *lines):
        for i, ln in enumerate(lines):
            sh.text(x, y + i * 3.81, ln, 1.27)

    # ================================================================
    # U10 — +3V3_AON. The one rail with no enable: it powers the STM32G0
    # that owns every other enable, so it must be up before firmware runs.
    # EN is tied to IN (tps7a02.pdf §7.3.4 permits it; the smart-enable
    # pulldown disconnects itself once the part is driven high).
    # ================================================================
    sh.text(30.48, 45.72, "+3V3_AON  —  always-on housekeeping rail", 2.0)
    note(30.48, 85.09,
         "STM32G0, I2C pull-ups, buttons. 25 nA quiescent.",
         "Dropout is 270 mV max at 200 mA, so the rail follows +VSYS down",
         "at low battery. Everything on it works below 3.3 V.")

    U10 = sh.place("r2:TPS7A0233DBV", "U10", "TPS7A0233DBVR", 69.85, 60.96,
                   footprint="Package_TO_SOT_SMD:SOT-23-5",
                   datasheet=TI + "tps7a02.pdf",
                   extra={"LCSC": "C5142805"},
                   ref_at=(62.23, 52.07), val_at=(62.23, 54.61),
                   justify="left")

    # input rail: +VSYS -> C20 -> IN, with EN strapped to IN
    sh.wire((34.29, 58.42), U10.pin("IN"))
    sh.wire((46.99, 58.42), (46.99, 53.34))
    sh.power("+VSYS", 46.99, 53.34)
    sh.junction(46.99, 58.42)
    C20 = CV("C20", "1uF/16V", 34.29, 66.04)
    sh.wire((34.29, 58.42), C20.pin("1"))
    sh.wire(C20.pin("2"), (34.29, 74.93))
    gnd(34.29, 74.93)

    sh.wire(U10.pin("EN"), (53.34, 63.5), (53.34, 58.42))
    sh.junction(53.34, 58.42)

    sh.nc(*U10.pin("NC"))
    sh.wire(U10.pin("GND"), (69.85, 74.93))
    gnd(69.85, 74.93)

    sh.wire(U10.pin("OUT"), (107.95, 58.42))
    sh.junction(92.71, 58.42)
    C21 = CV("C21", "1uF/16V", 92.71, 66.04)
    sh.wire((92.71, 58.42), C21.pin("1"))
    sh.wire(C21.pin("2"), (92.71, 74.93))
    gnd(92.71, 74.93)
    sh.wire((107.95, 58.42), (107.95, 53.34))
    sh.power("+3V3_AON", 107.95, 53.34)

    # ================================================================
    # U11 + U12 — +5V_DCDC. A boost has no load disconnect: disabled, its
    # body diode would leave ~VSYS-0.3 V on the SoM's VIN pin, which is a
    # partial-power state, not off. U11 breaks the input instead, upstream
    # of both the inductor and U12's own VIN pin. docs/power.md §2.2.
    # ================================================================
    sh.text(140.97, 45.72, "+5V_DCDC  —  SoM VIN and the EPD HV chain", 2.0)
    note(140.97, 116.84,
         "U11 is the real disconnect; U12's EN follows its own switched input,",
         "so one GPIO owns the pair and 'off' is unambiguous.")

    U11 = sh.place("r2:TPS22965DSG", "U11", "TPS22965DSGR", 177.8, 63.5,
                   footprint="Package_SON:Texas_DSG0008A_WSON-8-1EP_"
                             "2x2mm_P0.5mm_EP0.9x1.6mm",
                   datasheet=TI + "tps22965.pdf",
                   extra={"LCSC": "C122837"},
                   ref_at=(167.64, 52.07), val_at=(167.64, 54.61),
                   justify="left")

    # +VSYS bus into U11: C24 bypass, C22 bulk, VBIAS strap, then VIN 1+2
    sh.wire((140.97, 58.42), (165.1, 58.42))
    sh.wire((140.97, 58.42), (140.97, 53.34))
    sh.power("+VSYS", 140.97, 53.34)
    C24 = CV("C24", "100nF/16V", 146.05, 66.04, side="left")
    sh.wire((146.05, 58.42), C24.pin("1"))
    sh.wire(C24.pin("2"), (146.05, 74.93))
    gnd(146.05, 74.93)
    sh.junction(146.05, 58.42)

    C22 = CV("C22", "22uF/10V", 152.4, 66.04, fp=CB_FP)
    sh.wire((152.4, 58.42), C22.pin("1"))
    sh.wire(C22.pin("2"), (152.4, 74.93))
    gnd(152.4, 74.93)
    sh.junction(152.4, 58.42)

    sh.wire((161.29, 58.42), (161.29, 66.04), U11.pin("4"))    # VBIAS
    sh.junction(161.29, 58.42)
    sh.wire(U11.pin("1"), U11.pin("2"))                        # VIN 1 + 2
    sh.junction(165.1, 58.42)

    # ON: pulled down, so the 5 V rail is off until firmware asks
    sh.wire(U11.pin("3"), (165.1, 95.25), (146.05, 95.25))
    sh.label(146.05, 95.25, "MCU_EN_5V", justify="right")
    R20 = RV("R20", "100k", 156.21, 100.33)
    sh.wire((156.21, 95.25), R20.pin("1"))
    sh.junction(156.21, 95.25)
    sh.wire(R20.pin("2"), (156.21, 109.22))
    gnd(156.21, 109.22)

    # GND + thermal pad
    sh.wire(U11.pin("5"), (175.26, 77.47))
    sh.wire(U11.pin("9"), (180.34, 77.47))
    sh.wire((175.26, 77.47), (180.34, 77.47))
    sh.junction(177.8, 77.47)
    sh.wire((177.8, 77.47), (177.8, 82.55))
    gnd(177.8, 82.55)

    # CT sets the slew rate -> inrush; see docs/power.md §3.4
    C23 = CV("C23", "470pF/50V", 196.85, 74.93)
    sh.wire(U11.pin("6"), (196.85, 68.58), C23.pin("1"))
    sh.wire(C23.pin("2"), (196.85, 83.82))
    gnd(196.85, 83.82)

    # VSYS_SW: U11 out -> U12 in, and U12's own EN
    sh.wire(U11.pin("7"), U11.pin("8"))
    sh.junction(190.5, 58.42)
    sh.wire((190.5, 58.42), (236.22, 58.42))
    sh.label(203.2, 58.42, "VSYS_SW")

    U12 = sh.place("Converter_DCDC:TPS61022", "U12", "TPS61022RWUR",
                   241.3, 71.12,
                   footprint="Package_DFN_QFN:Texas_RWU0007A_VQFN-7_2x2mm_P0.5mm",
                   datasheet=TI + "tps61022.pdf",
                   extra={"LCSC": "C915088"},
                   ref_at=(233.68, 96.52), val_at=(233.68, 99.06),
                   justify="left")

    C25 = CV("C25", "22uF/10V", 209.55, 66.04, fp=CB_FP)
    sh.wire((209.55, 58.42), C25.pin("1"))
    sh.wire(C25.pin("2"), (209.55, 74.93))
    gnd(209.55, 74.93)
    sh.junction(209.55, 58.42)

    sh.wire((222.25, 58.42), (222.25, 71.12), U12.pin("5"))    # EN
    sh.junction(222.25, 58.42)

    sh.wire((236.22, 58.42), U12.pin("7"))                     # VIN
    sh.junction(236.22, 58.42)
    L10 = LH("L10", "1uH/6A", 240.03, 48.26)
    sh.wire((236.22, 58.42), (236.22, 48.26))
    sh.wire(L10.pin("2"), (246.38, 48.26), U12.pin("2"))       # -> SW

    sh.wire(U12.pin("1"), (241.3, 83.82))
    gnd(241.3, 83.82)

    # MODE low = automatic power save. Hardwired, but to the low-power
    # state; the 0R link is the place to lift it if a bench measurement
    # ever disagrees. docs/power.md §4.
    R23 = RV("R23", "0R", 224.79, 80.01, side="left")
    sh.wire(U12.pin("6"), (224.79, 73.66), R23.pin("1"))
    sh.wire(R23.pin("2"), (224.79, 88.9))
    gnd(224.79, 88.9)

    # output: divider first, then the two output caps, then the rail
    sh.wire(U12.pin("3"), (311.15, 71.12))
    R21 = RV("R21", "732k/1%", 259.08, 78.74)
    sh.wire((259.08, 71.12), R21.pin("1"))
    sh.junction(259.08, 71.12)
    C28 = CV("C28", "100pF/50V", 271.78, 78.74, dnp=True)
    sh.wire((271.78, 71.12), C28.pin("1"))
    sh.junction(271.78, 71.12)
    sh.wire(R21.pin("2"), (259.08, 86.36), (271.78, 86.36), C28.pin("2"))
    R22 = RV("R22", "100k/1%", 259.08, 92.71)
    sh.wire((259.08, 86.36), R22.pin("1"))
    sh.junction(259.08, 86.36)
    sh.wire(R22.pin("2"), (259.08, 101.6))
    gnd(259.08, 101.6)
    sh.wire(U12.pin("4"), (251.46, 73.66), (251.46, 88.9), (259.08, 88.9))
    sh.junction(259.08, 88.9)

    for ref, x in (("C26", 284.48), ("C27", 297.18)):
        c = CV(ref, "22uF/10V", x, 78.74, fp=CB_FP)
        sh.wire((x, 71.12), c.pin("1"))
        sh.junction(x, 71.12)
        sh.wire(c.pin("2"), (x, 87.63))
        gnd(x, 87.63)

    sh.wire((311.15, 71.12), (311.15, 66.04))
    sh.power("+5V_DCDC", 311.15, 66.04)

    # ================================================================
    # Sheet interface and ERC power flags, both in the right-hand margin.
    # +5V_DCDC, +3V3_DCDC and +3V3_AON each come off a pin the symbol
    # declares power_out, so ERC already sees a driver. The two buck rails
    # do not: their output is the far side of an inductor, and Device:L
    # pins are passive.
    # ================================================================
    sh.text(360.68, 60.96, "to mcu.kicad_sch", 1.27)
    y = 68.58
    for name, shape in HIER:
        sh.wire((372.11, y), (379.73, y))
        sh.label(372.11, y, name, justify="right")
        sh.hlabel(379.73, y, name, shape)
        y += 5.08

    sh.text(170.18, 226.06, "ERC power flags", 2.0)
    note(170.18, 229.87,
         "Only the two buck rails need one: their output is the far side",
         "of an inductor, so no pin declares itself a driver.")
    for i, (rail, x) in enumerate((("+1V2_DCDC", 224.79), ("+1V35_DCDC", 260.35))):
        sh.wire((x, 250.19), (x, 243.84))
        sh.power(rail, x, 250.19)
        sh.place("power:PWR_FLAG", f"#FLG{10 + i:02d}", "PWR_FLAG", x, 243.84,
                 ref_at=(x, 243.84), val_at=(x, 240.67), hide_ref=True)

    # ================================================================
    # U13 — +3V3_DCDC. Buck-boost, not buck: +VSYS runs 4.4 V down to
    # 3.0 V, so a step-down converter drops out halfway down the cell.
    # docs/power.md §2.1.
    # ================================================================
    sh.text(30.48, 124.46, "+3V3_DCDC  —  FPGA I/O, config NOR, microSD", 2.0)
    note(30.48, 203.2,
         "Buck-boost, not buck: a 1S cell cannot step down to 3.3 V.",
         "True shutdown with load disconnect, so the rail is genuinely",
         "off in standby.")

    U13 = sh.place("r2:TPS63802DLA", "U13", "TPS63802DLAR", 76.2, 158.75,
                   footprint="r2:Texas_DLA0010A_VSON-HR-10_2x3mm_P0.5mm",
                   datasheet=TI + "tps63802.pdf",
                   extra={"LCSC": "C2845237"},
                   ref_at=(85.09, 176.53), val_at=(85.09, 179.07),
                   justify="left")

    sh.wire((30.48, 153.67), U13.pin("VIN"))
    sh.wire((46.99, 153.67), (46.99, 148.59))
    sh.power("+VSYS", 46.99, 148.59)
    sh.junction(46.99, 153.67)
    C29 = CV("C29", "10uF/10V", 30.48, 161.29, fp=CB_FP, side="left")
    sh.wire((30.48, 153.67), C29.pin("1"))
    sh.wire(C29.pin("2"), (30.48, 170.18))
    gnd(30.48, 170.18)

    L11 = LH("L11", "0.47uH/6A", 76.2, 135.89, fp=L2_FP)
    sh.wire(U13.pin("L1"), L11.pin("1"))
    sh.wire(U13.pin("L2"), L11.pin("2"))

    sh.wire(U13.pin("EN"), (46.99, 161.29))
    sh.label(46.99, 161.29, "MCU_EN_3V3", justify="right")
    R26 = RV("R26", "100k", 55.88, 168.91, side="left")
    sh.wire((55.88, 161.29), R26.pin("1"))
    sh.junction(55.88, 161.29)
    sh.wire(R26.pin("2"), (55.88, 177.8))
    gnd(55.88, 177.8)

    R27 = RV("R27", "0R", 63.5, 175.26)
    sh.wire(U13.pin("MODE"), (63.5, 171.45), R27.pin("1"))
    sh.wire(R27.pin("2"), (63.5, 184.15))
    gnd(63.5, 184.15)

    sh.wire(U13.pin("GND"), (73.66, 180.34))
    sh.wire(U13.pin("AGND"), (78.74, 180.34))
    sh.wire((73.66, 180.34), (78.74, 180.34))
    sh.junction(76.2, 180.34)
    sh.wire((76.2, 180.34), (76.2, 185.42))
    gnd(76.2, 185.42)

    sh.wire(U13.pin("VOUT"), (127.0, 153.67))
    R24 = RV("R24", "511k/1%", 101.6, 161.29)
    sh.wire((101.6, 153.67), R24.pin("1"))
    sh.junction(101.6, 153.67)
    R25 = RV("R25", "91k/1%", 101.6, 173.99)
    sh.wire(R24.pin("2"), R25.pin("1"))
    sh.wire(R25.pin("2"), (101.6, 186.69))
    gnd(101.6, 186.69)
    sh.wire(U13.pin("FB"), (91.44, 161.29), (91.44, 167.64), (101.6, 167.64))
    sh.junction(101.6, 167.64)

    C30 = CV("C30", "22uF/10V", 114.3, 161.29, fp=CB_FP)
    sh.wire((114.3, 153.67), C30.pin("1"))
    sh.junction(114.3, 153.67)
    sh.wire(C30.pin("2"), (114.3, 170.18))
    gnd(114.3, 170.18)
    sh.wire((127.0, 153.67), (127.0, 148.59))
    sh.power("+3V3_DCDC", 127.0, 148.59)

    # PG is pulled up to +3V3_AON, the one rail that is always there, so
    # the MCU can read it before enabling anything. 470k not 10k: PG is
    # low whenever its rail is off, which in standby is always.
    sh.wire(U13.pin("PG"), (88.9, 193.04), (133.35, 193.04))
    sh.label(133.35, 193.04, "PG_3V3")
    R28 = RV("R28", "470k", 120.65, 187.96)
    sh.wire((120.65, 193.04), R28.pin("2"))
    sh.junction(120.65, 193.04)
    sh.wire(R28.pin("1"), (120.65, 180.34))
    sh.power("+3V3_AON", 120.65, 180.34)

    # ================================================================
    # U14, U15 — the two step-down rails. Identical circuits; only the
    # feedback divider and the net names differ.
    # ================================================================
    def buck(refs, x, y, rail, en_name, pg_name, r_top, vout_note):
        u, cin, cout, rtop, rbot, rpd, rpu, ind = refs
        sh.text(x - 44.45, y - 17.78, f"{rail}  —  {vout_note}", 2.0)

        U = sh.place("r2:TPS62A02DRL", u, "TPS62A02DRLR", x, y,
                     footprint="Package_TO_SOT_SMD:SOT-563",
                     datasheet=TI + "tps62a01.pdf",
                     extra={"LCSC": "C5350187"},
                     ref_at=(x - 7.62, y - 8.89), val_at=(x - 7.62, y - 6.35),
                     justify="left")

        # input
        sh.wire((x - 44.45, y - 2.54), U.pin("VIN"))
        sh.wire((x - 31.75, y - 2.54), (x - 31.75, y - 7.62))
        sh.power("+VSYS", x - 31.75, y - 7.62)
        sh.junction(x - 31.75, y - 2.54)
        c = CV(cin, "4.7uF/10V", x - 44.45, y + 5.08, fp=CB_FP)
        sh.wire((x - 44.45, y - 2.54), c.pin("1"))
        sh.wire(c.pin("2"), (x - 44.45, y + 13.97))
        gnd(x - 44.45, y + 13.97)

        # enable, pulled down
        sh.wire(U.pin("EN"), (x - 24.13, y))
        sh.label(x - 24.13, y, en_name, justify="right")
        r = RV(rpd, "100k", x - 17.78, y + 7.62)
        sh.wire((x - 17.78, y), r.pin("1"))
        sh.junction(x - 17.78, y)
        sh.wire(r.pin("2"), (x - 17.78, y + 16.51))
        gnd(x - 17.78, y + 16.51)

        sh.wire(U.pin("GND"), (x, y + 12.7))
        gnd(x, y + 12.7)

        # switch node -> inductor -> output rail
        li = LH(ind, "1uH/6A", x + 17.78, y - 7.62)
        sh.wire(U.pin("SW"), (x + 10.16, y - 7.62), li.pin("1"))
        sh.wire(li.pin("2"), (x + 21.59, y - 2.54), (x + 50.8, y - 2.54))

        rt = RV(rtop, r_top, x + 27.94, y + 5.08)
        sh.wire((x + 27.94, y - 2.54), rt.pin("1"))
        sh.junction(x + 27.94, y - 2.54)
        rb = RV(rbot, "100k/1%", x + 27.94, y + 17.78)
        sh.wire(rt.pin("2"), rb.pin("1"))
        sh.wire(rb.pin("2"), (x + 27.94, y + 26.67))
        gnd(x + 27.94, y + 26.67)
        sh.wire(U.pin("FB"), (x + 12.7, y), (x + 12.7, y + 11.43),
                (x + 27.94, y + 11.43))
        sh.junction(x + 27.94, y + 11.43)

        co = CV(cout, "22uF/6.3V", x + 40.64, y + 5.08, fp=CB_FP)
        sh.wire((x + 40.64, y - 2.54), co.pin("1"))
        sh.junction(x + 40.64, y - 2.54)
        sh.wire(co.pin("2"), (x + 40.64, y + 13.97))
        gnd(x + 40.64, y + 13.97)

        sh.wire((x + 50.8, y - 2.54), (x + 50.8, y - 7.62))
        sh.power(rail, x + 50.8, y - 7.62)

        # power good
        sh.wire(U.pin("PG"), (x + 11.43, y + 2.54), (x + 11.43, y + 33.02),
                (x + 50.8, y + 33.02))
        sh.label(x + 50.8, y + 33.02, pg_name)
        rp = RV(rpu, "470k", x + 17.78, y + 27.94, side="left")
        sh.wire((x + 17.78, y + 33.02), rp.pin("2"))
        sh.junction(x + 17.78, y + 33.02)
        sh.wire(rp.pin("1"), (x + 17.78, y + 20.32))
        sh.power("+3V3_AON", x + 17.78, y + 20.32)

    buck(("U14", "C31", "C32", "R29", "R30", "R31", "R32", "L12"),
         208.28, 158.75, "+1V2_DCDC", "MCU_EN_FPGA_CORE", "PG_1V2",
         "100k/1%", "Spartan-6 VCCINT")
    buck(("U15", "C33", "C34", "R33", "R34", "R35", "R36", "L13"),
         320.04, 158.75, "+1V35_DCDC", "MCU_EN_DDR", "PG_1V35",
         "124k/1%", "DDR3L and the FPGA's DDR bank VCCO")

    note(30.48, 233.68,
         "Every EN on this sheet is pulled down, so each rail is off until "
         "firmware asks for it.",
         "That is the whole difference from R1, where four bucks had ~SHDN "
         "wired to +5V.")

    return sh


if __name__ == "__main__":
    sheet = build()
    out = PROJ / "power.kicad_sch"
    sheet.write(out)
    print(f"wrote {out}")
    from sheet_pins import set_sheet_pins
    set_sheet_pins(PROJ / "r2.kicad_sch", "power", list(HIER))
