#!/usr/bin/env python3
"""Generate battery.kicad_sch — R2 work package 1.

Implements docs/battery.md. Run once; after the sheet has been opened and saved
in Eeschema it is edited in place, not regenerated.

Drawing style: the power path (VBUS -> PMID -> SW -> L -> SYS -> BAT), every
decoupling capacitor and both divider networks are drawn as real wires, because
their topology is what the layout has to honour. Control and status signals use
labels, and rails use power symbols (KiCad power symbols are global, so no
hierarchical label is needed for +VBUS / +VSYS / +VBAT / +3V3_AON).
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
CP_FP = "Capacitor_SMD:C_0805_2012Metric"   # bulk / power-path caps

HIER = (("SDA_AON", "bidirectional"), ("SCL_AON", "bidirectional"),
        ("CHG_INT#", "output"), ("CHG_PG#", "output"),
        ("CHG_STAT#", "output"), ("CHG_CE#", "input"),
        ("CHG_OTG", "input"), ("CHG_QON#", "bidirectional"),
        ("GAUGE_ALRT#", "output"), ("VBUS_DET", "output"),
        ("USB_DP", "bidirectional"), ("USB_DM", "bidirectional"))


def build():
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    sh = Sheet(
        sheets["battery"], root_uuid, "r2", paper="A3",
        title="Glider-R2 / Specter mainboard",
        rev="A", date="2026-08-05",
        comments=(
            "battery — cell, charger with power path, fuel gauge, USB-C",
            "See docs/battery.md. Values and pin data cite datasheets/.",
        ),
    )
    for n in ("Device", "Battery_Management", "Power_Protection",
              "Connector", "Connector_Generic", "power"):
        sh.lib.add_dir(n, SYMS)
    sh.lib.add_file("symbols", PROJ.parent / "pcb_common" / "symbols.kicad_sym")
    sh.lib.add_file("r2", PROJ / "r2.kicad_sym")

    # Vertical passives carry their reference and value to the right, clear of
    # the wires above and below; horizontal ones carry them above and below.
    def RV(ref, val, x, y, dnp=False, fp=R_FP):
        return sh.place("Device:R", ref, val, x, y, 0, footprint=fp, dnp=dnp,
                        ref_at=(x + 2.54, y - 1.27), val_at=(x + 2.54, y + 2.032),
                        justify="left")

    def RH(ref, val, x, y, dnp=False, fp=R_FP):
        return sh.place("Device:R", ref, val, x, y, 90, footprint=fp, dnp=dnp,
                        ref_at=(x, y - 3.81), val_at=(x, y + 4.445))

    def CV(ref, val, x, y, fp=C_FP):
        return sh.place("Device:C", ref, val, x, y, 0, footprint=fp,
                        ref_at=(x + 2.54, y - 1.27), val_at=(x + 2.54, y + 2.032),
                        justify="left")

    def CH(ref, val, x, y, fp=C_FP):
        return sh.place("Device:C", ref, val, x, y, 90, footprint=fp,
                        ref_at=(x, y - 4.445), val_at=(x, y + 5.08))

    def gnd(x, y):
        sh.power("GND", x, y)

    # ================================================================
    # USB-C input
    # ================================================================
    sh.text(27.94, 55.88, "USB-C  —  charge input and USB2 device port", 2.0)

    J1 = sh.place(
        "Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB-C 16P",
        43.18, 88.9,
        footprint="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
        extra={"LCSC": "C165948", "MPN": "TYPE-C-31-M-12"},
        ref_at=(27.94, 62.23), val_at=(27.94, 64.77), justify="left",
    )
    sh.wire(J1.pin("A1"), (43.18, 118.11))
    gnd(43.18, 118.11)
    sh.wire(J1.pin("SH"), (33.02, 118.11))
    gnd(33.02, 118.11)

    # VBUS -> polyfuse -> +VBUS
    F1 = sh.place("Device:Polyfuse", "F1", "1.5A hold", 71.12, 73.66, 90,
                  footprint="Resistor_SMD:R_1206_3216Metric",
                  ref_at=(71.12, 68.58), val_at=(71.12, 79.375))
    sh.wire(J1.pin("A4"), F1.pin("1"))
    sh.wire(F1.pin("2"), (86.36, 73.66))
    sh.power("+VBUS", 86.36, 73.66)

    sh.wire(J1.pin("A5"), (67.31, 78.74))
    sh.label(67.31, 78.74, "USB_CC1")
    sh.wire(J1.pin("B5"), (67.31, 81.28))
    sh.label(67.31, 81.28, "USB_CC2")

    # D+ / D- : tie the A- and B-side pins, then through the ESD array
    sh.wire(J1.pin("A7"), J1.pin("B7"))          # D- pair
    sh.wire(J1.pin("A6"), J1.pin("B6"))          # D+ pair
    sh.junction(58.42, 87.63)
    sh.wire((58.42, 87.63), (74.93, 87.63), (74.93, 90.17))
    sh.junction(58.42, 92.71)
    sh.wire((58.42, 92.71), (81.28, 92.71))

    U3 = sh.place("r2:USBLC6-2SC6", "U3", "USBLC6-2SC6", 86.36, 90.17,
                  footprint="Package_TO_SOT_SMD:SOT-23-6",
                  extra={"LCSC": "C7519"},
                  ref_at=(93.98, 82.55), val_at=(93.98, 85.09), justify="left")
    sh.wire((74.93, 90.17), U3.pin("1"))
    sh.wire(U3.pin("6"), (104.14, 90.17))
    sh.label(104.14, 90.17, "USB_DM")
    sh.wire(U3.pin("4"), (104.14, 92.71))
    sh.label(104.14, 92.71, "USB_DP")
    sh.wire(U3.pin("5"), (86.36, 80.01))
    sh.power("+VBUS", 86.36, 80.01)
    sh.wire(U3.pin("2"), (86.36, 100.33))
    gnd(86.36, 100.33)

    sh.nc(*J1.pin("A8"))
    sh.nc(*J1.pin("B8"))

    # CC pull-downs — 5.1k to GND on each CC line, never bridged
    sh.text(60.96, 127.0, "USB-C sink: 5.1k Rd on each CC, separately", 1.27)
    for ref, lbl, x in (("R1", "USB_CC1", 68.58), ("R2", "USB_CC2", 88.9)):
        r = RV(ref, "5.1k", x, 140.97)
        sh.wire(r.pin("1"), (x, 133.35))
        sh.label(x, 133.35, lbl, rot=90)
        sh.wire(r.pin("2"), (x, 149.86))
        gnd(x, 149.86)

    # ================================================================
    # Charger
    # ================================================================
    sh.text(146.05, 55.88, "Charger with power path  —  BQ25892", 2.0)

    U1 = sh.place("r2:BQ25892RTW", "U1", "BQ25892RTW", 177.8, 121.92,
                  footprint="Package_DFN_QFN:WQFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm",
                  datasheet="https://www.ti.com/lit/ds/symlink/bq25892.pdf",
                  extra={"LCSC": "C165480", "MPN": "BQ25892RTWR"},
                  ref_at=(167.64, 93.98), val_at=(167.64, 96.52), justify="left")

    # VBUS in, with its 1 uF close-in cap
    sh.wire((138.43, 104.14), U1.pin("1"))
    sh.power("+VBUS", 138.43, 104.14)
    c1 = CV("C1", "1uF/25V", 143.51, 111.76)
    sh.junction(143.51, 104.14)
    sh.wire((143.51, 104.14), c1.pin("1"))
    sh.wire(c1.pin("2"), (143.51, 120.65))
    gnd(143.51, 120.65)

    # left-side control pins -> labels
    for pin, name in (("2", "CHG_PSEL"), ("3", "CHG_PG#"), ("5", "SCL_AON"),
                      ("6", "SDA_AON"), ("7", "CHG_INT#"), ("8", "CHG_OTG"),
                      ("9", "CHG_CE#"), ("12", "CHG_QON#")):
        px, py = U1.pin(pin)
        sh.wire((px, py), (158.75, py))
        sh.label(158.75, py, name, justify="right")

    # ILIM: 260R -> 1.5 A ceiling (KILIM(max) 390 / 260). 130R would give 3 A.
    rl = RV("R8", "260R/1%", 158.75, 143.51)
    sh.wire(U1.pin("10"), rl.pin("1"))
    sh.wire(rl.pin("2"), (158.75, 151.13))
    gnd(158.75, 151.13)

    # right side
    sh.wire(U1.pin("4"), (198.12, 104.14))
    sh.label(198.12, 104.14, "CHG_STAT#")
    # pin 24 is NC on this variant, DSEL on the BQ25890/95
    sh.wire(U1.pin("24"), (198.12, 106.68))
    sh.label(198.12, 106.68, "CHG_DSEL")

    # PMID: 8.2 uF, 25 V rating
    cp = CV("C2", "8.2uF/25V", 209.55, 96.52, fp=CP_FP)
    sh.wire(U1.pin("23"), (209.55, 111.76), (209.55, 100.33))
    sh.wire(cp.pin("2"), (209.55, 100.33))
    sh.wire(cp.pin("1"), (209.55, 88.9))
    gnd(209.55, 88.9)

    # switching node -> inductor -> +VSYS
    L1 = sh.place("Device:L", "L1", "1uH/3A", 220.98, 116.84, 90,
                  footprint="Inductor_SMD:L_Taiyo-Yuden_NR-30xx",
                  ref_at=(220.98, 111.76), val_at=(220.98, 114.3))
    sh.wire(U1.pin("19"), L1.pin("1"))

    # bootstrap cap from BTST back to SW
    cb = sh.place("Device:C", "C3", "47nF/25V", 207.01, 128.27, 90,
                  footprint=C_FP, ref_at=(215.9, 127.0),
                  val_at=(215.9, 130.175), justify="left")
    sh.wire(U1.pin("21"), (203.2, 121.92), (203.2, 128.27))
    sh.wire(cb.pin("2"), (210.82, 128.27), (210.82, 116.84))
    sh.junction(210.82, 116.84)

    # SYS pins tie to the inductor output; every tap is a T, not a crossing
    sh.wire(L1.pin("2"), (264.16, 116.84))
    sh.wire(U1.pin("15"), (231.14, 127.0), (231.14, 116.84))
    sh.junction(231.14, 116.84)

    cs1 = CV("C4", "10uF/10V", 236.22, 127.0, fp=CP_FP)
    sh.wire((236.22, 116.84), cs1.pin("1"))
    sh.junction(236.22, 116.84)
    sh.wire(cs1.pin("2"), (236.22, 135.89))
    gnd(236.22, 135.89)

    cs2 = CV("C5", "10uF/10V", 251.46, 127.0, fp=CP_FP)
    sh.wire((251.46, 116.84), cs2.pin("1"))
    sh.junction(251.46, 116.84)
    sh.wire(cs2.pin("2"), (251.46, 135.89))
    gnd(251.46, 135.89)

    sh.wire((264.16, 116.84), (264.16, 109.22))
    sh.power("+VSYS", 264.16, 109.22)

    # BAT, REGN, TS
    sh.wire(U1.pin("13"), (196.85, 129.54))
    sh.power("+VBAT", 196.85, 129.54)
    sh.wire(U1.pin("22"), (198.12, 134.62))
    sh.label(198.12, 134.62, "REGN")
    sh.wire(U1.pin("11"), (198.12, 139.7))
    sh.label(198.12, 139.7, "CHG_TS")
    sh.wire(U1.pin("17"), (177.8, 151.13))
    gnd(177.8, 151.13)

    # REGN decoupling — 4.7 uF, also biases the TS divider
    cr = CV("C6", "4.7uF/10V", 214.63, 143.51, fp=CP_FP)
    sh.wire(cr.pin("1"), (214.63, 135.89))
    sh.label(214.63, 135.89, "REGN", rot=90)
    sh.wire(cr.pin("2"), (214.63, 151.13))
    gnd(214.63, 151.13)

    # ================================================================
    # TS network — 103AT NTC in the pack, RT1/RT2 derived from the
    # JEITA thresholds (docs/battery.md §4)
    # ================================================================
    sh.text(240.03, 152.4, "TS: 103AT NTC in the pack. RT1/RT2 solved from", 1.27)
    sh.text(240.03, 154.94, "V(T1) 73.25% and V(T5) 34.375% of REGN.", 1.27)
    sh.text(240.03, 157.48, "No NTC in pack -> fit 7.68k/10k instead.", 1.27)

    rt1 = RV("R9", "5.23k/1%", 220.98, 168.91)
    sh.wire(rt1.pin("1"), (220.98, 161.29))
    sh.label(220.98, 161.29, "REGN", rot=90)
    rt2 = RV("R10", "30.1k/1%", 220.98, 182.88)
    sh.wire(rt1.pin("2"), rt2.pin("1"))
    sh.junction(220.98, 175.26)
    sh.wire((220.98, 175.26), (231.14, 175.26))
    sh.label(231.14, 175.26, "CHG_TS")
    sh.wire(rt2.pin("2"), (220.98, 190.5))
    gnd(220.98, 190.5)

    # ================================================================
    # Battery connector
    # ================================================================
    sh.text(266.7, 55.88, "1S cell, 5000 mAh, with pack NTC", 2.0)

    J2 = sh.place("Connector_Generic:Conn_01x03", "J2", "JST-PH 3P",
                  299.72, 74.93,
                  footprint="Connector_JST:JST_PH_B3B-PH-K_1x03_P2.00mm_Vertical",
                  ref_at=(306.07, 66.04), val_at=(306.07, 68.58), justify="left")
    # BAT+
    sh.wire(J2.pin("1"), (275.59, 72.39))
    sh.wire((275.59, 72.39), (267.97, 72.39))
    sh.power("+VBAT", 267.97, 72.39)
    cbat = CV("C7", "10uF/10V", 275.59, 82.55, fp=CP_FP)
    sh.junction(275.59, 72.39)
    sh.wire((275.59, 72.39), cbat.pin("1"))
    sh.wire(cbat.pin("2"), (275.59, 91.44))
    gnd(275.59, 91.44)
    # NTC
    sh.wire(J2.pin("2"), (285.75, 74.93), (285.75, 97.79), (276.86, 97.79))
    sh.label(276.86, 97.79, "CHG_TS", justify="right")
    # BAT-
    sh.wire(J2.pin("3"), (290.83, 77.47), (290.83, 91.44))
    gnd(290.83, 91.44)

    # ================================================================
    # Fuel gauge
    # ================================================================
    sh.text(330.2, 55.88, "Fuel gauge  —  MAX17048, I2C 0x36", 2.0)

    U2 = sh.place("r2:MAX17048", "U2", "MAX17048G+T10", 355.6, 121.92,
                  footprint="Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm",
                  extra={"LCSC": "C2682616", "MPN": "MAX17048G+T10"},
                  ref_at=(368.3, 100.33), val_at=(368.3, 102.87), justify="left")
    # VDD is also the sense input: it must sit on the cell, not on a rail
    sh.wire(U2.pin("3"), (355.6, 105.41))
    sh.power("+VBAT", 355.6, 105.41)
    cg = CV("C8", "100nF/16V", 331.47, 116.84)
    sh.junction(355.6, 107.95)
    sh.wire((355.6, 107.95), (331.47, 107.95), cg.pin("1"))
    sh.wire(cg.pin("2"), (331.47, 125.73))
    gnd(331.47, 125.73)

    sh.nc(*U2.pin("2"))                      # CELL: not internally connected
    sh.wire(U2.pin("1"), (341.63, 127.0), (341.63, 133.35))
    gnd(341.63, 133.35)                       # CTG: connect to ground
    sh.wire(U2.pin("4"), (355.6, 140.97))
    gnd(355.6, 140.97)
    sh.wire(U2.pin("6"), (373.38, 127.0), (373.38, 133.35))
    gnd(373.38, 133.35)                      # QSTRT: to GND when unused

    for pin, name in (("8", "SDA_AON"), ("7", "SCL_AON"), ("5", "GAUGE_ALRT#")):
        px, py = U2.pin(pin)
        sh.wire((px, py), (378.46, py))
        sh.label(378.46, py, name)

    # ================================================================
    # Pull-ups, straps and the VBUS divider
    # ================================================================
    sh.text(27.94, 172.72, "Pull-ups to +3V3_AON (always-on domain)", 1.27)
    for ref, name, x in (("R3", "CHG_PG#", 30.48), ("R4", "CHG_STAT#", 50.8),
                         ("R5", "CHG_INT#", 71.12), ("R6", "SDA_AON", 91.44),
                         ("R7", "SCL_AON", 111.76),
                         ("R19", "GAUGE_ALRT#", 132.08)):
        r = RV(ref, "10k", x, 186.69)
        sh.wire(r.pin("1"), (x, 179.07))
        sh.power("+3V3_AON", x, 179.07)
        sh.wire(r.pin("2"), (x, 198.12))
        sh.label(x, 198.12, name, rot=270)

    # PSEL low = adapter source. High would declare a USB host source.
    sh.text(139.7, 172.72, "PSEL low = adapter source", 1.27)
    rp = RV("R11", "0R", 148.59, 186.69)
    sh.wire(rp.pin("1"), (148.59, 177.8))
    sh.label(148.59, 177.8, "CHG_PSEL", rot=90)
    sh.wire(rp.pin("2"), (148.59, 194.31))
    gnd(148.59, 194.31)

    # VBUS presence divider, 100k/100k -> 2.5 V at VBUS = 5 V.
    # Only draws while VBUS is present, so it costs no battery life.
    sh.text(173.99, 172.72, "VBUS presence, 2.5 V at 5 V in", 1.27)
    rv1 = RV("R12", "100k/1%", 182.88, 186.69)
    sh.wire(rv1.pin("1"), (182.88, 179.07))
    sh.power("+VBUS", 182.88, 179.07)
    rv2 = RV("R13", "100k/1%", 182.88, 200.66)
    sh.wire(rv1.pin("2"), rv2.pin("1"))
    sh.junction(182.88, 193.04)
    sh.wire((182.88, 193.04), (193.04, 193.04))
    sh.label(193.04, 193.04, "VBUS_DET")
    sh.wire(rv2.pin("2"), (182.88, 208.28))
    gnd(182.88, 208.28)

    # Both of these pins must be defined before the MCU is running.
    # CE has no internal pull, and the datasheet requires it be driven high
    # or low, never floating; pulling it low enables charging, which is the
    # behaviour needed to recover from a flat cell. OTG must default low so
    # boost mode cannot come up on its own.
    sh.text(27.94, 205.74,
            "Defaults while the MCU is unpowered: charging enabled, boost off",
            1.27)
    for ref, name, x in (("R17", "CHG_CE#", 30.48), ("R18", "CHG_OTG", 50.8)):
        r = RV(ref, "100k", x, 214.63)
        sh.wire(r.pin("1"), (x, 208.28))
        sh.label(x, 208.28, name, rot=90)
        sh.wire(r.pin("2"), (x, 222.25))
        gnd(x, 222.25)

    # ================================================================
    # Second-source option field — see docs/battery.md §1.
    # ================================================================
    sh.text(27.94, 236.22,
            "Second-source option field — fit ONLY for the BQ25890/95 "
            "(D+/D-/DSEL variant). Not fitted for the BQ25892/96.", 1.27)
    for ref, val, left, right, y in (
            ("R14", "0R", "CHG_PSEL", "USB_DP", 246.38),
            ("R15", "0R", "CHG_PG#", "USB_DM", 256.54),
            ("R16", "10k", "CHG_DSEL", "+3V3_AON", 267.97)):
        r = RH(ref, val, 82.55, y, dnp=True)
        sh.wire(r.pin("1"), (60.96, y))
        sh.label(60.96, y, left, justify="right")
        sh.wire(r.pin("2"), (104.14, y))
        if right.startswith("+"):
            sh.power(right, 104.14, y)
        else:
            sh.label(104.14, y, right)

    # ================================================================
    # ERC power flags. A KiCad power symbol is a power *input*; without a
    # PWR_FLAG, ERC reports every rail as undriven. These mark the rails
    # this sheet genuinely sources: +VBUS from the connector, +VBAT from
    # the cell, +VSYS from U1's power path (its SYS pin is `passive`, so
    # ERC cannot see it as a driver), and GND.
    # +3V3_AON is flagged only because power.kicad_sch does not exist yet.
    # ================================================================
    sh.text(264.16, 195.58, "ERC power flags — drop the +3V3_AON flag once", 1.27)
    sh.text(264.16, 198.12, "power.kicad_sch sources that rail.", 1.27)
    for i, (rail, x) in enumerate((("+VBUS", 269.24), ("+VBAT", 292.1),
                                   ("+VSYS", 314.96), ("GND", 337.82),
                                   ("+3V3_AON", 360.68))):
        sh.wire((x, 212.09), (x, 205.74))
        sh.power(rail, x, 212.09)
        sh.place("power:PWR_FLAG", f"#FLG{i:02d}", "PWR_FLAG", x, 205.74,
                 ref_at=(x, 205.74), val_at=(x, 202.57), hide_ref=True)

    # ================================================================
    # Sheet interface
    # ================================================================
    sh.text(383.54, 152.4, "to other sheets", 1.27)
    y = 157.48
    for name, shape in HIER:
        sh.wire((381.0, y), (388.62, y))
        sh.label(381.0, y, name, justify="right")
        sh.hlabel(388.62, y, name, shape)
        y += 5.08

    return sh


if __name__ == "__main__":
    sheet = build()
    out = PROJ / "battery.kicad_sch"
    sheet.write(out)
    print(f"wrote {out}")
    from sheet_pins import set_sheet_pins
    set_sheet_pins(PROJ / "r2.kicad_sch", "battery", list(HIER))
