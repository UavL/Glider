#!/usr/bin/env python3
"""Generate som.kicad_sch — R2 work package 8.

Implements docs/som.md §3-§5. Three of the `PCM-071`'s four units (unit 2, the
DPI link, is on `dpi_in`), plus the microSD, and it closes the last 12 dangling
root nets in the project.

    unit 1  POWER   VIN x3 -> +5V_SOM, VBAT, SoC_VDDSHV5_SDIO, 45 x GND
    unit 3  CTRL    SPI0 to the FPGA, UART0 to the MCU, USB0, MMC1, reset/PG
    unit 4  NC      119 pins R2 does not use, every one flagged

**Two pins are chosen here that docs/som.md left open**, and the evidence is in
the AM62x datasheet (SPRSP58C) rather than in PHYTEC's manual, which never uses
the word "wake" at all:

    SOM_WAKE#  -> A58  X_MCU_MCAN0_RX  ball B3  = MCU_GPIO0_14 in mux mode 7
    SOM_IRQ#   -> A57  X_MCU_MCAN0_TX  ball D6  = MCU_GPIO0_13 in mux mode 7

Both are in the **MCU always-on domain**, which is what survives DeepSleep, so
either can serve as the wake line. Cross-referencing the datasheet's pin-mux
table against `som_pinout.json` shows exactly 22 `X1` pins reach an
`MCU_GPIO0_*`, and CAN is the one function among them that a reader can never
want. The datasheet's feature list also names "CAN/GPIO/UART wakeup" explicitly
(for Partial IO mode), so these pins are wake-capable in at least one low-power
mode.

**Still to confirm at bring-up**, and stated plainly because it is not proven:
PHYTEC demonstrated wake from Suspend-to-RAM by GPIO but never named the pin,
and "Partial IO" is a *different* low-power mode from DeepSleep. If
`MCU_GPIO0_14` turns out not to be a DeepSleep wake source, moving to another
of the 22 is a one-net edit -- which is the reason for picking from that set
rather than from a MAIN-domain pin that certainly could not work.

Reference numbering continues the 5xx block: `J21` (microSD), `R500`-`R504`
(SD pull-ups), `C510`-`C513` (bulk and decoupling).

Run once. After the sheet has been opened and saved in Eeschema it is edited in
place, not regenerated.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402
from sheet_pins import set_sheet_pins  # noqa: E402

PROJ = HERE.parent


def _find(name: str) -> pathlib.Path:
    """Any datasheet-derived file, at any depth under datasheets/.

    Hardcoding `datasheets/<name>` broke silently when the SoM material was
    filed into a subfolder on 2026-08-19; commit 058e9b9 fixed three tools this
    way and missed this one, which only showed up when the sheet was next
    regenerated.
    """
    hits = sorted(PROJ.glob(f"datasheets/**/{name}"))
    assert hits, f"{name} is not anywhere under {PROJ / 'datasheets'}"
    return hits[0]


PINOUT = _find("som_pinout.json")
KICAD_CLI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/bin/kicad-cli"
KI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/share/kicad/symbols"

R_FP = "Resistor_SMD:R_0402_1005Metric"
C_FP = "Capacitor_SMD:C_0402_1005Metric"
CB_FP = "Capacitor_SMD:C_0805_2012Metric"      # 22 uF bulk

# Every origin must be a multiple of 1.27 or the whole part lands off-grid;
# schgen.Sheet.check_grid() enforces it at render time.
# One symbol per physical connector -- docs/som.md §10.3. J26 carries the
# module's A and B columns, J27 its C and D. Six unit boxes now instead of
# three, laid out in the same three columns: power, control, unused.
CONN = {
    "J26": ("r2:BTH-060_AB", "AB", "r2:BTH-060-01-L-D-A-K_AB",
            "rows A and B, the connector at module x = 4.800"),
    "J27": ("r2:BTH-060_CD", "CD", "r2:BTH-060-01-L-D-A-K_CD",
            "rows C and D, the connector at module x = 27.200"),
}
MPN = "BTH-060-01-L-D-A-K-TR"
LCSC = "C3646540"

# (x, y) per (refdes, unit). Heights follow from the pin counts -- 25/20 rows
# for POWER, 6/21 for CTRL, 29/29 for NC -- so the gaps below are what keeps
# them apart; `assert_no_overlap` checks it rather than trusting the arithmetic.
BOX = {                        # every value a multiple of 1.27, or the pins
    ("J26", 1): (76.20, 69.85),   # land off-grid and check_grid() says so
    ("J27", 1): (76.20, 144.78),
    ("J26", 3): (213.36, 44.45),
    ("J27", 3): (213.36, 105.41),
    ("J26", 4): (350.52, 62.23),
    ("J27", 4): (350.52, 158.75),
}
GND_BUS = 114.30               # both power units' ground bus, right of the pins
SD_X, SD_Y = 149.86, 226.06    # microSD J21
PU_X, PU_Y = 210.82, 210.82    # the five SD pull-ups, in a row
CB_X, CB_Y = 289.56, 210.82    # the card's bulk cap
BULK_X, BULK_Y = 33.02, 210.82  # C510-C512, bulk at the connectors
X2_XY = (241.30, 234.95)       # the module itself: outline and mounting holes
MK_XY = (241.30, 255.27)       # its M2.5 hardware -- both clear of the title block

# --- unit 1, power -------------------------------------------------------
VIN_PINS = ("A1", "A2", "A3")
SDIO_RAIL = "+3V3_SDIO"        # local: the module's own SD I/O supply, B1

# --- unit 3, what R2 wires ----------------------------------------------
# x1 pin -> (net, kind). "h" = hierarchical (leaves the sheet), "l" = local.
WIRED = {
    # CSR SPI: the SoM is master, to the FPGA and the config NOR
    "D40": ("FPGA_SCLK", "h"), "D41": ("FPGA_MOSI", "h"),
    "D42": ("FPGA_MISO", "h"), "C40": ("FPGA_CS", "h"),
    "C41": ("NOR_CS", "h"),
    # UART to the MCU. Named from the MCU's side: MCU_TXD lands on the SoM's RX.
    "D37": ("MCU_TXD", "h"), "D38": ("MCU_RXD", "h"),
    # reset and power-good -- power.md §5.1's five-step sequence
    "C52": ("SOM_RESET#", "h"), "C54": ("PG_SOM", "h"),
    # housekeeping, both on MCU always-on GPIO (see the module docstring)
    "A57": ("SOM_IRQ#", "h"), "A58": ("SOM_WAKE#", "h"),
    # the SoM's way back into a bricked MCU -- mcu.md §5.8. These were added by
    # tools/patch_som_mcu_recovery.py after the sheet was first generated; they
    # live here now so regenerating cannot silently drop them.
    "A59": ("SOM_MCU_NRST", "h"), "A60": ("SOM_MCU_BOOT0", "h"),
    # USB 2.0 from J1 on battery
    "A38": ("USB_DM", "h"), "A39": ("USB_DP", "h"), "A40": ("+VBUS", "p"),
    # microSD on MMC1, local to this sheet
    "D26": ("SD_CLK", "l"), "D25": ("SD_CMD", "l"),
    "C25": ("SD_DAT0", "l"), "C26": ("SD_DAT1", "l"),
    "D28": ("SD_DAT2", "l"), "D29": ("SD_DAT3", "l"),
    "C23": ("SD_CD#", "l"),
}
SD_PULLUPS = [("R500", "SD_CMD"), ("R501", "SD_DAT0"), ("R502", "SD_DAT1"),
              ("R503", "SD_DAT2"), ("R504", "SD_DAT3")]

# microSD socket pin -> net.
#
# Pin 9 is the card-detect contact and pins 10-13 are the shell/mounting tabs,
# which the symbol draws stacked at one coordinate so a single wire covers all
# four. Read off R1's own use of the same part rather than guessed: R1 wires
# 10-13 and leaves 9 open, which is only consistent with 9 being the detect
# switch against the grounded shell. Inserting a card closes it, so with the
# module's own 10K pullup on X_MMC1_SDCD the sense is active-low.
SD_SOCKET = {
    "1": "SD_DAT2", "2": "SD_DAT3", "3": "SD_CMD", "4": SDIO_RAIL,
    "5": "SD_CLK", "6": "GND", "7": "SD_DAT0", "8": "SD_DAT1",
    "9": "SD_CD#",
}
SD_SHELL = ("10",)          # 10-13 are one point; wiring 10 wires all four

NOTE_MAIN = [
    "som -- J26 and J27, the two BTH-060 receptacles, units 1/3/4.",
    "Unit 2, the DPI link, is on dpi_in. J26 = module columns A+B,",
    "J27 = C+D. Pin numbers are the MODULE's (Tables 7-10), not Samtec's",
    "1-120, so the schematic reads straight against L-1038e.A5.",
    "X2 is the module: outline and M2.5 holes only, no pads, no nets.",
    "Pin numbers from datasheets/som_pinout.json via parse_som_pinout.py.",
    "All three VIN pins and all 45 grounds are connected -- 4.6 requires it.",
    "B1 SoC_VDDSHV5_SDIO is an OUTPUT (Table 12), 100 mA: it powers the card.",
    "*** B2 VBAT is the RTC backup, 40 nA. It is NOT this board's +VBAT,",
    "*** which is the raw Li-ion cell on battery.kicad_sch.",
]
NOTE_CTRL = [
    "SEQUENCING -- power.md 5.1. Getting this wrong risks the module.",
    "L-1038e.A5 5.4 makes it *mandatory* that nothing drives the SOM's I/O",
    "before it is powered, and +3V3 is VCCO for the FPGA bank facing it:",
    "  1 SOM_RESET# low   2 MCU_EN_5V   3 wait PG_SOM",
    "  4 MCU_EN_3V3 + PG_3V3   5 release SOM_RESET#",
    "BOOTMODE_8/9 then latch with +3V3 already up.",
    "",
    "SOM_WAKE# = A58 (MCU_GPIO0_14), SOM_IRQ# = A57 (MCU_GPIO0_13). Both are",
    "MCU always-on domain, which survives DeepSleep. *** Confirm at bring-up:",
    "*** PHYTEC showed GPIO wake from Suspend-to-RAM but never named the pin.",
    "",
    "C51 PMIC_EN open: 100K pullup to 5 V on the module, MCU_EN_5V is the",
    "on/off. C22 MMC1_SDWP open: microSD has no write-protect switch.",
]


def build(pins: dict, unit_of: dict) -> tuple[str, list]:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    sh = Sheet(
        sheets["som"], root_uuid, "r2", paper="A3",
        title="Glider-R2 / Reflow mainboard",
        rev="A", date="2026-08-15",
        comments=(
            "som — J26/J27 BTH-060 units 1/3/4: power, control, microSD on MMC1",
            "See docs/som.md. Pin numbers from datasheets/som_pinout.json.",
        ),
        pwr_base=800,
    )
    sh.lib.add_file("r2", PROJ / "r2.kicad_sym")
    sh.lib.add_file("symbols", PROJ.parent / "pcb_common" / "symbols.kicad_sym")
    for n in ("Device", "power"):
        sh.lib.add_dir(n, KI / f"{n}.kicad_symdir")

    # Six unit boxes: three per connector. Unit 2, the DPI link, is on dpi_in.
    UDESC = {1: "power and grounds", 3: "SPI0, UART0, USB0, MMC1, reset and status",
             4: "every pin R2 does not use"}

    def half_height(ref: str, u: int) -> float:
        """Half a unit box's height, mirroring gen_som_symbol.unit_block.

        The six boxes are all different heights now, so a fixed ref_at offset
        puts one symbol's designator inside another's body -- which is exactly
        what the first render showed for J27A against J26A.
        """
        ps = [p for p, v in unit_of.items() if v == u and p[0] in CONN[ref][1]]
        if u == 1:
            rows = max(sum(1 for p in ps if pins[p]["name"] != "GND"),
                       sum(1 for p in ps if pins[p]["name"] == "GND"))
        else:
            rows = (len(ps) + 1) // 2
        return (rows - 1) * 2.54 / 2 + 2.54

    units = {}
    for ref, (lib, rows, fp, what) in CONN.items():
        for u in (1, 3, 4):
            x, y = BOX[(ref, u)]
            units[(ref, u)] = sh.place(
                lib, ref, MPN, x, y, 0, unit=u, footprint=fp,
                extra={"LCSC": LCSC, "MPN": MPN, "Manufacturer": "Samtec"},
                ref_at=(x - 30.48, y - half_height(ref, u) - 5.08),
                val_at=(x - 30.48, y - half_height(ref, u) - 2.54),
                justify="left",
                description=f"Samtec {MPN}, 2x60 0.5 mm receptacle carrying {what} "
                            f"of the PCM-071. Unit {u} of 4: {UDESC[u]}. Unit 2, the "
                            f"DPI link, is on dpi_in.")

    # The module itself is no longer a symbol with pins -- J26/J27 carry every
    # net. X2 keeps a footprint (outline plus the two M2.5 holes, no pads) so
    # layout knows where the module and its standoffs go, and a BOM line so it
    # gets ordered. It is excluded from the position file: it is fitted by hand.
    sh.place("r2:BOM_ITEM", "X2", "PCM-071", *X2_XY,
             footprint="r2:PCM-071_Module",
             extra={"MPN": "PCM-071", "Manufacturer": "PHYTEC",
                    "BOM Comments":
                        "Plug-in module, bought from PHYTEC and fitted by hand after "
                        "assembly -- NOT placed by the PCBA house, and excluded from the "
                        "position file. Its 240 contacts belong to J26/J27. This symbol "
                        "carries the module's outline and M2.5 mounting holes."},
             ref_at=(X2_XY[0], X2_XY[1] - 6.35),
             val_at=(X2_XY[0], X2_XY[1] + 6.35))
    sh.place("r2:BOM_ITEM", "MK20", "PCM-071 mounting kit", *MK_XY,
             extra={"MPN": "2x M2.5x5 F-F standoff, 4x M2.5x4 screw, 4x M2.5 washer",
                    "BOM Comments":
                        "PHYTEC's own recommendation, L-1038e.A5 section 4.3. Not "
                        "optional: the standoffs set the 5 mm stacking height the "
                        "BTH-060 pair is specified for, so without them the connector "
                        "solder joints carry the module's mechanical load."},
             ref_at=(MK_XY[0], MK_XY[1] - 6.35),
             val_at=(MK_XY[0], MK_XY[1] + 6.35))
    sh.text(X2_XY[0] - 25.40, X2_XY[1] - 12.70,
            "X2 and MK20 are bought, not placed by the assembler.", 1.27)

    hier: list[tuple[str, str]] = []

    # --- unit 1: power, one box per connector ----------------------------
    # Only J26 carries supplies: VIN x3 and VBAT are on column A, and
    # SoC_VDDSHV5_SDIO on B1. J27's power unit is 20 grounds and nothing else,
    # which is why the two boxes look so different.
    u1 = units[("J26", 1)]
    vin_pts = [u1.pin(p) for p in VIN_PINS]
    for px, py in vin_pts:
        sh.wire((px, py), (px - 12.7, py))
    top = vin_pts[0]
    sh.wire((top[0] - 12.7, vin_pts[0][1]), (top[0] - 12.7, vin_pts[-1][1]))
    for _, py in vin_pts[1:-1]:
        sh.junction(top[0] - 12.7, py)
    sh.wire((top[0] - 12.7, top[1]), (top[0] - 12.7, top[1] - 5.08))
    sh.power("+5V_SOM", top[0] - 12.7, top[1] - 5.08)

    # B1 is a local rail (it only feeds the card, so a label is right); B2 is a
    # global one and must be a power symbol or it would not join +3V3_AON at
    # all. They sit 2.54 apart, so B2 drops 10.16 mm before its symbol -- the
    # first attempt put both at the same x and the two texts overlapped.
    px, py = u1.pin("B1")
    sh.wire((px, py), (px - 12.7, py))
    sh.label(px - 12.7, py, SDIO_RAIL, rot=180, justify="right")
    px, py = u1.pin("B2")
    sh.wire((px, py), (px - 12.7, py))
    sh.wire((px - 12.7, py), (px - 12.7, py + 10.16))
    sh.power("+3V3_AON", px - 12.7, py + 10.16)

    # Each power box gets its own ground bus. They share an x, which is safe
    # because the two boxes never overlap in y -- assert_no_overlap proves it.
    for ref in CONN:
        box = units[(ref, 1)]
        gnds = [box.pin(p) for p, r in pins.items()
                if r["name"] == "GND" and unit_of[p] == 1 and p[0] in CONN[ref][1]]
        assert gnds, f"{ref} has no grounds in unit 1"
        gnds.sort(key=lambda q: q[1])
        for px, py in gnds:
            sh.wire((px, py), (GND_BUS, py))
        sh.wire((GND_BUS, gnds[0][1]), (GND_BUS, gnds[-1][1]))
        for _, py in gnds[1:-1]:
            sh.junction(GND_BUS, py)
        sh.wire((GND_BUS, gnds[-1][1]), (GND_BUS, gnds[-1][1] + 5.08))
        sh.power("GND", GND_BUS, gnds[-1][1] + 5.08)

    # bulk at the connector: the module draws up to 1 A through two 0.5 mm
    # Samtec parts, and power.md's output caps are back at the boost.
    for i, (ref, val, fpc) in enumerate((("C510", "22u", CB_FP),
                                         ("C511", "22u", CB_FP),
                                         ("C512", "100n", C_FP))):
        x = BULK_X + i * 10.16
        c = sh.place("Device:C", ref, val, x, BULK_Y, 0, footprint=fpc,
                     ref_at=(x + 2.54, BULK_Y - 1.27), val_at=(x + 2.54, BULK_Y + 2.54),
                     justify="left",
                     description="bulk at the SoM connector; the module draws "
                                 "up to 1 A (L-1038e.A5 §5.1)")
        sh.wire(c.pin("1"), (x, BULK_Y - 5.08))
        sh.label(x, BULK_Y - 5.08, "+5V_SOM", rot=90)
        sh.wire(c.pin("2"), (x, BULK_Y + 8.89))
        sh.power("GND", x, BULK_Y + 8.89)

    # --- unit 3: control, one box per connector --------------------------
    for ref, (_lib, rows, _fp, _what) in CONN.items():
        u3 = units[(ref, 3)]
        cx = BOX[(ref, 3)][0]
        for pin in sorted((p for p, u in unit_of.items()
                           if u == 3 and p[0] in rows),
                          key=lambda p: (p[0], int(p[1:]))):
            px, py = u3.pin(pin)
            left = px < cx
            end = px - 22.86 if left else px + 22.86
            if pin not in WIRED:
                sh.nc(px, py)
                continue
            net, kind = WIRED[pin]
            sh.wire((px, py), (end, py))
            if kind == "h":
                sh.hlabel(end, py, net, shape="bidirectional",
                          rot=180 if left else 0)
                hier.append((net, "bidirectional"))
            elif kind == "p":
                # A power symbol among hierarchical labels needs room, and it
                # must get it *horizontally*. The first attempt dropped a
                # vertical wire 10.16 mm from this row to clear the two USB
                # labels above -- and that wire ran straight through the label
                # anchors four rows below, shorting SOM_IRQ# and SOM_WAKE# to
                # +VBUS. ERC was silent; the netlist was not. A longer stub on
                # this row alone cannot touch anything, because every neighbour
                # lives on a different row.
                sh.wire((end, py), (end - 15.24, py))
                sh.power(net, end - 15.24, py, rot=270)
            else:
                sh.label(end, py, net, rot=180 if left else 0,
                         justify="right" if left else "left")

    # --- unit 4: every unused pin, one box per connector -----------------
    for ref, (_lib, rows, _fp, _what) in CONN.items():
        u4 = units[(ref, 4)]
        for pin in (p for p, u in unit_of.items() if u == 4 and p[0] in rows):
            sh.nc(*u4.pin(pin))

    # --- the microSD ------------------------------------------------------
    j = sh.place("symbols:MICRO_SD(TFC-WPAPR-08)", "J21",
                 "MICRO_SD(TFC-WPAPR-08)", SD_X, SD_Y, 0,
                 footprint="footprints:TFC-WPAPR-08",
                 ref_at=(SD_X - 25.40, SD_Y - 20.32),
                 val_at=(SD_X - 25.40, SD_Y - 17.78), justify="left",
                 description="microSD, MMC1. Boot backup per L-1038e.A5 §4.6; "
                             "the module's default straps are eMMC primary, "
                             "MMC1 backup (Table 17).")
    # Signals fan left to a label column. The two grounds -- VSS and the shell
    # -- drop to a short bus below the socket and share one symbol, because a
    # GND symbol placed on VSS's own row put its text through the DAT0 label
    # sitting 5 mm away.
    gnd_x = None
    for num, net in SD_SOCKET.items():
        px, py = j.pin(num)
        if net == "GND":
            gnd_x = px - 25.4          # clear of the label text, which ends near px-17
            sh.wire((px, py), (gnd_x, py))
            gnd_top = py
        else:
            sh.wire((px, py), (px - 10.16, py))
            sh.label(px - 10.16, py, net, rot=180, justify="right")

    # shell / mounting tabs -- 10 to 13 share one point, so one wire does all
    for num in SD_SHELL:
        px, py = j.pin(num)
        sh.wire((px, py), (gnd_x, py))
        sh.wire((gnd_x, gnd_top), (gnd_x, py))
        sh.junction(gnd_x, py)
        sh.wire((gnd_x, py), (gnd_x, py + 7.62))
        sh.power("GND", gnd_x, py + 7.62)

    for i, (ref, net) in enumerate(SD_PULLUPS):
        x = PU_X + i * 13.97
        r = sh.place("Device:R", ref, "47k", x, PU_Y, 0, footprint=R_FP,
                     ref_at=(x + 2.54, PU_Y - 1.27), val_at=(x + 2.54, PU_Y + 2.54),
                     justify="left",
                     description="SD CMD/DAT pull-up to the module's own SDIO "
                                 "rail, per L-1038e.A5 Fig. 22")
        sh.wire(r.pin("1"), (x, PU_Y - 7.62))
        sh.label(x, PU_Y - 7.62, SDIO_RAIL, rot=90)
        sh.wire(r.pin("2"), (x, PU_Y + 7.62))
        sh.label(x, PU_Y + 7.62, net, rot=270)

    c = sh.place("Device:C", "C513", "10u", CB_X, CB_Y, 0, footprint=CB_FP,
                 ref_at=(CB_X + 2.54, CB_Y - 1.27), val_at=(CB_X + 2.54, CB_Y + 2.54),
                 justify="left",
                 description="bulk at the card; SoC_VDDSHV5_SDIO delivers at "
                             "most 100 mA and a write burst is what finds it")
    sh.wire(c.pin("1"), (CB_X, CB_Y - 7.62))
    sh.label(CB_X, CB_Y - 7.62, SDIO_RAIL, rot=90)
    sh.wire(c.pin("2"), (CB_X, CB_Y + 7.62))
    sh.power("GND", CB_X, CB_Y + 7.62)

    # --- notes ------------------------------------------------------------
    for x, y0, block in ((26.67, 246.38, NOTE_MAIN), (152.40, 139.70, NOTE_CTRL)):
        y = y0
        for line in block:
            sh.text(x, y, line, 1.27)
            y += 3.81
        assert y <= 285.0, f"note block at x={x} runs to y={y:.1f}"
    text = sh.render()

    # MK20 is hardware in a bag, not a footprint: on_board=no keeps it off the
    # PCB and out of the position file while leaving it on the order. X2 stays
    # on_board=yes -- it has a real footprint (outline and the M2.5 holes) that
    # layout needs -- and its `exclude_from_pos_files` attribute, set in the
    # footprint itself, is what keeps it out of the CPL.
    blocks = text.split('(lib_id "r2:BOM_ITEM")')
    hit = 0
    for i, blk in enumerate(blocks[1:], 1):
        if re.search(r'\(property "Reference" "MK20"', blk):
            blocks[i], n = re.subn(r"\(on_board yes\)", "(on_board no)", blk, count=1)
            assert n == 1, "MK20 has no (on_board yes) to rewrite"
            hit += 1
    assert hit == 1, f"expected one MK20 block, found {hit}"
    return '(lib_id "r2:BOM_ITEM")'.join(blocks), sorted(set(hier))


def verify_netlist() -> None:
    """Assert every wired X1 pin really is on the net this file names.

    A schematic can be drawn so that it looks right and connects wrongly: a wire
    routed past a label anchor merges two nets in silence, and ERC reports
    nothing because nothing is illegal. That has now happened twice on this
    project -- `dpi_in`'s box overlapping `epd`, and `+VBUS`'s drop wire
    crossing SOM_IRQ#/SOM_WAKE#. Both were found by reading the netlist, so
    reading the netlist is part of generating the sheet.
    """
    out = pathlib.Path("/tmp/som-verify.net")
    subprocess.run([str(KICAD_CLI), "sch", "export", "netlist", "--format",
                    "kicadsexpr", "-o", str(out), str(PROJ / "r2.kicad_sch")],
                   check=True, capture_output=True)
    t = out.read_text()
    of = {}
    for m in re.finditer(r'\(net\n\t+\(code "\d+"\)\n\t+\(name "([^"]*)"\)', t):
        a = m.start()
        depth, j, ins = 0, a, False
        while True:
            c = t[j]
            if c == '"' and t[j - 1] != "\\":
                ins = not ins
            elif not ins:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        for ref, pin in re.findall(r'\(ref "([^"]+)"\)\n\t+\(pin "([^"]+)"\)',
                                   t[a:j + 1]):
            if ref in CONN:
                of[pin] = m.group(1)
    bad = []
    for pin, (net, _kind) in WIRED.items():
        got = of.get(pin, "<absent>")
        if got.split("/")[-1] != net:
            bad.append(f"{pin}: expected {net!r}, netlist has {got!r}")
    assert not bad, "wired pins landed on the wrong net:\n  " + "\n  ".join(bad)
    print(f"  netlist: all {len(WIRED)} wired pins are on the named net")


def main() -> int:
    pins = json.loads(PINOUT.read_text())
    sys.path.insert(0, str(HERE))
    from gen_som_symbol import assign_units
    unit_of = assign_units(pins)

    unknown = sorted(set(WIRED) - {p for p, u in unit_of.items() if u == 3})
    assert not unknown, f"WIRED names pins that are not in unit 3: {unknown}"

    text, hier = build(pins, unit_of)
    out = PROJ / "som.kicad_sch"
    out.write_text(text)
    subprocess.run([str(KICAD_CLI), "sch", "upgrade", str(out)],
                   check=True, capture_output=True)
    set_sheet_pins(PROJ / "r2.kicad_sch", "som", hier)

    verify_netlist()

    per = {}
    for ref, (_l, rows, _f, _w) in CONN.items():
        per[ref] = {u: sum(1 for p, v in unit_of.items()
                           if v == u and p[0] in rows) for u in (1, 3, 4)}
    print(f"wrote {out.name}:")
    for ref, n in per.items():
        print(f"  {ref}  units 1/3/4 = {n[1]}/{n[3]}/{n[4]} pins")
    print(f"  {len(WIRED)} wired, {len(hier)} hierarchical")
    for net, _ in hier:
        print(f"    {net}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
