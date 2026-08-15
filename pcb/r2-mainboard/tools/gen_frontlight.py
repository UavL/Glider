#!/usr/bin/env python3
"""Generate frontlight.kicad_sch — R2 work package 6.

Implements docs/frontlight.md. One converter, and it closes a hole rather than
adding a feature: before this sheet, `+5V2_FL` had **no source** (three loads on
`epd`, nothing driving them) and `+VSYS_FL` dead-ended at `power_mon`'s ammeter.
WP2 moved the frontlight from the 5 V rail to the cell and left the converter to
this work package.

`U53` is a second `TPS61022`, identical in topology to `U12` on the power sheet
and deliberately reusing its feedback values -- 732 k / 100 k gives 4.992 V,
which is what R1 actually delivered to the panel (`+5V_DCDC` through shunt
`R72`). The net's `+5V2_FL` name was already wrong in R1; docs/frontlight.md §3
explains why it is kept.

There is no LED driver here, and there was none on R1: the board supplies a
voltage rail plus `FL_EN`/`FL_PWM1`/`FL_PWM2` to `J6`, and the panel's tail does
the current regulation. Dimming is not this board's problem.

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
CB_FP = "Capacitor_SMD:C_0805_2012Metric"
L_FP = "Inductor_SMD:L_1210_3225Metric"

UX, UY = 127.00, 101.60        # U53, on the 1.27 grid

NOTE = [
    "frontlight -- the panel LED anode rail. See docs/frontlight.md.",
    "",
    "U53 is a second TPS61022, same topology and the same feedback values as",
    "U12 on power.kicad_sch: 0.600 x (1 + 732k/100k) = 4.992 V. That is what",
    "R1 delivered, from +5V_DCDC through shunt R72. The name +5V2_FL was",
    "already wrong in R1 and is kept: it names the rail, not its voltage.",
    "",
    "*** No LED driver on this board, and none on R1. The board supplies this",
    "*** rail plus FL_EN/FL_PWM1/FL_PWM2 to J6; the panel tail regulates the",
    "*** LED current and does the dimming.",
    "",
    "FL_EN starts the boost and also reaches J6.43 -- one signal, one intent.",
]


def build() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    sh = Sheet(
        sheets["frontlight"], root_uuid, "r2", paper="A4",
        title="Glider-R2 / Specter mainboard",
        rev="A", date="2026-08-15",
        comments=(
            "frontlight — TPS61022 boost, +VSYS_FL to the panel LED anode rail",
            "See docs/frontlight.md. No LED driver here: the panel tail does that.",
        ),
        pwr_base=1000,
    )
    for n in ("Device", "power", "Converter_DCDC"):
        sh.lib.add_dir(n, KI / f"{n}.kicad_symdir")
    # non-GND power symbols come from pcb_common's `+V`, as on every other sheet
    sh.lib.add_file("symbols", PROJ.parent / "pcb_common" / "symbols.kicad_sym")

    def RV(ref, val, x, y, side="right", descr=""):
        dx = 2.54 if side == "right" else -2.54
        return sh.place("Device:R", ref, val, x, y, 0, footprint=R_FP,
                        ref_at=(x + dx, y - 1.27), val_at=(x + dx, y + 2.032),
                        justify="left" if side == "right" else "right",
                        description=descr)

    def CV(ref, val, x, y, fp=C_FP, descr=""):
        return sh.place("Device:C", ref, val, x, y, 0, footprint=fp,
                        ref_at=(x + 2.54, y - 1.27), val_at=(x + 2.54, y + 2.032),
                        justify="left", description=descr)

    u = sh.place("Converter_DCDC:TPS61022", "U53", "TPS61022RWUR", UX, UY, 0,
                 footprint="Package_DFN_QFN:Texas_RWU0007A_VQFN-7_2x2mm_P0.5mm",
                 datasheet=TI + "tps61022.pdf", extra={"LCSC": "C915088"},
                 ref_at=(UX - 7.62, UY + 25.4), val_at=(UX - 7.62, UY + 27.94),
                 justify="left",
                 description="Frontlight boost, +VSYS_FL -> +5V2_FL (4.992 V). "
                             "Second instance of U12; true output disconnect in "
                             "shutdown is why FL_EN really removes the rail.")

    VIN_Y = u.pin("7")[1]      # read off the symbol, not assumed: a hardcoded
                               # offset here put the whole input side off-grid
    IN_X = UX - 45.72          # far enough left that C516's value text
                               # clears both the IC and the EN drop wire
    # --- input side ------------------------------------------------------
    sh.wire((IN_X, VIN_Y), u.pin("7"))
    sh.power("+VSYS_FL", IN_X, VIN_Y - 5.08)
    sh.wire((IN_X, VIN_Y - 5.08), (IN_X, VIN_Y))
    for ref, val, fp, dx, descr in (
            ("C514", "22uF/10V", CB_FP, 0.0,
             "tps61022.pdf §8.2.2.5: 10 uF is sufficient, larger may be used"),
            ("C516", "100nF/16V", C_FP, 12.7,
             "local HF bypass at VIN")):
        x = IN_X + dx
        c = CV(ref, val, x, VIN_Y + 8.89, fp=fp, descr=descr)
        sh.wire((x, VIN_Y), c.pin("1"))
        sh.wire(c.pin("2"), (x, VIN_Y + 17.78))
        sh.power("GND", x, VIN_Y + 17.78)
    sh.wire((IN_X, VIN_Y), (IN_X + 12.7, VIN_Y))
    sh.junction(IN_X, VIN_Y)

    # --- inductor: VIN rail to SW ---------------------------------------
    L_Y = VIN_Y - 15.24
    l33 = sh.place("Device:L", "L33", "1uH 4.8A Isat", UX - 12.7, L_Y, 90,
                   footprint=L_FP, extra={"LCSC": "C3224227"},
                   ref_at=(UX - 15.24, L_Y - 3.81),
                   val_at=(UX - 15.24, L_Y - 1.27), justify="right",
                   description="DFE322512F-1R0M. Same inductor as L10/L12/L13. "
                               "tps61022.pdf Fig. 8-1 asks for 1 uH.")
    a, b = l33.pin("1"), l33.pin("2")
    left, right = (a, b) if a[0] < b[0] else (b, a)
    sh.wire((IN_X, VIN_Y), (IN_X, L_Y))
    sh.wire((IN_X, L_Y), left)
    sw_x = u.pin("2")[0]
    sh.wire(right, (sw_x, L_Y))
    sh.wire((sw_x, L_Y), u.pin("2"))

    # --- EN --------------------------------------------------------------
    # Routed down and then left, under the input capacitors rather than through
    # them: the first attempt ran EN straight out at pin height, which put the
    # hierarchical label between C514 and C516 and their value text on top of
    # each other.
    en = u.pin("5")
    EN_Y = VIN_Y + 36.83                 # clear of the caps' grounds at +17.78
    EN_X = 60.96
    sh.wire(en, (en[0] - 5.08, en[1]))
    sh.wire((en[0] - 5.08, en[1]), (en[0] - 5.08, EN_Y))
    sh.wire((en[0] - 5.08, EN_Y), (EN_X, EN_Y))
    sh.hlabel(EN_X, EN_Y, "FL_EN", shape="input", rot=180)
    r507 = RV("R507", "100k", EN_X + 25.4, EN_Y + 8.89, side="right",
              descr="EN pull-down, the pattern every MCU_EN_* rail uses: the "
                    "rail is off until firmware asserts it")
    sh.wire((EN_X + 25.4, EN_Y), r507.pin("1"))
    sh.junction(EN_X + 25.4, EN_Y)
    sh.wire(r507.pin("2"), (EN_X + 25.4, EN_Y + 17.78))
    sh.power("GND", EN_X + 25.4, EN_Y + 17.78)

    # MODE: tie low for automatic PFM/PWM, which is what a light load wants
    mode = u.pin("6")
    sh.wire(mode, (mode[0] - 5.08, mode[1]))
    sh.wire((mode[0] - 5.08, mode[1]), (mode[0] - 5.08, mode[1] + 6.35))
    sh.power("GND", mode[0] - 5.08, mode[1] + 6.35)

    # --- output ----------------------------------------------------------
    vout = u.pin("3")
    OUT_X = vout[0] + 30.48
    sh.wire(vout, (OUT_X, vout[1]))
    sh.power("+5V2_FL", OUT_X, vout[1] - 7.62)
    sh.wire((OUT_X, vout[1] - 7.62), (OUT_X, vout[1]))
    c515 = CV("C515", "22uF/10V", OUT_X - 12.7, vout[1] + 8.89, fp=CB_FP,
              descr="tps61022.pdf §8.2.2.3 asks for 10-50 uF effective; one "
                    "22 uF derates into that band at this rail's current")
    sh.wire((OUT_X - 12.7, vout[1]), c515.pin("1"))
    sh.junction(OUT_X - 12.7, vout[1])
    sh.wire(c515.pin("2"), (OUT_X - 12.7, vout[1] + 17.78))
    sh.power("GND", OUT_X - 12.7, vout[1] + 17.78)

    # --- feedback divider -------------------------------------------------
    fb = u.pin("4")
    FB_X = OUT_X + 12.7
    sh.wire((OUT_X, vout[1]), (FB_X, vout[1]))
    sh.junction(OUT_X, vout[1])
    r505 = RV("R505", "732k", FB_X, vout[1] + 7.62,
              descr="feedback top; same value as R21 on power.kicad_sch")
    sh.wire((FB_X, vout[1]), r505.pin("1"))
    r506 = RV("R506", "100k", FB_X, vout[1] + 20.32,
              descr="feedback bottom, = R22. 0.600 x (1 + 732/100) = 4.992 V")
    sh.wire(r505.pin("2"), r506.pin("1"))
    mid = (FB_X, (r505.pin("2")[1] + r506.pin("1")[1]) / 2)
    sh.junction(*mid)
    sh.wire(mid, (FB_X + 10.16, mid[1]))
    sh.wire((FB_X + 10.16, mid[1]), (FB_X + 10.16, fb[1] - 10.16))
    sh.wire((FB_X + 10.16, fb[1] - 10.16), (fb[0] + 5.08, fb[1] - 10.16))
    sh.wire((fb[0] + 5.08, fb[1] - 10.16), (fb[0] + 5.08, fb[1]))
    sh.wire((fb[0] + 5.08, fb[1]), fb)
    sh.wire(r506.pin("2"), (FB_X, r506.pin("2")[1] + 5.08))
    sh.power("GND", FB_X, r506.pin("2")[1] + 5.08)

    # --- IC ground --------------------------------------------------------
    # pin 1 sits below the body, so the symbol goes *down*; the first attempt
    # subtracted and drew the ground inside the IC's own rectangle
    g = u.pin("1")
    sh.wire(g, (g[0], g[1] + 6.35))
    sh.power("GND", g[0], g[1] + 6.35)

    y = 149.86
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
    set_sheet_pins(PROJ / "r2.kicad_sch", "frontlight", [("FL_EN", "input")])
    print(f"wrote {out.name}: U53 TPS61022, L33, R505-R507, C514-C516")
    return 0


if __name__ == "__main__":
    sys.exit(main())
