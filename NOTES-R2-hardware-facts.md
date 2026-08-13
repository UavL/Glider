# Glider-R2 — verified hardware facts

Branch `Board-Design`. Last updated **2026-08-03**.

This file is the evidence base for R2: every fact with the source that proves it. The companion
`NOTES-R2-plan.md` says what to *do*; this says what is *known*. It replaces the earlier
`NOTES-R2-som-selection.md` and `NOTES-R2-procurement.md`, which recorded a lot of reasoning that
has since been settled or superseded.

**Rule for this file:** nothing goes in without a citable source — a datasheet table, a manual
section, a file and line in this repo, or a catalogue query with a date. Estimates are marked.

---

## Terms

| Term | Meaning |
| --- | --- |
| **DPI** | Display Pixel Interface — MIPI's name for the parallel RGB bus (data lines + pixel clock + DE + HSYNC + VSYNC). Also called "RGB parallel" or "TTL". Three names, same pins. |
| **OLDI / LVDS** | Serialised differential display link. 4 pairs, 7 bits per pair per clock. Fewer wires, but the receiver must lock to the clock before any pixel is valid. |
| **SoM / SOM** | System on Module — a small board with the processor, RAM and storage, mounted on a carrier board you design. |
| **DSC** | PHYTEC's "Direct Solder Connect" — a SoM variant with a solderable footprint instead of connectors. |
| **DSS / DISPC / VP** | TI's display subsystem, its display controller, and its Video Ports. VP1 drives OLDI; **VP2 drives the parallel DPI output**. |
| **Deep Sleep** | TI's suspend-to-RAM state: SoC off, DDR in self-refresh, context restored on wake. |
| **LCSC** | The component distributor JLCPCB assembles from. A part not in LCSC's catalogue must be *consigned* (bought separately and shipped to JLCPCB). |

---

## 1. The constraint everything else follows from

Caster has **no image framebuffer**. The 3.0 MB it keeps in DDR3 is per-pixel *waveform state*
(`frame_bytes = tcon_hact * 4 * tcon_vact * 2`); the target colour comes from the live video
stream every frame. `caster.v` ties `vin_ready = s1_active`, so **the video input is consumed in
lockstep with the panel scan** — input frame rate and panel frame rate are the same number.

| Panel rate | Pixels/frame (1528×1110 total) | Required pixel clock |
| --- | --- | --- |
| 75 Hz | 1.696 M | **127 MHz** |
| 60 Hz | 1.696 M | 102 MHz |
| **50 Hz (operating target)** | 1.696 M | **85 MHz** |

Decision: **design the link for 75 Hz, operate at 50 Hz.** Scaling down is free; designing up
later is not.

---

## 2. Video link — the receiver already exists and already runs

**Caster's Spartan-6 target has a complete DPI input**, and it is the path the R1 board runs on
today: the ADV7611 decodes HDMI and hands the FPGA plain parallel RGB.

| Evidence | Shows |
| --- | --- |
| `Caster/rtl/spartan6/vin_dpi.v` | Full receiver: `IBUFG` + `DCM_SP`, IOB-packed capture registers, DE-edge phase detector choosing between two pixel alignments, 2:1 pixel pack so the core runs at half the pin rate |
| `vin.v:101` | Instantiated as `SRC_DPI = 3'd1` in the source mux, alongside `SRC_INTERNAL` and `SRC_FPDLINK` |
| `top.v:56-60` | Ports `DPI_PCLK`, `DPI_DE`, `DPI_VSYNC`, `DPI_HSYNC`, `DPI_PIXEL[17:0]` |
| `constraint.ucf:16-17` | `TIMESPEC TS_DPI_CLK = PERIOD "DPI_CLK" 165 MHz HIGH 50%` |
| `constraint.ucf:228-255` | All 22 pins placed, `IOSTANDARD = LVCMOS33`, commented with the RGB bit each carries |
| `pcb/mainboard/tmds_in.kicad_sch` | The 22 `DPI_*` nets originate on the ADV7611 sheet and land in `fpga_io.kicad_sch` |

**Consequences:** there is no DPI gateware to write. The bus is **18 bits (RGB666), 22 signals
total** — `vin.v:117-123` expands to RGB888 by replicating each channel's top two bits, and the
panel is mono or 4-bit grey regardless. 165 MHz is already the declared timing target.
FPD-Link/LVDS ingest exists too (`vin_fpdlink.v`, 6 lanes, `SRC_FPDLINK`), so routing OLDI as a
fallback costs nothing in gateware — but note the existing module is FPD-Link, and OLDI/JEIDA
differs in bit mapping, which is a parameter change rather than a rewrite.

### 2.1 The AM62x side matches bit for bit

From the **AM62x TRM (SPRUIV7C)**, §12.9.1.2.1 "DSS Parallel Interface":

- **VP2** drives the parallel output: *"Parallel MIPI DPI 2.0: RGB **16/18/24-bit** output with
  separate sync signals."*
- Table 12-361, `DSS_DPI2_PCLK`: ***"The maximum interface frequency is 165 MHz."*** This
  settles the conflict between PHYTEC's "200 MHz" marketing and the datasheet's 165 MHz — the
  200 MHz figure belongs to the **OLDI** path (TRM: "Single Link Mode – 1920×1440@60fps with a
  200 MHz pixel clock"). **DPI is 165 MHz**, against 127 MHz needed at 75 Hz: **30 % headroom.**
- **Figure 12-471, "DISPC Video Port Pixel Data – 18-bit RGB Active Matrix"** gives the mapping:
  `data[0]=B0 … data[5]=B5`, `data[12]=R0 … data[17]=R5`, i.e.

  | Bits | Channel |
  | --- | --- |
  | `DATA[5:0]` | Blue |
  | `DATA[11:6]` | Green |
  | `DATA[17:12]` | Red |

  **This is exactly Caster's format.** `vin.v` reads `dpi_pixel[17:12]` as R, `[11:6]` as G,
  `[5:0]` as B. No remapping, no glue.

### 2.2 The BOOTMODE hazard is closed by using 18-bit mode

`VOUT0_DATA16..23` are shared with `GPMC0_AD8..15` = `BOOTMODE_8..15`, each with a 100 kΩ pull on
the module, and PHYTEC footnotes all eight *"should not be driven during reset"*
(L-1038e.A5 Table 31).

This looked like a serious problem: under **24-bit** RGB888 the red channel is `DATA[23:16]`, so
Caster's `R7..R2` would need `DATA23..18` — six strapped pins, three of them pulled *down*, facing
an FPGA whose I/O carry weak pull-ups during configuration.

**In 18-bit mode the DSS drives only `DATA[17:0]`.** Of the strap group only `DATA16` and
`DATA17` are used, and both carry **100 kΩ pull-*ups*** on the module — which a Spartan-6
configuration pull-up agrees with. `DATA18..23` are left unconnected. **The hazard disappears; no
sequencing workaround, no series resistors, no bitstream pull tricks.**

*Not yet chased:* the exact `DSS_VP2_CONFIG` field that selects 16/18/24-bit. In Linux this is
driven by the panel's `bus_format` (`MEDIA_BUS_FMT_RGB666_1X18`) through the `tidss` driver —
a device-tree property, not a board change.

---

## 3. The compute module

**Chosen: PHYTEC `PCM-071`, phyCORE-AM62x** — the **connectorised** variant. Changed 2026-08-13
by the hardware owner; `PCL-071` (solder-down) was the previous choice and is now the *second
revision* target. `NOTES-R2-plan.md` constraint 1 carries the reasoning; in short, PHYTEC quoted
`PCL-071-001-R` at €281 @1–9 with a **reel-only MOQ of 5**, the price includes ~€190 of memory-
shortage surcharge, and a soldered module would have to be consigned to the fab in China. The
board is still fully machine-assembled — the mating connectors are LCSC stock — and only the
module is plugged in afterwards. **The first prototype is allowed to be thick.**

The two variants are the same electrical module; what changes is how it attaches, so the DPI link,
the rails and the FPGA side of the design are unaffected. Only `som.kicad_sch` (WP8) and the pin
assignments feeding `dpi_in` (WP7) depend on which one is fitted, and neither is drawn yet.

### 3.1 `PCM-071` — what is known and what is not

| Property | Value | Source | Confidence |
| --- | --- | --- | --- |
| Dimensions | 43 × 32 mm; ~7.6 mm mated stack | prior note, this file | carried over |
| Attachment | **240 pins as 2 × 120-pin 0.5 mm** board-to-board | PHYTEC product page, 2026-08-13 | verified |
| Module-side connector | `BSH-060-01-L-D-A-TR` ×2 (Samtec Razor Beam) | prior note | **reconcile** — the product page names the pair as `ASP-205225-01` |
| Board-side mate | **`BTH-060-01-L-D-A-K-TR` ×2**, LCSC `C3646540`, 63 in stock, $5.56 | LCSC, 2026-08-03 | verified |
| Parallel display | **"Parallel Display (24bpp)" is listed** — 18 bpp is a subset, so the DPI link survives the change | PHYTEC product page, 2026-08-13 | verified |
| **DPI pin assignments** | — | — | **NOT KNOWN.** `PCL-071`'s are in L-1041e.A3 Table 30; `PCM-071` has its own manual and its own numbering |
| `VIN` range | assumed 4.5–5.5 V, same as `PCL-071` | — | **inferred, needs the manual** |
| `VDDSHV3` 1.8/3.3 V selection | assumed present, default 3.3 V | — | **inferred, needs the manual** |
| PCB cut-out | **not required** — this is the advantage of the connectorised part; `PCL-071` needs a ~14.4 × 22.4 mm hole for its bottom-side components | L-1041e.A3 Fig. 11 NOTE 2 | verified for `PCL` |
| Price and MOQ | **unquoted** — PHYTEC's mail covered `PCL-071-001-R` only | — | **ask Emma** |

**Neither PHYTEC manual is in this repo** (`L-1041e`, `L-1038e` were read online). The `PCM-071`
hardware manual has to be obtained before WP7 or WP8 can be drawn — it is the sole source for the
three "needs the manual" rows above, and the DPI pin numbers are the whole content of WP7.

### 3.2 `PCL-071` — the second-revision target, kept for reference

| Property | Value | Source |
| --- | --- | --- |
| Dimensions | **40.8 × 40.8 × 2.84 mm** | L-1041e.A3 Table 3 |
| Attachment | **270 pins, 0.8 mm pitch** — castellated half-holes round the perimeter (pins 1–188) plus inner SMD pads (189–270) | L-1041e.A3 Figs 10, 12 |
| **Requires a PCB cut-out** | ~**14.4 × 22.4 mm, R1.2** — *"Remove PCB material to accommodate components on bottom side of SOM"* | L-1041e.A3 Fig. 11 NOTE 2 |
| Input voltage | `VIN` **4.5–5.0–5.5 V** — needs a boost from a 1S cell | L-1041e.A3 Table 4 |
| Idle | **1.6 W** | L-1041e.A3 Table 3 |
| SoC / RAM | AM6254 (4× Cortex-A53), **DDR4** (2 GB default, 4 GB max), eMMC 32 GB default | product page, block diagram |
| DPI pins | `PCLK` 27, `DE` 28, `VSYNC` 29, `HSYNC` 30, `DATA0..15` on 46–31, `DATA16..23` on 12–19 | L-1041e.A3 Table 30 |
| I/O voltage | `VDDSHV3` domain, **jumper-selectable 1.8 V / 3.3 V, default 3.3 V** — matches Caster's `LVCMOS33`, **no level shifting** | L-1038e.A5 Table 6, Table 31 footnote 1 |

Everything in the table above stays true of `PCL-071` and is what a second revision goes back to.
The two properties that made it the first choice — 2.84 mm instead of a ~7.6 mm mated stack, and
one machine-assembled board with nothing plugged on — are still real; they were outweighed by a
€1 405 minimum order and a consignment shipment for a prototype that needs one module.

---

## 4. Power — what is measured, and by whom

### 4.1 TI SoC-level (SPRADG1, Feb 2024, on TI's Starter Kit EVM)

| State | Power | Section |
| --- | --- | --- |
| Active workloads (Dhrystone → glmark2 → concurrency) | 675 – 1078 mW | §4.2–4.7 |
| OS Idle @ 1000 MHz | **343.59 mW** | §4.1.1.2.5 |
| MCU Only | **54.91 mW** | §4.1.3.2 |
| **Deep Sleep, DDR4, 0.85 V `VDD_CORE`** | **24.44 mW** | §4.1.2.2 |
| Deep Sleep, DDR4, 0.75 V `VDD_CORE` | 32.51 mW | §4.1.2.2 |
| Deep Sleep, **LPDDR4**, 0.75 V | 14.62 mW | §4.1.2.2 |

⚠ **The applicable number is 24.44 mW, not 14.62 mW.** The phyCORE uses **DDR4**. Earlier notes
in this project quoted the LPDDR4 column — roughly half the real figure.

### 4.2 What SPRADG1's numbers do and do not cover

They are **SoC rails only, on TI's own EVM** (§3.2 "Starter Kit EVM Information", §3.3 "Starter
Kit EVM Power Rails" — the measured rails are `VDD_CORE`, `VDDR_CORE`, `VDD_DDR4`,
`SoC_DVDD1V8`, `SoC_DVDD3V3`, `VDDA_CORE`). They exclude everything else on a SoM: the PMIC's own
quiescent draw, the DDR4 devices' board-level self-refresh, eMMC, NOR flash, EEPROM, RTC, the
voltage supervisor and the Gigabit Ethernet PHY.

TI says so directly (§5.3): *"Board to board variance involving Pull-Up, Pull-Down resistors
coupled to peripheral components will reflect varying power measurements between AM62x board
variants."*

The gap is not small. PHYTEC's module idles at **1.62 W** (L-1038e.A5 Table 4: 324 mA at 5 V)
against TI's 343.59 mW for the bare SoC — **~1.28 W of module overhead at idle.**

### 4.3 Module-level comparison point

Toradex publishes a **measured 59.7 mW** suspend figure for the Verdin AM62 — a different module,
same SoC family. That is the only whole-module number in existence for an AM62x SoM, and it is
~2.4× TI's SoC-only DDR4 figure. **Expect the phyCORE in Deep Sleep to be 50–100 mW.**

### 4.4 The two things no document states

Both were checked directly in the sources, not assumed:

1. **PHYTEC publishes no suspend/Deep Sleep figure** for either module, in either manual revision.
2. **No numeric wake latency exists anywhere.** SPRADG1 §4.1 is power tables only — OS Idle at
   seven frequencies, Deep Sleep, MCU Only — and contains no timing at all (the only duration in
   the document is "tests were run at 60 seconds"). The TRM describes the *ordering* (§: Standby
   has the lowest wakeup latency, Partial I/O the highest; Deep Sleep keeps DDR in self-refresh
   "so wakeup events do not require a full cold boot, significantly reducing wakeup latencies")
   but gives no number — because it is a software property: the boot ROM runs, detects the
   resume, and branches to peripheral context restore from DDR, so it depends on how much context
   the BSP saves.

**These two gaps are the entire remaining risk in the architecture**, and both need PHYTEC or a
bench measurement. Nothing further in TI's documentation will close them.

### 4.5 TI's low-power mode taxonomy (SPRAD41 Table 2-2)

Useful because the reading state maps onto exactly one of these:

| Mode | Wake sources | State |
| --- | --- | --- |
| Standby | any SoC interrupt | contents fully preserved, A53 in WFI, DDR self-refresh. Fastest resume, highest power |
| MCU Only | Deep Sleep events + any MCU-channel interrupt | as Deep Sleep but the M4F keeps running |
| **Deep Sleep** | GP/RTC timers, UART, I²C, MCU GPIO0, I/O daisy chain, USB | **the reading state.** Core context lost and saved to DDR; DDR in self-refresh; boot ROM restores on wake |
| Partial I/O | CANUART bank pins only | entire SoC off except that one I/O bank. Lowest power, highest latency — a candidate for *standby*, not for reading |

---

## 5. Sourcing — the JLCPCB/PCBWay picture

Queried 2026-08-03 against the LCSC/JLCPCB catalogue.

**The decisive asymmetry: LCSC stocks DDR3/DDR3L and does not stock LPDDR4.** Every modern
low-power application processor is an LPDDR4 part, which is why "bare SoC soldered to the main
board, fully assembled by JLCPCB" is not reachable with an AM62x-class device.

| Part | Role | LCSC | Stock | US$ @1 |
| --- | --- | --- | --- | --- |
| `XC6SLX16-3FTG256` | the FPGA, unchanged from R1 — **corrected, see below** | re-query | — | — |
| `MT41K64M16TW-107` | R1's DDR3L | C2060943 | 1 949 | 4.49 |
| `W25Q128JVSIQ` | FPGA config flash — the **only JLC Basic part** in the list | C97521 | 110 435 | 1.22 |
| `BTH-060-01-L-D-A-K-TR` ×2 | `PCM-071` mating connector — **now the chosen route**, §3 | C3646540 | 63 | 5.56 |
| `STM32G0B1CBT6` | housekeeping MCU | C2847904 | 12 153 | 1.75 |
| `BQ25896RTWR` | charger with power path — **thin stock, find a second source** | C181475 | 127 | 1.40 |
| `MAX17048G+T10` | fuel gauge | C2682616 | 4 403 | 2.32 |
| `TPS62840DLCR` | ultra-low-Iq buck | C2071859 | 5 531 | 0.94 |
| `T113-S3` | fallback SoC, **128 MB DDR3 in package** | C5197687 | 1 810 | 5.60 |
| `AXP2101` | matching PMIC for the fallback | C3036461 | 1 443 | 1.40 |
| — | 200-pin SO-DIMM socket | **absent** | — | — |
| — | any multi-touch capacitive controller IC | **absent** | — | — |

Notes:
- **The FPGA is an LX16, not an LX9. Corrected 2026-08-12 in WP5.** This row previously read
  `XC6SLX9-2FTG256C`, LCSC `C95351`, 1 163 in stock, $6.10 — a price and stock figure for the
  wrong device. The gateware targets `xc6slx16-ftg256-3` in four independent places
  (`Caster/rtl/spartan6/caster.xise` `Device`/`Package`/`Speed Grade`, `par/ise_flow.sh`
  `-p xc6slx16-ftg256-3`, `par/ise_run.txt`, and `ipcore_dir/s6_ddr3/user_design/mig.prj`
  `<TargetFPGA>xc6slx16-ftg256/-3`), and R1's own schematic says `XC6SLX16-FTG256`. An LX9 is
  **not** a drop-in: the MIG's `C3_SMALL_DEVICE` parameter (`s6_ddr3.v:234`, currently `"FALSE"`)
  exists specifically for "all packages of xc6slx9", so an LX9 needs the memory controller
  regenerated in ISE. **LCSC stock and price still need re-querying for the LX16** — this was
  found while the catalogue was unreachable.
- **Every R1 part is in the catalogue.** The Caster half of the board could be assembled today.
- **No touch controller exists as a loose IC** — `GT911`, `GT9110`, `FT5316`, `FT6336`, `CST328`,
  `CST816`, `GSL1680` all return nothing. That is not a catalogue gap: the controller ships bonded
  to the touch film's flex (chip-on-flex). **R2 carries an FPC connector, not a controller IC.**
- **JLCPCB accepts consigned parts, including from overseas.** They audit and warehouse them, but
  explicitly do not test them and accept no responsibility for defects; JLC-stocked and consigned
  stock cannot be mixed for the same part. This is the route for `PCL-071`.
- Almost everything is a JLC **Extended** part (~$3 per unique part setup fee). With R1's 65
  unique parts that is ~$200 per order regardless of quantity — worth substituting Basic passives.
- `W25Q32JV` is **Obsolete** at DigiKey while LCSC still shows stock. Both are true; do not design
  it in.

---

## 6. The panel

**Model still unidentified.** The photo of the dev kit's flex shows the flex's own components, not
the model marking — that is usually printed further along the tail or on a label on the panel's
back. The firmware runs 1448 × 1072, which is the 6″ 300 ppi family: `ED060KC1`, `ED060KD1`,
`ED060KG1`, `ED060KH*`, or Kaleido colour `EC060KH1/KH3/KH5` (README panel table).

**What the photo did establish:** the flex carries a **Macronix `MX25U4033E`** — a 4 Mbit
(512 KB), 1.8 V serial NOR flash. This is the panel's **waveform store**: E Ink panels ship their
waveform LUT in a small serial flash on the tail. Useful to know it exists; R2 must keep whatever
R1 does about it, and the 1.8 V supply for it.

The green board in the same photo is one of this repo's own adapters (`pcb/35p-adapter-a/`),
carrying `J3`.

Suppliers, for the touch/frontlight/digitizer enquiry when that becomes live: **Good Display**
(<https://www.e-paper-display.com>, sales@e-paper-display.com) sells panels with touch and
frontlight already bonded and quotes small quantities; **Unisystem** (Poland) is the EU-shipping
alternative; E Ink's own kit shop is a price reference.

---

## 7. Sources

- **TI, *AM62x Sitara Processors Technical Reference Manual*, SPRUIV7C** (rev. Nov 2025) —
  §12.9.1.2.1 DSS Parallel Interface, Table 12-361 (`DSS_DPI2_*` signals, **165 MHz max**),
  Figs 12-470/471/472 (16/18/24-bit RGB bit mappings), §29.8xx Low Power Modes.
  <https://www.ti.com/lit/pdf/SPRUIV7>
- **TI, *AM62x Power Consumption*, SPRADG1** (Feb 2024) — §3.2/3.3 EVM scope, §4.1.1 OS Idle,
  §4.1.2.2 Deep Sleep, §4.1.3.2 MCU Only, §5.3 board-variance caveat.
  <https://www.ti.com/lit/an/spradg1/spradg1.pdf>
- **TI, *Enabling Low Power Embedded Systems With AM62x Processors*, SPRAD41** (May 2022) —
  Table 2-1 power-management features, **Table 2-2 low-power modes and wake sources**.
  <https://www.ti.com/lit/wp/sprad41/sprad41.pdf>
- TI, *AM625 datasheet*, SPRSP58C — DSS timing tables; "Up to 165MHz pixel clock … OLDI (4 lanes
  LVDS - 2x) and DPI (24-bit RGB LVCMOS)".
- **PHYTEC, *phyCORE-AM62x HW Manual*, L-1038e.A5** — Table 3 (1.62 W idle), Table 4 (`VIN`
  4.5–5.5 V, 324 mA idle / 651 mA loaded), Table 6 (`VDDSHV3`, jumper J4), Tables 7–10 (connector
  X1 columns A–D), Table 31 (VOUT pinout, BOOTMODE sharing, "not driven during reset").
- **PHYTEC, *phyCORE-AM62x DSC HW Manual*, L-1041e.A3** — Table 3, Table 4, Table 30 (VOUT pads),
  Figs 10–13 (landing pattern, cut-out NOTE 2).
- PHYTEC block diagram (shows `DPI` and `OLDI/LVDS` as separate lines to the connector) and
  pin-mux tool <https://pinmux.phytec.com/>.
- Xilinx, *Spartan-6 FPGA Data Sheet: DC and Switching Characteristics*, DS162 v1.11 — Table 3
  (`CIN`, LVDS receivers on `VCCAUX` with on-die 100 Ω termination), Table 25.
- Toradex, *Verdin AM62 Power Consumption* — measured 59.7 mW module suspend.
- JLCPCB, *How to consign parts* and *Consignment Part Terms & Conditions*.
- This repo: `Caster/rtl/spartan6/{vin.v,vin_dpi.v,top.v,constraint.ucf}`,
  `pcb/mainboard/{tmds_in,fpga_io,epd,power}.kicad_sch`, `README.md` panel table,
  `NOTES-STATUS.md`.
