# `mcu.kicad_sch` — housekeeping controller — R2 work package 3

Status: **drawn; reviewed once, review-1 fixes applied.** The review answers are §10. Companion to
`battery.md` and `power.md`. Every claim cites a datasheet in `../datasheets/` (with the table or
page), the LCSC catalogue, or a file in this repo. Estimates are marked **(est.)**.

`mcu.kicad_sch` has been saved in Eeschema, so **the sheet — not `gen_mcu.py` — is the source of
truth.** The review-1 fixes were applied surgically by `tools/patch_mcu_review1.py`; the generator
was not re-run.

This sheet holds one part that matters and a handful that support it. Its real content is not the
circuit — it is the **pin assignment**, which is a one-shot decision: peripheral functions on an
STM32 are fixed to particular pins, so a signal put in the wrong place cannot be moved in firmware.
Everything below is checked against `stm32g0b1.pdf` (DS13560 Rev 1) Tables 12–20.

The MCU owns the always-on domain: it turns rails on and off, sequences the EPD high-voltage
supply, sets VCOM, reads the charger and gauge, watches the buttons, and wakes the SoM. It does
**not** touch the FPGA's register bus — see §2.1.

---

## 1. The part

| Ref | Part | LCSC | Stock | Package |
| --- | --- | --- | --- | --- |
| `U20` | `STM32G0B1RCT6` | `C3034735` | 6 029 | LQFP-64 10×10, 0.5 mm |

Cortex-M0+ at 64 MHz, 256 KB flash, 144 KB RAM, **60 GPIO**, 1.7–3.6 V ‡.

Why this one, in order of what actually decided it:

- **Two 12-bit DACs.** R1 drives `VCOM_DAC` and `VGH_DAC` from `DAC_CHANNEL_1`/`_2`
  (`fw/User/power.c:227,238`). The STM32G0B1 has `DAC1_OUT1` on `PA4` and `DAC1_OUT2` on `PA5` ‡
  (Table 12, p.49). Most of the STM32G0 line — `G030`/`G031`/`G041` — has no DAC at all, which
  removes them from consideration outright.
- **60 I/O.** The signal count is 49 (§3). A 48-pin part gives ~44 usable and would need an I/O
  expander for a board whose entire premise is that housekeeping must be cheap and always awake.
- **Stock.** 6 029 units against 389 for `STM32G071RBT6`, the other 64-pin G0 with a DAC — and the
  `G0B1RC` is the *cheaper* of the two at $1.67 vs $1.84 (queried 2026-08-07).
- **KiCad has the exact symbol** (`MCU_ST_STM32G0:STM32G0B1RCTx`) with the right footprint
  (`Package_QFP:LQFP-64_10x10mm_P0.5mm`), so nothing has to be authored.

**Stop 1 mode, RTC running, flash unpowered, 3 V, 25 °C: 3.7 µA typ** ‡ (Table 32) — about
**12 µW**. `NOTES-R2-plan.md` budgets ~6 mW for "STM32G0 in STOP + RTC, charger, gauge"; the MCU's
own share of that is a rounding error, and the budget line is really the charger and gauge.

Supporting parts:

| Ref | Part | LCSC | Role |
| --- | --- | --- | --- |
| `Y20` | `Q13FC13500004` (Epson FC-135) | `C32346` | 32.768 kHz **LSE**, **JLC Basic**, 438 k stock |
| `FB20` | `BLM15AG121SN1D` | `C85812` | 120 Ω @ 100 MHz, **DCR 190 mΩ**, 550 mA; `VDD` → `VREF+` (§5.2) |
| `SW20` | `TS-1187A-B-A-B` | `C318884` | power button, 1.6 N, 100 k cycles, **JLC Basic**, 1.68 M stock |
| `SW21`, `SW22` | `EVQPLHA15` (Panasonic) | `C79172` | page buttons, 1.6 N, 1.5 mm, **500 k cycles** (§5.5) |
| `D20` | `LTST-C191KGKT` | `C125098` | green status LED, 0603 |
| `J20` | 1×5 2.54 mm header, **not fitted** | — | SWD pads (§6) |

`FB20`'s DCR is listed because it is load-bearing, not incidental: Table 21 caps `VREF+` at
`min(VDD + 0.4, 4.0) V`, so a series element there must have almost no DC drop. See §5.2.

## 2. Two decisions that shape this sheet

### 2.1 The SoM drives Caster's register bus, not the MCU

Caster's control/status interface is a **4-wire SPI slave** — `Caster/rtl/csr.v` is headed
"Control/status register over SPI", and `Caster/rtl/spartan6/top.v` exposes `SPI_CS`, `SPI_SCK`,
`SPI_MOSI`, `SPI_MISO`. In R1 the STM32H750 was that master, over the same SPI it used for
slave-serial configuration (`fw/User/fpga.c`). In R2 it is the SoM. The reasons, in order of weight:

1. **The bus carries bulk data, and the data lives on the SoM.** `csr.v` exposes waveform LUT writes
   (`csr_lut_frame`/`csr_lut_addr`/`csr_lut_wr`), OSD bitmap writes (13-bit `csr_osd_addr`), tone
   curves, and per-region op commands. R1 kept all of that in SPIFFS on a `W25Q32` beside the MCU.
   **R2 deletes that flash** — losing it is part of what lets the H750 become a G0. Making the MCU
   the master would mean adding a flash chip back or streaming tables over UART into a part with
   144 KB of RAM.
2. **Op commands are per-page-turn traffic on the latency path.** The SoM renders the page; routing
   its region-update commands `SoM → UART → MCU → SPI → FPGA` adds a hop and a bespoke protocol to
   the one path this project exists to keep short.
3. **It keeps the MCU small enough to stay asleep.** The 3.7 µA figure holds because the MCU does
   rails, battery, buttons and EPD HV, and nothing else.
4. **The reading-state sequence never needs it.** Per `NOTES-R2-plan.md`: the SoM writes hold and
   scan-stop, then sleeps; the MCU wakes it on a button; the SoM re-enables refresh and releases
   hold. The MCU's FPGA signals are `FPGA_PROG#`, `FPGA_DONE` and `FPGA_SUSP` — power-domain
   concerns, which stay here.

The cost, stated plainly: the MCU owns EPD HV power and the SoM owns panel drive, so the two must
stay in step across a UART. That is a handshake at power-up and power-down, not a per-frame
interaction, but it is a protocol somebody has to design. **Decided by the hardware owner,
2026-08-07.**

### 2.2 The power button never touches the MCU's supply domain

`battery.md` §3 requires that `QON` reach both the power button and the MCU. Reading
`bq25890.pdf` shows why the obvious wiring is wrong:

| `QON` property | Value ‡ |
| --- | --- |
| internal pull-up voltage, battery-only | `V(BAT)` |
| internal pull-up voltage, `VBUS` = 5 V | 4.3 V |
| internal pull-up voltage, `VBUS` = 9 V | 5.8 V |
| internal pull-up resistance | 200 kΩ |
| `VIL` max / `VIH` min | 0.4 V / 1.3 V |
| `tSHIPMODE` (low time to exit ship mode) | 1.25–2.25 s |
| `tQON_RST` (low time to force a full system reset) | 12–18 s |

So `CHG_QON#` idles **above** 3.3 V. Three consequences:

- **The switch must reach `QON` galvanically.** In ship mode the BATFET is off, so with no USB
  attached `+VSYS` — and therefore `+3V3_AON`, and therefore the MCU — does not exist. Ship-mode
  exit is the only way back from a fully-off device, and it cannot depend on any powered part.
  `SW20` therefore shorts `CHG_QON#` straight to `GND`, which is exactly TI's intended use and gives
  a guaranteed `VIL`.
- **The MCU only listens.** It has no reason to drive `QON`: ship mode is *entered* over I²C
  (`REG09`), *exited* only by the button, and a system reset is `NVIC_SystemReset()`. `PD6` is
  therefore a plain input behind `R41` (1 kΩ), which is a fault-current limiter and an isolation
  of the pin's capacitance — not a divider. The two sides are separate nets: **`CHG_QON#`** carries
  the charger, `SW20` and `C50`; **`QON_SNS`** carries `R41` and `PD6`. Naming them apart keeps it
  obvious in the netlist that nothing on the MCU side can pull the charger's pin.
- **`PD6` sees up to 4.3 V, and that is legal but conditional.** `PD6` is an `FT` (5 V-tolerant)
  pin ‡ (Table 12, p.53); absolute maximum on `FT` pins is `VDD + 4.0 V` = 7.3 V ‡ (Table 21).
  Input leakage at that level is ≤ 600 nA ‡ (Table 55), which across `QON`'s 200 kΩ pull-up is a
  0.12 V droop — irrelevant against a 1.3 V `VIH`. **But Table 21 note 2 is a firmware
  requirement: above 4 V the internal pull-up/pull-down on that pin must be disabled.** Configure
  `PD6` as input, no pull. It is the one pin on this sheet where a wrong `GPIO_PUPDR` value injects
  current instead of merely misreading.

A 15-second hold on the power button forces a BATFET reset — a hard power cut that bypasses any
clean shutdown. That is a *feature* (the last-resort recovery a sealed device otherwise lacks), but
firmware must complete its own power-down well inside 12 s so the gesture is never reached in normal
use.

## 3. Pin assignment

`STM32G0B1RCT6`, LQFP-64. Pin numbers from `stm32g0b1.pdf` Table 12, column **LQFP64 - GP**;
alternate functions from Tables 13–20; ADC and DAC channels from Table 12's "Additional functions".

### 3.1 Left side of the symbol — power tree, charger, buttons

| Pin | Port | Net | Function | Source |
| --- | --- | --- | --- | --- |
| 7 | `VREF+` | `+3V3_VREF` | ADC reference | §5.2 |
| 10 | `PF0` | `MCU_EN_5V` | GPIO out | |
| 11 | `PF1` | `MCU_EN_3V3` | GPIO out | |
| 12 | `PF2-NRST` | `MCU_NRST` | reset | Table 12 p.48 |
| 13 | `PC0` | `MCU_EN_FPGA_CORE` | GPIO out | |
| 14 | `PC1` | `MCU_EN_DDR` | GPIO out | |
| 15 | `PC2` | `LED_STAT#` | GPIO out, sinks `D20` | |
| 16 | `PC3` | — | spare | |
| 25 | `PC4` | — | spare, `ADC_IN17` | |
| 26 | `PC5` | — | spare, `ADC_IN18` | |
| 38 | `PC6` | — | spare | |
| 39 | `PC7` | `KEY_PREV#` | GPIO in, **EXTI7** | |
| 40 | `PD8` | `KEY_NEXT#` | GPIO in, **EXTI8** | |
| 41 | `PD9` | — | spare | |
| 48 | `PC8` | — | spare | |
| 49 | `PC9` | — | spare | |
| 50 | `PD0` | `CHG_INT#` | GPIO in, **EXTI0** | |
| 51 | `PD1` | `VBUS_DET` | GPIO in, **EXTI1** | |
| 52 | `PD2` | `CHG_PG#` | GPIO in, **EXTI2** | |
| 53 | `PD3` | `GAUGE_ALRT#` | GPIO in, **EXTI3** | |
| 54 | `PD4` | `CHG_STAT#` | GPIO in, polled | |
| 55 | `PD5` | `CHG_CE#` | GPIO out | |
| 56 | `PD6` | `QON_SNS` | GPIO in, **EXTI6**, no pull | §2.2 |
| 64 | `PC10` | — | spare | |
| 1 | `PC11` | `PG_1V35` | GPIO in | |
| 2 | `PC12` | `PG_1V2` | GPIO in | |
| 3 | `PC13` | `PG_3V3` | GPIO in | note below |
| 4 | `PC14` | `OSC32_IN` | LSE | Table 12 p.47 |
| 5 | `PC15` | `OSC32_OUT` | LSE | Table 12 p.47 |

`PC13`, `PC14` and `PC15` are supplied through the `VBAT` power switch, which sinks at most 3 mA;
the datasheet forbids using them as current sources and caps them at 2 MHz with 30 pF ‡ (Table 12
note 1, p.55). All three are inputs or oscillator pins here, so the restriction is satisfied — but
it is the reason `LED_STAT#` is on `PC2` and not on the otherwise-convenient `PC13`.

### 3.2 Right side of the symbol — analog, EPD, FPGA, SoM, frontlight

| Pin | Port | Net | Function | Source |
| --- | --- | --- | --- | --- |
| 17 | `PA0` | `VP_MEA` | `ADC_IN0` | Table 12 p.48 |
| 18 | `PA1` | `VN_MEA` | `ADC_IN1` | |
| 19 | `PA2` | `VGH_MEA` | `ADC_IN2` | |
| 20 | `PA3` | `VGL_MEA` | `ADC_IN3` | |
| 21 | `PA4` | `VCOM_DAC` | **`DAC1_OUT1`** | Table 12 p.49 |
| 22 | `PA5` | `VGH_DAC` | **`DAC1_OUT2`** | Table 12 p.49 |
| 23 | `PA6` | `VCOM_MEA` | `ADC_IN6` | |
| 24 | `PA7` | `VBUS_MEA` | `ADC_IN7` | |
| 36 | `PA8` | `SOM_WAKE#` | GPIO out, open-drain | §4 |
| 37 | `PA9` | `MCU_TXD` | `USART1_TX` (AF1) | Table 13 |
| 42 | `PA10` | `MCU_RXD` | `USART1_RX` (AF1) | Table 13 |
| 43 | `PA11` | — | spare (`USB_DM` capable) | |
| 44 | `PA12` | — | spare (`USB_DP` capable) | |
| 45 | `PA13` | `MCU_SWDIO` | `SWDIO` (AF0) | Table 13 |
| 46 | `PA14` | `MCU_SWCLK` | `SWCLK` (AF0), = `BOOT0` | Table 12 p.53 |
| 47 | `PA15` | `SOM_RESET#` | GPIO out, open-drain | §4 |
| 27 | `PB0` | `EPD_PWR_EN_MCU` | GPIO out, via `R45` 1 k | `epd-port.md` §2 |
| 28 | `PB1` | `EPD_POS_EN` | GPIO out | |
| 29 | `PB2` | `VCOM_EN` | GPIO out | |
| 57 | `PB3` | `CHG_OTG` | GPIO out | |
| 58 | `PB4` | `SOM_IRQ#` | GPIO out, open-drain | §4 |
| 59 | `PB5` | `FL_EN` | GPIO out | |
| 60 | `PB6` | `FL_PWM1` | `TIM4_CH1` (AF9) | Table 16 |
| 61 | `PB7` | `FL_PWM2` | `TIM4_CH2` (AF9) | Table 16 |
| 62 | `PB8` | `SCL_AON` | `I2C1_SCL` (AF6) | Table 15 |
| 63 | `PB9` | `SDA_AON` | `I2C1_SDA` (AF6) | Table 15 |
| 30 | `PB10` | `VCOM_MEA_EN` | GPIO out | |
| 31 | `PB11` | `EPD_THROT` | GPIO out | |
| 32 | `PB12` | — | spare, `ADC_IN16` | |
| 33 | `PB13` | `FPGA_PROG#` | GPIO out, open-drain | §4 |
| 34 | `PB14` | `FPGA_DONE` | GPIO in | |
| 35 | `PB15` | `FPGA_SUSP` | GPIO out | §4 |

**49 signals, 11 spares** (`PC3`, `PC4`, `PC5`, `PC6`, `PC8`, `PC9`, `PC10`, `PD9`, `PB12`, `PA11`,
`PA12`), of which four are ADC-capable. Every spare carries a no-connect flag so ERC stays honest;
any of them can be claimed later by deleting the flag.

`FL_PWM1` and `FL_PWM2` are deliberately two channels of the **same** timer, so warm and cool
frontlight strings share a period and cannot beat against each other. Whether the frontlight is
one channel or two is a WP6 decision; the second pin costs nothing to reserve and cannot be added
later.

### 3.3 The EXTI constraint, and why the assignment looks the way it does

On STM32G0 an EXTI line is selected by **pin number**, not by port: `EXTI6` can be sourced from
`PA6` *or* `PB6` *or* `PC6` *or* `PD6`, never two at once. Every input that has to raise an
interrupt therefore needs a distinct pin index. That is the single hardest constraint on this
sheet, and it is invisible in a pin-count check.

| Line | Pin | Net |
| --- | --- | --- |
| `EXTI0` | `PD0` | `CHG_INT#` |
| `EXTI1` | `PD1` | `VBUS_DET` |
| `EXTI2` | `PD2` | `CHG_PG#` |
| `EXTI3` | `PD3` | `GAUGE_ALRT#` |
| `EXTI6` | `PD6` | `QON_SNS` — power button, wake |
| `EXTI7` | `PC7` | `KEY_PREV#` — wake |
| `EXTI8` | `PD8` | `KEY_NEXT#` — wake |
| `EXTI14` | `PB14` | `FPGA_DONE`, if ever needed as an interrupt |

No other pin at those indices is an input: `PA0`–`PA3` and `PA6`/`PA7` are analog, `PB0`–`PB3`,
`PB6`–`PB8`, `PF0`, `PC2`, `PC3` and `PA8` are outputs. The three wake sources are all in this set,
which is what lets the MCU sit in Stop with the buttons armed.

## 4. Cross-domain drive rules

The MCU is the only part on the board that is always powered. Every one of its outputs that lands
on a rail the MCU itself controls is therefore, at some point, driving into an unpowered die. This
is the exact failure class R1 fell into from the other direction, so it is stated as a rule rather
than left to be discovered:

| Net | Goes to | Rule |
| --- | --- | --- |
| `SOM_WAKE#`, `SOM_IRQ#`, `SOM_RESET#` | SoM I/O, `+5V_DCDC` domain | **open-drain**, pull-ups on `som.kicad_sch` referenced to the SoM's own rail |
| `FPGA_PROG#` | Spartan-6, `+3V3_DCDC` | **open-drain**, pull-up on `fpga_config.kicad_sch` |
| `FPGA_SUSP` | Spartan-6, `+3V3_DCDC` | push-pull, but **firmware must not drive it before `PG_3V3`**; a pull-down on `fpga_config.kicad_sch` holds it defined meanwhile (WP5) |
| `FPGA_DONE` | Spartan-6 | input; reads low while the FPGA is unpowered, which is the correct meaning |
| `MCU_TXD` | SoM UART RX | push-pull. **Firmware must reconfigure it to input/analog before cutting `+5V_DCDC`** |
| `SDA_AON`, `SCL_AON` | charger, gauge, INA3221s | open-drain by construction; see §5.3 |
| `EPD_*_EN`, `VCOM_*` | `epd_power.kicad_sch` | drive into parts fed from `+5V`; sequencing is WP4's |

`MCU_TXD` is the one that will bite: a UART TX idles **high**, so leaving it configured while the
SoM is off pushes 3.3 V through the SoM's input protection into a dead rail. It is a firmware rule
because making it open-drain would need a pull-up on the SoM's rail, which is exactly the rail that
is gone.

## 5. Supporting circuit

### 5.1 Supply and decoupling

Straight from ST's own scheme ‡ (Figure 15, p.65):

| Node | Parts | Source |
| --- | --- | --- |
| `VDD`/`VDDA` (pin 8) **and `VBAT` (pin 6)** | `C40` 4.7 µF + `C41` 100 nF | Figure 15 — "1 × 100 nF + 1 × 4.7 µF" |
| `VREF+` (pin 7) | `FB20` from `VDD`, then `C43` 1 µF + `C44` 100 nF | Figure 15 — "100 nF + 1 µF" |
| `NRST` (pin 12) | `C45` 100 nF | Table 59 |

Pin numbers are the **LQFP64 - GP** column of Table 12: `VBAT` 6, `VREF+` 7, `VDD/VDDA` 8,
`VSS/VSSA` 9. All four are real pins on this package — worth stating because §3.7.1 warns that on
packages *without* them, `VBAT` is internally bonded to `VDD/VDDA` and `VREF+` to `VDD`.

**`VBAT` and `VDD` are one net.** There is no coin cell, so pin 6 is strapped to `+3V3_AON`
alongside pin 8, two pins away, and the pair above is the whole of the decoupling. Figure 15 shows
no capacitor on `VBAT` at all, and a third one there would decouple a node already decoupled — see
§10.1, which is why `C42` was deleted in review 1.

STM32G0 merges `VDDA` into the `VDD` pin ‡ (§3.7.1: "`VDDA` voltage level is identical to `VDD`
voltage as it is provided externally through `VDD/VDDA` pin"), so there is no separate analog supply
to filter — `VREF+` is the only analog node that can be isolated, and `FB20` is what isolates it.

### 5.2 `VREF+` is tied to `VDD`, and the internal buffer stays off

The `G0B1` has a `VREFBUF` that can drive `VREF+` to a trimmed 2.048 V or 2.500 V ‡ (Table 66),
which would make ADC readings independent of the `+3V3_AON` LDO's tolerance. **It is not used**, for
one concrete reason: R1's high-voltage measurement dividers are 1 MΩ/100 kΩ, an 11:1 ratio, and
`VGH` at its ~26.9 V maximum (`fw/User/power.c:287`) arrives at **2.45 V** — which clears a 3.3 V
reference comfortably and does not clear a 2.5 V one at all. WP4 ports `power_mon` from R1 as a
straight copy; changing the reference would force every divider to be rescaled to buy accuracy that
the dividers' own 1 % resistors do not deliver anyway.

So `VREF+` = `VDD` through `FB20`. **`VREFBUF` must stay disabled in firmware** — enabling it would
drive the buffer's output into the rail through the ferrite.

**`FB20` is not a datasheet requirement, and the review was right to ask.** Figure 15 shows `VREF+`
fed from the same supply with 100 nF + 1 µF and *no* series element. The bead is an engineering
addition, carried over from ST's practice on families where `VDDA` is its own pin; on G0 it is not,
so `VREF+` is the only place left where that idea can be applied. It stays for two reasons —
asymmetry (a bead can be replaced by a 0 Ω jumper after fabrication, but a filtered node cannot be
created after fabrication) and cost ($0.013). The full argument is §10.2.

What makes it *safe* is the part's DC resistance, and that is worth stating as a constraint rather
than a preference. Table 21 gives `VREF+` an absolute maximum of `min(VDD + 0.4, 4.0) V`, so `VREF+`
is only ever allowed 400 mV above `VDD`. `BLM15AG121SN1D` is **190 mΩ**, which at even 1 mA of
reference current is 0.19 mV — nothing. A plain resistor in the same position, or a bead chosen for
impedance without checking DCR, would eat into a 400 mV budget. On power-down the 1.1 µF on `VREF+`
discharges back through those 190 mΩ with a ~0.2 µs time constant, which is why the capacitors on
the quiet side cannot strand charge above `VDD` either. **Any future substitution for `FB20` must be
checked for DCR, not just for impedance at 100 MHz.**

### 5.3 One I²C bus, not two

`SDA_AON`/`SCL_AON` carry the charger (`BQ25892`, `battery.kicad_sch`), the gauge (`MAX17048`, same
sheet) and — proposed here, to be settled in WP4 — all three `INA3221`s from `power_mon`.

The reason it is one bus and not two is a leakage argument, not a pin-count one. If the `INA3221`s
were powered from a switched rail, their I²C pins would clamp the always-on bus through their ESD
diodes whenever that rail was down, which is most of the device's life. Powering them from
`+3V3_AON` instead removes the clamp entirely, and the `INA3221`'s own power-down mode costs about
2 µA each **(est., to confirm against its datasheet in WP4)** — roughly 6 µA for all three, against
the ~350 µA each they draw when converting. Their bus-voltage inputs sit on rails that come and go,
which is fine: the common-mode input range is independent of `VS`.

Pull-ups are the 10 kΩ pair already on `battery.kicad_sch` ‡ (`battery.md` §4). None are added here.

### 5.4 Clock

**LSE only.** `Y20` is a 32.768 kHz crystal for the RTC, which has to keep time across standby. The
system clock is the internal `HSI16` with the PLL — ±1 % ‡, which is inside the tolerance of every
peripheral on this sheet (I²C is a clocked bus; the UART to the SoM is well under the 2 % that
asynchronous framing needs). **No HSE**, so `PF0`/`PF1` are free for `MCU_EN_5V`/`MCU_EN_3V3`.

**`Y20` is the LSE, and the 8 MHz in the datasheet belongs to the HSE.** The two are different
oscillators on different pins, and the review round mixed them up — understandably, because the
datasheet's worked example is the HSE one:

| | HSE — *not fitted* | LSE — `Y20` |
| --- | --- | --- |
| frequency | 4 / **8** / 48 MHz min/typ/max ‡ (Table 42, p.83) | 32.768 kHz ‡ (Table 43, p.85) |
| pins | `OSC_IN`/`OSC_OUT` = `PF0`/`PF1` | `OSC32_IN`/`OSC32_OUT` = `PC14`/`PC15`, pins 4/5 |
| figure | Figure 20, "Typical application with an **8 MHz** crystal" (p.84) | Figure 21, "Typical application with a 32.768 kHz crystal" (p.85) |
| here | absent — `PF0`/`PF1` carry `MCU_EN_5V`/`MCU_EN_3V3` | fitted, for the RTC |

So the 8 MHz is `fOSC_IN` **typ** for a part range of 4–48 MHz, and the caption of the HSE's
application figure. Nothing in the datasheet asks for an 8 MHz resonator; it is simply the value ST
draws when it needs to draw something. See §10.3.

Two LSE numbers that matter downstream: `IDD(LSE)` is 250–630 nA depending on the `LSEDRV[1:0]`
drive setting ‡ (Table 43) — the low setting is a fifth of the MCU's own 3.7 µA Stop current, so use
the lowest drive the crystal will start on. And `tSU(LSE)` is **2 s** ‡, measured from software
enable to stable oscillation. Firmware must not gate anything behind "RTC ready" on a fast path.

Load capacitors are **`C46`/`C47`** (`C48`/`C49` are the button debounce caps — §5.5).
`C_L = C1·C2/(C1+C2) + C_stray`; for a 12.5 pF crystal with ~3 pF of stray,
`C1 = C2 = 2 × (12.5 − 3) = 19 pF` → **18 pF (E12)**, which is also what R1 fits on its 32.768 kHz
(`pcb/mainboard/mcu.kicad_sch`, `C13`/`C28`). **`Y20`'s load capacitance is not verified** — the
Epson FC-135 ships in 12.5 pF, 9 pF and 7 pF variants and the LCSC listing does not say which
`C32346` is. Table 43 names **AN2867** ("Oscillator design guide for ST microcontrollers") as the
selection reference, and also gives `Gmcritmax` per drive setting, which is the number AN2867's
margin check needs. §9.

### 5.5 Buttons

Three switches, all to `GND`. **Two of them are navigation; the third is power.** There is no
"enter" button on this sheet and never was — enter is the touchscreen's job, so the user-facing
navigation count is already the two the hardware owner wants (§10.5):

| Ref | Role | Net | Pull-up | Debounce | Part |
| --- | --- | --- | --- | --- | --- |
| `SW20` | **power** | `CHG_QON#` → `R41` → `QON_SNS` | internal to the charger, 200 kΩ ‡ | `C50` 100 nF → ~20 ms with that pull-up | `TS-1187A-B-A-B` |
| `SW21` | page back | `KEY_PREV#` | `R42` 100 kΩ to `+3V3_AON` | `C48` 100 nF → ~10 ms | `EVQPLHA15` |
| `SW22` | page forward | `KEY_NEXT#` | `R43` 100 kΩ to `+3V3_AON` | `C49` 100 nF → ~10 ms | `EVQPLHA15` |

**Which switch wakes the device depends on which "off" it is in, and the two are not the same
state.** This is the whole reason `CHG_QON#` gets singled out in §2.2:

| State | `+3V3_AON` | `SW21`/`SW22` | `SW20` |
| --- | --- | --- | --- |
| **standby** — the everyday off: MCU in Stop 1, rails gated | alive (3.7 µA) | **wake via `EXTI7`/`EXTI8`** | wakes via `EXTI6` |
| **ship mode** — storage: `BATFET` off, `+VSYS` = 0 | **gone** | dead — `R42`/`R43` pull to a rail that does not exist | **the only switch that works** |

`SW20` works with the whole board unpowered because its pull-up is *inside the charger*, referenced
to `V(BAT)` and fed from the cell directly, and the switch is a galvanic short to ground. Per
`bq25890.pdf` §9.2.10.2 there are exactly four ways out of ship mode, and two of them — clearing
`BATFET_DIS` and setting `REG_RST` — need a live I²C host, which by definition does not exist in
ship mode. That leaves **plug in a charger** or **hold `SW20`**. Deleting `SW20` would therefore make
a cable the only way to revive a stored device, and would also give up the `tQON_RST` 12–18 s
`BATFET` reset, which §9.2.10.3 notes only works while no input source is plugged in. **The hardware
owner chose to keep `SW20` (2026-08-12);** whether it presents as an edge button or a recessed
pinhole is an enclosure decision, not an electrical one.

**Why `SW21`/`SW22` are not the same part as `SW20`.** They are the most-actuated components on the
board. `TS-1187A` is rated 100 000 cycles; at a plausible ~200 page turns a day that is about 1.4
years. `EVQPLHA15` has the same 1.6 N force and 1.5 mm travel — so the same feel — and is rated
**500 000** cycles, about seven years on the same assumption, for $0.135 against $0.020. `SW20` stays
a `TS-1187A`: it is pressed rarely, and it is a JLC Basic part. Force and travel are what a datasheet
can tell us; **whether the click is *satisfying* through a plastic key in a sealed case is dominated
by keycap coupling and preload and cannot be read off any spec** — it needs samples on the bench
(§9). If a firmer action is wanted later, the `TS-1187A` land pattern also takes 2.6 N variants
(`-C-C-B`, `-C-E-B`, `-C-F-B`) as a pure BOM change.

100 kΩ rather than 10 kΩ: a pressed button is a static short to ground, and at 10 kΩ holding one
would cost 330 µA. Nobody holds a page-turn button for hours, but the same reasoning that set the
`PG` pull-ups in `power.md` §4 applies, and 100 kΩ against a CMOS input with ≤ ±70 nA of leakage ‡
(Table 55) still gives a solid high.

`R41` (1 kΩ) sits between `CHG_QON#` and `PD6` — see §2.2. `C50` also slows the edge the switch
sees, which is harmless: exiting ship mode needs the line held low for 1.25 s ‡.

**The buttons are on the MCU, not on SoM GPIO.** `Project_description.md` prefers buttons that
arrive as `gpio-keys` events, and putting them on the SoM would give that for free — but only if
the module brings out WKUP-domain GPIO that can wake it from Deep Sleep, and that is unknown until
PHYTEC answers. MCU pins are known to exist today. The cost is a small serial key-event protocol
on the UART; the alternative risks a respin.

### 5.6 `BOOT0` and SWD

`PA14` is `SWCLK` **and** `BOOT0` ‡ (Table 12, p.53). On reset the pin already has an internal
pull-down and is configured as a debug function ‡ (note 4), and the factory `nBOOT_SEL` option bit
makes boot selection come from the option bytes rather than the pin. `R40` (10 kΩ to `GND`) is
fitted anyway: it is invisible to a push-pull debugger and it guarantees "boot from main flash"
even if `nBOOT_SEL` is ever cleared by accident. Recovery is then via SWD, which is always present.

`J20` is a 1×5 2.54 mm header **with pads only, not fitted** — `+3V3_AON`, `SWCLK`, `GND`, `SWDIO`,
`NRST`, matching the `CN4` order on ST Nucleo boards so a stock ST-LINK cable fits. Leaving it
unpopulated keeps the device thin; a header can be soldered in for bring-up and removed.

### 5.7 How the MCU gets programmed

Datasheet §3.5 (p.16) is unusually explicit for once, and it decides this section. The boot loader
lives in System memory and reprogrammes flash over one of:

- **USART on `PA9`/`PA10`**, `PC10`/`PC11`, or `PA2`/`PA3`
- I²C on `PB6`/`PB7` or `PB10`/`PB11`
- SPI on `PA4`/`PA5`/`PA6`/`PA7` or `PB12`/`PB13`/`PB14`/`PB15`
- **USB on `PA11`/`PA12`**

Two of those land on nets this sheet already has. `MCU_TXD`/`MCU_RXD` **are** `PA9`/`PA10` (§3.2) —
the bootloader's first USART option, with the SoM on the other end. And `PA11`/`PA12` are two of the
eleven spares (§3.2), which are exactly the USB bootloader pins; the G0B1's USB is also crystal-less
capable ‡ (§3.24: `HSI48` "in automatic trimming mode", synchronised from the USB `SOF`), so the
absence of an HSE does not rule USB out.

| Path | Works today? | What it needs |
| --- | --- | --- |
| **SWD via `J20`** | **yes** — this is the bring-up and recovery path | ST-LINK, a header soldered on, the case open |
| Factory USART bootloader from the SoM | **no** | `BOOT0` high at reset **and** a reset the SoM can drive — it has neither |
| Firmware-hosted updater over the same UART | not written | firmware only, no hardware change |
| USB DFU | **no** | `PA11`/`PA12` routed somewhere; the USB-C data pair is committed to the SoM |

The gap is worth naming plainly, because it is cheap now and impossible later. `PA14` is `BOOT0` but
carries `R40`, a 10 kΩ pull-**down**, and `MCU_NRST` goes only to `J20` — so **the SoM cannot reset
the MCU or force it into the factory bootloader.** A firmware-hosted updater over the existing UART
closes the *update* case with no hardware change, but not the *recovery* case: a bad flash then needs
the case opened. Giving the SoM two GPIO — one to `MCU_NRST`, one to `BOOT0` through a series
resistor so it does not fight `R40` or a connected debugger — would make the MCU reflashable and
un-brickable from the SoM. That is a WP8 decision and it is in §9. Note also that using `BOOT0` at
all means clearing `nBOOT_SEL`: §3.5 says the boot pin "can be enabled through the boot selector
option bit", and §5.6 keeps it at the factory default, where the pin is ignored.

## 6. Footprints

All stock KiCad 10, all verified present in this KiCad install:

| Ref | Footprint |
| --- | --- |
| `U20` | `Package_QFP:LQFP-64_10x10mm_P0.5mm` |
| `Y20` | `Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm` |
| `FB20` | `Inductor_SMD:L_0402_1005Metric` |
| `D20` | `LED_SMD:LED_0603_1608Metric` |
| `SW20` | `Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A` |
| `SW21`, `SW22` | `Button_Switch_SMD:SW_SPST_Panasonic_EVQPL_3PL_5PL_PT_A15` |
| `J20` | `Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical` |
| `R4x`, `C4x` | `Resistor_SMD:R_0402_1005Metric`, `Capacitor_SMD:C_0402_1005Metric` |

Nothing has to be authored for this sheet — unlike `power.md` §7, which still owes three.
`TS-1187A` was chosen partly *because* KiCad carries its land pattern and JLCPCB lists it as a
Basic part; the 4.5 × 4.5 mm switches with more stock have no KiCad footprint.

`SW_SPST_Panasonic_EVQPL_3PL_5PL_PT_A15` was checked pad by pad before being assigned: pads `1` and
`2` are the two SPST terminals (two pads each, at x = ∓1.85, y = ±2.2), and the two pads numbered
`0` are unconnected mechanical anchors, which is what lets a 2-pin `Switch:SW_Push` symbol drive it.
The pad envelope is 5.5 × 5.4 mm, consistent with the 4.9 × 4.9 mm J-lead body LCSC lists for
`EVQPLHA15`. **This is a dimensional check, not a check against the vendor drawing** — the footprint
cites Panasonic `ATK0000CE3.pdf`, which is not in `../datasheets/`. Confirm against it before Stage D
(§9).

## 7. What this sheet costs

| | |
| --- | --- |
| `U20` in Stop 1, RTC on, 3 V ‡ | 3.7 µA |
| `R42`, `R43` button pull-ups, buttons released | 0 |
| `R41` / `PD6` leakage from `CHG_QON#` ‡ | ≤ 0.6 µA |
| `D20` status LED, off | 0 |
| **total, standby** | **~4.3 µA ≈ 14 µW** |

Against `power.md` §8's ~24 µA of converter overhead and the ~10 mW standby target, the controller
that owns the whole scheme costs about 0.15 % of it. That is the intended shape: the always-on
domain has to be nearly free, or there is no point gating anything else.

Awake at 64 MHz the part draws single-digit mA, but it has no reason to be awake — its work is
interrupt-driven and measured in microseconds per event.

## 8. Sheet interface

41 hierarchical labels, grouped by destination:

| Group | Nets |
| --- | --- |
| `power` | `MCU_EN_5V`, `MCU_EN_3V3`, `MCU_EN_FPGA_CORE`, `MCU_EN_DDR`, `PG_3V3`, `PG_1V2`, `PG_1V35` |
| `battery` (+ `power_mon` for I²C) | `SDA_AON`, `SCL_AON`, `CHG_INT#`, `CHG_PG#`, `CHG_STAT#`, `CHG_CE#`, `CHG_OTG`, `CHG_QON#`, `GAUGE_ALRT#`, `VBUS_DET` |
| `epd_power`, `power_mon` | `EPD_PWR_EN`, `EPD_POS_EN`, `VCOM_EN`, `VCOM_MEA_EN`, `EPD_THROT`, `VCOM_DAC`, `VGH_DAC`, `VCOM_MEA`, `VP_MEA`, `VN_MEA`, `VGH_MEA`, `VGL_MEA`, `VBUS_MEA` |
| `fpga_config`, `som`, `frontlight` | `FPGA_PROG#`, `FPGA_DONE`, `FPGA_SUSP`, `SOM_WAKE#`, `SOM_IRQ#`, `SOM_RESET#`, `MCU_TXD`, `MCU_RXD`, `FL_EN`, `FL_PWM1`, `FL_PWM2` |

`+3V3_AON` and `GND` are power symbols, which are global in KiCad and need no hierarchical label.
`KEY_PREV#`, `KEY_NEXT#`, `QON_SNS`, `MCU_SWDIO`, `MCU_SWCLK`, `MCU_NRST`, `LED_STAT#`,
`EPD_PWR_EN_MCU`, `+3V3_VREF`, `OSC32_IN` and `OSC32_OUT` stay on this sheet.

**`MCU_TXD` and `MCU_RXD` are named from the MCU's point of view.** On `som.kicad_sch`, `MCU_TXD`
lands on the SoM's UART **RX** and `MCU_RXD` on its **TX**. Written down because it is the classic
error and the sheets are drawn months apart.

## 9. Open

- **`Y20`'s load capacitance is unverified.** Epson FC-135 exists in 12.5 pF, 9 pF and 7 pF;
  **`C46` and `C47`** are 18 pF on the assumption of 12.5 pF and ~3 pF stray (§5.4). Confirm from the
  Epson datasheet before layout, and check the crystal's drive-level rating against the G0's LSE
  drive setting — an overdriven watch crystal ages badly. Table 43 gives `Gmcritmax` per
  `LSEDRV[1:0]` setting, which is the figure **AN2867**'s margin check consumes; neither the Epson
  datasheet nor AN2867 is in `../datasheets/`. *(Corrected in review 1: this item previously named
  `C48`/`C49`, which are the button debounce capacitors.)*
- **The page buttons' click quality is untested, and no datasheet settles it.** `EVQPLHA15` is
  specified at 1.6 N and 1.5 mm travel (§5.5), but feel through a keycap in a sealed case depends on
  coupling and preload. Order samples — including the 2.6 N `TS-1187A` variants, which share the
  `SW20` land pattern — and decide on the bench. **Needs a hardware test; cannot be settled from
  here.**
- **`SW21`/`SW22`'s footprint is checked dimensionally, not against the vendor drawing.** Panasonic
  `ATK0000CE3.pdf` is not in `../datasheets/`; §6 records what *was* checked.
- **The MCU has no field-update or brick-recovery path (§5.7).** SWD via `J20` is the only way in
  today, and it needs the case open. The factory USART bootloader is already on the right pins
  (`PA9`/`PA10`), so the missing pieces are only a SoM-drivable `MCU_NRST` and `BOOT0`. Two GPIO,
  free now, impossible after fabrication. **WP8, and it should be decided with the SoM's pin budget
  rather than after it.**
- ~~**`INA3221` supply and shutdown current**~~ — **confirmed in WP4**: 0.5 µA typ / 2 µA max in
  power-down ‡ (`ina3221.pdf`). All three are on `+3V3_AON` in `power_mon.kicad_sch`, ~1.5 µA typ
  total, and §5.3's single-bus argument holds.
- **`VBUS_MEA` may be redundant.** The `BQ25892` has its own ADC reporting `VBUS`, `VBAT`, `SYS` and
  `TS` over I²C ‡, which R1 had no equivalent of. The divider is kept as an independent cross-check
  and costs one pin; WP4 may delete it, and `PA7` becomes a twelfth spare.
- ~~**Negative-rail measurement.**~~ **Answered in WP4** (`epd-port.md` §4.2): R1 divides between
  the negative rail and `+3V3_DCDC` rather than to ground. Carried over unchanged. One consequence
  for firmware: `VREF+` is `+3V3_AON` here but the divider references `+3V3_DCDC`, so `VN_MEA` and
  `VGL_MEA` can only be interpreted together with the `+3V3` bus voltage read from `U21` ch3.
- **`SOM_*` handshake.** Three signals are reserved (`WAKE#`, `IRQ#`, `RESET#`) plus the UART. What
  the SoM actually needs — and whether `SOM_RESET#` is even accessible on `PCL-071` — is WP8, and
  waits on PHYTEC.
- **Spare-pin access.** Eleven spares are no-connected in the schematic. Whether any get test pads
  is a layout call; on a board with a soldered-down module and no second chance, at least a few
  probably should.
- **`U1.12` (`QON`) trips `pin_not_driven`, and no future sheet will fix it.** WP1 left this error
  open "waiting on the MCU sheet", but §2.2 settles that the MCU deliberately never drives `QON` —
  the net is driven by an internal pull-up and a switch to ground, neither of which ERC models as a
  driver. Two honest resolutions: retype the `QON` pin in `r2.kicad_sym` from `input` to `passive`
  (it is a pin with its own pull-up, so `passive` is arguably the more accurate description), or
  add an ERC exclusion. **The symbol is not changed here** because `battery.kicad_sch` embeds a
  copy of it and is out for review; changing one without the other produces `lib_symbol_issues`.
- **The root sheet is not wired.** `r2.kicad_sch` carries the sheet symbols and their pins but no
  wires between them, so `MCU_EN_5V` on this sheet and `MCU_EN_5V` on `power.kicad_sch` are still
  two nets (`/mcu/...` and `/power/...` in the netlist). That is what produces most of the ERC
  noise above, and it is why §13's cross-sheet name check had to be done by script. Wiring it is a
  small, mechanical job — a labelled stub on each sheet pin — but it should happen when the sheet
  symbols stop moving, since wires follow them.
- **KiCad's global library tables point at a dead path.** `~/.config/kicad/10.0/{sym,fp}-lib-table`
  both reference `/tmp/.mount_kicadremp4722615889122143643/...`, a stale AppImage mount. With it
  gone, ERC reports 170 `lib_symbol_issues` and 100 `footprint_link_issues` that are entirely
  artefacts. Re-mounting the AppImage restores the path and was used for the runs above, but the
  real fix is the one in the plan: point those tables at `~/Apps/kicad-10.0.4/usr/share/kicad/`,
  which is already extracted. **That is a change outside this repo, so it is the hardware owner's
  to make** — Preferences → Configure Paths, then Manage Symbol/Footprint Libraries.

## 10. Review 1 (2026-08-12) — the analysis notes, answered

The notes are `../manual-analysis/Analysis_mcu.md`. Each point is restated, answered from a datasheet
with the page or table, and closed as either **changed** or **correct as drawn**. Where the note was
mistaken it says so, and where it found a real error it says that too.

Score, plainly: **two of the six points were right and changed the sheet** (§10.1, and the cycle-life
problem §10.5 surfaced), **one was right about the evidence but the part stays** (§10.2), **one was
reading the wrong section of the datasheet** (§10.3), and **one rested on a wrong premise but asked
exactly the right question underneath it** (§10.5). §10.7 turned up a gap neither of us had written
down. Two errors of my own were found on the way — both in this document, both listed below.

### 10.1 `C42`: "Isn't this capacitor one too much?" — **right; deleted**

Yes. `stm32g0b1.pdf` **Figure 15 (p.65)** is the entirety of ST's decoupling scheme, and it asks for
exactly three groups:

| Node in Figure 15 | Capacitors drawn |
| --- | --- |
| `VDD/VDDA` | "1 × 100 nF + 1 × 4.7 µF" |
| `VDDIO2` | "100 nF + 4.7 µF" (not present on this package) |
| `VREF+` | "100 nF" + "1 µF" |
| **`VBAT`** | **none — the pin goes straight to the internal power switch** |

There is no coin cell here, so `VBAT` is not an independent supply: Table 12's LQFP64-GP column puts
`VBAT` on pin 6 and `VDD/VDDA` on pin 8, and the netlist confirmed both sat on `+3V3_AON` together
with `C40`, `C41`, `C42` and `FB20`. So `C42` was a third capacitor on a net that already carried
Figure 15's specified pair, two pin-pitches from `C41`. It contributed nothing that `C41` was not
already contributing.

**Changed:** `C42`, its `GND` symbol `#PWR305`, its stub wire and its rail junction are deleted. The
`+3V3_AON` rail on that block is a single wire from x = 25.40 to 76.20, so removing a mid-span tap
cannot break it — confirmed by netlist diff, which showed exactly `C42.1` leaving `+3V3_AON` and
`C42.2` leaving `GND` and nothing else. The on-sheet note now reads "VDD/VDDA (8) + VBAT (6) - one
net" so the next reader does not re-ask this.

For the record, this is not a general rule. If `VBAT` ever gets its own source — a coin cell or a
supercap, which §3.7.6 explicitly contemplates — it becomes a separate supply pin and wants its own
decoupling immediately.

### 10.2 `FB20`: "Where in the doc does it call for this?" — **right: it doesn't. Kept anyway, and the doc now says so**

Nowhere. That was worth catching, because §5.1 introduced the whole block with "straight from ST's
own scheme", which made `FB20` look like it had a citation. It does not. Figure 15 feeds `VREF+` from
the same supply through 100 nF + 1 µF with **no series element**.

Where it came from: ST's other families bring `VDDA` out as its own pin and their reference designs
filter it from `VDD`. On G0 that pin does not exist — §3.7.1 says "`VDDA` voltage level is identical
to `VDD` voltage as it is provided externally through `VDD/VDDA` pin" — so `VREF+` is the only analog
node left where the idea can be applied at all. §5.1 already said that; what it failed to say was
that applying it is a choice.

**Correct as drawn, on these grounds rather than the datasheet's:**

- **Asymmetry.** `FB20` can be replaced by a 0 Ω jumper at any time after fabrication. A filtered
  `VREF+` cannot be created after fabrication. The same reasoning reserved `FL_PWM2` in §3.2.
- **What it buys.** The ADC reads the EPD high-voltage rails through 11:1 dividers (§5.2), so one
  ADC LSB at 3.3 V is 0.8 mV at the pin but 8.8 mV at the divider input. Reference noise is
  multiplied by the same 11.
- **Cost.** $0.0134, one 0402, 1.56 M in stock.

The review did make me check something I had not: **whether a series element there is even legal.**
Table 21 gives `VREF+` an absolute maximum of `min(VDD + 0.4, 4.0) V` — only 400 mV of headroom over
`VDD`. `BLM15AG121SN1D` is **190 mΩ** DCR (LCSC, queried 2026-08-12), so 0.19 mV at 1 mA of reference
current, and the 1.1 µF on the quiet side re-equalises through it with a ~0.2 µs time constant on
power-down. Safe — but only because of the DCR. A resistor, or a bead picked purely for its 100 MHz
impedance, could eat that 400 mV budget. **That constraint is now written into §5.2 and into the
part's `Description` on the sheet**, because it is exactly the kind of thing a future substitution
would silently break.

### 10.3 `Y20`: "Doesn't the doc say 8 MHz resonator?" — **no; that is the HSE. Correct as drawn**

The 8 MHz is real, and it is in the datasheet twice — but both times it describes the **HSE**, which
this design does not fit:

- **Table 42 (p.83), "HSE oscillator characteristics":** `fOSC_IN` = min **4**, typ **8**, max **48**
  MHz. The 8 is a typical value in a range, not a requirement.
- **Figure 20 (p.84)** is captioned "Typical application with an **8 MHz** crystal" — ST's worked
  example for the HSE.

`Y20` is the **LSE**: 32.768 kHz, specified in **Table 43 (p.85)**, drawn in **Figure 21**, and wired
to `OSC32_IN`/`OSC32_OUT` = `PC14`/`PC15` (pins 4 and 5) — different pins from the HSE's
`OSC_IN`/`OSC_OUT` on `PF0`/`PF1`, which this sheet uses for `MCU_EN_5V`/`MCU_EN_3V3`. §5.4 said "LSE
only. No HSE" but never put the two side by side, which is what let the confusion happen; it now
carries a comparison table.

Two useful things came out of re-reading Table 43 and are now in §5.4: `IDD(LSE)` runs 250 nA to
630 nA across the four `LSEDRV[1:0]` settings — the high setting alone would be a sixth of this
sheet's entire standby budget — and `tSU(LSE)` is **2 seconds** from software enable to stable
oscillation.

### 10.4 `D20`: "What is this LED for? Only for the prototype?" — **correct as drawn; keep it**

It is a status LED on `PC2` (`LED_STAT#`), sinking through `R44` 1 kΩ from `+3V3_AON`. Active low —
the MCU pulls the cathode side down — hence the `#`. Current is **≈1.3 mA (est.)**: `(3.3 − Vf)/1 kΩ`
with a green Vf around 2.0 V at that current. *(Est. because `LTST-C191KGKT`'s datasheet is not in
`../datasheets/`. It affects brightness only; nothing depends on the exact figure.)*

Not only for the prototype, for one specific reason: **it is the only output this board has before
anything else works.** The panel needs `+5V_DCDC`, the EPD HV chain, the FPGA bitstream and the SoM;
the UART needs a SoM that is alive; SWD needs the case open. On a sealed device with a soldered-down
module, a blink pattern is the difference between "dead" and "the MCU is running and here is why it
stopped". Beyond bring-up, a charge/status indicator is ordinary for an e-reader.

Cost of keeping it: **zero when off** — it is already in §7's budget at 0 µA, because a dark LED and
a 1 kΩ resistor with the pin driven high or left as an input pass nothing. Whether it gets a light
pipe to the outside is an enclosure decision; if the answer is no, mark it DNP at that point and the
pads stay for bring-up.

### 10.5 Buttons — **the premise was wrong, the question underneath it was the right one**

Three separate things here.

**"For the final product I want only two buttons, prev and next, since enter will be done with
touchscreen."** There is no enter button on this sheet. The three switches are **power** (`SW20`),
**page back** (`SW21`) and **page forward** (`SW22`) — so the navigation count is already two, and
the touchscreen is already doing what the note wanted it to do. Going to two *switches* would mean
deleting the **power** button, which is a different proposition entirely, so it was raised rather
than done. **The hardware owner chose to keep `SW20` (2026-08-12);** no schematic change.

Why it matters: `bq25890.pdf` §9.2.10.2 lists exactly four ways to leave ship mode — plug in an
adapter, clear `BATFET_DIS`, set `REG_RST`, or hold `QON` low for `tSHIPMODE` (1.25–2.25 s per the
timing table). The middle two need a live I²C host, and in ship mode `BATFET` is off, so `+VSYS` and
therefore `+3V3_AON` and therefore the MCU do not exist. **The real exits are a cable or the button.**
Deleting `SW20` would also give up the `tQON_RST` 12–18 s `BATFET` reset, and §9.2.10.3 notes that
one only works while no input source is plugged in — so USB is not a substitute for it either.

**"Will these buttons work with mcu unpowered to wake everything up, or why is this specifically
mentioned for `CHG_QON#`?"** This is the right question and the answer is that "off" is two different
states:

| | standby (the everyday off) | ship mode (storage) |
| --- | --- | --- |
| `BATFET` | on | **off** |
| `+VSYS`, `+3V3_AON` | up | **0 V** |
| MCU | Stop 1, 3.7 µA, `EXTI` armed | **unpowered** |
| `SW21`/`SW22` | **wake it** — `EXTI7`/`EXTI8` | dead: `R42`/`R43` pull up to a rail that is gone |
| `SW20` | wakes it — `EXTI6` | **works** |

So: with the MCU merely *asleep*, prev/next wake everything, and that is the case the device is in
almost all of the time. With the MCU *unpowered*, nothing on `+3V3_AON` can do anything — including
the touchscreen. `CHG_QON#` is singled out because its pull-up is inside the charger, referenced to
`V(BAT)` and fed from the cell directly, and `SW20` is a galvanic short to ground: it is the one
switch on the board that does not depend on any powered part. That is also why §2.2 forbids wiring it
to a `+3V3_AON` pull-up.

**"I don't know which switches to use since I would like a satisfying click."** Asking this turned up
a real problem that has nothing to do with click: **`TS-1187A` is rated 100 000 cycles.** `SW21` and
`SW22` are the most-actuated parts on the board, and at ~200 page turns a day 100 k is about **1.4
years**. Nothing in the review notes was aimed at this; it fell out of looking up the force spec.

Queried on LCSC 2026-08-12:

| Part | LCSC | Force | Travel | Cycles | Size | Price | Footprint in KiCad 10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TS-1187A-B-A-B` *(was fitted)* | `C318884` | 1.6 N | 1.5 mm | 100 k | 5.1×5.1 | $0.0197 | yes, **Basic** |
| `TS-1187A-C-C-B` | `C318889` | **2.6 N** | 1.7 mm | 100 k | 5.1×5.1 | $0.0397 | same footprint |
| `TS-1187A-C-E-B` | `C318887` | **2.6 N** | 2.5 mm | 100 k | 5.1×5.1 | $0.0402 | same footprint |
| `TS-1187A-C-F-B` | `C571338` | **2.6 N** | 3.0 mm | 100 k | 5.1×5.1 | $0.0474 | same footprint |
| **`EVQPLHA15`** *(now fitted on `SW21`/`SW22`)* | `C79172` | 1.6 N | 1.5 mm | **500 k** | 4.9×4.9 | $0.1348 | `SW_SPST_Panasonic_EVQPL_3PL_5PL_PT_A15` |

**Changed:** `SW21`/`SW22` → `EVQPLHA15`, footprint and `LCSC` field with it. Same force and travel,
so the feel is unchanged; five times the cycle life, about seven years on the same assumption.
`SW20` stays a `TS-1187A-B-A-B` — pressed rarely, and JLC Basic.

On the click itself, the honest answer: **force and travel are all a datasheet gives, and they do not
predict it.** What a finger feels through a keycap in a sealed case is dominated by how the cap
couples to the stem and how much preload the assembly puts on it. The useful fact is that the
`TS-1187A` land pattern takes all four variants above, so 2.6 N remains available as a pure BOM
change with no layout consequence. Ordering a handful and pressing them is the only way to settle it
— logged in §9 as needing a bench test, since **I cannot feel these for you.**

### 10.6 "Is it possible to change things on the MCU if needed?" — **partly, and the boundary is worth knowing**

| Fixed at fabrication | Changeable in firmware, forever |
| --- | --- |
| which physical pin a net lands on | pin direction, pull-up/pull-down, output speed, open-drain vs push-pull |
| which peripheral *instances* are reachable at all | which alternate function a pin uses, among those in its own AF row (Tables 13–20) |
| the 11 spare pins staying spare or not | whether a signal is polled or interrupt-driven |

So: a peripheral can be swapped for another that Tables 13–20 offer **on that same pin**, and any
function can be dropped and its pin reused. What cannot happen is moving a signal to a different pin.
That is why §3 is written the way it is, and why the DAC and ADC channel assignments were read twice.
Eleven spares are available (`PC3`–`PC6`, `PC8`–`PC10`, `PD9`, `PB12`, `PA11`, `PA12`), four of them
ADC-capable, each behind a no-connect flag that can simply be deleted.

Checking this properly turned up one thing worth confirming rather than assuming. The KiCad symbol
labels two pins `PA9/PA11` and `PA10/PA12`, which looks like the STM32G0 pin-sharing that smaller
packages have. On **LQFP64 all four are separately bonded** — Table 12's LQFP64-GP column gives pin
37 = `PA9`, 42 = `PA10`, 43 = `PA11 [PA9]`, 44 = `PA12 [PA10]`, and note 3 (p.55) explains the
brackets: "Pins PA9/PA10 can be remapped in place of pins PA11/PA12 (default mapping), using
SYSCFG_CFGR1 register" — an *option*, not a constraint. So §3.2's assignment holds, the spare count
of 11 is right, and `PA11`/`PA12` are genuinely free. That last part matters in §10.7.

### 10.7 "How do I flash/program the MCU?" — **answered, and it exposed a gap**

Today: **SWD**. `MCU_SWDIO`/`MCU_SWCLK` on `PA13`/`PA14` to `J20`, which is pads only and not fitted
(§5.6) — solder a header on, use any ST-LINK, the `CN4` pin order means a stock Nucleo cable fits.
That is the bring-up path and the recovery path, and it needs the case open.

Datasheet §3.5 (p.16) then says something useful: the System-memory boot loader reprogrammes flash
over **USART on `PA9`/`PA10`**, `PC10`/`PC11` or `PA2`/`PA3`; I²C on `PB6`/`PB7` or `PB10`/`PB11`; SPI
on `PA4`–`PA7` or `PB12`–`PB15`; or **USB on `PA11`/`PA12`**. Two of those are already on this sheet:
`MCU_TXD`/`MCU_RXD` **are** `PA9`/`PA10`, with the SoM at the far end, and `PA11`/`PA12` are two of
the spares — with the G0B1's USB being crystal-less capable ‡ (§3.24), so the missing HSE does not
rule it out.

**The gap:** the data path exists, the control path does not. `BOOT0` is `PA14`, which carries `R40`
as a 10 kΩ pull-*down*, and `MCU_NRST` goes only to `J20`. **The SoM can talk to the bootloader but
cannot start it, because it can neither reset the MCU nor pull `BOOT0` high.** A firmware-hosted
updater over the existing UART closes the *update* case with no hardware change at all, but not the
*recovery* case — a bad flash then needs the case opened. Two SoM GPIO, one to `MCU_NRST` and one to
`BOOT0` through a series resistor so it fights neither `R40` nor a connected debugger, would close
both. Free now, impossible after fabrication. Recorded in §9 as a WP8 decision, and §5.7 is the new
section that lays it out.

### 10.8 Two errors of mine, found while answering

- **§9 named `C48`/`C49` as the crystal load capacitors.** They are the button debounce capacitors;
  the load capacitors are **`C46`/`C47`**. §5.4's arithmetic was right and named no reference at all,
  which is how the two survived side by side. Both sections now name them explicitly.
- **§5.1 presented the whole supply block as "straight from ST's own scheme".** `FB20` is not, and
  §10.2 is the correction. The claim was too broad, and it is the reason the review had to ask.

### 10.9 Not changed, and why

- **`R44` stays 1 kΩ.** ≈1.3 mA is visible on a modern green 0603 and the pin's 15 mA sink limit ‡
  (Table 22) is nowhere near.
- **`R42`/`R43` stay 100 kΩ.** §5.5's reasoning is unaffected by the switch change; the new part is
  the same 50 mA / 12 V rating.
- **`C48`/`C49`/`C50` stay 100 nF.** Debounce times are set by the pull-up, which did not change.
- **The `QON_SNS` / `CHG_QON#` split stays** (§2.2), and with `SW20` retained the whole argument for
  it stands unchanged.

## 11. Layout guidelines — collected now, to be applied at Stage D

Written while the datasheets are open, in the shape of `battery.md` §11 and `power.md` §11. Nothing
here is placement; it is the constraints placement has to satisfy.

### 11.1 The one rule that comes from ST in writing

The caution under Figure 15 (p.65) is the only layout instruction in the datasheet and it is
imperative: the supply pin pairs "must be decoupled with filtering ceramic capacitors as shown
above. These capacitors must be placed **as close as possible to, or below, the appropriate pins on
the underside of the PCB**". Concretely, for this sheet:

- `C41` (100 nF) at pin 8 `VDD/VDDA`, with `C40` (4.7 µF) behind it. Pin 6 `VBAT` shares the net and
  sits two pitches away, which is what makes one group sufficient (§10.1) — but it only holds if the
  group really is at pin 8. If `C41` migrates during placement, `VBAT` loses its decoupling too.
- `C44` (100 nF) then `C43` (1 µF) at pin 7 `VREF+`, on the far side of `FB20`.
- The ground return for all four goes to the plane directly under the part, not around it.

### 11.2 `VREF+` and `FB20`

`FB20` must sit between the `+3V3_AON` pour and pin 7, with `C43`/`C44` on the pin-7 side of it —
a bead with its capacitors on the wrong side filters nothing. Keep the `VREF+` island small; it is a
quiet high-impedance node and any copper on it is an antenna. Do not pour `+3V3_AON` over it.

### 11.3 The crystal — the most layout-sensitive circuit here

`Y20` at 32.768 kHz is a high-impedance, sub-microamp oscillator (`IDD(LSE)` 250–630 nA, Table 43),
which makes it the easiest thing on this sheet to break with copper:

- `Y20`, `C46` and `C47` as close to pins 4/5 as the footprints allow, on the same layer, with the
  shortest possible traces. No vias in `OSC32_IN`/`OSC32_OUT`.
- A **guard ring** tied to `GND` around the whole oscillator, with the crystal's own ground and both
  load capacitors' returns landing on it, and a solid ground directly beneath.
- Nothing switching may cross or run beside `OSC32_IN`/`OSC32_OUT` on any layer — specifically not
  `MCU_SWCLK`, the I²C pair, `FL_PWM1`/`FL_PWM2`, or anything from `power.kicad_sch`'s switching
  nodes. Crosstalk here shows up as an RTC that gains or loses time, which is a miserable bug to
  chase.
- Keep the SWD header away from it: `J20` is a 2.54 mm header whose long stubs sit near `PA13`/`PA14`.
- **AN2867 is the reference and is not in the repo.** Fetch it before this is committed (§9).

### 11.4 `QON` and the power button

`CHG_QON#` is the one net on the sheet that is alive with everything else dead, and it idles at up to
4.3 V (§2.2). Route it as a plain signal, but:

- Keep `R41` **at the MCU end**, next to `PD6` — its job is to limit fault current into that pin, so
  the resistor must be between the pin and the rest of the world, not next to the switch.
- `C50` belongs at `SW20`, where it can debounce the contact.
- Keep the net away from the EPD high-voltage nets on `epd_power`. A short from a 26 V rail into a
  4.3 V net that reaches an MCU pin is one of the few genuinely destructive faults available here.

### 11.5 Buttons and the LED

- `SW21`/`SW22` are pressed by a finger through a case: give them mechanical support, keep the keep-out
  clear on the solder side, and expect assembly force on the pads. `EVQPLHA15`'s two pads numbered
  `0` are mechanical anchors — land them, they are what takes that force.
- Their debounce capacitors (`C48`/`C49`) go at the switch, not at the MCU.
- `D20` needs its position decided with the enclosure, since a light pipe constrains it more than
  electrons do. `R44` can sit anywhere.

### 11.6 The part itself

- LQFP-64 at 0.5 mm pitch on a 10 × 10 mm body: no fine-pitch surprises, but 60 I/O leaving a small
  part means the escape pattern decides the whole board's routing. Place `U20` before anything else
  on this sheet.
- `MCU_NRST` wants `C45` close to pin 12, and the net kept short — it is an input with no internal
  glitch filter worth relying on.
- The I²C pair `SCL_AON`/`SDA_AON` leaves for `battery` and `power_mon`; route them together, and
  remember the pull-ups are on `battery.kicad_sch` (§5.3), so the bus's electrical length spans two
  sheets' worth of placement.
- `MCU_TXD`/`MCU_RXD` cross into a domain that gets powered down (§4). Nothing layout-specific, but
  keep them away from `OSC32_*` per §11.3.

## 12. Conventions

Reference designators on this sheet start at 20 (`U`, `Y`, `SW`, `D`, `J`, `FB`) and 40 (`R`, `C`),
and its `#PWRnnn` symbols at 300. `battery.kicad_sch` owns `U1`–`U3`/`C1`–`C8`/`R1`–`R19`/`L1` and
`power.kicad_sch` owns `U10`–`U15`/`C20`–`C34`/`R20`–`R36`/`L10`–`L13`, so each sheet keeps its own
block rather than relying on a global re-annotate that would renumber reviewed work.

## 13. Verification — what was actually run

- **`kicad-cli sch erc --severity-all --format json`, re-run after the review-1 patch: 490
  violations project-wide, and `/mcu/` accounts for none of them.** Read from JSON, not from the text
  report — the text report files `footprint_link_issues`, `isolated_pin_label` and `four_way_junction`
  under `***** Sheet /` regardless of which sheet they are really on, which is how an earlier version
  of this section came to under-report.

  | Sheet | Violations |
  | --- | --- |
  | `/` (root, unwired) | 472 |
  | **`/mcu/`** | **0** |
  | `/battery/` | 1 |
  | `/epd/` | 2 |
  | `/epd_power/` | 8 |
  | `/power_mon/` | 7 |

  The root's 472 break down as 207 `footprint_link_issues` (the dead global library tables, §9), 164
  `isolated_pin_label` and 91 `pin_not_connected` (both consequences of the unwired root — a signal
  like `MCU_EN_5V` terminates at one MCU pin here and leaves through a hierarchical label), 9
  `four_way_junction`, 1 `lib_symbol_mismatch` and the rest spread across `pin_not_driven`,
  `power_pin_not_driven` and `multiple_net_names`. **`pin_to_pin` is now zero**: the redundant
  `+3V3_AON` `PWR_FLAG` that caused it is still fitted, but the hardware owner's `+3V3_AON_DCDC`
  rename made it the net's only ERC driver, so it must now stay — see `power.md` §10 and the plan's
  standing asks, where that request is withdrawn.
- **Before/after ERC comparison by violation type, not just by count.** Deleting `C42` removed
  **exactly one** violation, a `footprint_link_issues` — its own dead footprint link, an artefact of
  the broken library tables rather than a real finding. Every other class was byte-identical across
  the patch: `four_way_junction` 9→9, `isolated_pin_label` 164→164, `pin_not_connected` 91→91,
  `pin_not_driven` 3→3, `power_pin_not_driven` 14→14. This is the check that proves the patch did not
  quietly change connectivity somewhere else on the sheet.
- **Netlist node-diff across the review-1 patch.** The netlist was exported before and after and
  compared node by node. The entire diff is `C42.1` leaving `+3V3_AON` and `C42.2` leaving `GND`;
  net count unchanged at 228, no new `unconnected-*` nets. `+3V3_AON` retains `C40.1`, `C41.1`,
  `FB20.1`, `U20.6(VBAT)` and `U20.8(VDD)` — Figure 15's scheme exactly.
- **Re-rendered to PNG and read at 150 and 400 dpi after patching.** The decoupling block is
  continuous from `C40`/`C41` across to `FB20` with no stranded stub where `C42` was, the rail
  junctions at both remaining taps are intact, and the reworded note does not collide with anything.
- **`tools/patch_mcu_review1.py` refuses to run twice** — it asserts on `C42` still being present and
  exits non-zero once the patch has been applied.
- **`kicad-cli sch export netlist`, checked mechanically rather than by eye.** A script re-read the
  exported netlist and asserted that all **50** pin assignments in §3 land on the port they claim
  (using the netlist's own `pinfunction` field), and that the set of unconnected `U20` pins is
  **exactly** the 11 in the reserve list — no more, no less. Both passed. Multi-pin nets were then
  read individually: `CHG_QON#` = `SW20.1, C50.1, R41.2`; `QON_SNS` = `R41.1, U20.56`;
  `KEY_PREV#` = `SW21.1, R42.2, C48.1, U20.39`; `OSC32_IN`/`OSC32_OUT` each = crystal, load cap,
  `U20.4`/`U20.5`; `+3V3_VREF` = `FB20.2, C43.1, C44.1, U20.7`; `MCU_SWCLK` = `J20.2, R40.1,
  U20.46`.
- **Cross-sheet name and direction agreement checked against `power.kicad_sch` and
  `battery.kicad_sch`.** All 7 names shared with `power` and all 10 shared with `battery` match
  exactly, and every direction is complementary (`output` here ↔ `input` there, `bidirectional`
  both sides). `USB_DP`/`USB_DM` are on `battery` but correctly absent here — they go to `som`.
  The remaining 24 hierarchical labels belong to sheets not yet drawn. **This check exists because
  ERC cannot do it while the root sheet is unwired**, and a typo in a net name would otherwise
  survive until WP8.
- **Every pin number in §3 checked against `stm32g0b1.pdf` Table 12's LQFP64-GP column**, and every
  alternate function against Tables 13–20. The DAC and ADC channel assignments are the two that
  cannot be fixed later, and both were read twice.
- **EXTI uniqueness proved by inspection** across all 60 I/O, not just the interrupt inputs (§3.3).
- **Footprint names checked against this KiCad 10 install** — all seven resolve.
- **Rendered to PDF and read.** Three collisions were found that way and fixed: the button row ran
  under the A3 title block, the SWD header's five labels overlapped at 2.54 mm pitch, and the LED
  block's rail symbol sat on its own heading. None were electrical; all were unreadable.

Not verified, and not verifiable here: nothing on this sheet has been built, flashed or measured.
The 3.7 µA in §7 is a datasheet typical at 25 °C, not a bench result.

## 14. What changed from R1, and why

R1's sheet is `pcb/mainboard/mcu.kicad_sch` (KiCad 8, `version 20231120`), which is **read-only**. It
was copied to a scratch directory and the netlist exported there with `kicad-cli` 10, so nothing in
`pcb/mainboard/` was opened, migrated or written. Every number below comes from that netlist or from
the sheet, not from memory.

### 14.1 The headline numbers

| | R1 | R2 |
| --- | --- | --- |
| MCU | `STM32H750VBT6`, Cortex-M7 480 MHz | `STM32G0B1RCT6`, Cortex-M0+ 64 MHz |
| Package | LQFP-100, 14 × 14 mm | LQFP-64, 10 × 10 mm |
| Flash | 128 KB internal **+ `W25Q32JV` QSPI NOR** | 256 KB internal, no external flash |
| Pins connected | **94 of 100** — 6 spare | **49 of 60** — 11 spare |
| Parts on the sheet | **41** | **24** |
| HSE | `Y1` 24 MHz + `R20` damping + 2 load caps | **none** |
| LSE | `Y2` 32.768 kHz | `Y20` 32.768 kHz |
| Analog filter | `FB3` 120 Ω → `+3V3A` → `VDDA` **and** `VREF+` | `FB20` 120 Ω → `VREF+` only |
| Core regulator caps | 2 × `VCAP`, 4 × 4.7 µF | none — the G0 needs no external core cap |
| Buttons | 3, switch to **`+3V3`**, active-high | 3, switch to **`GND`**, active-low |
| `BOOT0` | **`KEY1` doubles as `BOOT0`** → USB DFU | `R40` 10 k pull-down, no DFU path |
| Debug connector | `J5` 2×6 1.27 mm, **fitted**, FPGA JTAG *and* MCU SWD | `J20` 1×5 2.54 mm, **pads only**, SWD only |
| Status LEDs | 2 (green + red), sourced | 1 (green), sunk |
| microSD | `J7` on this sheet, 6 SDIO pins | moved to `io_expansion` (WP6) |
| Sheet interface | 94 global labels, **0 hierarchical** | 0 global, **41 hierarchical** + 106 local |

### 14.2 The net-level diff

Comparing named nets on `U3` against named nets on `U20`: **78 → 52**, of which **22 carried over
unchanged, 56 were dropped, 30 are new.** That ratio is the whole story of R2's MCU in one line — two
thirds of R1's MCU pin budget went to work R2 does not do here, and the replacement work is a
different, smaller set.

### 14.3 The choice everything else follows from: the part shrank because the job shrank

R1's H750 was the board's only processor, so it owned:

- **Caster's CSR bus as SPI master** (`FPGA_CS`/`SCLK`/`MOSI`/`MISO`) plus configuration
- **A 13-pin FMC parallel bus to the FPGA** (`FMC_D0`–`D7`, `A16`, `NE1`, `NOE`, `NWE`)
- **6 QSPI pins** to `U14`, the `W25Q32JV` holding the bitstream, fonts, LUTs and config
- **6 SDIO pins** to the microSD `J7`
- **7 pins of USB-C** — `USB_DP`/`DN`, `TYPEC_ORI`, `TCPC_INT`, `HPD_EN`, `DP_PDN`, `DP_HPD`
- **Video frontend control** — `DEC_RST` for the ADV7611, `LVDS_BKLTEN`/`LVDS_PVCCEN` for the PTN3460
- **6 `USER_*` pins** to the `user_extension` sheet

In R2 every one of those belongs to the SoM (§2.1). What is left is the always-on housekeeping the
SoM cannot do because it is asleep: rail enables, power-good inputs, charger and gauge I²C, buttons,
EPD high-voltage sequencing and VCOM. That is a small enough job for a Cortex-M0+ that sits in Stop
at 3.7 µA — and staying at that figure is the point of R2, given that 82 % of R1's idle draw sat on
bucks whose enable pins were hardwired on.

### 14.4 What survived untouched — and why WP4 is a port, not a redraw

The 22 nets that carried over are almost entirely the EPD analog interface plus the frontlight:

`VCOM_DAC`, `VGH_DAC`, `VCOM_MEA`, `VP_MEA`, `VN_MEA`, `VGH_MEA`, `VGL_MEA`, `VBUS_MEA`, `VCOM_EN`,
`VCOM_MEA_EN`, `EPD_POS_EN`, `EPD_THROT`, `FL_EN`, `FL_PWM1`, `FL_PWM2`, `FPGA_DONE`, `FPGA_SUSP`,
`MCU_SWDIO`, `MCU_SWCLK`, `OSC32_IN`, `OSC32_OUT`, `GND`.

This is the concrete reason `epd`, `epd_power` and `power_mon` port from R1 net-identically: the
analog measurement and control interface did not change, so neither did the circuits behind it. It is
also what constrained the R2 part choice — **two 12-bit DACs on `PA4`/`PA5`** (§1) is a hard
requirement inherited from these two nets, and it is what removed the whole `G030`/`G031`/`G041` line
from consideration.

### 14.5 The HSE: why R1 needed 24 MHz and R2 needs no crystal at all

R1 really does run its PLL from the HSE — `fw/Core/Src/main.c:228` sets
`RCC_OSCILLATORTYPE_HSE` / `HSEState = RCC_HSE_ON` / `PLL.PLLSource = RCC_PLLSOURCE_HSE`, and
`fw/Core/Inc/stm32h7xx_hal_conf.h:109` defines `HSE_VALUE (24000000UL)`. It needs it for two things a
480 MHz M7 with a USB device cannot get from an internal RC: the core PLL and USB's 48 MHz at USB's
frequency tolerance.

The wiring is textbook and worth recording because it is the thing R2 does *not* have: `Y1.1` →
`OSC_IN` with `C6` 18 pF; `Y1.3` → **`R20`, a 1 kΩ series damping resistor** → `OSC_OUT` with `C10`
18 pF; `Y1.2`/`Y1.4` are the case ground.

R2 has no USB on the MCU and no 480 MHz core, so `HSI16` + PLL is inside the tolerance of everything
on the sheet (§5.4). Two consequences worth naming:

- **`PF0`/`PF1` — the HSE's `OSC_IN`/`OSC_OUT` — become `MCU_EN_5V` and `MCU_EN_3V3`.** Deleting the
  crystal directly paid for two of the four rail enables that R2 exists to add.
- Neither board damps its 32.768 kHz LSE with a series resistor. On the G0 that is deliberate rather
  than inherited: `LSEDRV[1:0]` sets drive in firmware (§5.4), which is the modern replacement for
  `R20`'s job on the HSE.

And for the record, §10.3's confusion has a real basis: R1 *does* have a megahertz crystal on this
exact sheet. It is just not the one R2 kept.

### 14.6 `FB3` → `FB20`: the same part, with a justification that evaporated

This is the most interesting single difference, because it explains why review 1 was right (§10.2).

In R1, `FB3` (120 Ω @ 100 MHz — the *same* value as `FB20`) generates a separate rail `+3V3A` from
`+3V3`, and `+3V3A` carries `C47` 4.7 µF + `C48`/`C50` 100 nF and feeds **both `U3.21 (VDDA)` and
`U3.20 (VREF+)`**. On the H750, `VDDA` is its own pin, so ST's own supply scheme *does* ask for that
filter. The bead had a citation.

The G0 merges `VDDA` into the `VDD` pin — §3.7.1: "`VDDA` voltage level is identical to `VDD` voltage
as it is provided externally through `VDD/VDDA` pin". So there is no analog supply left to filter and
only `VREF+` remains. **`FB20` is `FB3`, carried across and applied to the one pin still eligible** —
which is exactly why no page of `stm32g0b1.pdf` asks for it, and why §5.1's "straight from ST's own
scheme" was the wrong frame. It stays on the asymmetry argument in §10.2, with Table 21's
`min(VDD + 0.4, 4.0) V` ceiling making DCR the binding specification rather than impedance.

The capacitors shrank with the justification: R1's analog group is 4.7 µF + 2 × 100 nF for two pins;
R2's is 1 µF + 100 nF, which is precisely what Figure 15 draws for `VREF+` alone.

### 14.7 Buttons: the polarity flipped, and one part choice came back around

| | R1 | R2 |
| --- | --- | --- |
| Common terminal | `SW1`–`SW3` pin 2 → **`+3V3`** | all three → **`GND`** |
| Sense | active-**high** | active-**low** (`KEY_PREV#`, `KEY_NEXT#`, `CHG_QON#`) |
| External resistor | `R21` 10 kΩ pull-down on `KEY1` only; `KEY2`/`KEY3` use internal pulls | `R42`/`R43` 100 kΩ pull-ups; `CHG_QON#` uses the charger's internal 200 kΩ |
| Part | Panasonic `EVQPUL`/`EVQPUC`, 4.7 × 4.5 mm, 100 k cycles | `TS-1187A` (power) + Panasonic `EVQPLHA15`, 500 k cycles (pages) |

The polarity flip is not taste. `CHG_QON#` **must** be a galvanic short to ground — that is TI's
intended use and the only arrangement that works with the whole board unpowered (§2.2, §10.5). Once
one switch on the sheet has to be active-low, matching the other two costs nothing and avoids running
two conventions side by side. R1 had no such constraint because it had no charger and no ship mode.

`R21` existing on `KEY1` alone is explained by the next section: `KEY1` is also `BOOT0`, so it must
read a defined level at reset, before any firmware has configured an internal pull.

The part choice is a small loop closed: R1 used Panasonic tactiles, R2's first draft moved to
`TS-1187A` for the JLC Basic listing, and review 1 moved the two page buttons **back** to the
Panasonic family — but to `EVQPLHA15` at 500 k cycles rather than R1's 100 k parts. R1's 100 k rating
was never a problem, and the reason is worth stating: **nobody turns pages on a monitor.** The same
switch rating that was ample for a desktop EPD monitor is about 1.4 years of service on a reader
(§10.5). The use case changed the spec, not the vendor.

### 14.8 The one place R2 is currently *worse* than R1: getting firmware in

R1 can be reflashed by anyone holding the board, with no tools and without opening anything:
**`KEY1` is wired to both `U3.3 (PE4)` and `U3.94 (BOOT0)`.** Hold that button while plugging in USB
and the H750 boots the system bootloader, which enumerates as DFU on the USB-C the board already has
— which is exactly the procedure `CLAUDE.md` and `USAGE.md` document and what
`scripts/dev_flash_mcu.sh` drives via `dfu-util`. R1 additionally fits `J5`, a 2×6 1.27 mm SMD socket
carrying FPGA JTAG (`FPGA_TCK`/`TDI`/`TDO`/`TMS`) **and** MCU SWD (`MCU_SWCLK`/`MCU_SWDIO`), not
marked DNP.

R2 has none of that. The MCU's USB is unused, `BOOT0` is held low by `R40`, and `MCU_NRST` reaches
only `J20`, which is unfitted pads. **Reflashing R2's MCU currently means opening the case and
soldering a header.** That is a real regression, and R1 shows the pattern worth copying: give the
bootloader a route in that survives the device being sealed. §5.7 works out the R2 equivalents —
the factory USART bootloader is *already* on `MCU_TXD`/`MCU_RXD`, so it needs only a SoM-drivable
`NRST` and `BOOT0`; or route the free `PA11`/`PA12` for USB DFU. §9 carries it as a WP8 item, and it
should be settled while the SoM's pin budget is still being written.

### 14.9 Sheet-interface style, and why R2 pays a cost for it

R1's MCU sheet has **94 global labels and no hierarchical labels at all** — its sheets are
organisational, and every net is visible everywhere. R2 has **41 hierarchical labels and no global
ones** (bar the power symbols, which are global by construction).

The reason for changing is that a global-label design cannot express a sheet's contract: a net name
reused on another sheet silently merges, and no tool can tell an intentional cross-sheet connection
from a collision. R2's hierarchical interface is what made §13's cross-sheet name-and-direction check
possible in the first place. The cost is real and still outstanding — **the root sheet must actually
be wired**, and until it is, most of the project's ERC noise is the consequence (§9).

### 14.10 Spare capacity, deliberately larger on the smaller part

R1 left **6 of 100 pins** unconnected; R2 leaves **11 of 60**. The smaller part is proportionally
*less* fully used, on purpose: R2 is a sealed device with no planned respin, and four of its spares
are ADC-capable. §9 argues some of them should get test pads for the same reason.
