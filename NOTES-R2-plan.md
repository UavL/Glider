# Glider-R2 — plan

Branch `Board-Design`. Last updated **2026-08-10**.

Capture is under way — see **Stage C progress** below for which sheets exist and
which have been reviewed. Per-sheet specs live in `pcb/r2-mainboard/docs/`.

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

1. ~~**One board, manufactured complete by JLCPCB or PCBWay. Nothing plugged on afterwards** — a
   mated module makes the device too thick.~~ **Revised by the hardware owner 2026-08-13: R2 uses
   the connectorised `PCM-071`.** The board is still manufactured complete — the SoM connectors are
   LCSC parts the fab can fit — but the module itself is plugged in afterwards. Four reasons, all
   the owner's:
   - **PHYTEC's quote (Emma Tholey, 2026-08-13) prices `PCL-071-001-R` at €281 / €272 / €265 at
     1–9 / 10–99 / 100–199**, and notes that "the current memory chip shortage has already been
     factored in, adding around €190 extra per module. These prices apply under the current market
     conditions, not under normal ones."
   - **The solder-down variant is reel-only, in reels of 5, 20, 100 and 250.** Minimum spend is
     therefore ~€1 405 for five modules, for a first prototype that needs one.
   - **Consigned parts.** A soldered module has to be bought here and shipped to the fab in China
     before assembly, which adds cost, delay and customs risk. A connector the fab already stocks
     does not.
   - **Reversibility.** A socket lets a different SoM be tried without a respin.

   The thickness constraint is not withdrawn, it is deferred: **the first prototype is allowed to
   be thick.** A later revision can move to `PCL-071` once the design is settled, which is a
   footprint swap on one sheet. Everything else on the board is unaffected.
2. Design the video link for 75 Hz; operate at 50 Hz.
3. First board is **compute + display + power only**. Touch and pen get unpopulated FPC
   connectors so they can be added without a respin.
4. Nothing gets ordered until the open questions below are answered.

---

## Architecture

```
   ┌───────────────────────────────┐
   │  phyCORE-AM62x (PCM-071)      │  plugged in, 43×32 mm, ~7.6 mm mated
   │  AM6254 · DDR4 · eMMC         │  Suspend-to-RAM 128.6 mW ‡, wake ~150 ms ‡
   └──┬──────────────┬─────────────┘  VIN 5.0 V ‡ (A1/A2/A3) → boost from the cell
      │              │                2x Samtec 120p 0.5 mm on the board
DPI 18b + PCLK/DE/   │ I2C, UART, GPIO
HS/VS  (22 signals)  │
   ┌──▼──────────────▼─────────────┐     ┌──────────────┐
   │  XC6SLX16 (Caster, unchanged) │◄───►│ DDR3L 1 Gbit │ 3.0 MB waveform state
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
| `+1V5_DDR` | `MCU_EN_DDR` | on, self-refresh | holds the waveform state |
| `+VP/+VGH/−VN/−VGL/VCOM` | `EPD_PWR_EN`, `EPD_POS_EN`, `VCOM_EN` | **off** | carried from R1 |
| `+5V2_FL` frontlight | `FL_EN` + PWM | off unless lit | R1 declares `FL_EN`/`EPD_THROT` but never drives them — wire and use them. **`FL_EN`/`FL_PWM*` are firmware-only and straightforward. `EPD_THROT` is not: see below.** |
| `+3V3_TOUCH` / `+3V3_PEN` | `MCU_EN_TOUCH` / `_PEN` | off (unpopulated in R2) | |

**On `EPD_THROT` — "wire and use them" is not available for this one.** Found in WP5 by
`tools/check_ucf.py`: the net runs MCU → FPGA (`U41.M16`) on both boards, but **the string "throt"
does not appear anywhere in Caster's RTL, headers or constraints.** There is no gateware port to
receive it, so it is a wired-but-unimplemented signal exactly like the FMC bus that WP5 deleted.
Driving it from firmware would do nothing. Three honest options, none of them free: implement a
throttle in Caster (a gateware feature, not a wiring fix), delete the net and reclaim `M16`, or keep
it reserved and say so. R2 currently keeps it reserved — `mcu.kicad_sch` declares it and `fpga_io`
terminates it — which costs one ball and leaves the option open. **Decide before Stage D**, since
reclaiming the ball later is free but adding the net back is not.

**On `+3V3_FPGA_IO`:** R1's ~420 mW of FPGA I/O is *dynamic* switching power (CV²f), not static.
Stopping the scan removes essentially all of it, so cutting the bank rail buys little while
reading — it matters only for deep standby. Keep it gateable, but **do not build the design around
powering a VCCO bank down while the die is configured** (real I/O-clamp constraints, UG393 bank
rules); rely on scan-stop for the reading state.

Other changes from R1: run the converters **from the cell, not from a 5 V intermediate** (R1 does
VBUS → 5 V → four bucks, ~10 % wasted); add a **charger with power path** (`BQ25896` or
`MP2762A`) and a **fuel gauge** (`MAX17048`, ~3 µA, no sense resistor); add a **4 MB SPI NOR** on
the FPGA's config pins so it self-boots — R1 streams the bitstream from the MCU's SPIFFS on every
pipeline start (~360–400 ms measured), and removing the MCU from the boot path is what lets the
H750 become a G0.

**Superseded by capture, 2026-08-06 — see `pcb/r2-mainboard/docs/`:**

- The charger is a **`BQ25892`**, not a `BQ25896`. Same footprint and register map; the `BQ25896`
  had 127 units in stock and the `BQ25892` is also the correct variant on merit, because D+/D− go
  to the SoM for sideloading. `docs/battery.md` §1.
- **The DDR bank rail is 1.5 V, not 1.35 V. Changed in WP5, 2026-08-12.** Caster's UCF constrains
  all 48 DDR pins as `SSTL15_II`, which `ds162.pdf` Table 7 specifies only over VCCO 1.425–1.575 V,
  and Spartan-6 has no 1.35 V I/O standard to relabel to. `mt41k64m16.pdf` p.1 makes 1.5 V legal on
  the memory side ("Backward compatible to VDD = VDDQ = 1.5V ±0.075V"), so the DRAM part is
  unchanged. Costs ~1.9 mW of standby; `docs/power.md` §3.1 and §9.
- **"Run the bucks from the cell" holds for 1.2 V and 1.5 V but not for 3.3 V.** `+VSYS` runs from
  ~4.4 V down to ~3.0 V, so a step-down converter drops out halfway down the discharge curve;
  `+3V3` is a **buck-boost** (`TPS63802`). `docs/power.md` §2.1.
- `+3V3_SYS` and `+3V3_FPGA_IO` are **one rail**, since each 3.3 V rail costs a whole buck-boost and
  the note above already says not to build around powering a `VCCO` bank down. Per-rail measurement
  survives through `power_mon`'s shunts. `docs/power.md` §6.
- `+5V_SOM` is **`+5V_DCDC`** (it feeds the EPD HV chain too). ~~and needs a **load switch on the
  boost input**: a boost has no load disconnect, so disabling it alone would leave ~3.4 V on the
  SoM's `VIN`.~~ **Withdrawn in review 1 of `power.kicad_sch`, 2026-08-11.** That is true of boosts
  in general but not of the `TPS61022`: its p.1 feature list says "True disconnection between input
  and output during shutdown", §7.3.2 repeats it, and §6.5 backs it with `IVOUT_LKG` = 1 µA typ
  measured with `VOUT` forced to 5.5 V and `VIN` at 0 V. The `TPS22965` load switch has been deleted;
  `MCU_EN_5V` drives the boost's `EN` directly. `docs/power.md` §2.2 and §10.7.
- The **frontlight boost moves to `frontlight.kicad_sch`** and runs from `+VSYS` directly.

---

## What is still open

| Gap | Blocks ordering? | Closes at |
| --- | --- | --- |
| ~~**Module-level Deep Sleep power**~~ | ~~YES~~ | **CLOSED 2026-08-14 — 128.6 mW ‡ measured on `PCM-071`.** Facts §4.6 |
| ~~**Resume latency** — no number exists in any TI or PHYTEC document~~ | ~~YES~~ | **CLOSED 2026-08-14 — ~150 ms ‡**, and ≤237 ms for a full round trip from the kernel log. Facts §4.6 |
| ~~**`PCL-071` price, MOQ, will they sell 1–2 units**~~ | ~~YES~~ | **CLOSED 2026-08-13** — €281 @1–9, reel-only MOQ 5. Answered by moving to `PCM-071` (constraint 1) |
| **`PCM-071` price and MOQ** | **YES** | replaces the row above; the quote covered `PCL-071-001-R` only |
| Orderable variants (1 GB RAM, small eMMC, `VDDSHV3` = 3.3 V, WiFi) | **YES** | PHYTEC Q3 |
| **The R2 schematic does not exist** | **YES** | Stages B–E — months, not a purchase |
| ~~Will JLCPCB accept the 270-pin consigned module on a custom footprint~~ | ~~soon~~ | **Gone with the `PCM-071` switch** — nothing is consigned |
| Panel model | no — deferred with touch/pen | read it off the tail/back label |
| R1 firmware + gateware untested on hardware | no | needs the ISE VM (192.168.56.102, currently down) |

**Nothing is ordered until the remaining `YES` rows are answered** — now `PCM-071` price/MOQ,
orderable variants, and the schematic existing.

### Answered, so no longer open

- DPI ingest gateware — **exists and runs** (`vin_dpi.v`, `SRC_DPI`).
- DPI max pixel clock — **165 MHz**, TRM Table 12-361, vs 127 MHz needed at 75 Hz.
- 18-bit RGB666 bit mapping — **identical to Caster's**, TRM Fig. 12-471.
- ~~`BOOTMODE` strap conflict — **avoided entirely by 18-bit mode**.~~ **Reopened and re-closed
  2026-08-14, with a correction and a new requirement.** 18-bit mode does *not* avoid it entirely:
  TRM Fig. 12-471 shows the video port driving `DATA[17:0]`, and `L-1038e.A5` Table 31 puts
  `DATA17`/`DATA16` on `BOOTMODE_9`/`BOOTMODE_8` — i.e. **`DPI_R7` and `DPI_R6`, two of the
  eighteen**. (24-bit mode would have used all eight strap pins, which is what the original claim
  was really about.) `BOOTMODE[9:3]` is the *primary boot mode* field, so this matters.
  **New hard requirement out of it: `+3V3` must be up before the SoM leaves reset**, or the FPGA's
  unpowered input clamps drag `BOOTMODE_9` low and the module boots from the wrong device. Firmware
  ordering, since §5 of `docs/power.md` says enables are not interlocked. Facts §3.1.
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
**→ Answered 2026-08-14: 128.6 mW ‡ and ~150 ms ‡. Proceeding** — see the note under the power
budget for why the in-between result is still a proceed.

**~~Fallback:~~ `T113-S3`** — **no longer live**, since the gate above cleared. Kept for the
record: dual Cortex-A7 with 128 MB DDR3 in package, JLCPCB catalogue (`C5197687`, $5.60), LCD
controller to 1920×1080; it would have removed consignment, the cut-out and the boost stage in one
move, at the cost of the risk that mattered most — **suspend-to-RAM support on mainline Allwinner
is weak**, and that is the entire power architecture.

### Follow-up enquiry — ready to send

Answers received have opened four new asks, three of which block work now.

> 1. **Price, MOQ and lead time for `PCM-071`** at 1, 10 and 100 pieces. Your quote of 2026-08-13
>    covered `PCL-071-001-R`; we have since moved to the connectorised module, largely because the
>    solder-down part is reel-only in reels of five.
> 2. **In Suspend-to-RAM, what state are the two Gigabit Ethernet PHYs in, and can they be held
>    in power-down?** Your report's resume log re-initialises both `am65-cpsw-nuss` interfaces.
>    Our product uses no Ethernet at all, and at 128.6 mW the module is now the largest consumer in
>    our reading state, so this is the first place we would look for headroom.
> 3. **Which `X1` pin is BTN1 on the phyBOARD-Lyra**, and which WKUP-domain GPIOs reach the
>    connector? Your report proves a GPIO edge can wake Deep Sleep; we need to know which pin to
>    route it to.
> 4. Any timeline for **MCU-Only mode** support in the BSP, since the M4 demo firmware currently
>    prevents measuring it?

(Question 3 also decides `docs/mcu.md` §5.5 — whether the page-turn buttons can move from the
housekeeping MCU onto SoM GPIO and arrive as `gpio-keys` events, which is what
`Project_description.md` prefers.)

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

### Stage C progress — capture

Project: `pcb/r2-mainboard/`, KiCad 10 native. **`pcb/mainboard/` (R1, KiCad 8) is
read-only** — opening it in KiCad 10 upgrades it irreversibly; copy out, never
save in.

Working loop, agreed with the hardware owner: **assistant draws → owner reviews
and edits in Eeschema → assistant reviews the edits back and redraws.** Once a
sheet has been saved in Eeschema its `.kicad_sch` is the source of truth and is
patched surgically; the `tools/gen_*.py` generators are not re-run over it.

| WP | Sheets | Drawn | Reviewed by owner | Notes |
| --- | --- | --- | --- | --- |
| WP1 | `battery` | yes | **yes — round 1 done** | `manual-analysis/Analyse_battery.md` → answered in `docs/battery.md` §10; four fixes applied |
| WP2 | `power` | yes | **yes — round 1 done** | `manual-analysis/Analysis_power.md` → answered in `docs/power.md` §10. **The `TPS22965` load switch is deleted** — the boost already has true output disconnect; layout guidelines written (§11) |
| WP3 | `mcu` | yes | **yes — round 1 done** | `manual-analysis/Analysis_mcu.md` → answered in `docs/mcu.md` §10. `C42` deleted (Figure 15 asks for no `VBAT` cap); page buttons → `EVQPLHA15` for **500 k cycles** instead of 100 k; layout guidelines written (§11). Opened a real gap: **the MCU has no field-update or brick-recovery path** (§5.7) |
| WP4 | `epd`, `epd_power`, `power_mon` | yes — ported from R1 | **yes — round 1 done, accepted as a 1:1 port** | `manual-analysis/Analysis_epd_files.md` → answered in `docs/epd-port.md` §9. `epd`/`epd_power` provably net-identical to R1; `power_mon` differs in 4 intended groups. **No schematic change.** Two items opened: keep the panel adapter board for now (the panel model is still deferred), and `J3` (16p) is probably droppable once the panel is chosen |
| WP5 | `fpga_ddr`, `fpga_io`, `fpga_config` | **yes** | — **waiting on owner** | `docs/fpga.md`. All three drawn plus the **root sheet wired**. Verified against the gateware by `tools/check_ucf.py`: 113 constrained balls, **0 failures**. Corrected two documented errors (the FPGA is an **XC6SLX16**, not LX9; R1 fits a **1 Gb** DRAM, not 4 Gb). Bank 3 moved 1.35 V → **1.5 V** (`LVCMOS15`/`SSTL15` have no 1.35 V form), which reached back into `power`, `power_mon` and `fpga_config`. `fpga_config` gains the SPI NOR, master-SPI strap, and **IO2/IO3 wired to `N12`/`P12`** so x4 boot stays a software change. Found three signal groups the board wires that Caster does not implement — which settles `J3` (§2.1) |
| WP6 | `frontlight`, `io_expansion` | no | — | FL driver, unpopulated touch/pen FPC, microSD |
| WP7 | `dpi_in` | no | — | the 22-signal link. **Unblocked 2026-08-14** — `L-1038e.A5` Table 31 has the full `X1` DPI pin map. First job on this sheet is the `BOOTMODE` question above, not the wiring |
| WP8 | `som` | no | — | **held last.** A **2 × `BTH-060-01-L-D-A-K-TR`** footprint (240 pins, 0.5 mm), not a `PCL-071` landing pattern — constraint 1, revised 2026-08-13. No PCB cut-out any more. **Unblocked 2026-08-14** by the same manual: `VIN` on A1/A2/A3, `VBAT` on B2, full pinout in Tables 7–10 |

**Root sheet is wired** as of WP5 (2026-08-13). `tools/wire_root.py` stubs each of
the 187 sheet pins and attaches a local label; a local label on the root *is* a
root-sheet net, so same-named pins are one net. Wires would have been several
hundred crossings across 13 boxes and unreadable. **75 names joined, 34 still
one-sided** — 22 `DPI_*` waiting on WP7, and 12 waiting on WP8 — each checked
against a table of expected-dangling names, so anything dangling and *not* in
that table is reported as a finding. `docs/fpga.md` §8.

Wiring it exposed a direction error the split nets had been hiding: `FPGA_CLK33`
was declared `input` on both `fpga_io` and `fpga_config`, though `X1` is on
`fpga_config` and the net leaves it. Two `input`s meeting is the one interface
shape combination on this board that is never legitimate.

Whole-project ERC as of 2026-08-13: **387 violations, of which 282 are
`footprint_link_issues`** (standing ask 3, the owner's broken library tables).
Excluding those: **105**, down from 295 before the root was wired.
**Read the JSON report (`--format json`), not the text one** — the text report
files `footprint_link_issues`, `isolated_pin_label` and `four_way_junction` under
`***** Sheet /` no matter which child sheet the item is really on.

By type, with everything accounted for:

| Type | n | What it is |
| --- | ---: | --- |
| `isolated_pin_label` | 68 | the 34 interfaces waiting on WP7/WP8, counted at both ends |
| `power_pin_not_driven` | 15 | rails with no `PWR_FLAG`; `+DRAM_VREF` genuinely has no driver |
| `four_way_junction` | 11 | R1-inherited geometry, style only |
| `label_dangling` | 5 | the same pending interfaces (`USB_D*`, `FPGA_S*`) |
| `multiple_net_names` | 3 | 2 from the DRAM symbol's `VDD`/`VSS` pin names, 1 on `epd_power` |
| `lib_symbol_mismatch` | 2 | library-table artifacts; the embedded copies are byte-identical |
| `pin_to_pin` | 1 | the `M1` mode strap hard-tied to GND, which UG380 requires |

Per sheet: `/fpga_ddr/` 4 (one *fewer* than R1's 5 for the same sheet),
`/fpga_config/` 2, `/epd/` 2, `/epd_power/` 6, `/power_mon/` 5, and **`/power/`
0, `/mcu/` 0, `/battery/` 0, `/fpga_io/` 0.** `docs/power.md` §13 and
`docs/mcu.md` §13 carry the older breakdowns; `docs/fpga.md` §10 has this one.

Standing asks for the owner, carried across sessions:

1. ~~Delete the `+3V3_AON` `PWR_FLAG` at (360.68, 205.74) on `battery.kicad_sch`.~~
   **Withdrawn 2026-08-11 — keep it.** Once ask 2 was done, `U10` drives
   `+3V3_AON_DCDC` and the only thing feeding `+3V3_AON` is `power_mon`'s passive
   shunt, so that flag is now the net's sole ERC driver. Deleting it would turn
   one warning into `power_pin_not_driven` errors on the STM32G0 and all three
   `INA3221`s. The `pin_to_pin` violation is gone anyway — the rename fixed it.
   `docs/power.md` §9.
2. ~~Rename `U10`'s output on `power.kicad_sch` to `+3V3_AON_DCDC`.~~ **Done by
   the owner**, 2026-08-11 save. Verified in the exported netlist.
3. Fix KiCad's **global** library tables (Preferences → Configure Paths →
   `~/Apps/kicad-10.0.4/usr/share/kicad/`). They still point at a dead AppImage
   mount, which is the sole cause of the ~208 `footprint_link_issues`. Outside
   the repo, so not the assistant's to change. **Still open.**
4. New, from WP2: two items on `power` need a bench measurement once there is
   hardware — how fast `+5V_DCDC` decays when the boost is disabled, and how far
   `+VSYS` dips when the boost's ~2.4 A pre-charge starts with the cell near
   3.3 V. Both are consequences of deleting the load switch. `docs/power.md` §9.

Recommended, not yet done: retype `QON` in `r2.kicad_sym` from `input` to
`passive` (clears a permanent `pin_not_driven`); deferred because
`battery.kicad_sch` embeds a copy of the symbol.

---

## Power budget

Basis: 1S 5000 mAh at 3.7 V = 18.5 Wh, ~92 % usable, ~92 % conversion ⇒ **~15.7 Wh delivered**.
‡ = measured or from a datasheet; everything else is an estimate to be replaced in Stage B.

| Reading-state consumer | Estimate |
| --- | --- |
| **SoM Suspend-to-RAM, at its 5 V `VIN`** | **128.6 mW ‡** — measured on `PCM-071`, Facts §4.6 |
| FPGA core + I/O, scan stopped, hold asserted | 50–100 mW |
| DDR3L self-refresh | 10–20 mW (‡ `IDD6` 7 mA @ 1.5 V, Facts §6) |
| STM32G0 in STOP + RTC, charger, gauge | ~6 mW |
| EPD HV | 0 ‡ |
| **Reading-state total** | **~195–255 mW** |

The old SoM line read "50–100 mW" plus a separate "— boost conversion loss ~10 %" row. Both are
gone: the measurement is at the module's `VIN`, and the **basis line above already includes ~92 %
conversion**, so that extra row was double-counting. If you would rather carry the boost loss
explicitly, drop the 92 % from the basis instead — do not do both.

| Mode | Average | Hours from 15.7 Wh |
| --- | --- | --- |
| Reading, one page / 30 s | ~295–355 mW | **~44–53 h** |
| Reading, idle | ~195–255 mW | ~62–81 h |
| Active — SoM awake, video streaming, panel driving | ~2.5 W | ~6 h |
| Standby — SoM off, FPGA rails off, MCU in STOP | ~10 mW | weeks |

Against R1's 6.4 h baseline that is roughly **7–8×**, and against
`Project_description.md`'s stated target of **15–20 h active reading it is ~2.5×**. Days of heavy
reading rather than one evening. Not a Kobo month — that needs the FPGA out of the idle path
entirely — but comfortably past what the product asks for.

**The measurement moved this table, and not in our favour.** The estimate was 50–100 mW; the
truth is 128.6 mW. Idle reading drops from ~67–116 h to ~62–81 h, and one-page-per-30-s from
~47–67 h to ~44–53 h. More importantly it **inverts the optimisation priority**: the SoM is now
**51–66 % of the whole reading-state budget**, larger than the FPGA, where the two were previously
assumed comparable. The one identified lever is the module's two Gigabit Ethernet PHYs, which
Glider never uses — Facts §4.6, and question 3 of the follow-up enquiry below.

**On the decision rule.** It reads "Deep Sleep ≤ ~100 mW and resume ≤ ~500 ms → proceed; above
~250 mW or ~1 s → the architecture is wrong". 128.6 mW lands in the **gap the rule never
legislated**. Recording the call explicitly rather than letting it look satisfied: **proceed**,
because the abort threshold is untouched, resume beat its threshold by 3×, and the product target
retains ~2.5× margin.

---

## Risks

| Risk | Impact | Closes at |
| --- | --- | --- |
| ~~Module Deep Sleep > 250 mW or resume > 1 s~~ | ~~architecture is wrong; fall back to `T113-S3`~~ | **CLEARED 2026-08-14. 128.6 mW ‡ and ~150 ms ‡** — Facts §4.6. The `T113-S3` fallback is no longer live |
| ~~PHYTEC will not sell 1–2 units, or `PCL-071` is priced out of reach~~ | ~~same~~ | **Realised, 2026-08-13.** €281 each with a reel-only MOQ of 5 = ~€1 405 for one prototype. Answered by moving to `PCM-071` (constraint 1) |
| ~~JLCPCB refuses the consigned module or its custom footprint~~ | ~~forces PCBWay, or hand assembly~~ | **Gone with the `PCM-071` switch** — nothing is consigned, and the mating connector is ordinary LCSC stock |
| ~~A soldered-down module cannot be swapped if the board is wrong~~ | ~~one bad board = one dead module~~ | **Gone with the `PCM-071` switch** — the module unplugs |
| `PCM-071`'s DPI pin numbers are unknown | blocks WP7 and WP8 | needs the `PCM-071` hardware manual — the `PCL-071` numbers in L-1041e Table 30 do **not** carry over |
| `PCM-071` price and MOQ never quoted | could reopen the whole decision | ask Emma; the quote covered `PCL-071-001-R` only |
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
