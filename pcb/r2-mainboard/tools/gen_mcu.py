#!/usr/bin/env python3
"""Generate mcu.kicad_sch — R2 work package 3.

Implements docs/mcu.md. Run once; after the sheet has been opened and saved in
Eeschema it is edited in place, not regenerated.

Drawing style follows power.kicad_sch. The MCU symbol is large and has 60 I/O,
so every pin fans out to a local label rather than to a wire that crosses the
page; the supporting circuits (decoupling, crystal, reset, SWD, buttons, LED)
sit in labelled blocks around it, and the sheet interface is three columns of
hierarchical labels on the right. Local and hierarchical labels of the same
name are one net in KiCad, which is what joins the two halves.

Reference designators start at 20 (U/Y/SW/D/J/FB) and 40 (R/C) so they do not
collide with battery.kicad_sch (U1-U3, C1-C8, R1-R19, L1) or power.kicad_sch
(U10-U15, C20-C34, R20-R36, L10-L13).
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402

PROJ = HERE.parent
KI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/share/kicad/symbols"

R_FP = "Resistor_SMD:R_0402_1005Metric"
C_FP = "Capacitor_SMD:C_0402_1005Metric"
CB_FP = "Capacitor_SMD:C_0603_1608Metric"          # 4.7 uF bulk
FB_FP = "Inductor_SMD:L_0402_1005Metric"
XTAL_FP = "Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm"
LED_FP = "LED_SMD:LED_0603_1608Metric"
SW_FP = "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A"
HDR_FP = "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical"

DS_ST = "https://www.st.com/resource/en/datasheet/stm32g0b1rc.pdf"

UX, UY = 152.4, 152.4          # MCU origin
LLAB, RLAB = 114.3, 190.5      # local-label columns either side of the MCU

# --- pin assignment ------------------------------------------------------
# Verified against stm32g0b1.pdf (DS13560 Rev 1) Table 12, column "LQFP64 - GP",
# and Tables 13-20 for every alternate function. docs/mcu.md §3.
LEFT = [
    ("7",  "+3V3_VREF"),         # VREF+, fed from VDD through FB20
    ("10", "MCU_EN_5V"),         # PF0
    ("11", "MCU_EN_3V3"),        # PF1
    ("12", "MCU_NRST"),          # PF2-NRST
    ("13", "MCU_EN_FPGA_CORE"),  # PC0
    ("14", "MCU_EN_DDR"),        # PC1
    ("15", "LED_STAT#"),         # PC2
    ("39", "KEY_PREV#"),         # PC7  EXTI7
    ("40", "KEY_NEXT#"),         # PD8  EXTI8
    ("50", "CHG_INT#"),          # PD0  EXTI0
    ("51", "VBUS_DET"),          # PD1  EXTI1
    ("52", "CHG_PG#"),           # PD2  EXTI2
    ("53", "GAUGE_ALRT#"),       # PD3  EXTI3
    ("54", "CHG_STAT#"),         # PD4
    ("55", "CHG_CE#"),           # PD5
    ("56", "QON_SNS"),           # PD6  EXTI6 -- input only, no pull (§2.2)
    ("1",  "PG_1V35"),           # PC11
    ("2",  "PG_1V2"),            # PC12
    ("3",  "PG_3V3"),            # PC13 -- VBAT-domain pin, input only
    ("4",  "OSC32_IN"),          # PC14
    ("5",  "OSC32_OUT"),         # PC15
]
RIGHT = [
    ("17", "VP_MEA"),            # PA0  ADC_IN0
    ("18", "VN_MEA"),            # PA1  ADC_IN1
    ("19", "VGH_MEA"),           # PA2  ADC_IN2
    ("20", "VGL_MEA"),           # PA3  ADC_IN3
    ("21", "VCOM_DAC"),          # PA4  DAC1_OUT1
    ("22", "VGH_DAC"),           # PA5  DAC1_OUT2
    ("23", "VCOM_MEA"),          # PA6  ADC_IN6
    ("24", "VBUS_MEA"),          # PA7  ADC_IN7
    ("36", "SOM_WAKE#"),         # PA8
    ("37", "MCU_TXD"),           # PA9  USART1_TX  AF1
    ("42", "MCU_RXD"),           # PA10 USART1_RX  AF1
    ("45", "MCU_SWDIO"),         # PA13 SWDIO
    ("46", "MCU_SWCLK"),         # PA14 SWCLK / BOOT0
    ("47", "SOM_RESET#"),        # PA15
    ("27", "EPD_PWR_EN_MCU"),    # PB0  -- via R45, see block F
    ("28", "EPD_POS_EN"),        # PB1
    ("29", "VCOM_EN"),           # PB2
    ("57", "CHG_OTG"),           # PB3
    ("58", "SOM_IRQ#"),          # PB4
    ("59", "FL_EN"),             # PB5
    ("60", "FL_PWM1"),           # PB6  TIM4_CH1 AF9
    ("61", "FL_PWM2"),           # PB7  TIM4_CH2 AF9
    ("62", "SCL_AON"),           # PB8  I2C1_SCL AF6
    ("63", "SDA_AON"),           # PB9  I2C1_SDA AF6
    ("30", "VCOM_MEA_EN"),       # PB10
    ("31", "EPD_THROT"),         # PB11
    ("33", "FPGA_PROG#"),        # PB13
    ("34", "FPGA_DONE"),         # PB14
    ("35", "FPGA_SUSP"),         # PB15
]
# Reserve, no-connected so ERC stays honest. Four are ADC-capable.
SPARE = ["16", "25", "26", "38", "48", "49", "64", "41", "32", "43", "44"]

# --- sheet interface -----------------------------------------------------
GROUPS = [
    (228.6, "to power.kicad_sch", [
        ("MCU_EN_5V", "output"), ("MCU_EN_3V3", "output"),
        ("MCU_EN_FPGA_CORE", "output"), ("MCU_EN_DDR", "output"),
        ("PG_3V3", "input"), ("PG_1V2", "input"), ("PG_1V35", "input"),
    ]),
    (228.6, "to battery.kicad_sch   (I2C also to power_mon)", [
        ("SDA_AON", "bidirectional"), ("SCL_AON", "bidirectional"),
        ("CHG_INT#", "input"), ("CHG_PG#", "input"), ("CHG_STAT#", "input"),
        ("CHG_CE#", "output"), ("CHG_OTG", "output"),
        ("CHG_QON#", "bidirectional"), ("GAUGE_ALRT#", "input"),
        ("VBUS_DET", "input"),
    ]),
    (297.18, "to epd_power.kicad_sch and power_mon.kicad_sch", [
        ("EPD_PWR_EN", "output"), ("EPD_POS_EN", "output"),
        ("VCOM_EN", "output"), ("VCOM_MEA_EN", "output"),
        ("EPD_THROT", "output"), ("VCOM_DAC", "output"),
        ("VGH_DAC", "output"), ("VCOM_MEA", "input"), ("VP_MEA", "input"),
        ("VN_MEA", "input"), ("VGH_MEA", "input"), ("VGL_MEA", "input"),
        ("VBUS_MEA", "input"),
    ]),
    (365.76, "to fpga_config, som and frontlight", [
        ("FPGA_PROG#", "output"), ("FPGA_DONE", "input"),
        ("FPGA_SUSP", "output"), ("SOM_WAKE#", "output"),
        ("SOM_IRQ#", "output"), ("SOM_RESET#", "output"),
        ("MCU_TXD", "output"), ("MCU_RXD", "input"),
        ("FL_EN", "output"), ("FL_PWM1", "output"), ("FL_PWM2", "output"),
    ]),
]
HIER = [pin for _, _, pins in GROUPS for pin in pins]


def build():
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    sh = Sheet(
        sheets["mcu"], root_uuid, "r2", paper="A3",
        title="Glider-R2 / Reflow mainboard",
        rev="A", date="2026-08-07",
        comments=(
            "mcu — STM32G0 housekeeping: rail enables, EPD HV, charger, buttons",
            "See docs/mcu.md. Pin assignment cites datasheets/stm32g0b1.pdf.",
        ),
        pwr_base=300,
    )
    for n in ("Device", "power", "Switch", "Connector_Generic",
              "MCU_ST_STM32G0"):
        sh.lib.add_dir(n, KI / f"{n}.kicad_symdir")
    sh.lib.add_file("symbols", PROJ.parent / "pcb_common" / "symbols.kicad_sym")

    def _vert(lib_id, ref, val, x, y, fp, side, dnp=False):
        dx = 2.54 if side == "right" else -2.54
        return sh.place(lib_id, ref, val, x, y, 0, footprint=fp, dnp=dnp,
                        ref_at=(x + dx, y - 1.27), val_at=(x + dx, y + 2.032),
                        justify="left" if side == "right" else "right")

    def RV(ref, val, x, y, side="right", fp=R_FP):
        return _vert("Device:R", ref, val, x, y, fp, side)

    def CV(ref, val, x, y, side="right", fp=C_FP):
        return _vert("Device:C", ref, val, x, y, fp, side)

    def gnd(x, y):
        sh.power("GND", x, y)

    def note(x, y, *lines):
        for i, ln in enumerate(lines):
            sh.text(x, y + i * 3.81, ln, 1.27)

    def shunt(cls, ref, val, x, y_top, y_gnd, side="right", fp=None):
        """A part hanging from a node at y_top down to a ground at y_gnd."""
        kw = {"fp": fp} if fp else {}
        p = cls(ref, val, x, y_top + 3.81, side=side, **kw)
        sh.wire(p.pin("2"), (x, y_gnd))
        gnd(x, y_gnd)
        return p

    # ================================================================
    # U20 — the controller. Every pin fans out to a local label; the
    # supporting blocks reach it by name.
    # ================================================================
    U = sh.place("MCU_ST_STM32G0:STM32G0B1RCTx", "U20", "STM32G0B1RCT6",
                 UX, UY, 0,
                 footprint="Package_QFP:LQFP-64_10x10mm_P0.5mm",
                 datasheet=DS_ST,
                 extra={"LCSC": "C3034735"},
                 ref_at=(UX - 25.4, UY - 50.8),
                 val_at=(UX + 5.08, UY - 50.8),
                 justify="left")

    for num, net in LEFT:
        x, y = U.pin(num)
        sh.wire((x, y), (LLAB, y))
        sh.label(LLAB, y, net, justify="right")
    for num, net in RIGHT:
        x, y = U.pin(num)
        sh.wire((x, y), (RLAB, y))
        sh.label(RLAB, y, net, justify="left")
    for num in SPARE:
        sh.nc(*U.pin(num))

    # VDD (pin 8) and VBAT (pin 6) sit 2.54 mm apart on the top edge. No coin
    # cell, so the backup domain simply follows VDD.
    vbat, vdd = U.pin("6"), U.pin("8")
    sh.wire(vbat, (vbat[0], vbat[1] - 6.35), (vdd[0], vdd[1] - 6.35), vdd)
    sh.wire((vbat[0], vbat[1] - 6.35), (vbat[0], vbat[1] - 11.43))
    sh.junction(vbat[0], vbat[1] - 6.35)
    sh.power("+3V3_AON", vbat[0], vbat[1] - 11.43)

    vss = U.pin("9")
    sh.wire(vss, (vss[0], vss[1] + 6.35))
    gnd(vss[0], vss[1] + 6.35)

    # ================================================================
    # Block A — supply and decoupling.  stm32g0b1.pdf Figure 15 (p.65).
    # ================================================================
    sh.text(25.4, 34.29, "Supply and decoupling", 2.0)
    for ref, val, x, fp in (("C40", "4.7uF/10V", 25.4, CB_FP),
                            ("C41", "100nF/16V", 38.1, C_FP),
                            ("C42", "100nF/16V", 50.8, C_FP)):
        shunt(CV, ref, val, x, 45.72, 60.96, fp=fp)
    sh.wire((25.4, 45.72), (76.2, 45.72))
    for x in (31.75, 38.1, 50.8):
        sh.junction(x, 45.72)
    sh.wire((31.75, 45.72), (31.75, 40.64))
    sh.power("+3V3_AON", 31.75, 40.64)
    sh.text(21.59, 68.58, "VDD/VDDA (8)        VBAT (6)", 1.27)

    FB = sh.place("Device:FerriteBead", "FB20", "120R@100M", 76.2, 49.53, 0,
                  footprint=FB_FP, extra={"LCSC": "C85812"},
                  ref_at=(78.74, 48.26), val_at=(78.74, 52.324),
                  justify="left")
    sh.wire(FB.pin("2"), (76.2, 66.04), (104.14, 66.04))
    sh.label(104.14, 66.04, "+3V3_VREF", justify="left")
    for ref, val, x in (("C43", "1uF/16V", 88.9), ("C44", "100nF/16V", 101.6)):
        shunt(CV, ref, val, x, 66.04, 81.28)
        sh.junction(x, 66.04)
    sh.text(80.01, 71.12, "VREF+ (7)", 1.27)

    note(25.4, 88.9,
         "Figure 15, p.65: 100 nF + 4.7 uF on VDD/VDDA, 100 nF + 1 uF on VREF+.",
         "LAYOUT — the caution under that figure asks for these directly at, or",
         "below, their own pins: C40/C41 at pin 8, C43/C44 at pin 7.",
         "VDDA is merged into the VDD pin on STM32G0, so FB20 isolates the ADC",
         "reference and nothing else. VREFBUF must stay DISABLED in firmware:",
         "enabling it drives the buffer output back into the rail. docs/mcu.md §5.2.")

    # ================================================================
    # Block B — LSE. The RTC has to keep time across standby; the system
    # clock is HSI16, so there is no HSE and PF0/PF1 stay free for enables.
    # ================================================================
    sh.text(25.4, 116.84, "32.768 kHz LSE", 2.0)
    Y = sh.place("Device:Crystal", "Y20", "32.768kHz", 60.96, 129.54, 0,
                 footprint=XTAL_FP, extra={"LCSC": "C32346"},
                 ref_at=(60.96, 123.19), val_at=(60.96, 126.365),
                 justify="left")
    for x, pin, lab, lx, just in ((48.26, "1", "OSC32_IN", 33.02, "right"),
                                  (73.66, "2", "OSC32_OUT", 88.9, "left")):
        sh.wire(Y.pin(pin), (x, 129.54))
        sh.wire((x, 129.54), (lx, 129.54))
        sh.label(lx, 129.54, lab, justify=just)
        shunt(CV, "C46" if pin == "1" else "C47", "18pF/50V", x,
              129.54, 144.78)
        sh.junction(x, 129.54)

    note(25.4, 154.94,
         "CL = C1·C2/(C1+C2) + Cstray. A 12.5 pF crystal with ~3 pF of stray",
         "gives 18 pF each. Y20's actual CL is NOT verified — Epson FC-135",
         "ships in 12.5 / 9 / 7 pF and the LCSC listing does not say which.",
         "Confirm before layout, and check drive level. docs/mcu.md §9.")

    # ================================================================
    # Block C — reset and SWD.
    # ================================================================
    sh.text(25.4, 179.07, "Reset and SWD", 2.0)
    sh.wire((22.86, 190.5), (33.02, 190.5))
    sh.label(22.86, 190.5, "MCU_NRST", justify="right")
    shunt(CV, "C45", "100nF/16V", 33.02, 190.5, 205.74)

    J = sh.place("Connector_Generic:Conn_01x05", "J20", "SWD (DNP)",
                 88.9, 198.12, 0, footprint=HDR_FP, dnp=True,
                 ref_at=(88.9, 186.69), val_at=(88.9, 189.865),
                 justify="left")
    # 2.54 mm pin pitch is too tight for five pieces of 1.27 mm text side by
    # side, so the three signal labels fan out at staggered lengths and the two
    # supply symbols leave vertically, where their own text has room.
    for pin, net, reach in (("2", "MCU_SWCLK", 22.86), ("4", "MCU_SWDIO", 15.24),
                            ("5", "MCU_NRST", 30.48)):
        x, y = J.pin(pin)
        sh.wire((x, y), (x - reach, y))
        sh.label(x - reach, y, net, justify="right")
    jx, jy = J.pin("1")
    sh.wire((jx, jy), (jx - 7.62, jy), (jx - 7.62, jy - 7.62))
    sh.power("+3V3_AON", jx - 7.62, jy - 7.62)
    jx, jy = J.pin("3")
    sh.wire((jx, jy), (jx - 10.16, jy), (jx - 10.16, jy + 12.7))
    gnd(jx - 10.16, jy + 12.7)

    note(48.26, 218.44,
         "J20 is pads only, not fitted — the device has to stay thin. Order",
         "matches CN4 on ST Nucleo boards (3V3, SWCLK, GND, SWDIO, NRST) so a",
         "stock ST-LINK cable fits if a header is soldered on for bring-up.")

    # PA14 is SWCLK and BOOT0 on one pin. R40 is invisible to a push-pull
    # debugger and makes boot-from-flash unconditional.
    sh.wire((88.9, 233.68), (99.06, 233.68))
    sh.label(88.9, 233.68, "MCU_SWCLK", justify="right")
    shunt(RV, "R40", "10k", 99.06, 233.68, 248.92)

    note(25.4, 240.03,
         "R40: PA14 is SWCLK *and* BOOT0 (Table 12, p.53). Reset already",
         "applies an internal pull-down (note 4) and nBOOT_SEL defaults to",
         "booting from the option bytes; R40 makes that unconditional.")

    # ================================================================
    # Block D — status LED. Deliberately not on PC13: that pin is fed
    # through the VBAT power switch, which the datasheet caps at 3 mA and
    # explicitly forbids using as an LED current source (Table 12 note 1).
    # ================================================================
    sh.text(25.4, 257.81, "Status LED", 2.0)
    sh.power("+3V3_AON", 25.4, 267.97)
    sh.wire((25.4, 267.97), (25.4, 271.78))
    D = sh.place("Device:LED", "D20", "GREEN", 33.02, 271.78, 0,
                 footprint=LED_FP, extra={"LCSC": "C125098"},
                 ref_at=(31.75, 266.7), val_at=(31.75, 278.13),
                 justify="left")
    sh.wire((25.4, 271.78), D.pin("1"))
    r44 = sh.place("Device:R", "R44", "1k", 44.45, 271.78, 90,
                   footprint=R_FP,
                   ref_at=(44.45, 266.7), val_at=(44.45, 278.13),
                   justify="left")
    sh.wire(D.pin("2"), r44.pin("1"))
    sh.wire(r44.pin("2"), (60.96, 271.78))
    sh.label(60.96, 271.78, "LED_STAT#", justify="left")

    # ================================================================
    # Block E — buttons. docs/mcu.md §2.2 and §5.5.
    # ================================================================
    sh.text(133.35, 217.17, "Buttons", 2.0)

    def button(ref, x, net, pull_ref, cap_ref, caption):
        sh.text(x - 1.27, 233.68, caption, 1.27)
        SW = sh.place("Switch:SW_Push", ref, "SW", x, 246.38, 0,
                      footprint=SW_FP, extra={"LCSC": "C318884"},
                      ref_at=(x - 1.27, 240.03), val_at=(x - 1.27, 252.73),
                      justify="left")
        node = x - 15.24
        sh.wire(SW.pin("1"), (node, 246.38))
        sh.wire(SW.pin("2"), (x + 10.16, 246.38), (x + 10.16, 254))
        gnd(x + 10.16, 254)
        # node column: pull-up above, debounce cap below, label to the left
        sh.wire((node, 237.49), (node, 252.73))
        sh.wire((node - 12.7, 241.3), (node, 241.3))
        sh.label(node - 12.7, 241.3, net, justify="right")
        sh.junction(node, 241.3)
        sh.junction(node, 246.38)
        # The node column already ends exactly on R.2 and C.1 -- wiring to
        # them again would emit a zero-length wire, which ERC reports as a
        # four-way junction.
        if pull_ref:
            r = RV(pull_ref, "100k", node, 233.68, side="left")
            sh.wire(r.pin("1"), (node, 226.06))
            sh.power("+3V3_AON", node, 226.06)
        c = CV(cap_ref, "100nF/16V", node, 256.54, side="left")
        sh.wire(c.pin("2"), (node, 264.16))
        gnd(node, 264.16)
        return node

    # Kept left of x = 295: the A3 title block owns the bottom-right corner.
    button("SW21", 165.1, "KEY_PREV#", "R42", "C48",
           "page back   PC7 / EXTI7")
    button("SW22", 220.98, "KEY_NEXT#", "R43", "C49",
           "page forward   PD8 / EXTI8")
    qnode = button("SW20", 276.86, "CHG_QON#", None, "C50",
                   "power   PD6 / EXTI6")

    # R41 taps CHG_QON# for the MCU. Series only: the MCU never drives QON,
    # so this is a fault-current limiter and an isolation of pin capacitance,
    # not a divider. QON idles at 4.3 V — see docs/mcu.md §2.2.
    r41 = RV("R41", "1k", qnode, 229.87, side="left")
    sh.wire((qnode, 237.49), r41.pin("2"))
    sh.wire(r41.pin("1"), (qnode, 222.25), (qnode + 15.24, 222.25))
    sh.label(qnode + 15.24, 222.25, "QON_SNS", justify="left")

    note(114.3, 271.78,
         "SW20 shorts CHG_QON# straight to GND — what the charger expects, and "
         "the only path that still works with the MCU unpowered:",
         "in ship mode the BATFET is off, so with no USB attached +VSYS and "
         "therefore +3V3_AON do not exist. QON idles at 4.3 V from a",
         "200 k internal pull-up (bq25890.pdf) and PD6 is a 5 V-tolerant FT "
         "pin, so firmware must leave that pin's internal pull-up/pull-down",
         "DISABLED (Table 21 note 2). A 15 s hold forces a BATFET reset, so a "
         "clean shutdown has to finish well inside 12 s.")

    # ================================================================
    # Block F — EPD_PWR_EN series resistor, carried over from R1.
    #
    # R1 puts a 1 k in series between the MCU pin and EPD_PWR_EN (R22 on its
    # mcu sheet) because power_mon's U21 has its open-drain CRITICAL output on
    # the same net: an INA3221 over-current trip has to be able to pull the EPD
    # rail's enable low even while the MCU is driving it high. Without the
    # resistor the two fight and the protection does nothing.
    # ================================================================
    sh.text(299.72, 177.8, "EPD_PWR_EN series", 2.0)
    r45 = sh.place("Device:R", "R45", "1k", 320.04, 190.5, 90,
                   footprint=R_FP,
                   ref_at=(320.04, 185.42), val_at=(320.04, 196.85),
                   justify="left")
    sh.wire((299.72, 190.5), r45.pin("1"))
    sh.label(299.72, 190.5, "EPD_PWR_EN_MCU", justify="right")
    sh.wire(r45.pin("2"), (345.44, 190.5))
    sh.label(345.44, 190.5, "EPD_PWR_EN", justify="left")
    note(299.72, 198.12,
         "power_mon's U21 drives this net open-drain from CRITICAL, so an",
         "over-current trip must win against the MCU. R45 limits that fight to",
         "~3.3 mA. PB0 can also be read back to see the trip. docs/epd-port.md §4.")

    # ================================================================
    # Sheet interface.
    # ================================================================
    sh.text(215.9, 34.29, "Sheet interface", 2.0)
    ys = {}
    for x, heading, pins in GROUPS:
        y = ys.get(x, 45.72)
        sh.text(x - 15.24, y, heading, 1.27)
        y += 6.35
        for name, shape in pins:
            # A hierarchical label has to sit on a wire that carries the name,
            # or it dangles; the local label is what ties it to the pin.
            sh.wire((x - 7.62, y), (x, y))
            sh.label(x - 7.62, y, name, justify="right")
            sh.hlabel(x, y, name, shape)
            y += 5.08
        ys[x] = y + 6.35

    note(215.9, 165.1,
         "MCU_TXD and MCU_RXD are named from the MCU's point of view. On",
         "som.kicad_sch, MCU_TXD lands on the SoM's UART RX and MCU_RXD on its TX.",
         "",
         "The SoM, not the MCU, drives Caster's CSR bus — Caster/rtl/csr.v is a",
         "4-wire SPI slave, and the LUT/OSD data it carries lives on the SoM's",
         "eMMC. The MCU keeps only FPGA_PROG#/DONE/SUSP, which are power-domain",
         "signals. docs/mcu.md §2.1.",
         "",
         "SOM_WAKE#, SOM_IRQ#, SOM_RESET# and FPGA_PROG# are open-drain: they",
         "land on dies the MCU itself can unpower, and their pull-ups belong on",
         "the far sheet, referenced to the far rail. MCU_TXD is push-pull and a",
         "UART TX idles high, so firmware must release it before cutting",
         "+5V_DCDC. docs/mcu.md §4.")

    return sh


if __name__ == "__main__":
    sheet = build()
    out = PROJ / "mcu.kicad_sch"
    sheet.write(out)
    print(f"wrote {out}")
    from sheet_pins import set_sheet_pins
    set_sheet_pins(PROJ / "r2.kicad_sch", "mcu", list(HIER))
    print(f"set {len(HIER)} sheet pins on r2.kicad_sch")
