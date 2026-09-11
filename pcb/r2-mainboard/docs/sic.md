# `sic` — the Octavo `OSD62x-PM` page — R2 page 15

Status: **draft 2026-09-11; the owner's decisions of the same day are folded in** (Phase 2 of
`NOTES-R2-osd62x-plan.md`). This is
the spec the owner captures from in Phase 4. It replaces everything the `PCM-071` did on `som` (page 5)
and changes parts of `power`, `mcu` and `dpi_in`.

**Tags:** **[B]** read from a source on 2026-09-11 — every one is collected with its page number in
`NOTES-R2-hardware-facts.md` §3.3 · **[I]** inferred, check before relying on it · **[H]** needs a
hardware test.

**What it rests on** (plan §9.2 — all owner decisions of 2026-09-11): **D1** the PMIC runs from the
battery rail · **D2** core 0.75 V · **D3** `TPS6521903` · **D4** SD-only boot, with an eMMC footprint
fitted on one or two prototypes (§6.1) · **D5** no UHS-I · **D8** 1 GB · **D10** the FPGA kept quiet
while the SoC is off, in firmware *and* in Caster (§9). **D11** (USB-DFU backup boot) stands as
proposed. **D6 — the fab — is open** (§12). §1 still needs TI to confirm LDO1 fed from BUCK2.

**Reference designators:** page 15 gives four digits, `U1500`… The SiP itself is `U1500` if all its
units sit here, or `U600` if its `VIDEO` unit goes on `dpi_in` (a shared part takes its lowest page).
Every other part below is `…15xx` either way.

---

## 1. The power architecture — rests on D1

```
+VSYS 3.0-4.4 V ──U1503 TPS22965 (ON = MCU_EN_SOC)──► +VSYS_SOC
                                                        │
      U1501 TPS6521903 ◄── VSYS, PVIN_B1/B2/B3, PVIN_LDO34
        BUCK1 0.75 V ──► +0V75_SOC   VDD_CORE, VDD_CANUART, VDDA_CORE_CSIRX0, VDDA_CORE_USB
        BUCK2 1.8 V  ──► +1V8_SOC    VMON_1P8_SOC, PVIN_LDO2, PVIN_LDO1
        BUCK3 1.2 V  ──► +1V2_SOC    VDDS_DDR
        LDO2  0.85 V ──► +0V85_SOC   VDDR_CORE
        LDO3  1.8 V  ──► +1V8A_SOC   VDDA_1P8_*, VDDA_PLL0-2, VDDA_MCU, VDDA_TEMP, VDDS_OSC0
        LDO4  2.5 V  ──► +2V5_SOC    DDR_VPP
        LDO1         ──► unloaded (2.2 µF only)
        GPO2 ────────► ON of U1502
+3V3_DCDC (U302) ──U1502 TPS22965 (CT 1000 pF)──► +3V3_SOC   every VDDSHV incl. VDDSHV5,
                                                               VDDA_3P3_USB, VMON_3P3_SOC, SD card,
                                                               the page's pull-ups
```

**Why it differs from the BRK** [B for the BRK, I for R2]: the BRK feeds everything from a regulated
3.3 V. R2 has a 1S cell, so the PMIC takes `+VSYS` directly — one conversion instead of two, and
`U302` is not asked for the SiP's ~1.5 A worst case on top of the FPGA and panel. Every PMIC input
stays at or below VSYS, as the datasheet demands. **The one exception is LDO1.** In `…03` it is a
3.3 V bypass rail, and bypass needs 1.5–3.4 V at `PVIN_LDO1` *and* `PVIN_LDO1` ≤ VSYS — no 3.3 V
source meets both on a cell that sags to 3.0 V. So **`PVIN_LDO1` comes from BUCK2 (1.8 V)**, LDO1
drives nothing, and `VDDSHV5` joins the switched 3.3 V rail (hence D5: no UHS-I). **Ask TI to confirm
this LDO1 arrangement** (plan E10).

The new net names all start with `+`, so `r2.kicad_pro`'s `PWR` pattern `+*` picks them up.

## 2. Rail map and decoupling

| SiP balls | Net | Source | Max current [B] | Decoupling [B, Octavo Table 4-3] |
| --- | --- | --- | ---: | --- |
| `VDD_CORE` ×18, `VDD_CANUART`, `VDDA_CORE_CSIRX0`, `VDDA_CORE_USB` | `+0V75_SOC` | BUCK1 | 2710 mA (worst) | one net, so note 1 applies: **10 µF + 6 × 100 nF** |
| `VDDR_CORE` ×8 | `+0V85_SOC` | LDO2 | 150 mA | 3 × 100 nF |
| `VDDS_DDR` ×10 | `+1V2_SOC` | BUCK3 | 600 mA (datasheet Table 7-3) | 3 × 100 nF |
| `DDR_VPP` | `+2V5_SOC` | LDO4 | 60 mA | 100 nF |
| `VDDA_1P8_OLDI0`, `_CSIRX0`, `_USB`, `VDDA_PLL0`–`2`, `VDDA_MCU`, `VDDA_TEMP`, `VDDS_OSC0` | `+1V8A_SOC` | LDO3 | 155 mA group | one net, so note 2 applies: **1 µF + 100 nF** (OLDI0), **4.7 µF + 100 nF** (CSIRX0), **+ 1 µF** |
| `VMON_1P8_SOC` | `+1V8_SOC` | BUCK2 | — | as the BRK |
| `VDDSHV0`–`6`, `VDDSHV_MCU`, `VDDSHV_CANUART` (×2 each) | `+3V3_SOC` | U1502 | 150 mA group + SD card | 100 nF per ball pair + 10 µF bulk [I] |
| `VDDA_3P3_USB` | `+3V3_SOC` | U1502 | 50 mA | 100 nF |
| `VMON_3P3_SOC` | `+3V3_SOC` | U1502 | — | — |
| `VMON_VSYS` | divider, §7 | — | — | — |
| `VPP` | **not connected** | — | — | "floating or grounded except while programming eFuses" |

The PMIC's own output capacitors and inductors follow the BRK [B]: **47 µF + 10 µF** at each buck
output, **10 µF** at each LDO output, **2.2 µF** on `VDD1P8`, **0.47 µH** on all three bucks. R2
already stocks a suitable 0.47 µH: `DFE252012F-R47M` (`C703140`, 4.9 A saturation, `power.md` §3.2).
Put ≥ 4.7 µF on `PVIN_B1` and the BRK's input bank on `+VSYS_SOC`: 3 × 10 µF + 2 × 22 µF.

## 3. The PMIC — `U1501`, `TPS6521903RHBR` (`C18716455`)

| Pin | R2 connection | BRK | Note |
| --- | --- | --- | --- |
| `VSYS`, `PVIN_B1_1/_2`, `PVIN_B2`, `PVIN_B3`, `PVIN_LDO34` | `+VSYS_SOC` | 3.3 V | D1 |
| `PVIN_LDO2` | `+1V8_SOC` (BUCK2) | same | |
| `PVIN_LDO1` | **`+1V8_SOC` (BUCK2)** | 3.3 V | **R2 deviation**, §1 |
| `VLDO1` | 2.2 µF to GND, nothing else | → `VDDSHV5` | unloaded |
| `LX_B1_1/_2`, `LX_B2`, `LX_B3` | 0.47 µH each | same | |
| `FB_B1`, `FB_B2`, `FB_B3` | sensed at the SiP's balls | | |
| `EN/PB/VSENSE` | 10 kΩ to `+VSYS_SOC`; optional DNP 0 Ω to an MCU spare pin | 10 kΩ to VIN | First Supply Detection starts the PMIC; a push-button input is 8 s low = OFF |
| `MODE/STBY` | ← `PMIC_LPM_EN0`, 10 kΩ to `+3V3_SOC` | same | low = standby auto-PFM (Deep Sleep) |
| `MODE/RESET` | ← `RESETSTATZ` | same | |
| `VSEL_SD/VSEL_DDR` | 10 kΩ to `+3V3_SOC`; **`MMC1_SDWP` not connected** | ← `MMC1_SDWP` | no UHS-I (D5) |
| `nINT` | → `EXTINTN`, 10 kΩ to `+3V3_SOC` | same | |
| `nRSTOUT` | → `MCU_PORZ`, 10 kΩ to `+1V8A_SOC` | same (to LDO3) | `MCU_PORz` is a 1.8 V, fail-safe input |
| `SDA`, `SCL` | ↔ `I2C0_SDA`/`I2C0_SCL`, 4.7 kΩ to `+3V3_SOC` | same | address **0x30** |
| `GPO2` | → U1502 `ON`, 10 kΩ to `+VSYS_SOC` | same (to VIN) | open-drain |
| `GPO1`, `GPIO` | floating | | disabled in the NVM |
| `VDD1P8` | 2.2 µF | same | |
| `AGND`, thermal pad | GND, with vias | same | |

**What the NVM does on its own** [B]: at power-up, 3.3 V IO (`GPO2`, slot 0) → 1.8 V, LDO1 and DDR
VPP (slot 2) → DDR 1.2 V (slot 3) → core 0.75 V (slot 4) → `VDDR_CORE` 0.85 V (slot 5) →
`MCU_PORz` 11.5 ms later (slot 8). At power-down, `MCU_PORz`, DDR and `VDDR_CORE` go first, the rest
10 ms later. Every rail and `GPO2` **stay on in standby**. This meets `SPRSP58C`'s sequence, the
9.5 ms `MCU_PORz` hold a crystal needs, and the DDR4 VPP ≥ VDD rule — without firmware.

## 4. Load switches

| Ref | Part | In | Out | Control | Notes |
| --- | --- | --- | --- | --- | --- |
| `U1503` | `TPS22965DSGR` (`C122837`) | `+VSYS` (and `VBIAS`) | `+VSYS_SOC` | `ON` = `MCU_EN_SOC`, 100 kΩ pull-down (default off) | 4 A, 16 mΩ; quick output discharge. Worst case ~1.5 A at 3.0 V [I] |
| `U1502` | `TPS22965DSGR` (`C122837`) | `+3V3_DCDC` (and `VBIAS`) | `+3V3_SOC` | `ON` = PMIC `GPO2` | **CT = 1000 pF** (the BRK leaves it empty): ~2–2.5 ms rise — under 18 mV/µs, inside the 10 ms slot 0, inside Spartan-6's 0.2–50 ms ramp if a `VCCO` ever moves here [B] |

**No SD-card switch** (the BRK has a `TPS22918`): with `VDDSHV5` fixed at 3.3 V the card never enters
1.8 V signalling, so the residual-voltage trap it guards against cannot happen. The card is
power-cycled with the SoC [I]. Add the `TPS22918` (`C131941`) back if UHS-I ever returns.

## 5. Clocks

- **`Y1500`, 25 MHz crystal — YXC `SX3B25.000F1010F30` (`C2901684`), 3225, CL 10 pF, ESR 30 Ω,
  ±10 ppm / ±30 ppm** [B, LCSC parametrics]. `SPRSP58C` Table 6-22 allows ±100 ppm without Ethernet,
  CL 6–12 pF, and at ESR 30 Ω a shunt capacitance up to 7 pF [B]. Load capacitors: CL1+PCB =
  CL2+PCB = 2 × CL = 20 pF (the table allows 12–24 pF), so **2 × 18 pF C0G** allowing ~2 pF of
  pin + trace each [I — trim at bring-up]. Alternative: `X322525MMB4SI` (`C70582`), ESR 50 Ω, CL 10 pF.
- **Why a crystal, not the BRK's oscillator:** the oscillator draws 4.5 mA at 1.8 V, ~8 mW, all the
  time [B, Octavo budget], and that matters in the reading state. The crystal's cost — the 9.5 ms
  `MCU_PORz` hold — is already paid by the NVM's 11.5 ms [B].
- **`WKUP_LFOSC0` unused:** `XI` to ground, `XO` open (`SPRSP58C` Fig. 6-25) [B]. The MCU keeps
  time, and R2 wakes the SoC through `SOM_WAKE#`, not its RTC [I].

## 6. Boot straps — `BOOTMODE[15:0]` = `GPMC0_AD0`…`15`

Each pin gets **10 kΩ** to `+3V3_SOC` (the TRM asks for `VDDSHV3`'s rail) or to GND; none may float
(TRM §5.3.1) [B]. They are latched when `MCU_PORz` releases [B].

| Bit | Ball | Field (TRM Tables 5-2…5-5, 5-18, 5-29) | R2 | BRK |
| --- | --- | --- | :---: | :---: |
| 0 | `G28` | PLL config → 25 MHz = `011` | 1 | 1 |
| 1 | `G27` | PLL config | 1 | 1 |
| 2 | `F28` | PLL config | 0 | 0 |
| 3 | `F27` | primary boot = `1000` MMCSD · **`1001` = eMMC boot, §6.1** | 0 | 0 |
| 4 | `E28` | primary boot | 0 | 0 |
| 5 | `E27` | primary boot | 0 | 0 |
| 6 | `D28` | primary boot | 1 | 1 |
| 7 | `D27` | FS/Raw → 0 = filesystem (FAT) | 0 | 0 |
| 8 | `L27` | reserved — **also `DPI_R6`** | 0 | 0 |
| 9 | `L28` | Port → **1 = MMC port 1**, the SD card ("must be set to 1") — **also `DPI_R7`** | 1 | 1 |
| 10 | `K27` | backup boot | 1 | 1 |
| 11 | `K28` | backup boot → `001` = **USB** | **0** | 1 |
| 12 | `J28` | backup boot | 0 | 0 |
| 13 | `J27` | backup config → **0 = DFU** | **0** | 1 |
| 14 | `H28` | reserved | 0 | 0 |
| 15 | `H27` | reserved | 0 | 0 |

**R2 boots from the SD card, and falls back to USB DFU on USB0** — R2's USB-C port — so a board with
no working card can be recovered from a PC (D11). The BRK falls back to UART instead; R2 differs in
exactly bits 11 and 13. **`DPI_R6`/`DPI_R7` carry two of these straps.** The FPGA does not fight them:
R2 leaves `HSWAPEN` unconnected, so its I/O pull-ups are off during configuration (`fpga.md` §5.4),
and once configured those pins are inputs [B]. In normal operation the SoC drives them against 10 kΩ,
about 0.33 mA [I].

### 6.1 The eMMC option — MMC0, fitted on one or two prototypes (D4)

The footprint goes on **every** board; the part is fitted on one or two of each batch of five. The
rest boot from the SD card, and nothing else changes on them.

| | |
| --- | --- |
| Port | **MMC0, 8-bit.** The ROM boots eMMC from no other port, and 8-bit eMMC must use MMC0 [B TRM §5.4.4.1; Octavo `62_EMMC_1/2`]. The balls sit on the SiP's left edge in rings 1–2 — `CLK J1`, `CMD K1`, `DAT0 K2`, `DAT1 L1`, `DAT2 L2`, `DAT3 M1`, `DAT4 M2`, `DAT5 N1`, `DAT6 N2`, `DAT7 P1` [B] — so they escape on `F.Cu` without vias |
| Supply | `VCC` (flash) and `VCCQ` (controller) both from **`+3V3_SOC`**, the rail that already feeds `VDDSHV4`. Octavo `62_EMMC_3` and TI `SPRAD21I` §7.3.2.1.1.1 both ask for the eMMC's IO supply and `VDDSHV4` on one source [B]. **The part is dual-voltage** — LCSC and JLCPCB both list `VCCQ` as *1.7–1.95 V and 2.7–3.6 V*, the datasheet's Table 1 says the same, and its OCR advertises both windows [B]; §9.4's Table 35 lists only the 1.8 V window, because that is what HS200/HS400 need. **Confirm 3.3 V `VCCQ` with the vendor before a production order** |
| Speed | **DDR52 — 52 MHz, 8-bit, ≈100 MB/s** [B, `DEVICE_TYPE` bit 2: "52 MHz DDR — 1.8V **or 3V** I/O — Support"]. HS200/HS400 need 1.8 V signalling on both sides; `VDDSHV4` switches independently of the other rails [B, Octavo power note], so that upgrade costs a 1.8 V rail for `VDDSHV4` + `VCCQ` and a level-matched reset — not worth it for a reader |
| Part | Samsung **`KLM8G1GETF-B041`**, 8 GB, 153-ball FBGA, 11.5 × 13 mm, 0.5 mm pitch — `C499918`, 148 in stock, $24.79 [B, LCSC 2026-09-11]. Any JEDEC 153-ball part fits the same land pattern |
| Footprint | KiCad's stock **`Package_BGA:LFBGA-153_11.5x13mm_Layout14x14_P0.5mm`** — 153 lands of 0.24 mm on a 14 × 14 grid at 0.5 mm, JEDEC MO-276F [B]. Checked against the datasheet: 11.5 × 13 mm body, 0.30 mm balls (0.24 mm is the usual 80 % NSMD land), and every ball [Table 2] names has a land. **Referenced from the stock library, not copied** — the board already places three other stock `Package_BGA` footprints |
| Symbol | **`r2:KLM8G1GETF-B041`** — none exists in KiCad's stock libraries, so `tools/gen_emmc_symbol.py` generates it from the datasheet's [Table 2] (2026-09-12). Three units: **`MEM`** (`CLK`, `CMD`, `Data_Strobe`, `RSTN`, `DAT0`–`7`), **`PWR`** (`VCC` ×4, `VCCQ` ×5, `VDDI`, `VSS` ×11), **`NC`** (the 120 RFU and unused balls, all `no_connect`). `VDDI` is a `power_out` — it drives its own capacitor and must never be tied to a rail. `libraries.md` §2 |
| Reset | **`RST_n` ← `RESETSTATZ` directly**, with a 0 Ω series provision. Octavo `62_EMMC_9`: "Either an AND logic gate with RESETSTATz and IO output (pulled up) or **RESETSTATz alone** can be used to reset eMMC. Make sure that IO voltage level for the device is matched" — here both sides are 3.3 V, so no translator [B]. TI `SPRAD21I` §7.3.2.1.1.3 prefers ANDing a processor GPIO with `RESETSTATz` so software can reset the part too, and TI's own SK EVM drives it from an **IO-expander GPIO** (`GPIO_eMMC_RSTn`, `PROC142A` p. 18) [B]. R2 takes the simple path: nothing else needs to reset the eMMC, and `RESETSTATZ` is push-pull, so it cannot be wire-ANDed. The TRM still requires `ext_csd[162]` `RST_n_ENABLE` = `0x1`, written once from Linux (`mmc rstn enable`) and permanent once set [B] |
| Pulls and termination | Every value from TI `SPRAD21I` §7.3.2.1.1.2, each inside Samsung's Table 36 limits [B]: **47 kΩ pull-ups to `+3V3_SOC` on `CMD` and `DAT0` only**, placed at the eMMC (Samsung allows 4.7–100 kΩ on `CMD`, 10–100 kΩ on `DAT`) · **no pull-ups on `DAT1`–`7`** — the device holds its own 10–150 kΩ internal ones until the bus widens, and an external pull fights them (Octavo `62_EMMC_8` agrees) · **10 kΩ pull-down on `CLK` at the eMMC's clock input**, holding the line low while the SoC's buffers are off (Octavo `62_EMMC_5`) · **10 kΩ pull-down on `Data_Strobe`** with a test point — unused below HS400 (Samsung Table 37: 10–100 kΩ) · **series resistor at the SiP's `CLK` ball: 0 Ω fitted, footprint for 22 Ω** — TI says start at 0 Ω and match the trace, Octavo `62_EMMC_7` says 22 Ω may be needed |
| Decoupling | **2.2 µF + 2 × 100 nF on `VCC`, and the same on `VCCQ`** — Octavo `62_EMMC_6` [B]. **`VDDI`: 100 nF and nothing else** — it is the controller's internal regulator output (the datasheet's block diagram shows a capacitor `CReg` there but **states no value**), and it must never be tied to a rail [B for the role, I for the value] |
| Strap | **`AD3` (`F27`) is the only change:** pulled **down** = SD boot (`1000`), pulled **up** = eMMC boot from the boot partition (`1001`). `1001` carries no configuration bits, so `AD9`/`DPI_R7` and every other strap stay as they are [B]. Lay out both resistors, fit one |
| The first image | a blank eMMC fails primary boot and the ROM falls back to **USB DFU** (D11): a PC sends U-Boot, which writes the eMMC. Or boot the same board from SD with `AD3` down, write the eMMC from Linux, then move the strap [I] |

**What it costs `+3V3_SOC`** [B, datasheet Tables 32–34, the 8 GB row]: **180 mA `VCCQ` + 50 mA `VCC`**
worst case (x8 at HS400, RMS averaged over 100 ms — our DDR52 draw is lower), **120 µA + 40 µA** in
standby at 25 °C, and 120 µA in sleep, where `VCC` may be switched off entirely. So budget ~230 mA of
writing current on top of §10's figures, and nothing that matters while reading.

Two layout constraints: the eMMC is a second 0.5 mm-pitch BGA under the same via rules (§12) — with
its 0.24 mm lands a 0.15/0.25 mm via between the balls keeps 4.3 mil to them, while a 0.2/0.30 mm via
does **not** fit at 3.5 mil [I, geometry] — and **`CHOST` + `CBUS` must stay under 20 pF** per line
(the device itself is 12 pF), so the eMMC sits close to the SiP with short, direct traces [B, Table 36].

## 7. Resets, interrupts, monitors, USB sense

| Signal | R2 | Source |
| --- | --- | --- |
| `MCU_PORZ` | PMIC `nRSTOUT` + 10 kΩ to `+1V8A_SOC`, **wire-ANDed with MCU `PA15`** (was `SOM_RESET#`), open-drain only — it is a 1.8 V net | [B] BRK; [I] the wire-AND |
| `RESETSTATZ` | → PMIC `MODE/RESET` **and → MCU `PC8`** (was `PG_SOM`) as "SoC is running", 3.3 V (`VDDSHV0`). `R408`'s 1 MΩ pull-down stays and reads "off" | [B] BRK, `mcu.md` §5.9 |
| `EXTINTN` | ← PMIC `nINT` | [B] |
| `PMIC_LPM_EN0` | → PMIC `MODE/STBY` | [B] |
| `MCU_RESETZ`, `RESET_REQZ`, `MCU_ERRORN`, `TRSTN`, `EMU0/1`, `TCK/TDI/TMS/TDO` | **no trace** — the internal pulls hold them (checklist `62_CONFIG_1/3/4`, `62_RESET_4/6`) | [B] |
| `PORZ_OUT`, `MCU_RESETSTATZ` | not connected (erratum i2407: never reset other parts with `MCU_RESETSTATz`) | [B] |
| `VMON_VSYS` | `+VSYS_SOC` → **100 kΩ / 16.9 kΩ, 1 %** → trips at ≈ 3.11 V (0.45 V ±3 % threshold); 0.64 V at 4.4 V | [B] threshold; [I] trip point — the owner's to choose |
| `VMON_1P8_SOC`, `VMON_3P3_SOC` | `+1V8_SOC`, `+3V3_SOC` | [B] BRK |
| `USB0_VBUS` | `J200` VBUS → TI's clamp divider: **16.5 kΩ + 3.48 kΩ over 10 kΩ, 1 %, 6.8 V Zener** (`BZX84C6V8`, `C12746`). The BRK's 20 k/10 k is not enough: R2's charger accepts 9–12 V inputs | [B] `SPRSP58C` Fig. 8-4 |
| `USB1_VBUS` | the host port's VBUS, same circuit. The PHYTEC module did this internally; now it is ours | [B] |
| `VPP` | not connected | [B] |

## 8. What carries over from the `PCM-071` design

All 48 signals, by AM62x name, onto the balls in `osd62x-symbol-guide.md` §6. Changes on the way:

- `SOM_RESET#` → the `MCU_PORz` wire-AND (§7). `X_nRESET_IN` existed only on PHYTEC's module.
- `PG_SOM` → `RESETSTATz` (§7). `X_PGOOD` existed only on PHYTEC's module.
- **microSD `J500`:** its supply and its pull-ups (`R500`–`R504`, 47 kΩ) move to `+3V3_SOC`, which is
  now `VDDSHV5`. Add **22 Ω in series with `MMC1_CLK`** at the SiP, as the BRK does (`R33`) [B].
- **USB VBUS sensing** is now on this page (§7).
- **Removed:** `J501`, `J502`, `X500`, and `+5V_DCDC`'s role as the SoM supply — the boost now feeds
  only the EPD HV chain and the USB1 host port (`power.md` §8.1).

## 9. MCU and firmware — replaces `power.md` §5.1

**Pins:** `PA15` (47) → `MCU_PORZ`, open-drain · `PC8` (48) ← `RESETSTATZ` · a spare (`PC4`, `PC5`,
`PA12`, `PB7` or `PB12` — owner's pick) → `MCU_EN_SOC` · `FPGA_PROG#` (33) as today.

**Power-on**
1. `MCU_EN_3V3` → `U302` → `+3V3_DCDC`. Hold `FPGA_PROG#` **low**; keep the UART TX low or Hi-Z.
2. `MCU_EN_SOC` → `U1503` → `+VSYS_SOC`. First Supply Detection starts the PMIC: ~2.3 ms of EEPROM
   load, then the NVM sequence, and `MCU_PORz` releases ~40 ms later [B].
3. Wait for `RESETSTATz` high; time out and report after ~200 ms [I].
4. Release `FPGA_PROG#` — the FPGA configures from the NOR (**D10**).
5. Enable the UART TX and the `SOM_WAKE#`/`SOM_IRQ#` handshake.

**Reading state:** the SoC enters Deep Sleep and drops `PMIC_LPM_EN0`, and the PMIC goes to auto-PFM.
Every rail, **`+3V3_SOC` included**, stays up, so the FPGA and the panel keep running — the retain
model [B NVM; H for the power figure].

**Power-off**
1. Ask the SoC to shut down; its poweroff sends the PMIC an OFF request over I²C [I — **H**].
2. Pull `FPGA_PROG#` **low** and park the UART TX *before* the SoC's rails fall (**D10**).
3. Wait for `RESETSTATz` low, then ≥ 30 ms — the PMIC's two 10 ms power-down slots plus margin [B/I].
4. `MCU_EN_SOC` low; `U1503`'s discharge drains `+VSYS_SOC`.
5. `MCU_EN_3V3` low if nothing else needs it.

**Forced off**, for a hung SoC: pull `MCU_PORz` low, then `MCU_EN_SOC` low — the equivalent of pulling
the battery. Last resort only [I].

**The rule behind D10 and step 2** [B `SPRSP58C`; Octavo]: nothing may drive a SoC pin whose IO rail
is not up. Caster's `SPI_MISO` is driven all the time, and the FPGA's configuration reads the NOR over
the same line, so the FPGA must stay unconfigured (`PROG_B` low, `HSWAPEN` → pins Hi-Z) whenever
`RESETSTATz` is low. The MCU's own lines into the SoC — `MCU_TXD` → `UART0_RXD`, `SOM_WAKE#` →
`MCU_MCAN0_RX` — must be low or Hi-Z then too. **D10 is decided as firmware *plus* the Caster fix.** In `Caster/rtl/spartan6/top.v` the CSR block
drives the pin directly (`.spi_miso(SPI_MISO)`, line 793) while `wire spi_miso;` (line 685) sits
unused. Route it through that wire and tri-state on the chip select, which is active low:

```verilog
    .spi_miso(spi_miso),                          // was .spi_miso(SPI_MISO)
...
assign SPI_MISO = SPI_CS ? 1'bz : spi_miso;       // new
```

**Not applied.** `Caster/` is a submodule, and the change needs an ISE build and a test on the dev
kit before it goes anywhere near a board (plan §9.2 D10).

## 10. Power budget

**PMIC input** (Octavo's rail maxima and nominal figures [B]; efficiency 85 % [B]; LDO losses taken
at the input voltage [I]):

| Case | 0.75 V | 1.2 V | 1.8 V (BUCK2) | LDO3 | LDO4 | ≈ input power | at 3.0 V | at 3.7 V |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Worst | 2710 mA | 800 mA | 150 mA | 155 mA | 60 mA | **~4.5 W** | 1.5 A | 1.2 A |
| Nominal | 913 mA | 147 mA | 10 mA | 72 mA | 10 mA | **~1.3 W** | 0.43 A | 0.35 A |

Running LDO3 and LDO4 from the cell instead of 3.3 V costs up to ~0.2 W more loss at the top of the
charge (4.4 V) in the worst case [I]. Budget the PMIC's thermal pad for ~1 W of dissipation [I].

**`+3V3_SOC` adds to `U302`:** ≤ ~0.3 A of SoC IO (`VDDSHV` groups + `VDDA_3P3_USB`) plus the SD
card [B/I]. **`+5V_DCDC` loses the SoM's 1.0 A.** **The gap:** R2 has no `+3V3_DCDC` budget, so
`U302`'s 2 A cannot yet be shown sufficient — it needs the FPGA's power estimate.

## 11. Parts added

| Ref | Part | LCSC | Stock (checked) |
| --- | --- | --- | --- |
| `U1500` (or `U600`) | `OSD6254-1G-IPM` | — (DigiKey/Mouser) | 100+ (owner, 2026-09-11) |
| `U1501` | `TPS6521903RHBR` | `C18716455` | **6** (2026-09-10) — check DigiKey/Mouser |
| `U1502`, `U1503` | `TPS22965DSGR` | `C122837` | 24 086 |
| `U1504` | `KLM8G1GETF-B041` eMMC 8 GB — **fitted on 1–2 boards** (§6.1) | `C499918` | 148 (2026-09-11) |
| `Y1500` | `SX3B25.000F1010F30` | `C2901684` | 6 605 |
| `D1500`, `D1501` | `BZX84C6V8` | `C12746` | 35 309 |
| `L1500`–`L1502` | `DFE252012F-R47M` 0.47 µH | `C703140` | already on R2 |
| — | resistors and capacitors per §2–§7 | | |

## 12. Layout notes, for Phase 5

- The SiP goes in the SoM corner, next to `J200`, so the USB0 pair stays short (`layout.md` §1.1).
- Put the PMIC beside the SiP's core and DDR supply balls — BUCK1 carries up to 2.7 A. Pour
  `+0V75_SOC` and `+1V2_SOC` as islands on `In2.Cu` (`layout.md` §4.1.1).
- **Vias between the balls** (facts §3.3). With the footprint's 0.20 mm lands a via may be at most
  **0.329 mm at 3.5 mil** spacing, or 0.304 mm at 4 mil. JLCPCB's published 0.15/0.25 mm via fits with
  5 mil to spare; **PCBWay's published 4 mil via ring fits no drill at all** (0.2 mm → 0.40 mm,
  0.15 mm → 0.353 mm). **Keep the 0.20 mm lands:** 0.17 mm is below PCBWay's 8 mil and JLCPCB's 0.2 mm
  BGA-land minimum, so the footprint is not to be shrunk.
- A trace between two balls needs **3.5/3.5 mil**. PCBWay allows that "only … from the BGA chip area
  line to the PAD"; JLCPCB allows it board-wide, and 3 mil in BGA fan-outs.
- **Fine-pitch rules scoped to the SiP's and the eMMC's courtyards** — plan E8 proved a custom rule can
  go below the board's 0.45/0.3 mm via floor — but remember §7 of the plan: rules bind the interactive
  router.
- **What to ask the fab** (D6 — send the same text to both): *"6 layers, 0.8 mm, stack-up 3313, ENIG,
  5 pieces. The board carries a 0.5 mm-pitch 500-ball BGA with 0.20 mm round lands and a 0.5 mm-pitch
  153-ball BGA with 0.24 mm lands. Between the balls we need through vias of **0.20 mm drill /
  0.30 mm pad** (2 mil ring), or **0.15 mm / 0.30 mm**, tented, with local 3.5/3.5 mil trace and
  space and ≤ 1 mil solder-mask expansion on the BGA lands. Can you build it, at which price tier,
  and do you X-ray BGA joints when you assemble?"* Note that a 0.2 mm drill saves nothing at JLCPCB —
  a small pad carries the same surcharge as a 0.15 mm hole.
- **Assembly:** have the fab place and X-ray the SiP and the eMMC. Nothing else can inspect a
  0.5 mm-pitch joint, and R2 already has two other BGAs [I].
- Keep the crystal next to `G1`/`G2` with a ground guard and no traffic underneath.
- Thermal-pad vias under the PMIC. Follow the TPS65219 datasheet's layout section for its three
  switch nodes.

## 13. Open items

| Item | Who |
| --- | --- |
| Confirm LDO1 fed from BUCK2 with `…03`'s bypass setting (§1) | TI E2E / Octavo (plan E10) |
| `+3V3_DCDC` budget (§10) | assistant, once the FPGA estimate exists |
| `TPS6521903RHBR` stock at DigiKey/Mouser | owner |
| **D6:** quote the between-ball vias at PCBWay *and* JLCPCB, with §12's question | owner |
| Which spare MCU pin becomes `MCU_EN_SOC` (§9) | owner |
| **D10:** build and test Caster's `SPI_MISO` tri-state (§9) — ISE, then the dev kit | owner |
| **eMMC (§6.1):** confirm 3.3 V `VCCQ` operation with Samsung or the distributor before a production order — the datasheet's own Table 35 lists only the 1.8 V window | owner |
| Does Octavo's BSP need a board-ID EEPROM? If yes, add a 24C32 on I²C0 (the BRK has `24AA32A`) | Octavo (plan E10) |
| **Hardware tests [H]:** PMIC sequence on a scope; strap latch with the FPGA powered; SD boot and USB-DFU fallback; Deep Sleep power at the battery; that SoC poweroff issues the PMIC OFF request | bring-up |
