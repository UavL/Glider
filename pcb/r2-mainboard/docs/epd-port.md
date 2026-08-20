# `epd`, `epd_power`, `power_mon` — the R1 port — R2 work package 4

Status: **ported; reviewed once — accepted as a 1:1 port.** The review raised one question, about
why the panel connector lives on a separate adapter board; it is answered in §9. Companion to
`battery.md`, `power.md` and `mcu.md`.

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
| `epd` | 11 | 0 | panel connectors `J6` (50p) and `J3` (16p) + 7 caps — `J3` deleted 2026-08-15, so 10 parts now (§7) |
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
| `U27` | 0x43 | 1 | `+1V5_DCDC` → `+1V5` | unchanged | |
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
| `epd` | 33 × `EPDC_*` (to `fpga_io`, WP5), `FL_EN`, `FL_PWM1`, `FL_PWM2` (to `frontlight`, WP6). **23 × `EPDC_*` since the `J3` deletion** — the ten it carried are gone |
| `epd_power` | `EPD_PWR_EN`, `EPD_POS_EN`, `VCOM_EN`, `VCOM_MEA_EN`, `VCOM_DAC`, `VGH_DAC` in; `VCOM_MEA` out |
| `power_mon` | `SCL_AON`, `SDA_AON`, `EPD_PWR_EN`; `VBUS_MEA`, `VP_MEA`, `VN_MEA`, `VGH_MEA`, `VGL_MEA` out |

Rails cross as power symbols, which are global in KiCad and need no label: `+5V_DCDC`, `+5V_EPD`,
`+5V_ES`, `+5V_EG`, `+3V3`, `+3V3_AON`, `+VSYS`, `+VBUS`, `+VP`, `+VGH`, `-VN`, `-VGL`, `-VCOM`,
`+1V5`, `+1V2_FPGA`, `+VSYS_FL`.

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
- ~~**`+5V2_FL` is still called that** on `epd`~~ — **resolved 2026-08-17, by deletion.** WP6
  replaced the frontlight rail with a constant-current driver, so `+5V2_FL` no longer exists as a
  source anywhere. `J6.7`/`J6.44` and `C147` still carry the name on this frozen sheet and are now
  **unused pins with no driver**, which is intended and needs no edit: the bonded frontlight reaches
  the board on its own connector, `J24`. `frontlight.md` §7.1. The same applies to `FL_PWM2` on
  `J6.42`, which the LM3630A does not use.
- **`epd`'s `J6` pinout was carried pin-for-pin and not re-checked** against the panel.
  `NOTES-R2-plan.md`'s verification list asks for that diff explicitly — it is a WP-E task, not a
  port task, but it is still owed. (`J3` no longer needs checking; it is gone.)
- ~~**`J3` (the 16-pin connector) is probably dead weight for R2, and dropping it is free only until
  the panel is chosen.** It carries nothing but `EPDC_D8`–`D11`, a clock pair and six grounds — the
  width/LVDS extension (§9.3). An 8- or 16-bit reader panel needs `J6` alone. Decide with the
  panel.~~ **Closed 2026-08-15 — deleted** by the owner, `tools/patch_drop_j3.py`. `fpga.md` §15.2
  has the reasoning and what moved; §9.3 below is what it was decided from. `epd.kicad_sch` is
  therefore no longer a pin-for-pin port of R1's, and its title-block caption says so.
- ~~**Layout guidelines are still owed for these three sheets.**~~ **Written 2026-08-15 — §11.**
  The headline is §11.1: `U9` and `U26` are inverting buck-boosts whose `GND` pin sits on `-VGL`
  and `-VN`, so each needs a local copper island at −20 V / −15 V with the plane cut away beneath
  it. Confirmed from the exported netlist rather than from the drawing.
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

## 9. Review 1 (2026-08-12) — the analysis note, answered

The note is `../manual-analysis/Analysis_epd_files.md`, and it accepts the port: *"it looks like a
1 to 1 port and is fine for me."* One question remains, and it is a good one because the answer is
not in these three sheets at all.

> The display is not connected directly into the main pcb on the Glider board on the dev kit by
> Modos. Is that because it's a dev kit and should we do it differently, or also keep a separate
> small PCB for the display connector? Maybe if we would offer different device sizes?

### 9.1 Why R1 does it — not a dev-kit compromise, a deliberate architecture

`README.md` says it in as many words, under "Screen Adapters":

> "**Different screen panels have different connectors.** It would take a huge amount of space to
> have every possible screen connector on the motherboard. Instead, a series of different screen
> adapters are provided to adapt to the screen with different pinouts.
>
> The motherboard uses a **50 pin + 16 pin** connector. A single 50 pin connector is enough for
> 8/16-bit screens, the 16 pin connector additionally adds support for LVDS screens and 32-bit /
> 64-bit screens."

The repo backs that up: `pcb/` contains **ten** adapter projects — `34p-adapter-a`, `34p-adapter-b`,
`35p-adapter-a`, `39p-adapter-b`, `39p-adapter-c`, `40p-adapter-ab`, `50p-adapter-b`,
`50p-adapter-c`, `mega_adapter` and `u133_adapter` — each a four-file KiCad project whose whole job
is to map one panel family's FPC pinout onto the mainboard's bus. README's mapping:

| Adapter | Panels |
| --- | --- |
| 33P-A | `ED097OC1-4`/`TC1` |
| 34P-A | `ED060XC3`/`XD4`/`XG1` etc. |
| 39P-A | `ED133UT1-3`, `ED050SU3` etc. |
| 40P-A / 40P-B | `ED078KC1`, `ED103TC2` — **A inserts contacts-down, B contacts-up** |
| 50P-A | `ED113TC1` |

Two things follow. First, the driver is **board area**: EPD FPCs come in 33, 34, 35, 39, 40 and 50
pin variants and you cannot fit them all on one mainboard edge. Second — and this is the part that
cannot be designed away — the **A/B distinction is mechanical**, contacts facing up versus down. No
pinout cleverness on a single connector satisfies both; only a different land pattern does. So even a
mainboard willing to spend the area could not be panel-agnostic without adapters.

So: it is not because it is a dev kit. It is because the dev kit's job is to drive *any* panel, and
`README.md`'s Appendix 1 screen list has an "Adapter" column precisely so a user can look theirs up.

### 9.2 What R2 inherited, and what I recommend

R2 carries the same bus, ported unchanged: `J6` = `FPC-05F-50PH20` (50-pin, 0.5 mm, horizontal) and
`J3` = `FPC-05F-16PH20` (16-pin). So R2 is on the adapter model today by inheritance, not by
decision.

**Recommendation: keep it for now, and revisit at Stage D — because the panel is not chosen yet.**
`NOTES-R2-plan.md`'s open-questions table still lists "Panel model — no, deferred with touch/pen,
read it off the tail/back label". Direct-mounting means committing the mainboard to one panel's exact
pin count, pinout *and* FPC exit geometry. On a board whose stated premise is that there is no
respin, that is betting the most expensive PCB on the one variable still undecided. The adapter is
the cheap hedge: if the panel changes, a $2 board changes.

**But the trade is real, and it goes the other way once the panel is locked.** For a battery reader,
against R1's monitor:

| | Adapter board | Direct-mount |
| --- | --- | --- |
| Z-height | two connector stacks + a second PCB | one FPC connector |
| Cost | extra PCB, extra connector, extra assembly | — |
| Drop reliability in a sealed handheld | two more joints to fail, unserviceable | one joint |
| Signal integrity | two extra discontinuities on a wide parallel bus | clean run |
| Panel flexibility | **one mainboard, N panels** | one panel, or a respin |

Thickness and drop reliability are the ones that actually matter for a reader and do not matter for a
desk monitor, which is why this question deserves a different answer in R2 than in R1 — **once there
is a panel to answer it about.**

**And the note's own hypothesis is the strongest argument for keeping it.** If R2 ever ships in more
than one size, the adapter model is exactly how: one mainboard, one adapter per panel. That is not a
dev-kit artefact — it is a product-line decision, and R1 already paid the engineering cost of it. If
multiple sizes are a real intention rather than a maybe, the question is settled and the adapter
stays permanently.

### 9.3 One thing worth deciding early: `J3` is probably dead weight

> **Decided 2026-08-15: deleted.** Kept below as written, because it is the reasoning the decision
> was made from. What finally settled it was not this argument but a stronger one found in WP5 —
> no `LOC` line in Caster's `constraint.ucf` assigns *any* of `J3`'s ten signals, so the connector
> could not have worked even with a MiniLVDS panel attached. `fpga.md` §2.1 and §15.2.


Reading the exported netlist, `J3`'s sixteen pins carry **only** `EPDC_D8P/N`, `D9P/N`, `D10P/N`,
`D11P/N`, `EPDC_CLKP/N` and six grounds. Everything a normal panel needs is on `J6`: `EPDC_D0`–`D7`,
the gate strobes (`GDCLK`, `GDOE`, `GDSP`), the source strobes (`SDCE0`, `SDLE`, `SDOE`, `SE_CLK`),
all five HV rails (`+VGH`, `+VP`, `-VCOM`, `-VGL`, `-VN`), `+3V3`, the frontlight (`+5V2_FL`,
`FL_EN`, `FL_PWM1/2`) and ten grounds — with five pins spare.

That matches README exactly: 50-pin alone covers 8/16-bit panels, and the 16-pin adds LVDS and
32/64-bit. **A 6″–8″ reader panel is 8- or 16-bit, so `J3` would never be populated.** Deleting it
saves a 0.5 mm-pitch FPC connector, ten routed signals and its share of board edge — on a device
where edge space is scarce. It cannot be added back after fab, so this is a decide-with-the-panel
item, now in §7 rather than a change made on a guess.

### 9.4 Nothing changed in the schematics

This review round is answers only. `epd`, `epd_power` and `power_mon` are untouched, so §6's
verification — `epd` and `epd_power` provably net-identical to R1, `power_mon` differing in exactly
four intended groups — still stands as run.

## 10. `VGH` for the `GDEP103TC2` — the one value the port has to change

Written 2026-08-17, when the panel was decided. **Designed, not yet applied to the schematic.**

`epd_power.kicad_sch` is a frozen, reviewed 1:1 port of R1. This is the only change the panel
forces on it, and it is one resistor.

> **APPLIED 2026-08-19**, owner-approved. `R225` is now `20.5K/1%`, LCSC **`C57105`**
> (`0402WGF2052TCE`, UNI-ROYAL, 144 k in stock) — the same resistor family as the rest of the
> board. Verified against LCSC's parametric table, not its part number. The netlist is unchanged:
> 518 nets, identical pin membership, as expected for a value edit.
>
> Rendered and checked by eye: the divider reads `R224` 390 kΩ over `R225` 20.5 kΩ with `R213`
> 100 kΩ injecting `VGH_DAC`, so 20.5 ∥ 100 = 17.01 kΩ and `VGH = 1.2 × (1 + 390/17.01)` =
> **28.71 V** at DAC = 0 — matching §10.3's target exactly.
>
> `R88`/`R224` also changed part, though not value: `C25782` had **14 units** at LCSC against two
> per board. Now **`C54920667`** (`HRC0402F3903DNTO`, HWA CHN, 390 kΩ ±1 %, 20 k in stock).

### 10.1 The problem

`GDEP103TC2-FT11.pdf` §6.2 ‡ wants **`VGH` = 27 V min / 28 V typ / 29 V max**. `fw/User/power.c:286`
fits the R1 chain as `V = 26.945 − 0.003126 × DAC`, so **DAC = 0 is the ceiling** — the MCU's DAC
only ever pulls `VGH` down. Its own calibration comment records that ceiling as **26.87 V**.

That is below the panel's *minimum*, not merely below its typical.

### 10.2 The network, and a model that checks out

From the exported netlist, `U24` (`LGS6302B5`) is the `VGH` boost: `+5V_VGH` → `L5` → `SW`, `D2` to
`+VGH`, and an FB node carrying four things:

| Ref | Value | Role |
| --- | --- | --- |
| `R224` | 390 k | feedback top, from `+VGH` |
| `R225` | **22 k** | feedback bottom, to `GND` |
| `R213` | 100 k | injects `VGH_DAC` into FB — this is how the MCU trims `VGH` down |
| `C241` | 18 pF | feedforward across `R224` |

`lgs6302.pdf` ‡ gives `V_FB` = **1.2 V** (1.195/1.200/1.205). With the DAC at 0 V, `R213` is simply
a second resistor to ground:

```
R_bot = 22k ∥ 100k = 18.033k
VGH   = 1.2 × (1 + 390/18.033) = 27.15 V
```

Against firmware's three usable calibration points:

| DAC | Computed | `power.c` measured | Error |
| --- | ---: | ---: | ---: |
| 0x000 | 27.15 V | 26.87 V | −1.04 % |
| 0x0F2 | 26.39 V | 26.19 V | −0.76 % |
| 0x77E | 21.13 V | 20.95 V | −0.85 % |

**Consistent to within about 1 %, same sign** — so the model is good enough to size a change
against the tolerance corners rather than against the nominal. (`power.c`'s fourth point, 0xFF0 =
12.26 V, disagrees with its own linear fit as well as with this model; the response is non-linear at
the bottom of the range and it is outside the 22–27 V band the comment calls valid.)

### 10.3 The change: `R225` 22 kΩ → **20.5 kΩ**, 1 %

Options weighed at the corners, applying the −1.05 % bias measured above, and stacking 1 % on all
three resistors with `V_FB`'s ±0.4 %:

| `R225` | Expected at DAC = 0 | Corners | Verdict |
| ---: | ---: | --- | --- |
| 22 k as drawn | 26.87 V | — | **below the 27 V minimum** |
| 20.0 k | 28.97 V | 28.31 – 29.65 V | high corner is over the 29 V maximum |
| **20.5 k** | **28.41 V** | **27.76 – 29.07 V** | **inside the panel's window** |
| 21.0 k | 27.87 V | 27.23 – 28.52 V | cannot reach 28 V typ — the DAC only pulls down |

**Change the bottom resistor, not the top.** The DAC's authority is `R224/R213` = 3.90 V per volt of
DAC output, which depends only on those two — so moving `R225` shifts the setpoint and **leaves the
gain untouched**. Firmware then needs its intercept changed and nothing else.

The 20.5 k worst corner is 29.07 V, 0.07 V above the panel's operating maximum and still ~0.9 V
inside its absolute maximum (`VGL` + 50 V ‡, i.e. 30 V at `VGL` = −20 V). If that is not comfortable,
`R224`/`R225` at 0.5 % halves the band; it is not a different design.

### 10.4 What does *not* change, and why that is the useful result

- **`VGH_MEA` needs nothing.** `R98` 1 M / `R97` 100 k puts 29 V at **2.64 V**, inside the 3.3 V ADC
  range — `mcu.md` §5.2's 2.45 V figure at 26.9 V is the same divider.
- **`U24` is nowhere near a limit.** `lgs6302.pdf` ‡: 3.0–60 V range, 2 A peak switch. The panel
  draws `I_GH` = 1.52 mA typ / 1.89 mA max ‡, so ≈ 13 mA in at 5 V.
- **`D2`** is a 1N5819WS, 40 V ‡, against 29 V.
- **`C241`/`C244`/`C62`** on `+VGH` are all 50 V rated.
- **DAC resolution** stays 3.14 mV of `VGH` per LSB; the range becomes ≈ 15.8–28.7 V, still covering
  R1's 22–27 V band.
- **`VGH − VGL` ≤ 50 V ‡** holds: 29 − (−20) = 49 V. At `VGL` = −21 V (the panel's own minimum ‡) it
  is exactly 50 V — worth knowing, not worth designing around.

### 10.5 Firmware, which is not ours to verify

`power_set_vgh()`'s constants are **empirical** — someone measured that chain. The replacements are
**computed**:

```c
// was:  setpt = (26.945f - vgh) / 0.003126f;   // valid 22V - 27V
//  now: setpt = (28.71f  - vgh) / 0.003141f;   // valid 22V - 29V
```

The divisor barely moves (0.5 %, which is this model against their measurement); only the intercept
does. **These must be re-measured on hardware before they are trusted.** The assistant cannot flash
or measure the board.

#### ⚠ And a second change in the same file, which is not optional

Found 2026-08-20, reading `power.c` for the constants above. **The bring-up sanity window will
reject a correctly built R2 board**, and it does not warn — it calls `fatal()`.

```c
// fw/User/power.c:199-204
static bool epd_pos_rails_good(void) {
    float vp  = power_get_rail_voltage(RAIL_VP);
    float vgh = power_get_rail_voltage(RAIL_VGH);
    return (vp  >= 14.0f) && (vp  <= 16.0f) &&
           (vgh >= 21.0f) && (vgh <= 28.0f);   // <-- 28.0 is the problem
}
```

`power_on_epd()` polls this for `EPD_PWRUP_TIMEOUT_MS` = 1200 ms and then, on `false`, calls
`fatal("Failed to bring up pos rails")` (`power.c:239-244`). It is not a warning path.

Line up the three numbers:

| | `VGH` | vs the window's 28.0 V ceiling |
| --- | ---: | --- |
| R1 as built | 26.87 V at DAC = 0 | inside, with 1.1 V to spare — which is why nobody hit this |
| **R2 nominal**, after `R225` = 20.5 k | **28.41 V** | **0.41 V over. Fails.** |
| R2 low corner | 27.76 V | inside |
| R2 high corner | 29.07 V | 1.07 V over |

So R2 fails at *nominal*, and only the low tail of the tolerance band passes. The window was written
around R1's chain and the panel change moved the rail out from under it. **The window has to move
with the resistor** — the two are one change, not two:

```c
// was:  (vgh >= 21.0f) && (vgh <= 28.0f)
//  now: (vgh >= 21.0f) && (vgh <= 30.0f)
```

30.0 V is the panel's absolute maximum (`VGL` + 50 V at `VGL` = −20 V, §10.3). That is the right
*kind* of ceiling for a sanity check — its job is to catch a boost that has run away or a divider
stuffed wrong, not to enforce the operating window, which is the DAC loop's business. The 21.0 V
floor is left alone: it still catches "the boost never started", and the DAC legitimately pulls
`VGH` down into the low 20s in normal use.

**But 30.0 V is tighter than it looks, and this is the number to check on the bench.** The high
tolerance corner is 29.07 V, and it is *measured* through `R98`/`R97` at 1 % each into a 12-bit ADC
referenced to the `+3V3_AON` LDO — call it another 2 %, so a genuine 29.07 V board can report about
29.6 V. That leaves 0.4 V, which is not much of a margin against a check whose failure mode is
`fatal()`. Two ways out, both cheap, and the choice needs one bench measurement to make:

- If the built boards land near 28.4 V nominal, **30.0 V is fine** and the corner is theoretical.
- If they land high, either take `R224`/`R225` to 0.5 % (§10.3 — halves the band) or raise the check
  to **31.0 V** and accept that it no longer catches a mild over-voltage, only a gross one.

Do not raise it silently to "make the error go away" — 31.0 V is above what the panel is rated to
survive, so it is a deliberate trade of protection for robustness, not a free fix.

**Both changes are needed together.** Fitting `R225` = 20.5 k without touching the window turns a
correct board into one that dies at every EPD power-up; changing the window without `R225` leaves
`VGH` below the panel's minimum. Neither has been tested — see the caveat above.

`epd_neg_rails_good()` was checked at the same time and needs nothing: it wants `VN` ∈ [−16, −14]
and `VGL` ∈ [−21, −19], and the `GDEP103TC2` asks for `VGL` = −20 V ±1 V, which sits inside.

### 10.6 One observation the earlier review could not make

`U24.4` (`EN`) and `U24.5` (`VIN`) are **both on `+5V_VGH`**, and `U23` is wired the same way.
`lgs6302.pdf` Absolute Maximum Ratings ‡ give `EN`-to-`GND` as **−0.3 to 6 V**, and its application
note says *"EN is a low-voltage pin. Use a voltage divider from VIN for proper operation."* A 5 V
rail leaves 1 V of margin to the absolute maximum.

**No change recommended** — this is R1's arrangement and R1 works, `+5V_VGH` is a gated 4.99 V rail
rather than anything that can wander, and the enable threshold is 0.5 V rising ‡ so a divider would
be about protection, not function. It is recorded because the datasheet was not in the repo at
review 1 and this is the kind of thing that gets rediscovered expensively.

## 11. Layout guidelines — written 2026-08-15, for Stage D

§7 has owed these since WP4, with the note that "the EPD supply is the most layout-sensitive
circuit on the board". It is, and for one reason that is invisible on the schematic.

### 11.1 ⚠ Two ICs have a "GND" pin that is not ground, and a plane connection destroys them

**Verified from the exported netlist, not from the drawing:**

| Part | Pin 2, labelled `GND` | Sits on | Voltage relative to board ground |
| --- | --- | --- | --- |
| `U9` `LGS5145` | `GND` | **`-VGL`** | about **−20 V** |
| `U26` `LGS5145` | `GND` | **`-VN`** | about **−15 V** |
| `U23` `LGS6302B5` | `GND` | `GND` | 0 V — a normal boost |
| `U24` `LGS6302B5` | `GND` | `GND` | 0 V — a normal boost |

Both `LGS5145`s are wired as **inverting buck-boosts** (`epd-port.md` §4.1): the IC's ground
reference *is* the negative output. So each one needs its own **local copper island at −20 V or
−15 V**, and that island must not touch the ground plane anywhere. The failure mode is not subtle
— tie either to ground and the part sees its full input across the wrong terminals.

Concretely, for `U9` and again for `U26`:

- The island carries pin 2, the local input capacitor's "ground" end, the output capacitor's
  return, and the feedback divider's bottom. **Nothing else.**
- The plane layer under each island must be **cut away**, not just avoided on the outer layer. A
  ground pour under a −20 V island is a 20 V capacitor across a thin prepreg and a coupling path
  for the switching node.
- Silkscreen each island. This is the one thing on the board that a reasonable person will "fix".

### 11.2 The switching loops, in order of how much they radiate

Four converters here, and the two inverting ones have the hottest loops because their return is
the negative rail rather than a plane.

- **Input loop first**: for each of `U9`, `U26`, `U23`, `U24`, the input capacitor goes across the
  IC's `VIN` and its own reference pin with the shortest possible loop — this is the
  high-di/dt path, and it matters more than the inductor placement.
- `L5`, `L6`, `L30`, `L32` (`WPN3012H4R7MT`, 4.7 µH): keep the **`SW` node copper small**. It is
  the dv/dt aggressor and the only reason to make it wide is current, which at these currents is
  not a reason.
- The catch diodes `D1`–`D6`, `D15`, `D17` (`1N5819WS`) belong **immediately** at their converter's
  `SW` node. A Schottky at the far end of a trace turns the trace into an antenna at every edge.
- Keep all four converters' loops away from `VCOM_MEA` and the panel connector (§11.3, §11.4).

### 11.3 `VCOM` is measured, and the measurement is the point

`VCOM_MEA` runs to the MCU's `ADC_IN6`, and R1's whole VCOM kick-back scheme depends on that
reading being clean. `U31` (`LM321`) buffers it.

- Route `VCOM_MEA` as a **quiet analogue trace**: away from every `SW` node, guarded by ground on
  the same layer where it is convenient, and never over a switching-converter island.
- `U6` (`MT9700`) and the `VCOM` divider network sit close to `U31`, not close to the converters.
- The `-VCOM` rail itself goes to the panel and is comparatively low current; give it clearance,
  not width.

### 11.4 High-voltage clearance, which is smaller than it feels

The extremes are about **+22 V (`+VGH`)** and **−20 V (`-VGL`)**, so the worst pair-wise
difference on this board is roughly **42 V**. IPC-2221B for 31–50 V external, uncoated, asks for
**0.13 mm**; internal layers less. Our ordinary 0.2 mm class rules therefore already satisfy it,
and no special HV spacing class is needed.

**What does need care is not clearance but sequencing damage**: `+VGH` and `-VGL` are generated
from `+5V_EG`/`+5V_ES`, which the `TPS22914`s (`U7`, `U8`) gate. Keep those load switches and their
enables physically near the converters they feed, so the enable trace is short and cannot pick up
the switching it is supposed to control.

### 11.5 The `INA3221` shunts want Kelvin connections

`power_mon` carries eight 20 mΩ shunts. At 20 mΩ, **1 mΩ of trace resistance is a 5 % error**, and
a shunt sensed at the wrong end of its own pad measures the pad too.

- Sense traces leave from the **inside edges of the shunt pads**, symmetrically, as a tight pair.
- Route the pair together to the `INA3221`, away from the converters.
- The five HV measurement dividers belong at the `INA3221`, not at the rail, so the high-impedance
  node is short.
- All three `INA3221`s are on `+3V3_AON` (§3) — their supply and I²C should not have to cross a
  switching region to get there.

### 11.6 The panel connector

`J6` (`FPC-05F-50PH20`, 50-pin 0.5 mm) is the board's edge interface and it carries five HV rails,
`+3V3`, the frontlight pair and the whole source/gate bus.

- **Place it first.** It is the one part whose position is fixed by the enclosure and the panel's
  own tail, and everything else on this sheet arranges around it.
- The HV rails arrive at it from §11.1's islands; give each a direct route rather than a plane,
  since these are not plane nets.
- `EPDC_SE_CLK` and the source bus are the fastest signals here; keep them over continuous ground.
- `J3` is **gone** (§7), so the 16-pin connector's board edge is free — worth remembering when the
  outline is drawn, because that was ~13 mm of edge on R1.
