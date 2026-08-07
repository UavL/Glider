# `epd`, `epd_power`, `power_mon` — the R1 port — R2 work package 4

Status: **ported, not reviewed.** Companion to `battery.md`, `power.md` and `mcu.md`.

These three sheets are **copied** from `pcb/mainboard/`, not redrawn. The acceptance criterion here
is "is it the same as R1", so every part, value, coordinate and wire is carried over byte-for-byte
wherever it can be; redrawing would have changed the geometry and made that check impossible.
`tools/port_r1.py` does it, and **only ever reads R1** — `pcb/mainboard/` is untouched.

**Headline result: `epd` and `epd_power` are provably identical to R1** — same 49 and 44 net groups,
pin for pin (§6). `power_mon` differs in exactly four net groups, all intended (§3).

---

## 1. What came across

| Sheet | Parts | Renamed | Circuit |
| --- | --- | --- | --- |
| `epd` | 11 | 0 | panel connectors `J6` (50p) and `J3` (16p) + 7 caps |
| `epd_power` | 85 | 23 | EPD HV chain: 2× `LGS5145`, 2× `LGS6302B5`, 2× `TPS22914`, VCOM DAC buffer + `LM321` sense |
| `power_mon` | 32 | 2 | 3× `INA3221`, eight 20 mΩ shunts, five HV measurement dividers |

**103 of 128 parts keep their exact R1 designator.** Only references that collide with something R2
already issued are renamed, by a fixed offset so the R1 number stays readable inside the new one:

| Rule | Applies to |
| --- | --- |
| `C`, `R` → **+200** | `C32,33,41,42,44,45,46,49` and `R13,17,18,19,24–30,34` on `epd_power`; `R7,R8` on `power_mon` |
| `U`, `L` → **+20** | `U11`→`U31`, `L10`→`L30`, `L12`→`L32` on `epd_power` |

So R1's `C41` is R2's `C241`, R1's `U11` is R2's `U31`, and everything else is unchanged. `epd` needed
no renames at all.

Five other mechanical transforms, and nothing else:

- **Global labels became hierarchical labels.** R1 wires its sheets together with global labels; R2
  uses hierarchical labels and sheet pins. In KiCad those are *different nets*, so a mixed project
  would have failed to connect silently. Two names were also brought to R2's convention:
  `I2C1_SCL`/`I2C1_SDA` → **`SCL_AON`/`SDA_AON`**.
- **`SY8120` and `MT9700` now live in `r2.kicad_sym`.** Neither is in `pcb_common` at its pinned
  commit — in R1 they survive only as definitions embedded in the sheet, so R1's library link for
  them is dead. `gen_r2_symbols.py` now lifts both verbatim out of R1 and R2 links to its own copy.
  (`SY8120` is the *symbol*; the LGS5145 instances reuse it. §7.)
- **Three transistor symbols moved library** in KiCad 10 — `Device:Q_{NMOS,PMOS}_GSD` are now in
  `Transistor_FET`, `Device:Q_NPN_BEC` in `Transistor_BJT`. Repointed.
- **Stock symbol definitions refreshed** from the installed KiCad 10 libraries, which is what
  Eeschema's *Update Symbols from Library* does. The refresh **refuses to touch any symbol whose pin
  geometry changed**, so it can never move a pin out from under a wire.
- **Project identity** — instance paths, project name, title block. The `company` field still reads
  *Copyright 2025 Modos Tech Inc*: this is their design, carried over.

**Page size stays A4.** The rest of R2 is A3. Keeping R1's page preserves every coordinate, which is
the whole point of a port; a mixed-size hierarchy is legal in KiCad and the sheets can be re-papered
later with a one-line change since the content already sits in the top-left of an A3.

## 2. What the port revealed — `EPD_PWR_EN` needs a series resistor

R1 puts **1 kΩ (its `R22`) in series between the MCU pin and `EPD_PWR_EN`**, and that is not
decoration. `power_mon`'s `U21` has its open-drain `CRITICAL` output on the same net: an `INA3221`
over-current trip must be able to pull the EPD rail's enable low **while the MCU is driving it
high**. Without the resistor the two fight and the protection does nothing.

WP3 drove `EPD_PWR_EN` straight from `PB0`. **`mcu.kicad_sch` has been changed** to match R1: `PB0`
now carries `EPD_PWR_EN_MCU`, and `R45` (1 kΩ) bridges to `EPD_PWR_EN`. The fight current is
3.3 mA. A bonus falls out of it: `PB0` can be read back as an input to see the trip.

## 3. `power_mon` — the only sheet whose nets changed

R1's nine `INA3221` channels included two for the `ADV7611`/`PTN3460` video front end, which R2
deletes. **No topology changed** — same parts, same shunts, same wires. Only which rail passes
through three of the shunts, which is a net-name edit:

| INA | Addr | ch | R1 | R2 | Why |
| --- | --- | --- | --- | --- | --- |
| `U21` | 0x40 | 1 | `+5V_EPD` → `+5V_ES` | unchanged | |
| `U21` | | 2 | `+5V_EPD` → `+5V_EG` | unchanged | |
| `U21` | | 3 | `+3V3_DCDC` → `+3V3` | unchanged | |
| `U22` | 0x41 | 1 | `+1V8_DCDC` → `+1V8_VID` | **`+5V_DCDC` → `+5V_SOM`** | video rail gone; the SoM's input current is the biggest unknown in the whole budget |
| `U22` | | 2 | `+3V3_DCDC` → `+3V3_VID` | **`+3V3_AON_DCDC` → `+3V3_AON`** | video rail gone; closes `power.md` §9's first open item |
| `U22` | | 3 | `+5V_DCDC` → `+5V2_FL` | **`+VSYS` → `+VSYS_FL`** | the frontlight runs from the cell in R2, not from 5 V |
| `U27` | 0x43 | 1 | `+1V35_DCDC` → `+1V35` | unchanged | |
| `U27` | | 2 | `+1V2_DCDC` → `+1V2_FPGA` | unchanged | |
| `U27` | | 3 | unused, tied to GND | unchanged | R1 left it spare; so does R2 |

**All three `INA3221`s move from `+3V3_DCDC` to `+3V3_AON`.** Two reasons, and the second is the one
that matters:

1. On a switched rail their I²C pins would clamp the always-on bus through their ESD diodes whenever
   that rail was down — which is most of the device's life. `mcu.md` §5.3 predicted this; the port is
   where it gets fixed.
2. It is the only way to measure the always-on domain at all. Power-down `IQ` is **0.5 µA typ,
   2 µA max** ‡ (`ina3221.pdf`), so three of them cost ~1.5 µA typ — against a 10 mW standby target,
   nothing. `U22` ch2's shunt sits upstream of everything including the `INA3221`s' own supply, so
   that channel measures the whole always-on domain honestly, itself included.

`U22`'s `A0` address strap also moves from `+3V3` to `+3V3_AON` — otherwise the address is undefined
whenever the switched rail is down, which is exactly when the part is supposed to be readable.

> **One change is needed in `power.kicad_sch` and I have not made it.** `U22` ch2 measures
> `+3V3_AON_DCDC` → `+3V3_AON`, so the LDO `U10`'s output net must be renamed from `+3V3_AON` to
> **`+3V3_AON_DCDC`** — one power symbol, matching the `*_DCDC` convention every other rail already
> follows. That sheet is out for review, so it is left for the reviewer rather than edited
> underneath them. Until it is done, `+3V3_AON_DCDC` has no source and ERC will say so.

## 4. Two questions the port answered

### 4.1 The EPD chain cannot run from `+VSYS` — `power.md` §9 is closed

`power.md` asked whether the HV chain could be fed from the cell instead of `+5V`, saving a
conversion. **No.** The `LGS5145` is a **buck**, `VIN` **4.5–55 V**, 1 A, 1.2 MHz ‡ (Legend-Si, via
the JLCPCB and LCSC catalogue entries for `C5123971`; the manufacturer's own PDF is not reachable
from this machine, so treat the number as catalogue-sourced rather than datasheet-verified).

R1 runs both `LGS5145`s as **inverting buck-boosts** — the IC's `GND` pin sits on the negative output
(`U9`'s on `-VGL`, `U26`'s on `-VN`), so in steady state it sees `VIN − VOUT` ≈ 25 V, comfortably
inside range even from a 3.0 V cell. **But at startup the negative rail is at 0 V**, so the part sees
`+VSYS` alone. At 3.0 V that is below the 4.5 V minimum and the converter never starts. The 5 V feed
stays.

### 4.2 How R1 measures negative rails — `mcu.md` §9 is closed

`mcu.md` flagged that a plain divider cannot present a negative rail to an ADC. R1's answer: divide
between the negative rail and **`+3V3_DCDC`**, not to ground. `R115` 1 MΩ from `-VN` and `R116`
100 kΩ up to the rail; same for `-VGL` via `R117`/`R118`.

```
V_node = V_3V3 + (V_neg − V_3V3) × 100k/1100k
-VN  ≈ −15 V → 3.3 − 1.66 = 1.64 V
-VGL ≈ −20 V → 3.3 − 2.12 = 1.18 V
```

Both land mid-range. **Kept exactly as R1 has it**, with one firmware consequence: in R1 the divider
reference and the ADC reference were the same rail, and in R2 they are not — `VREF+` is `+3V3_AON`
(`mcu.md` §5.2) while the divider references `+3V3_DCDC`. Firmware must therefore read the `+3V3`
bus voltage from `U21` ch3 to interpret `VN_MEA`/`VGL_MEA`. That is a measurement it takes anyway,
it costs nothing, and it keeps standby draw at zero — referencing the dividers to `+3V3_AON` instead
would have been simpler arithmetic but would leak ~6 µA continuously.

## 5. Sheet interface

| Sheet | Hierarchical labels |
| --- | --- |
| `epd` | 33 × `EPDC_*` (to `fpga_io`, WP5), `FL_EN`, `FL_PWM1`, `FL_PWM2` (to `frontlight`, WP6) |
| `epd_power` | `EPD_PWR_EN`, `EPD_POS_EN`, `VCOM_EN`, `VCOM_MEA_EN`, `VCOM_DAC`, `VGH_DAC` in; `VCOM_MEA` out |
| `power_mon` | `SCL_AON`, `SDA_AON`, `EPD_PWR_EN`; `VBUS_MEA`, `VP_MEA`, `VN_MEA`, `VGH_MEA`, `VGL_MEA` out |

Rails cross as power symbols, which are global in KiCad and need no label: `+5V_DCDC`, `+5V_EPD`,
`+5V_ES`, `+5V_EG`, `+3V3`, `+3V3_AON`, `+VSYS`, `+VBUS`, `+VP`, `+VGH`, `-VN`, `-VGL`, `-VCOM`,
`+1V35`, `+1V2_FPGA`, `+VSYS_FL`.

`EPD_PWR_EN` is declared **bidirectional** on `power_mon` because `U21` drives it as well as
listening — §2.

## 6. Verification — what was actually run

- **Net-group isomorphism against R1, computed rather than eyeballed.** R1's own netlist was
  exported from a scratch copy (R1 itself never opened), and for each sheet the partition of its
  parts' pins into nets was compared with R2's, undoing the designator renames first:

  | Sheet | R1 groups | R2 groups | Identical |
  | --- | --- | --- | --- |
  | `epd` | 49 | 49 | **yes** |
  | `epd_power` | 44 | 44 | **yes** |
  | `power_mon` | 39 | 40 | no — 3 R1-only, 4 R2-only |

  All seven `power_mon` differences were read individually and are exactly §3's four channel
  changes: `R208.2`+`U22.15` became `+3V3_AON_DCDC`; `U22.5` left `+3V3`; the two negative-divider
  references stayed on `+3V3_DCDC` while the three `INA3221` supplies and their decoupling moved to
  `+3V3_AON`. Nothing else moved.
- **ERC on the whole project: 284 violations.** Nearly all are the unwired root sheet (§8):
  164 `isolated_pin_label`, 91 `pin_not_connected`, 15 `power_pin_not_driven`. Then 8
  `four_way_junction`, 3 `pin_not_driven`, 1 `pin_to_pin`, 1 `multiple_net_names`, 1
  `footprint_link_issues`.
- **The 8 `four_way_junction` warnings are R1's drawing**, on `epd_power` (`L6`, `L32`, `R78`/`R79`
  and five more). R1's own ERC reports none because its KiCad 8 project file does not enable that
  check; R2's KiCad 10 defaults do. Carried over deliberately — changing them would change R1's
  geometry.
- **R1's own ERC, run under the same KiCad 10, for calibration:** 140 `lib_symbol_mismatch`,
  27 `power_pin_not_driven`, 24 `pin_not_connected`, 19 `lib_symbol_issues`, 12
  `label_multiple_wires`, 5 `footprint_link_issues`, 4 `multiple_net_names`, 3 `pin_not_driven`.
  R2's ported sheets have **zero** `lib_symbol_mismatch` and `lib_symbol_issues` — that is what the
  symbol refresh and the `SY8120`/`MT9700` lift bought.
- **All three sheets load in KiCad 10** and export a netlist individually.

Not verified, and not verifiable here: nothing on these sheets has been built or measured in R2.
The circuits themselves *are* proven — this is the hardware `NOTES-STATUS.md`'s measurements came
from — but only in R1's rail context.

## 7. Open

- **`SY8120` is the wrong part name for what it draws.** R1 reuses that symbol for the `LGS5145`,
  and the `Value` on each instance is what names the real part. It works because the pinouts match,
  but nobody appears to have written down *that* they match. Worth one pin-by-pin check against the
  `LGS5145` drawing before fab, and then renaming the symbol.
- **`power.kicad_sch` needs the `+3V3_AON_DCDC` rename** — §3, and it is the reviewer's to make.
- **`TPS22914BYFPR` stock is thin** — 1 487 units at LCSC (`C1848394`), for a part used twice.
  `LGS5145` (`C5123971`, 139 k) and `LGS6302B5` (`C5123975`, 11 k) are comfortable. Find a second
  source for the load switch before ordering.
- **`+5V2_FL` is still called that** on `epd` although the frontlight now boosts from `+VSYS`. The
  name describes the LED anode rail, which is unchanged; WP6 confirms or renames it.
- **`epd`'s `J3`/`J6` pinouts were carried pin-for-pin and not re-checked** against the panel.
  `NOTES-R2-plan.md`'s verification list asks for that diff explicitly — it is a WP-E task, not a
  port task, but it is still owed.
- **The root sheet is still unwired**, so most of §6's ERC count is noise and cross-sheet
  connectivity is verified by script instead of by ERC. See §8.

## 8. The root sheet

Adding sheet pins grew three boxes until they overlapped (`mcu` is 41 pins tall, `epd` 36).
`tools/layout_root.py` now re-packs each column vertically, keeping every sheet in the column it was
put in by hand, so the left-to-right arrangement survives. Nine sheets moved; nothing else on the
root was touched.

The root still has **no wires between sheet pins**, which is why `MCU_EN_5V` on `mcu` and on `power`
are still two nets (`/mcu/...` and `/power/...`). Wiring it is mechanical — a labelled stub per pin
— but it should happen when the sheet symbols stop moving, since wires follow them. Until then,
cross-sheet agreement is checked by comparing hierarchical label names and directions between
sheets directly, which is what WP3 §11 and §6 above do.
