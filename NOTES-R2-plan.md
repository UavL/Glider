# Glider-R2 — plan

Branch `Board-Design`. Last updated **2026-08-03**.

Evidence for every claim here is in **`NOTES-R2-hardware-facts.md`**. R1's state is in
`NOTES-STATUS.md`. This file is only what to do and in what order.

---

## Why R2 exists

R1 cannot be fixed in firmware. Retain draws 1412 mW; the EPD rails are already at 0 mW, and 82 %
of what remains sits on bucks whose `~SHDN` pins are hardwired to `+5V` (`power.kicad_sch`;
confirmed three independent ways in `NOTES-STATUS.md`). The only firmware-switchable supplies on
the whole board are the EPD HV chain and `HPD_EN`. No amount of firmware work changes that.

**Goal:** a board that reaches e-reader battery life while keeping Caster's low-latency
high-refresh drive.

## Constraints from the hardware owner

1. **One board, manufactured complete by JLCPCB or PCBWay. Nothing plugged on afterwards** — a
   mated module makes the device too thick.
2. Design the video link for 75 Hz; operate at 50 Hz.
3. First board is **compute + display + power only**. Touch and pen get unpopulated FPC
   connectors so they can be added without a respin.
4. Nothing gets ordered until the open questions below are answered.

---

## Architecture

```
   ┌───────────────────────────────┐
   │  phyCORE-AM62x DSC (PCL-071)  │  soldered down, 40.8×40.8×2.84 mm
   │  AM6254 · DDR4 · eMMC         │  Deep Sleep ≈ 50-100 mW (to confirm)
   └──┬──────────────┬─────────────┘  VIN 4.5-5.5 V → boost from the cell
DPI 18b + PCLK/DE/   │ I2C, UART, GPIO
HS/VS  (22 signals)  │
   ┌──▼──────────────▼─────────────┐     ┌──────────────┐
   │  XC6SLX9 (Caster, unchanged)  │◄───►│ DDR3L 1 Gbit │ 3.0 MB waveform state
   └──┬────────────────────────────┘     └──────────────┘
      │ 8-12 diff pairs + GD/SD          ┌──────────────┐
   ┌──▼────────────────────────────┐     │ SPI cfg NOR  │ FPGA self-boot
   │  EPD panel J6 (50p) / J3 (16p)│     └──────────────┘
   │  + EPD HV chain (from R1)     │
   └───────────────────────────────┘
   ┌────────────────────────────────────────────────────┐
   │ STM32G0 housekeeping (always-on domain)            │
   │ rail enables · sequencing · VCOM DAC · buttons     │
   │ + charger with power path + fuel gauge             │
   └────────────────────────────────────────────────────┘
   Unpopulated: touch FPC (I2C+INT+RST+3V3), pen FPC (UART+INT+gated rail)
```

**Carried over from R1 unchanged:** Caster EPDC and panel timing (proven at 1448×1072@75), the
EPD HV chain (LGS5145 ×2, LGS6302B5 ×2, TPS22914 ×2, VCOM DAC + LM321 sense), panel connectors
J6/J3 pin-for-pin, DDR3L, and all three INA3221s — every conclusion in this project came from
`sensor` output.

**Deleted:** `ADV7611` (the whole 588 mW `VIDEO IN` rail), `PTN3460`, `CBTL02043A`, HDMI
connector, `STM32H750VBT6` (overkill once the FPGA self-boots from its own flash).

### Three board-level consequences of the DSC footprint

- **A cut-out is required** — ~14.4 × 22.4 mm, R1.2, because the module has bottom-side
  components. Both JLCPCB and PCBWay mill internal cut-outs. **This must be in the floorplan from
  the start, not discovered during layout.**
- **`VIN` is 4.5–5.5 V**, so the SoM needs a boost from the 1S cell. Every other rail still runs
  buck-direct from the cell.
- **Use the DSS in 18-bit RGB666 mode.** It matches Caster's bit layout exactly *and* it sidesteps
  the `BOOTMODE_8..15` straps — see `NOTES-R2-hardware-facts.md` §2.2. This is a device-tree
  `bus_format` choice, not a board choice, but the board must be laid out for `DATA[17:0]` and
  leave `DATA18..23` unconnected.

---

## The reading state — where the power goes

The gateware for this already exists as of the `power-analysis` work:

1. **Hold** (`CSR_ENABLE` bit 2 → `framecap_en`) freezes the framebuffer, so the pixel processor
   stops caring what the video input says.
2. Because nothing reads the input, **the SoM shuts its display controller down and enters Deep
   Sleep.** The DPI link goes dark. There is no link to renegotiate on wake — the thing HDMI made
   impossible and DPI makes free.
3. **Scan stop** (`CASTER_EN_REFRESH` = 0, viable now that `vin_ready = s1_active || !global_en`
   drains the input FIFO) stops the panel source/gate bus toggling and stops framebuffer reads.
   This is where the ~420 mW of FPGA I/O switching power lives.
4. DDR3L drops to self-refresh; the 3.0 MB of waveform state survives.
5. EPD HV rails are already off in retain.
6. The STM32G0 sits in STOP with the RTC and button/touch interrupts armed.

Wake: button/touch → MCU → SoM resume → DSS restart → FPGA sees a valid clock →
`CASTER_EN_REFRESH` on → hold released → the changed region repaints as an ordinary per-pixel
update. **No clear phase, no flash** — `caster_redraw()` was deleted from the resume path
precisely because hold keeps the framebuffer and the glass in agreement.

**On "variable refresh rate":** continuously variable does not work here. E-ink waveforms are
frame-count based (the LUT is 38 frames, mono drive 9, `AUTOLUT_QUIET_FRAMES` 60), so changing
frame rate mid-waveform changes drive time per frame and corrupts the update. What is worth having
and is achievable: **on-demand scan** (0 Hz idle, nominal during an update — the whole win) and
**per-mode nominal rate** (a CSR-set divider on `clk_epdc`, chosen at mode-switch time and held
constant through any one waveform). Both gateware-side, no board cost.

---

## Power tree

The rule, and the entire reason R2 exists: **no rail is permanently on except the housekeeping
domain.**

| Rail | Enable | State when reading | Note |
| --- | --- | --- | --- |
| `+VBAT` 1S 5000 mAh | — | live | charger power-path output |
| `+3V3_AON` | always | on, ~5 mW | STM32G0, gauge, charger I²C, buttons only |
| `+5V_SOM` (boost) | `MCU_EN_SOM` | on | required — SoM `VIN` min is 4.5 V |
| `+3V3_SYS` | `MCU_EN_SYS` | on | FPGA config flash, housekeeping |
| `+1V2_FPGA` | `MCU_EN_FPGA_CORE` | on | off in standby |
| `+3V3_FPGA_IO` | `MCU_EN_FPGA_IO` | on, not toggling | see note |
| `+1V35_DDR` | `MCU_EN_DDR` | on, self-refresh | holds the waveform state |
| `+VP/+VGH/−VN/−VGL/VCOM` | `EPD_PWR_EN`, `EPD_POS_EN`, `VCOM_EN` | **off** | carried from R1 |
| `+5V2_FL` frontlight | `FL_EN` + PWM | off unless lit | R1 declares `FL_EN`/`EPD_THROT` but never drives them — wire and use them |
| `+3V3_TOUCH` / `+3V3_PEN` | `MCU_EN_TOUCH` / `_PEN` | off (unpopulated in R2) | |

**On `+3V3_FPGA_IO`:** R1's ~420 mW of FPGA I/O is *dynamic* switching power (CV²f), not static.
Stopping the scan removes essentially all of it, so cutting the bank rail buys little while
reading — it matters only for deep standby. Keep it gateable, but **do not build the design around
powering a VCCO bank down while the die is configured** (real I/O-clamp constraints, UG393 bank
rules); rely on scan-stop for the reading state.

Other changes from R1: run the bucks **from the cell, not from a 5 V intermediate** (R1 does
VBUS → 5 V → four bucks, ~10 % wasted); add a **charger with power path** (`BQ25896` or
`MP2762A`) and a **fuel gauge** (`MAX17048`, ~3 µA, no sense resistor); add a **4 MB SPI NOR** on
the FPGA's config pins so it self-boots — R1 streams the bitstream from the MCU's SPIFFS on every
pipeline start (~360–400 ms measured), and removing the MCU from the boot path is what lets the
H750 become a G0.

---

## What is still open

| Gap | Blocks ordering? | Closes at |
| --- | --- | --- |
| **Module-level Deep Sleep power** | **YES** | PHYTEC Q1 |
| **Resume latency** — no number exists in any TI or PHYTEC document | **YES** | PHYTEC Q1, or a bench measurement |
| **`PCL-071` price, MOQ, will they sell 1–2 units** | **YES** | PHYTEC Q2 |
| Orderable variants (1 GB RAM, small eMMC, `VDDSHV3` = 3.3 V, WiFi) | **YES** | PHYTEC Q3 |
| **The R2 schematic does not exist** | **YES** | Stages B–E — months, not a purchase |
| Will JLCPCB accept the 270-pin consigned module on a custom footprint | soon | ask before Stage E |
| Panel model | no — deferred with touch/pen | read it off the tail/back label |
| R1 firmware + gateware untested on hardware | no | needs the ISE VM (192.168.56.102, currently down) |

**Nothing is ordered until the first four are answered.**

### Answered, so no longer open

- DPI ingest gateware — **exists and runs** (`vin_dpi.v`, `SRC_DPI`).
- DPI max pixel clock — **165 MHz**, TRM Table 12-361, vs 127 MHz needed at 75 Hz.
- 18-bit RGB666 bit mapping — **identical to Caster's**, TRM Fig. 12-471.
- `BOOTMODE` strap conflict — **avoided entirely by 18-bit mode**.
- Level shifting between SoM and FPGA — **not needed**, both 3.3 V LVCMOS.
- Touch controller sourcing — **wrong question**; it ships bonded to the touch film.

---

## The PHYTEC enquiry

**To:** technical sales, quote form at
<https://www.phytec.eu/en/produkte/system-on-modules/phycore-am62x/>, or +49 6131 9221-32.

> **Subject: phyCORE-AM62x DSC (PCL-071) — quote and technical enquiry**
>
> We are developing a battery-powered e-paper reading device. An FPGA drives a 1448×1072 E Ink
> panel and receives video from the module over the parallel RGB (DPI) interface in 18-bit RGB666
> mode. The device spends nearly all of its time with the module suspended and the image retained
> on the panel, so suspend power and resume speed matter far more to us than performance. We
> intend to solder the module down, using PCL-071.
>
> 1. What is the module's power consumption in Deep Sleep (suspend-to-RAM), and how long does it
>    take to resume to valid display output?
> 2. Price and lead time for PCL-071 at 1, 10 and 100 pieces, and the minimum order quantity.
> 3. Which module variants can we order — specifically 1 GB RAM, the smallest eMMC option, and
>    VDDSHV3 set to 3.3 V? Is an on-module WiFi/Bluetooth option available?

(WiFi is asked about as an option only — `Project_description.md` defers it: books are sideloaded
and the radio costs power. But an on-module, pre-certified radio would be far cheaper to adopt
later than adding one to our own board, so it is worth knowing whether the option exists.)

**Decision rule.** Deep Sleep ≤ ~100 mW and resume ≤ ~500 ms → proceed to Stage B. Above ~250 mW
or ~1 s → the architecture is wrong and the fallback becomes primary.

**Fallback:** `T113-S3` — dual Cortex-A7 with **128 MB DDR3 in package**, in JLCPCB's own
catalogue (`C5197687`, $5.60, 1810 in stock), LCD controller rated to 1920×1080. It removes
consignment, the cut-out and the boost stage in one move. Its unverified risk is the one that
matters most: **suspend-to-RAM support on mainline Allwinner is weak**, and that is the entire
power architecture. Do not adopt it without proving suspend on real hardware first.

---

## Build stages

**A — the enquiry.** Send the three questions. Order nothing.

**B — power tree and part selection.** Every rail gets a named enable net and a named owner.
**Verify each regulator's EN threshold and quiescent current against its datasheet** — R1's entire
failure was that this was never done. New versus R1: the 5 V boost, charger, gauge, FPGA config
NOR. Replace every estimate in the budget below with a datasheet figure.

**C — schematic capture**, mirroring R1's hierarchy where the circuit is unchanged:
`epd.kicad_sch`, `epd_power.kicad_sch`, `fpga_ddr.kicad_sch`, `fpga_config.kicad_sch` are largely
reusable. `tmds_in`/`dp_in` are deleted, replaced by a much smaller `dpi_in`. New: `som.kicad_sch`,
`battery.kicad_sch`.

**D — layout.** Budget **6 layers**. Two fixed constraints drive the floorplan: the DSC cut-out,
and placing the module's DPI pads directly adjacent to the FPGA bank that receives them
(`DPI_PIXEL[17:0]` currently on `T14…D14`).

**E — review before fab.** Full `kicad` skill review (schematic, PCB `--full`, cross-analysis,
EMC, thermal), datasheet-backed pin verification for every IC, then JLCPCB/PCBWay DFM. Resolve
module consignment logistics here, not at order time.

**In parallel, independent of all of the above:** flash and test the R1 firmware and gateware from
`613e8ee`. The gateware half needs the ISE VM back up. This is the only thing that can make
progress today.

---

## Power budget

Basis: 1S 5000 mAh at 3.7 V = 18.5 Wh, ~92 % usable, ~92 % conversion ⇒ **~15.7 Wh delivered**.
‡ = measured or from a datasheet; everything else is an estimate to be replaced in Stage B.

| Reading-state consumer | Estimate |
| --- | --- |
| SoM Deep Sleep, module level | 50–100 mW (‡ 24.44 mW SoC-only DDR4; ‡ 59.7 mW Toradex module) |
| — boost conversion loss on the above | ~10 % |
| FPGA core + I/O, scan stopped, hold asserted | 50–100 mW |
| DDR3L self-refresh | 10–20 mW |
| STM32G0 in STOP + RTC, charger, gauge | ~6 mW |
| EPD HV | 0 ‡ |
| **Reading-state total** | **~135–235 mW** |

| Mode | Average | Hours from 15.7 Wh |
| --- | --- | --- |
| Reading, one page / 30 s | ~235–335 mW | **~47–67 h** |
| Reading, idle | ~135–235 mW | ~67–116 h |
| Active — SoM awake, video streaming, panel driving | ~2.5 W | ~6 h |
| Standby — SoM off, FPGA rails off, MCU in STOP | ~10 mW | weeks |

Against R1's 6.4 h baseline that is roughly **8–10×**: days of heavy reading rather than one
evening. Not a Kobo month — that needs the FPGA out of the idle path entirely — but the right
order of magnitude for a high-refresh reader.

---

## Risks

| Risk | Impact | Closes at |
| --- | --- | --- |
| Module Deep Sleep > 250 mW or resume > 1 s | architecture is wrong; fall back to `T113-S3` | Stage A |
| PHYTEC will not sell 1–2 units, or `PCL-071` is priced out of reach | same | Stage A |
| JLCPCB refuses the consigned module or its custom footprint | forces PCBWay, or hand assembly of one board | ask before Stage E |
| A soldered-down module cannot be swapped if the board is wrong | one bad board = one dead module | accepted; mitigated by Stage E review depth |
| Estimated FPGA idle power wrong | battery life misses target | Stage B datasheets; the three INA3221s make it measurable on board 1 |
| EMR digitizer unavailable for this panel | pen support drops | deferred out of R2 scope |

## Verification

- Every power figure in the budget traced to a datasheet page or re-measured on R1. The ‡ marks
  show how few qualify today.
- `TS_DPI_CLK` timing closure re-read from `par/*.twr` after the next gateware build, at the
  operating pixel clock rather than the 165 MHz constraint.
- J6/J3 pinouts diffed against `pcb/mainboard/epd.kicad_sch` to confirm nothing was lost.
- The DSC landing pattern cross-checked pin by pin against L-1041e.A3 Figs 10–13 before fab.
- On first silicon: `sensor` in each of the four states in the battery table, folded back into
  `NOTES-STATUS.md` the same way the R1 measurements were.
