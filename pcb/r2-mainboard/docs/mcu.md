# `mcu.kicad_sch` — housekeeping controller — R2 work package 3

Status: **drawn, not reviewed.** Companion to `battery.md` and `power.md`. Every claim cites a
datasheet in `../datasheets/` (with the table or page), the LCSC catalogue, or a file in this repo.
Estimates are marked **(est.)**.

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
| `Y20` | `Q13FC13500004` (Epson FC-135) | `C32346` | 32.768 kHz LSE, **JLC Basic**, 438 k stock |
| `FB20` | `BLM15AG121SN1D` | `C85812` | 120 Ω @ 100 MHz, `VDD` → `VREF+` |
| `SW20`–`SW22` | `TS-1187A-B-A-B` | `C318884` | tact switches, **JLC Basic**, 918 k stock |
| `D20` | `LTST-C191KGKT` | `C125098` | green status LED, 0603 |
| `J20` | 1×5 2.54 mm header, **not fitted** | — | SWD pads (§6) |

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
| `VDD`/`VDDA` (pin 8) | `C40` 4.7 µF + `C41` 100 nF | Figure 15 — "1 × 100 nF + 1 × 4.7 µF" |
| `VBAT` (pin 6) | tied to `+3V3_AON`, `C42` 100 nF | no coin cell; backup domain follows `VDD` |
| `VREF+` (pin 7) | `FB20` from `VDD`, then `C43` 1 µF + `C44` 100 nF | Figure 15 — "100 nF + 1 µF" |
| `NRST` (pin 12) | `C45` 100 nF | Table 59 |

STM32G0 merges `VDDA` into the `VDD` pin, so there is no separate analog supply to filter — `VREF+`
is the only analog node that can be isolated, and `FB20` is what isolates it.

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

Load capacitors: `C_L = C1·C2/(C1+C2) + C_stray`. For a 12.5 pF crystal with ~3 pF of stray,
`C1 = C2 = 2 × (12.5 − 3) = 19 pF` → **18 pF (E12)**, which is also what R1 fits on its 32.768 kHz
(`pcb/mainboard/mcu.kicad_sch`, `C13`/`C28`). **`Y20`'s load capacitance is not verified** — the
Epson FC-135 ships in 12.5 pF, 9 pF and 7 pF variants and the LCSC listing does not say which
`C32346` is. §9.

### 5.5 Buttons

Three `TS-1187A` tact switches, all to `GND`:

| Ref | Net | Pull-up | Debounce |
| --- | --- | --- | --- |
| `SW20` power | `CHG_QON#` → `R41` → `QON_SNS` | internal to the charger, 200 kΩ ‡ | `C50` 100 nF → ~20 ms with that pull-up |
| `SW21` page back | `KEY_PREV#` | `R42` 100 kΩ to `+3V3_AON` | `C48` 100 nF → ~10 ms |
| `SW22` page forward | `KEY_NEXT#` | `R43` 100 kΩ to `+3V3_AON` | `C49` 100 nF → ~10 ms |

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

## 6. Footprints

All stock KiCad 10, all verified present in this KiCad install:

| Ref | Footprint |
| --- | --- |
| `U20` | `Package_QFP:LQFP-64_10x10mm_P0.5mm` |
| `Y20` | `Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm` |
| `FB20` | `Inductor_SMD:L_0402_1005Metric` |
| `D20` | `LED_SMD:LED_0603_1608Metric` |
| `SW20`–`SW22` | `Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A` |
| `J20` | `Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical` |
| `R4x`, `C4x` | `Resistor_SMD:R_0402_1005Metric`, `Capacitor_SMD:C_0402_1005Metric` |

Nothing has to be authored for this sheet — unlike `power.md` §7, which still owes three.
`TS-1187A` was chosen partly *because* KiCad carries its land pattern and JLCPCB lists it as a
Basic part; the 4.5 × 4.5 mm switches with more stock have no KiCad footprint.

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

- **`Y20`'s load capacitance is unverified.** Epson FC-135 exists in 12.5 pF, 9 pF and 7 pF; `C48`
  and `C49` are 18 pF on the assumption of 12.5 pF and ~3 pF stray (§5.4). Confirm from the Epson
  datasheet before layout, and check the crystal's drive-level rating against the G0's LSE drive
  setting — an overdriven watch crystal ages badly.
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
  noise above, and it is why §11's cross-sheet name check had to be done by script. Wiring it is a
  small, mechanical job — a labelled stub on each sheet pin — but it should happen when the sheet
  symbols stop moving, since wires follow them.
- **KiCad's global library tables point at a dead path.** `~/.config/kicad/10.0/{sym,fp}-lib-table`
  both reference `/tmp/.mount_kicadremp4722615889122143643/...`, a stale AppImage mount. With it
  gone, ERC reports 170 `lib_symbol_issues` and 100 `footprint_link_issues` that are entirely
  artefacts. Re-mounting the AppImage restores the path and was used for the runs above, but the
  real fix is the one in the plan: point those tables at `~/Apps/kicad-10.0.4/usr/share/kicad/`,
  which is already extracted. **That is a change outside this repo, so it is the hardware owner's
  to make** — Preferences → Configure Paths, then Manage Symbol/Footprint Libraries.

## 10. Conventions

Reference designators on this sheet start at 20 (`U`, `Y`, `SW`, `D`, `J`, `FB`) and 40 (`R`, `C`),
and its `#PWRnnn` symbols at 300. `battery.kicad_sch` owns `U1`–`U3`/`C1`–`C8`/`R1`–`R19`/`L1` and
`power.kicad_sch` owns `U10`–`U15`/`C20`–`C34`/`R20`–`R36`/`L10`–`L13`, so each sheet keeps its own
block rather than relying on a global re-annotate that would renumber reviewed work.

## 11. Verification — what was actually run

- **`kicad-cli sch erc` on the whole project: 186 violations, one of them real.**
  - 123 `isolated_pin_label` — "label connected to only one pin". On this sheet that is the normal
    case, not a defect: a signal like `MCU_EN_5V` terminates at exactly one MCU pin here and leaves
    through a hierarchical label. They collapse once the root sheet is wired (below).
  - 60 `pin_not_connected` — the sheet pins on the parent: 12 `battery` + 7 `power` + 41 `mcu`,
    which is all of them, because the root sheet joins no sheets yet.
  - 1 `pin_to_pin` — the redundant `+3V3_AON` `PWR_FLAG` on the battery sheet (`power.md` §9),
    still the hardware owner's to delete.
  - 1 `pin_not_driven` on `U1.12` (`QON`) — see §9.
  - 1 `footprint_link_issues` — the `DLA0010A` footprint `power.md` §7 still owes.
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
