#!/usr/bin/env python3
"""External 1 MOhm pull-down on `PG_SOM`, replacing the MCU's internal one.

`patch_mcu_pg_som.py` claimed `PC8` for the module's power-good and told
firmware to enable the internal pull-down, so that "no SoM" would read as
"not good" rather than as noise. **That fix does not work**, and the review
round of 2026-08-19 caught it.

`X_PGOOD` (`X2` C54) is open-drain with a **100 kOhm pull-up on the module**
(`L-1038e.A5` Table 13 and §5.4). The STM32G0's internal pull-down is
**25 / 40 / 55 kOhm** (`stm32g0b1.pdf` Table 55). Both enabled at once is a
divider, and it is the wrong way round:

    3.3 V x 40k / (100k + 40k) = 0.94 V      (0.66 - 1.17 V across corners)
    V_IH min = 0.7 x V_DD      = 2.31 V

So `PC8` reads **low even when the module is asserting power-good**, and
`power.md` §5.1 step 3 -- "wait PG_SOM" -- never returns. `MCU_EN_3V3` is never
asserted and bring-up hangs. The pull-down strength is not configurable on the
G0, so there is no firmware escape.

Simply leaving `PC8` passive fixes that case but loses the one the pull-down was
written for. Three cases have to work, and only an external resistor covers all
three, because the `PCM-071` is a plug-in module on two `BTH-060` receptacles
and can be absent entirely:

    SoM absent              1 MOhm alone                    -> 0 V      not good
    SoM present, unpowered  100k to a dead rail || 1 MOhm    -> ~0 V     not good
    SoM present, PG asserted  3.3 x 1M/1.1M                  -> 3.00 V   good

3.00 V against a 2.31 V threshold is 0.69 V of margin, and the leakage is
3.3 uA and only while the module is powered and asserting good -- with the SoM
off there is nothing to draw from.

**Firmware requirement reverses**: the internal pull-down on `PC8` must now be
**disabled**. Leaving it on puts 40k in parallel with the 1 MOhm and brings the
good case back down to 0.91 V.

`R512` goes on free canvas and reaches `PG_SOM` by label, so the dense region
around `U20` is untouched. Layout must still place it at pin 48 -- noted in
`mcu.md` §11.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402
from patch_mcu_pg_som import splice  # noqa: E402

PROJ = HERE.parent
KI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/share/kicad/symbols"
SCH = PROJ / "mcu.kicad_sch"
X, Y = 378.46, 232.41


def build() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["mcu"], root_uuid, "r2", paper="A3", pwr_base=1190)
    s.lib.add_dir("Device", KI / "Device.kicad_symdir")
    s.lib.add_dir("power", KI / "power.kicad_symdir")

    s.text(374.65, 226.06, "PG_SOM bias. mcu.md §5.9", size=1.27)
    s.label(X, Y, "PG_SOM")
    r = s.place("Device:R", "R512", "1M", X, 237.49,
                footprint="Resistor_SMD:R_0402_1005Metric",
                extra={"LCSC": "C26083", "MPN": "0402WGF1004TCE",
                       "Manufacturer": "UNI-ROYAL"},
                ref_at=(373.38, 236.22), val_at=(383.54, 238.76))
    s.wire((X, Y), r.pin("1"))
    s.power("GND", *r.pin("2"))
    s.check_grid()
    return s.render()


def main() -> int:
    t = SCH.read_text()
    assert '"R512"' not in t, "already patched"
    assert '"PG_SOM"' in t, "PG_SOM is not on this sheet; run patch_mcu_pg_som first"
    SCH.write_text(splice(t, build()))
    print("mcu: R512 1M pull-down added on PG_SOM (no sheet-pin change, "
          "so wire_root.py is not needed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
