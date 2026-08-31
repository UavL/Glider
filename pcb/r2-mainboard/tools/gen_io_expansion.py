#!/usr/bin/env python3
"""Generate io_expansion.kicad_sch — R2 work package 6.

Implements docs/io-expansion.md. `NOTES-R2-plan.md` constraint 3: "First board is
compute + display + power only. Touch and pen get unpopulated FPC connectors so
they can be added without a respin."

**Everything on this sheet is DNP** -- both connectors, both load switches and
their capacitors. With no connector fitted there is no load, so a fitted switch
would be two parts powering nothing. It also means these two `TPS22914`s consume
none of the thin LCSC stock `epd-port.md` §7 flags.

What this sheet actually buys, and what it does not:

  * the seven MCU pins exist and are routed  -- certain, and the thing that
    would otherwise force a whole-board respin
  * `+3V3_TOUCH` / `+3V3_PEN` exist          -- certain
  * the FPC pad order matches the part       -- **a guess**, because neither the
    touch controller nor the digitizer is chosen. docs/io-expansion.md §5 puts
    the decision in front of the owner rather than burying it.

`USART3` on `PC4`/`PC5` is the one allocation here that is not interchangeable:
both are `USART3_TX`/`USART3_RX` at AF0 in `stm32g0b1.pdf`'s alternate-function
table, and both were free. The other five pins are ordinary GPIO.

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

C_FP = "Capacitor_SMD:C_0402_1005Metric"
SW_FP = "Package_BGA:WLP-4_0.83x0.83mm_P0.4mm"
FPC6 = "footprints:HC-FPC-05-09-6RLTAG"
DS = "https://www.diodes.com/assets/Datasheets/AP22913.pdf"

# (ref, rail, enable, x, y) for the two load switches
SWITCHES = [
    ("U1400", "+3V3_TOUCH", "MCU_EN_TOUCH", 66.04, 66.04),
    ("U1401", "+3V3_PEN", "MCU_EN_PEN", 66.04, 111.76),
]
# (ref, x, y, [(pin, net)]) -- the order is provisional, docs/io-expansion.md §5
CONNECTORS = [
    ("J1400", "touch", 175.26, 62.23, [
        ("1", "+3V3_TOUCH"), ("2", "GND"), ("3", "SCL_AON"),
        ("4", "SDA_AON"), ("5", "TOUCH_INT#"), ("6", "TOUCH_RST#")]),
    ("J1401", "pen", 175.26, 107.95, [
        ("1", "+3V3_PEN"), ("2", "GND"), ("3", "PEN_TXD"),
        ("4", "PEN_RXD"), ("5", "PEN_INT#"), ("6", "GND")]),
]
HIER = [("SCL_AON", "bidirectional"), ("SDA_AON", "bidirectional"),
        ("MCU_EN_TOUCH", "input"), ("MCU_EN_PEN", "input"),
        ("TOUCH_RST#", "input"), ("TOUCH_INT#", "output"),
        ("PEN_INT#", "output"), ("PEN_TXD", "input"), ("PEN_RXD", "output")]

NOTE = [
    "io_expansion -- touch and pen, provisioned but NOT FITTED.",
    "See docs/io-expansion.md. Plan constraint 3: the first board is compute +",
    "display + power only, and these get pads so they can be added later.",
    "",
    "*** EVERYTHING ON THIS SHEET IS DNP -- both connectors, both load",
    "*** switches, their capacitors. No connector fitted means no load, so a",
    "*** fitted switch would power nothing. It also means these two TPS22914s",
    "*** consume none of the thin stock epd-port.md 7 flags.",
    "",
    "*** THE FPC PIN ORDER IS PROVISIONAL. Neither the touch controller nor",
    "*** the digitizer is chosen -- the panel is not either -- so the pad order",
    "*** is the one guess here. Confirm against the real parts before fab, or",
    "*** accept that this group alone may need a respin. io-expansion.md 5.",
    "",
    "Certain, and what stops a whole-board respin: the seven MCU pins exist and",
    "are routed, and both gated rails exist. PC4/PC5 are USART3_TX/RX at AF0 --",
    "the one allocation that is not interchangeable. Touch adds no I2C pins; it",
    "sits on the existing always-on bus with the charger, gauge and INA3221s.",
]


def build() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    sh = Sheet(
        sheets["io_expansion"], root_uuid, "r2", paper="A3",
        title="Glider-R2 / Reflow mainboard",
        rev="A", date="2026-08-15",
        comments=(
            "io_expansion — touch and pen FPCs, all DNP. See docs/io-expansion.md",
            "*** FPC pin order is provisional — confirm against the real parts",
        ),
        pwr_base=1100,
    )
    for n in ("Device", "power", "Power_Management", "Connector_Generic"):
        sh.lib.add_dir(n, KI / f"{n}.kicad_symdir")
    sh.lib.add_file("symbols", PROJ.parent / "pcb_common" / "symbols.kicad_sym")

    for ref, rail, en, x, y in SWITCHES:
        u = sh.place("Power_Management:AP22913CN4", ref, "TPS22914BYFPR", x, y, 0,
                     footprint=SW_FP, datasheet=DS, dnp=True,
                     extra={"LCSC": "C1848394"},
                     ref_at=(x - 7.62, y + 12.7), val_at=(x - 7.62, y + 15.24),
                     justify="left",
                     description=f"DNP. Gates {rail} off +3V3. Same part as "
                                 f"U7/U8 on epd_power; DNP here, so it uses none "
                                 f"of the thin stock.")
        i, o, g, e = (u.pin("A2"), u.pin("A1"), u.pin("B1"), u.pin("B2"))
        sh.wire(i, (i[0] - 12.7, i[1]))
        sh.power("+3V3", i[0] - 12.7, i[1] - 5.08)
        sh.wire((i[0] - 12.7, i[1] - 5.08), (i[0] - 12.7, i[1]))
        sh.wire(o, (o[0] + 12.7, o[1]))
        sh.label(o[0] + 12.7, o[1], rail, rot=0, justify="left")
        sh.wire(g, (g[0], g[1] + 6.35))
        sh.power("GND", g[0], g[1] + 6.35)
        sh.wire(e, (e[0] - 20.32, e[1]))
        sh.hlabel(e[0] - 20.32, e[1], en, shape="input", rot=180)
        c = sh.place("Device:C", f"C{517 + SWITCHES.index((ref, rail, en, x, y))}",
                     "1uF/16V", o[0] + 25.4, o[1] + 8.89, 0, footprint=C_FP,
                     dnp=True, ref_at=(o[0] + 27.94, o[1] + 7.62),
                     val_at=(o[0] + 27.94, o[1] + 10.92), justify="left",
                     description=f"DNP. {rail} output capacitor.")
        sh.wire((o[0] + 25.4, o[1]), c.pin("1"))
        sh.junction(o[0] + 12.7, o[1])
        sh.wire((o[0] + 12.7, o[1]), (o[0] + 25.4, o[1]))
        sh.wire(c.pin("2"), (o[0] + 25.4, o[1] + 17.78))
        sh.power("GND", o[0] + 25.4, o[1] + 17.78)

    for ref, what, x, y, pins in CONNECTORS:
        j = sh.place("Connector_Generic:Conn_01x06", ref,
                     "HC-FPC-05-09-6RLTAG", x, y, 0, footprint=FPC6, dnp=True,
                     ref_at=(x + 5.08, y - 10.16), val_at=(x + 5.08, y - 7.62),
                     justify="left",
                     description=f"DNP. {what} FPC, 6-pin 0.5 mm. *** The pin "
                                 f"order is provisional -- see docs/"
                                 f"io-expansion.md §5.")
        n_gnd = 0
        for num, net in pins:
            px, py = j.pin(num)
            if net == "GND":
                # Each ground gets its own column and drops clear of the whole
                # pin stack. Dropping only 5.08 put the GND symbol's text on a
                # label two rows below, and two grounds sharing a column would
                # have needed a junction on a crossing.
                gx = px - 38.1 - 7.62 * n_gnd
                n_gnd += 1
                sh.wire((px, py), (gx, py))
                sh.wire((gx, py), (gx, y + 12.7))
                sh.power("GND", gx, y + 12.7)
                continue
            sh.wire((px, py), (px - 30.48, py))
            if net.startswith("+"):
                sh.label(px - 30.48, py, net, rot=180, justify="right")
            else:
                sh.hlabel(px - 30.48, py, net, rot=180,
                          shape=dict(HIER)[net])

    y = 152.4
    for line in NOTE:
        sh.text(25.4, y, line, 1.27)
        y += 3.81
    assert y <= 265.0, f"note block runs to y={y:.1f}"
    return sh.render()


def main() -> int:
    out = PROJ / "io_expansion.kicad_sch"
    out.write_text(build())
    subprocess.run([str(KICAD_CLI), "sch", "upgrade", str(out)],
                   check=True, capture_output=True)
    set_sheet_pins(PROJ / "r2.kicad_sch", "io_expansion", sorted(HIER))
    print(f"wrote {out.name}: 2 load switches + 2 FPCs, all DNP; "
          f"{len(HIER)} hierarchical labels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
