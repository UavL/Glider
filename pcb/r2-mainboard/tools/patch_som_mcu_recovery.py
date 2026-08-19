#!/usr/bin/env python3
"""Give the SoM a way to reset the MCU and force it into the ROM bootloader.

`mcu.md` §5.7 named the gap: SWD via `J20` is the only way into the MCU, and it
needs the case open. §5.8 picks the two module pins and this applies them.

    SOM_MCU_NRST   X2 A59  X_MCU_MCAN1_TX   VDDSHV_CANUART (J14, 3.3 V default)
    SOM_MCU_BOOT0  X2 A60  X_MCU_MCAN1_RX   same domain

Both are in `VDDSHV_CANUART`, which is *already* load-bearing for `SOM_IRQ#`
(A57) and `SOM_WAKE#` (A58), so this adds no new module-jumper dependency, and
A57-A60 becomes one contiguous block. Neither is a boot strap -- all sixteen
are `X_GPMC0_AD0..15/BOOTMODE_0..15`.

**`NRST` goes through a FET, and that is the whole point of this patch.**
The MCU runs on `+3V3_AON` and gates the SoM's own supply with `MCU_EN_5V`, so
"SoM unpowered while the MCU is alive" is the normal standby state. A direct
tie would let an unpowered A59 clamp `MCU_NRST` toward a dead
`VDDSHV_CANUART` and hold the MCU in reset permanently -- the exact failure the
always-on MCU exists to prevent. `Q9` makes it one-way:

    SoM off or GPIO low -> R510 holds the gate at 0 V -> Q9 off
                        -> NRST released by the STM32's internal pull-up
                        -> MCU runs
    SoM drives the gate high -> Q9 on -> NRST to ground -> MCU in reset

`AO3400A` is already on the BOM as `Q6` (`C347475`), and `Q_NMOS_GSD` is the
symbol `Q6` uses -- SOT-23 pin 1 = G, 2 = S, 3 = D, which is the AO3400A's
actual pinout.

**`BOOT0` needs no FET**, because the danger runs the other way: nothing on R2
drives `PA14` high, so an unpowered SoM pin can only help `R40`'s 10 kOhm
pull-down hold it low, which is the safe state. `R511` 1 kOhm against `R40`
gives 3.3 x 10/11 = 3.0 V at `PA14`, over V_IH = 0.7 x V_DD = 2.31 V, and is
also the contention limit §5.7 asked for -- `PA14` is `SWCLK` too, so an
attached ST-LINK wins and the current stays near 3.3 mA.

Both sheets are reviewed and committed, so this is surgical: two no-connects
deleted on `som`, one new block on unused canvas on `mcu`, and two sheet pins
added to each box on the root. Nothing that exists moves.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402
from sheet_pins import set_sheet_pins, _sheet_span  # noqa: E402
from patch_mcu_pg_som import drop_nc, splice  # noqa: E402

PROJ = HERE.parent
KI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/share/kicad/symbols"

NRST = "SOM_MCU_NRST"
BOOT = "SOM_MCU_BOOT0"

# --- som side -------------------------------------------------------------
# X2 unit 3 (CTRL) sits at (213.36, 88.9); A57..A60 are the -35.56 column, so
# the pins land on x=177.8 and the label column this sheet uses is x=154.94 --
# read off SOM_IRQ#/SOM_WAKE# on A57/A58 rather than assumed.
SOM_PIN_X, SOM_LABEL_X = 177.8, 154.94
A59_Y, A60_Y = 73.66, 76.2

# --- mcu side -------------------------------------------------------------
# Free canvas: x 300..410, y 208..250 is empty on this sheet (x 255..300 is
# not -- the EPD_PWR_EN note and the button row reach into it, which is why the
# label column sits at 320.04 and the text extends right, not left into them).
LBL_X = 320.04
BOOT_Y = 219.71
NRST_Y = 236.22


def build_mcu() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["mcu"], root_uuid, "r2", paper="A3", pwr_base=1130)
    s.lib.add_dir("Device", KI / "Device.kicad_symdir")
    s.lib.add_dir("Transistor_FET", KI / "Transistor_FET.kicad_symdir")
    s.lib.add_dir("power", KI / "power.kicad_symdir")

    s.text(302.26, 212.09, "SoM -> MCU recovery. mcu.md §5.8", size=1.27)

    # BOOT0: a plain series link, same shape as the EPD_PWR_EN_MCU chain above.
    s.hlabel(LBL_X, BOOT_Y, BOOT, shape="bidirectional", rot=180)
    r511 = s.place("Device:R", "R511", "1k", 335.28, BOOT_Y, rot=90,
                   footprint="Resistor_SMD:R_0402_1005Metric",
                   extra={"LCSC": "C11702", "MPN": "0402WGF1001TCE",
                          "Manufacturer": "UNI-ROYAL"},
                   ref_at=(335.28, 217.17), val_at=(335.28, 224.79))
    s.wire((LBL_X, BOOT_Y), r511.pin("1"))
    s.wire(r511.pin("2"), (350.52, BOOT_Y))
    s.label(350.52, BOOT_Y, "MCU_SWCLK")

    # NRST: open-drain through Q9 so an unpowered SoM cannot hold the MCU down.
    s.hlabel(LBL_X, NRST_Y, NRST, shape="bidirectional", rot=180)
    q9 = s.place("Transistor_FET:Q_NMOS_GSD", "Q9", "AO3400A", 345.44, NRST_Y,
                 footprint="Package_TO_SOT_SMD:SOT-23",
                 extra={"LCSC": "C347475", "MPN": "AO3400A",
                        "Manufacturer": "UMW"},
                 ref_at=(351.79, 232.41), val_at=(351.79, 240.03))
    s.wire((LBL_X, NRST_Y), q9.pin("G"))

    r510 = s.place("Device:R", "R510", "100k", 327.66, 243.84,
                   footprint="Resistor_SMD:R_0402_1005Metric",
                   extra={"LCSC": "C25741", "MPN": "0402WGF1003TCE",
                          "Manufacturer": "UNI-ROYAL"},
                   ref_at=(322.58, 240.03), val_at=(332.74, 243.84))
    s.wire((327.66, NRST_Y), r510.pin("1"))
    s.junction(327.66, NRST_Y)
    s.power("GND", *r510.pin("2"))

    # The drain turns right before its label: a vertical label here runs back
    # into the BOOT0 row, which is what the first attempt looked like.
    dx, dy = q9.pin("D")
    s.wire((dx, dy), (dx, 228.6), (360.68, 228.6))
    s.label(360.68, 228.6, "MCU_NRST")
    s.power("GND", *q9.pin("S"))

    s.check_grid()
    return s.render()


def build_som() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["som"], root_uuid, "r2", paper="A3", pwr_base=1160)
    for y, net in ((A59_Y, NRST), (A60_Y, BOOT)):
        s.wire((SOM_PIN_X, y), (SOM_LABEL_X, y))
        s.hlabel(SOM_LABEL_X, y, net, shape="bidirectional", rot=180)
    s.check_grid()
    return s.render()


def add_pins(stem: str, names: list[str]) -> int:
    root = PROJ / "r2.kicad_sch"
    text = root.read_text()
    a, b = _sheet_span(text, stem)
    have = re.findall(r'\t\t\(pin "([^"]+)" (\w+)\n', text[a:b])
    assert have, f"no sheet pins found on the root's {stem} box"
    pins = sorted(set(have) | {(n, "bidirectional") for n in names})
    added = len(pins) - len(have)
    set_sheet_pins(root, stem, pins)
    return added


def main() -> int:
    som, mcu = PROJ / "som.kicad_sch", PROJ / "mcu.kicad_sch"
    for p in (som, mcu):
        assert f'"{NRST}"' not in p.read_text(), f"already patched ({p.name})"

    t = som.read_text()
    t = drop_nc(t, SOM_PIN_X, A59_Y)
    t = drop_nc(t, SOM_PIN_X, A60_Y)
    som.write_text(splice(t, build_som()))
    mcu.write_text(splice(mcu.read_text(), build_mcu()))

    n_som = add_pins("som", [NRST, BOOT])
    n_mcu = add_pins("mcu", [NRST, BOOT])
    print(f"som: A59/A60 no-connects dropped, {NRST}/{BOOT} declared "
          f"({n_som} sheet pins added)")
    print(f"mcu: Q9 + R510 + R511 placed, {n_mcu} sheet pins added")

    # `set_sheet_pins` re-lays every pin on the box, so adding two shifts the
    # ones below them by a slot. The root's stubs and labels are positional and
    # belong to `wire_root.py`, so they MUST be re-emitted or every label below
    # the insertion point ends up on the wrong pin -- which is exactly what the
    # first run of this patch did: 18 nets silently swapped members.
    import subprocess
    r = subprocess.run([sys.executable, str(HERE / "wire_root.py")],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    assert r.returncode == 0, "wire_root.py failed; the root is now inconsistent"
    return 0


if __name__ == "__main__":
    sys.exit(main())
