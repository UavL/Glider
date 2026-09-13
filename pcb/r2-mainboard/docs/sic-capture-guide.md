# Capturing the `OSD62x-PM` and retiring the `PCM-071` — a step-by-step

Status: **written 2026-09-12**, for the owner. This is **Phase 4** of `NOTES-R2-osd62x-plan.md`
(D9: the owner captures). The *what* is `docs/sic.md` — every value, part and net is specified
there, and this guide does not repeat them; this is the *order of operations*, the traps, and the
checks that tell you a step is done.

**Ground rules** (`CLAUDE.md`): a sheet saved in Eeschema is edited by hand, never regenerated ·
no script writes a `.kicad_*` file while KiCad is open · never bare-string-replace a designator ·
`pcb_common` is untouched.

---

## 0. Where things actually stand — checked 2026-09-12

| | |
| --- | --- |
| `sic.kicad_sch` | exists, **page 15**. All **11 units** of `Reflow:OSD6254-1G-IPM` are placed, footprint field already `Reflow:BGA500C50P28X18_1400X900X130`. **But they carry two different references — one unit is `IC1`, ten are `U1`** — so KiCad currently sees two parts. Nothing else on the page: no power, no PMIC, no labels |
| `som.kicad_sch` | page 5: `J501`+`J502` units, the microSD `J500` + `MK500`, the module outline `X500`, `R500`–`R504` (47 k SD pull-ups), `C510`–`C513`; **19 hierarchical labels** |
| `dpi_in.kicad_sch` | page 6: **nothing but `J501`/`J502` units** and the **22 DPI labels**. Delete the connectors and the page is empty |
| `mcu.kicad_sch` | carries `SOM_RESET#`, `SOM_IRQ#`, `SOM_WAKE#`, `SOM_MCU_NRST`, `SOM_MCU_BOOT0`, `PG_SOM`, `MCU_TXD`, `MCU_RXD` |
| `fpga_config.kicad_sch` | `FPGA_SCLK`, `FPGA_MOSI`, `FPGA_MISO`, `FPGA_CS`, `NOR_CS` |
| root `r2.kicad_sch` | joins sheets with **local labels on short wire stubs** (233 of each) — that is the house style for any new cross-sheet net |
| `tools/check_pcb_connectors.py` | asserts `J501`/`J502`/`X500` geometry — **it is supposed to fail** after this work; Phase 4 retires it |
| `tools/check_ucf.py` | only knows `U700`; unaffected |

---

## 0a. Progress — 2026-09-12

| Step | State |
| --- | --- |
| 1 baseline | done (netlist exported before each change) |
| 2 one reference | **done** — all 11 units are `U600`; `IC1500`/`U1500`/`U1501`/`U1`/`U1403` are gone |
| 3 `VIDEO` on `dpi_in` | **done by the owner** (option B) |
| 4 power the SiP | **done** — every power ball on its rail, `VPP` flagged, 30 decoupling capacitors |
| 5 PMIC + load switches | **done** — `U1501` all 33 pins to §3, `U1502`/`U1503` to §4 |
| 6 crystal | **done** — `Y1500` + `C1552`/`C1553` 18 pF on `OSC_XI`/`OSC_XO`; `WKUP_LFOSC0_XI` grounded, `XO` open |
| 7 boot straps | **done** — 14 × 10 k on page 15 (`R1511`–`R1524`), bits 8/9 on `dpi_in` (`R600`/`R601`). Netlist decodes to `AD15..AD0 = 0000011001000011`, matching §6 |
| 8 resets / monitors / VBUS | open — `VMON_VSYS` is labelled and waiting for its divider |
| 9 the 48 signals | open — 135 SiP signal pins unwired (`BOOT_GPMC`, `SYSTEM`, `SERIAL`, `STORAGE`) |
| 10 page 5 | open |
| 11 eMMC | open |
| 12 prove it | ERC/netlist run after every change; 7 `hier_label_mismatch` remain by design (step 9 adds the root sheet pins) |

The page is now **A2**: it went A4 → A3 for the PMIC and decoupling, then A3 → A2 after the owner spread the eleven units out to x = 480, past A3's 420 mm frame. Originally: the owner's drawing already spanned x 30–258, y 23–168, and the
PMIC, its passives, the two switches and the decoupling bank do not fit on A4.

---

## 1. Two things to settle before opening Eeschema

### 1.1 The PMIC symbol — done 2026-09-12

**`Reflow:TPS6521903` exists now.** The owner created the container in the symbol editor (name,
Value, Description, and an embedded copy of the datasheet); `tools/gen_pmic_symbol.py` filled in all
**33 pins** from `SLVSGA0D` Table 5-1 and set the footprint. Layout: supply inputs then the four
control pins then I²C down the left, the bucks' `LX`/`FB` pairs then the LDO outputs then the
open-drain outputs down the right, `AGND` (15) and `PGND` (33) out of the bottom. `VLDO1`–`4` and
`VDD1P8` are `power_out`, the switch nodes are `passive`, and `GPO1`, `GPO2`, `nINT`, `nRSTOUT` are
`open_collector` so ERC does not object when two of them share a pull-up.

The **footprint** comes from stock, with one caveat: the datasheet's package is **`RHB0032W`** —
VQFN-32, 5.0 × 5.0 mm, 0.5 mm pitch, exposed pad **3.5 mm** — while KiCad ships `RHB0032E`
(EP 3.45 mm) and `RHB0032M` (EP 2.1 mm). Use
**`Package_DFN_QFN:Texas_RHB0032E_VQFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm_ThermalVias`**: 0.05 mm
smaller on the pad, and the `_ThermalVias` variant already carries the ≥ 9 vias the datasheet demands
under the power pad. Reject `RHB0032M` — its pad is 1.4 mm too small.

### 1.2 Where the `VIDEO` unit lives — this sets the SiP's designator

`dpi_in` (page 6) holds nothing but the two connector units, so once they go the page is empty.
Two ways to finish it, and `CLAUDE.md`'s "a shared part takes its lowest page" decides the name:

| | **B — recommended** | A |
| --- | --- | --- |
| Where | `VIDEO` unit goes **on `dpi_in`**, the other ten on `sic` | all 11 units on `sic`; delete the `dpi_in` sheet |
| SiP designator | **`U600`** | `U1500` |
| DPI wiring | **nothing to do** — `dpi_in`'s 22 hierarchical labels already exist and stay exactly where they are | 22 new sheet pins + 22 stubs + 22 labels at the root |
| `DPI_R6`/`R7` straps | `R600`/`R601`, right next to the unit | on `sic`, or two more labels |
| Cost | the part is `U600` although most of it is drawn on page 15 | more hand-wiring, more chances to typo a net name |

**B is recommended**: it is less work, touches the root sheet not at all, and keeps page 6 meaningful
("the SoC's DPI output" instead of "the connector's DPI pins"). Everything else on page 15 stays
`…15xx` either way. If you prefer one designator on one page, take A — but budget for the 22 labels
and check every one against the table in §3.

---

## 2. The steps

### Step 1 — a baseline you can diff against
With KiCad **closed**:
```
cd pcb/r2-mainboard
git status                 # must be clean; commit anything outstanding first
kicad-cli sch export netlist -o /tmp/before.net r2.kicad_sch
```
Keep `/tmp/before.net`. Step 12 diffs against it, and that diff is the real proof this went right.

> **Trap — do not run Tools → Annotate Schematic.** R2's designators are the page-based scheme
> (`CLAUDE.md`), assigned by hand. A global annotation run renumbers the whole board and silently
> breaks `check_ucf.py`, the BOM and every doc. Fix references by editing the symbol's Reference
> field, one at a time.

### Step 2 — make page 15's SiP one part
Open `sic.kicad_sch`. The 11 placed units answer to two names (`IC1` ×1, `U1` ×10).

1. Find the `IC1` unit (Edit → Find, or click each until the properties show `IC1`).
2. Set **every** unit's Reference to the single name from §1.2 — `U600` (B) or `U1500` (A).
3. Confirm each of units 1–11 appears **exactly once**: `PWR_CORE`, `PWR_IO`, `GND`, `VIDEO`,
   `BOOT_GPMC`, `SYSTEM`, `SERIAL`, `STORAGE`, `USB`, `UNUSED_HS`, `NC_RSVD`. A duplicated unit is
   an ERC error and a silently wrong netlist.
4. Value = `OSD6254-1G-IPM`, Footprint = `Reflow:BGA500C50P28X18_1400X900X130` (already set).

*Exit:* ERC reports no duplicate or missing units for that reference.

### Step 3 — the `VIDEO` unit (option B)
On `dpi_in`: delete the `J501`/`J502` units, drop the SiP's `VIDEO` unit in their place, and wire the
22 existing hierarchical labels to it — `DPI_B2…B7`, `DPI_G2…G7`, `DPI_R2…R7`, `DPI_PCLK`, `DPI_DE`,
`DPI_HS`, `DPI_VS`. The mapping is §3's table; **`DPI_R6`/`DPI_R7` are `GPMC0_AD8`/`AD9`**, so their
strap resistors (`sic.md` §6, bits 8 and 9) go here too.

*Exit:* every one of the 22 labels lands on the ball §3 names, and nothing on page 6 is unconnected.

### Step 4 — power the SiP
`sic.md` §2 is the rail map and the decoupling, from Octavo's Table 4-3. Draw, in this order, on page 15:

1. `PWR_CORE` and `PWR_IO` units: `+0V75_SOC`, `+0V85_SOC`, `+1V2_SOC`, `+1V8_SOC`, `+1V8A_SOC`,
   `+2V5_SOC`, `+3V3_SOC` to the ball groups.
2. `GND` unit (104 balls) to `GND`.
3. The decoupling bank per §2 — 10 µF + 6 × 100 nF on the core net, 3 × 100 nF on `VDDR_CORE` and on
   `VDDS_DDR`, 100 nF per `VDDSHV` pair + 10 µF bulk, the `VDDA` group's 1 µF/4.7 µF, `DDR_VPP`'s
   100 nF.
4. `VPP` (`sic.md` §2, last row): **leave unconnected**.

*Exit:* no SiP power ball is left floating; ERC's "power input not driven" list is empty once §5 adds
the sources.

### Step 5 — the PMIC, the load switches
`U1501` `TPS6521903RHBR` per `sic.md` §3 (pin-by-pin table), `U1502`/`U1503` `TPS22965DSGR` per §4.
Needs §1.1's symbol first. Watch three things §3 calls out:
- **`PVIN_LDO1` comes from BUCK2 (1.8 V)**, not from 3.3 V, and `VLDO1` drives nothing but its 2.2 µF.
- `U1502`'s **`CT` = 1000 pF** — the BRK leaves it empty; R2 needs the slow ramp.
- `EN/PB/VSENSE` gets 10 kΩ to `+VSYS_SOC` plus a **DNP** 0 Ω to an MCU spare.

### Step 6 — the crystal
`Y1500` per `sic.md` §5: `SX3B25.000F1010F30`, 2 × 18 pF C0G, `WKUP_LFOSC0_XI` to ground and `XO`
open. (`Device:Crystal` + the stock 3225 footprint; nothing to generate.)

### Step 7 — boot straps
`sic.md` §6's table, 10 kΩ each, none floating. Bits 8 and 9 are the two DPI nets from step 3. If the
eMMC goes on (step 11), lay out **both** resistors on bit 3 (`AD3`/`F27`) and fit one.

### Step 8 — resets, monitors, USB sense
`sic.md` §7: `MCU_PORZ` (open-drain, 1.8 V — the MCU's `PA15` wire-ANDs here), `RESETSTATZ` out to the
PMIC and to MCU `PC8`, `EXTINTN`, `PMIC_LPM_EN0`, the `VMON_VSYS` 100 k/16.9 k divider, and TI's
clamped VBUS dividers on `USB0_VBUS`/`USB1_VBUS` (16.5 k + 3.48 k / 10 k with a `BZX84C6V8`).

### Step 9 — the 48 carry-over signals
Add hierarchical labels on `sic` for everything in §3's table that is not DPI, then fix the **other
side** of the three renamed nets:

| Sheet | Change |
| --- | --- |
| `mcu` | `SOM_RESET#` → **`MCU_PORZ`** (open-drain only) · `PG_SOM` → **`RESETSTATZ`** · keep `R406`/`R407`/`R408` as `sic.md` §7/§8 describe |
| `fpga_config` | unchanged names — but read `sic.md` §9's **D10**: the MCU must hold `FPGA_PROG#` low whenever `RESETSTATZ` is low |
| `power` | `power.md` §8.1 — `+5V_DCDC` loses the SoM's 1.0 A; the boost now feeds only the EPD chain and USB1 |

*Exit:* no hierarchical label on `sic` is unconnected, and no label name exists on exactly one sheet
(the classic typo signature).

### Step 10 — page 5, the old `som` sheet
Delete `J501`, `J502` and `X500`. **Keep the microSD**: `J500`, `MK500`, `R500`–`R504`, `C510`–`C513`.
Then, per `sic.md` §8:
- move the card's supply **and** `R500`–`R504` from `+3V3_SDIO` to **`+3V3_SOC`**;
- add **22 Ω in series with `MMC1_CLK`** at the SiP;
- the sheet is now the SD card, not the module — rename the sheet (its `Sheetname`, not the file) so
  the hierarchy stops saying `som`.

### Step 11 — the eMMC, optional
`sic.md` §6.1, fitted on one or two boards. Symbol `r2:KLM8G1GETF-B041` and the stock
`Package_BGA:LFBGA-153…` footprint both exist already. Mind the pulls: **47 kΩ on `CMD` and `DAT0`
only**, nothing on `DAT1`–`7`, a 10 kΩ pull-down at the eMMC's `CLK`, a 10 kΩ pull-down on
`Data_Strobe`, and 0 Ω (22 Ω footprint) in series at the SiP. `RST_n` comes straight from
`RESETSTATZ`.

### Step 12 — prove it
With KiCad closed:
```
kicad-cli sch export netlist -o /tmp/after.net r2.kicad_sch
diff <(sort /tmp/before.net) <(sort /tmp/after.net) | less
python3 tools/check_pcb.py          # PCB still untouched at this point
python3 tools/check_ucf.py          # must stay 0 failures — the FPGA did not move
```
The diff should contain **only**: the SoC side of the 48 nets moving from `J501`/`J502` pads to SiP
balls · the new parts of `sic.md` §11 · the three renamed nets of step 9 · the SD pull-ups' new rail.
Anything else is a mistake — find it before the PCB.

`check_pcb_connectors.py` **will fail**, by design: it asserts the geometry of parts that no longer
exist. Retire it in favour of a SiP placement check (plan Phase 4).

### Step 13 — handing over to layout
Phase 5 in the plan, `sic.md` §12 for the rules: the SiP in the same corner as `J200`, the PMIC beside
the core and DDR balls, `+0V75_SOC`/`+1V2_SOC` islands on `In2.Cu`, fine-pitch DRC scoped to the SiP's
courtyard, and **the fab question of §12 answered before you commit to a via size**.

---

## 3. The signal map — what each old net becomes

From `osd62x-symbol-guide.md` §6, which was checked against the datasheet's ball map and Octavo's own
library, 500/500.

| Old net | SiP pin | Ball | Unit | After the swap |
| --- | --- | --- | --- | --- |
| `DPI_B2`…`B7` | `VOUT0_DATA0`…`5` | `P26 N25 N26 M25 M26 U27` | `VIDEO` | page 6, step 3 |
| `DPI_G2`…`G7` | `VOUT0_DATA6`…`11` | `T27 T28 R27 R28 P27 P28` | `VIDEO` | page 6 |
| `DPI_R2`…`R5` | `VOUT0_DATA12`…`15` | `N27 N28 M27 M28` | `VIDEO` | page 6 |
| `DPI_R6`/`R7` | `GPMC0_AD8`/`AD9` | `L27`/`L28` | `VIDEO` | page 6 **+ strap resistors** |
| `DPI_PCLK`, `DE`, `HS`, `VS` | `VOUT0_PCLK`, `_DE`, `_HSYNC`, `_VSYNC` | `T26 R25 P25 R26` | `VIDEO` | page 6 |
| `FPGA_SCLK/MOSI/MISO/CS` | `SPI0_CLK`, `_D0`, `_D1`, `_CS0` | `C11 D12 C12 D13` | `SERIAL` | label on `sic` |
| `NOR_CS` | `SPI0_CS1` | `C13` | `SERIAL` | label on `sic` |
| `MCU_RXD`/`MCU_TXD` | `UART0_TXD`/`UART0_RXD` | `B10`/`A10` | `SERIAL` | **note the crossover** |
| `SOM_IRQ#`/`SOM_WAKE#` | `MCU_MCAN0_TX`/`_RX` | `E2`/`E1` | `SERIAL` | label on `sic` |
| `SOM_MCU_NRST`/`_BOOT0` | `MCU_MCAN1_TX`/`_RX` | `F2`/`F1` | `SERIAL` | label on `sic` |
| `SD_CLK`, `SD_CMD`, `SD_CD#` | `MMC1_CLK`, `_CMD`, `_SDCD` | `B21 A21 A23` | `STORAGE` | + 22 Ω on CLK |
| `SD_DAT0`…`3` | `MMC1_DAT0`…`3` | `A22 B22 A20 B20` | `STORAGE` | pull-ups → `+3V3_SOC` |
| `USBD+`/`USBD-` | `USB0_DP`/`USB0_DM` | `V12`/`U12` | `USB` | label on `sic` |
| `USB1_D+`/`USB1_D-` | `USB1_DP`/`USB1_DM` | `V10`/`U10` | `USB` | label on `sic` |
| `USB1_DRVVBUS`, `USB1_VBUS` | same | `D19`, `U11` | `USB` | **VBUS now needs the §7 divider** |
| `SOM_RESET#` | `MCU_PORZ` | `D6` | `SYSTEM` | **renamed**, open-drain |
| `PG_SOM` | `RESETSTATZ` | `C18` | `SYSTEM` | **renamed** — no ball ever matched `PG_SOM` |

New, because the module used to do it internally: PMIC `nRSTOUT`→`MCU_PORZ` `D6` · `MODE/STBY`←
`PMIC_LPM_EN0` `D5` · `MODE/RESET`←`RESETSTATZ` `C18` · `nINT`→`EXTINTN` `C17` · I²C `A12`/`B12` ·
crystal `G1`/`G2` · monitors `A15`/`B15`/`C15` · `USB0_VBUS` `V11` · straps `D27`–`K28`.

---

## 4. Traps, each of which has a reason

1. **Never run global annotation** (step 1) — it destroys the page-based designator scheme.
2. **`MCU_RXD` ↔ `UART0_TXD`.** The names cross. Wire by the table, not by the name.
3. **`DPI_R6`/`DPI_R7` are boot straps** inside `BOOTMODE[9:3]`. Their resistors must overpower the
   Spartan-6's `HSWAPEN` pull-ups on the same nets (`sic.md` §6).
4. **`PG_SOM` has no equivalent ball.** It was PHYTEC's module-level signal; `RESETSTATZ` replaces it
   and means something different ("the SoC is running", not "the rails are good").
5. **`VPP` stays unconnected.** It is the eFuse programming pin.
6. **Nine signals sit in ball ring 4** (`osd62x-symbol-guide.md` §6) — irrelevant now, decisive in
   Phase 5's escape routing.
7. **Do not use KiCad's Local History → Restore** in this project: it deletes untracked non-KiCad
   files from the project directory. It has bitten this repo twice.
8. **Close KiCad before any `tools/` script runs**, and before `kicad-cli` touches the project.
