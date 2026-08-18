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

**Confirmed cheaper as well as more convenient, 2026-08-18.** PHYTEC quoted the `PCM-071` at
**€250.00 @ 1–9 pcs** — €31 *below* the solder-down part's unit price, and orderable singly against
a five-reel minimum. The module cost of a first prototype therefore falls from **~€1 405 to €250**.
The switch was made on convenience and consignment grounds; the price turned out to favour it too.

The two variants are the same electrical module; what changes is how it attaches, so the DPI link,
the rails and the FPGA side of the design are unaffected. Only `som.kicad_sch` (WP8) and the pin
assignments feeding `dpi_in` (WP7) depend on which one is fitted, and neither is drawn yet.

### 3.1 `PCM-071` — what is known and what is not

**The `PCM-071` hardware manual is now in `datasheets/` as
`L-1038e.A5_phyCORE-AM62x_HW Manual.pdf`** (added by the owner 2026-08-14). Its title page reads
"SOM Prod. No.: PCM-071", so it is *this* module's manual, and it closes every row that was open
when the switch was made. **WP7 and WP8 are unblocked.**

| Property | Value | Source |
| --- | --- | --- |
| Dimensions | 43 × 32 mm; ~7.6 mm mated stack | prior note |
| Attachment | **240 pins: 2 × 0.5 mm 2×60 Samtec** | L-1038e.A5 §1 |
| Module-side connector | **`BSH-060-01-L-D-A-TR` ×2** — our note was right, the product page's `ASP-205225-01` is something else | L-1038e.A5 §1 |
| Board-side mate | **`BTH-060-01-L-D-A-K-TR` ×2**, LCSC `C3646540`, 63 in stock, $5.56 | L-1038e.A5 §"Mount the SOM…"; LCSC 2026-08-03 |
| `VIN` | **5.0 V**, pins **A1, A2, A3**, draw 5 W (1 A) | L-1038e.A5 Table 12 |
| `VBAT` | RTC backup, pin **B2**, 120 nW (40 nA) | L-1038e.A5 Table 12 |
| Typical idle | **1.62 W** — corroborated by the measured 1485.7 mW, §4.6 | L-1038e.A5 Table 3 |
| DPI | **Parallel MIPI DPI 2.0, RGB 16/18/24-bit with separate syncs**, full `X1` pin map in **Table 31** | L-1038e.A5 §8.1.1 |
| I/O voltage | `X_VOUT0_*` default **3.3 V**, solder-jumper selectable to 1.8 V (§4.7) — matches Caster's `LVCMOS33`, no level shifting | L-1038e.A5 Table 31 note 1 |
| PCB cut-out | **not required** — the advantage of the connectorised part; `PCL-071` needs a ~14.4 × 22.4 mm hole | L-1041e.A3 Fig. 11 NOTE 2 |
| Price | **€250.00 @ 1–9 pcs**, variant `PCM-071-5432DE11I`, PHYTEC order code `C618992` | PHYTEC (Emma Tholey) mail, 2026-08-18 |
| MOQ | **1** | PHYTEC, confirmed to the owner 2026-08-18 |
| Lead time | **still not stated** | **open** |
| Quoted population | AM6254 quad A53 1.4 GHz + M4F 400 MHz, **2 GB DDR4, 32 GB eMMC**, 64 MB QSPI NOR, 4 kB EEPROM, Ethernet PHY, industrial temp | same mail |

#### The quoted variant is larger than this design needs

`PCM-071-5432DE11I` carries **2 GB DDR4 and 32 GB eMMC**. Nothing in R2 needs either: the SoM's
job is to run Linux and push DPI, and the framebuffer for 1872×1404 is a few megabytes. PHYTEC
said again that the price still carries the memory-shortage surcharge ("we are currently passing
on the increased memory costs directly to our customers without adding any margin") and will fall
when the market settles. **How much of the €250 that surcharge is was not stated** — the ~€190
figure quoted on 2026-08-13 was for `PCL-071-001-R` and must not be assumed to carry over. What is
safe to say is only the direction: the largest cost driver in this module is memory this design
does not use.

The manual will not answer what else is orderable — §6.1.1 and §6.1.3 both say only *"Contact our
sales team for information on the available DDR4 [/eMMC] population options"*. It is a sales
question, and worth asking before a production order rather than before the prototype: a smaller
population may carry its own MOQ, which is exactly the trap the `PCL-071` sprang.

One row of that open question is already dead, though — **`VDDSHV3` = 3.3 V is not a variant to
order.** It is solder jumper `J4` on the module and ships at 3.3 V by default (Table 6, Table 31
footnote 1). Only RAM, eMMC and the WiFi option remain genuinely open.

#### ⚠ The `BOOTMODE` overlap — settled 2026-08-14, and it is two signals, not six

`VOUT0_DATA16`–`DATA23` sit on `X_GPMC0_AD8`–`AD15`, which are **also `BOOTMODE_8`–`BOOTMODE_15`**,
each with a 100 K pull-up or pull-down on the module, and Table 31 note 2 says *"This signal should
not be driven during reset."*

**AM62x TRM (SPRUIV7C) Figure 12-471** settles how many of them 18-bit mode touches: in 18-bit RGB
the video port drives **`DATA[17:0]` only**, packed as `data[17:12]` = red, `data[11:6]` = green,
`data[5:0]` = blue (Fig. 12-472 shows 24-bit using `DATA[23:0]`, which is the case that would have
used all eight strap pins). So:

| Caster net | TRM bit | `VOUT0_` | `X1` | strap |
| --- | --- | --- | --- | --- |
| `DPI_R7` (MSB) | `data[17]` = R5 | `DATA17` | D4 | **`BOOTMODE_9`**, 100 K pull-up |
| `DPI_R6` | `data[16]` = R4 | `DATA16` | D2 | **`BOOTMODE_8`**, 100 K pull-up |
| `DPI_R5`…`R2` | `data[15:12]` | `DATA15`…`12` | A13 A12 A10 A8 | — |
| `DPI_G7`…`G2` | `data[11:6]` | `DATA11`…`6` | A11 A16 B14 B15 B9 B11 | — |
| `DPI_B7`…`B2` | `data[5:0]` | `DATA5`…`0` | B10 B7 B5 B4 B6 B12 | — |

(The `DPI_Rn` ↔ `data[n]` rows assume MSB-to-MSB alignment, which is what "the 18-bit RGB666 bit
mapping is identical to Caster's" has always meant. `DATA18`–`DATA23` are unused in 18-bit mode, so
`BOOTMODE_10`–`15` are untouched.)

**`BOOTMODE[9:3]` is the primary boot mode selection and config field** (Table 17), so these are not
spare strap bits — they choose eMMC vs OSPI vs SDIO. Two consequences for WP7, neither of which is
a wiring choice:

1. **Nothing on our board may load `DPI_R6`/`DPI_R7`.** No pull-up, no pull-down, no termination.
   PHYTEC's own guidance for *deliberately* overriding a strap is a 1 kΩ pull-up or 10 kΩ
   pull-down against their 100 K, which is the scale an accidental load would have to reach — so
   ordinary routing is not a threat, but a "helpful" resistor would be.
2. ⚠ **The FPGA's bank-1 `VCCO` (`+3V3`) must be up before the SoM *samples* boot mode.** Caster's
   DPI pins are inputs and never drive, but an FPGA whose `VCCO` is *off* clamps its inputs through
   the ESD structure to an unpowered rail — and a forward-biased clamp diode beats a 100 K pull-up,
   so `BOOTMODE_9` would latch 0 instead of 1 and the module would boot from the wrong device.

   ~~So `MCU_EN_3V3` (and `PG_3V3`) must precede `MCU_EN_5V`.~~ **Corrected 2026-08-15: that
   ordering is backwards and unsafe.** L-1038e.A5 §5.4 makes the opposite **mandatory** — "it is
   mandatory to avoid driving the I/O pins of the phyCORE-AM62x SOM when the SOM is not fully
   powered up … the peripheral carrier board power should be switched on/enabled by the `X_PGOOD`
   signal". `+3V3` *is* the rail that powers the FPGA pins facing the SoM, so bringing it up first
   is the damage case.

   Both rules hold at once because "the SoM is powered" and "the SoM samples boot mode" are
   different instants, separated by cold reset. Hold `SOM_RESET#` (→ `X_nRESET_IN`, `X1 C52`) low
   across the 5 V ramp; bring `+3V3` up only after `X_PGOOD`; then release reset. Full sequence,
   and the new `PG_SOM` signal it requires, in `docs/power.md` §5.1.

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
~2.4× TI's SoC-only DDR4 figure. ~~**Expect the phyCORE in Deep Sleep to be 50–100 mW.**~~
**Superseded 2026-08-14 by a measurement on our own variant — §4.6. The estimate was low: the
truth is 128.6 mW, 29–157 % above this range.** The extrapolation method was sound and the answer
was still wrong, which is worth remembering the next time a number is scaled from a neighbouring
vendor's module.

### 4.4 ~~The two things no document states~~ — both closed 2026-08-14

**Kept for the reasoning, not because it is still true.** Both gaps were closed by PHYTEC's
verification report; see §4.6.

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

~~**These two gaps are the entire remaining risk in the architecture**, and both need PHYTEC or a
bench measurement. Nothing further in TI's documentation will close them.~~ **They did need
PHYTEC, and PHYTEC measured them. §4.6.**

### 4.5 TI's low-power mode taxonomy (SPRAD41 Table 2-2)

Useful because the reading state maps onto exactly one of these:

| Mode | Wake sources | State |
| --- | --- | --- |
| Standby | any SoC interrupt | contents fully preserved, A53 in WFI, DDR self-refresh. Fastest resume, highest power |
| MCU Only | Deep Sleep events + any MCU-channel interrupt | as Deep Sleep but the M4F keeps running |
| **Deep Sleep** | GP/RTC timers, UART, I²C, MCU GPIO0, I/O daisy chain, USB | **the reading state.** Core context lost and saved to DDR; DDR in self-refresh; boot ROM restores on wake |
| Partial I/O | CANUART bank pins only | entire SoC off except that one I/O bank. Lowest power, highest latency — a candidate for *standby*, not for reading |

### 4.6 ‡ Measured, module level, on our own variant — the numbers that matter

**Source: `datasheets/lowpowermode_phytec.pdf`** — "Test Verification for PCM-071 (phyCORE-AM62x):
Low Power Mode Testing", PHYTEC America, executed by cbrown 2026-08-12, sent by Khalid Talash
2026-08-14. This supersedes §4.1–4.4 for every purpose except understanding how we got here.

It is the right measurement in every respect that was previously in doubt: **the `PCM-071`**, the
exact variant chosen on 2026-08-13; a **whole module**, not SoC rails; by the vendor, on a
phyBOARD-Lyra carrier with `R492` replaced by a **70 mΩ** shunt; BSP **PD25.1.1**.

| Case | Current ‡ | Power ‡ | vs idle |
| --- | ---: | ---: | ---: |
| Idle in Linux, no low-power mode | 297.1 mA | 1485.7 mW | — |
| **Suspend-to-RAM** | **25.7 mA** | **128.6 mW** | **−91.3 %** |
| MCU-Only | N/A | N/A | see below |

128.6 / 25.7 = **5.004 V**, so these are drawn at the module's `VIN` (Table 12: 5.0 V main supply,
pins A1/A2/A3). The idle figure corroborates the manual's own 1.62 W typical (Table 3).

**Wake ≈ 150 ms ‡** (Khalid Talash's covering mail). The kernel log in the report gives an
independent bound: `PM: suspend entry (deep)` at 163.995928 to `PM: suspend exit` at 164.232937
is **237 ms for a complete suspend-and-resume round trip** with no dwell in between, so the resume
half cannot be more than that.

#### What it does not cover, and where the headroom is

- **MCU-Only mode could not be measured.** "The MCU/M4 demo firmware deployed to our current BSP
  release does not work in combination with the MCU-only mode. It may be available in future
  versions." So 128.6 mW is the floor *today*, not the floor of the silicon — TI's SoC-only figure
  for MCU Only is 54.91 mW (§4.1).
- **Both Gigabit Ethernet PHYs are present and were driven by the BSP.** The resume log
  reconfigures `am65-cpsw-nuss` `end0` and `end1`, each with a TI DP83867. Glider uses no
  Ethernet. **This is the only identified headroom against 128.6 mW, and it is now the largest
  single line in the reading budget** — but the log only shows the driver re-initialising the PHYs
  *on resume*, which says nothing about their state *while suspended*. **Ask; do not assume.**

#### ⚠ A software requirement that will bite at bring-up

**The Cortex-M4 must be stopped before Suspend-to-RAM, or the second suspend hangs.** PHYTEC's
published low-power guide does not say so and they have undertaken to fix it. Measured behaviour
with the M4 running: suspend "worked reliably 1 time per boot, but locked up when entering
low-power mode a second time", and drew more power. The fix in the report:

```
cat /sys/class/remoteproc/remoteproc0/name     # -> 5000000.m4fss
echo stop > /sys/class/remoteproc/remoteproc0/state
```

After that, "we were able to enter and leave the Suspend-2-RAM low-power mode as many times as
desired". PHYTEC's own recommended change is "Update firmware to completely turn off MCU to enable
multiple uses of Suspend-2-RAM."

#### Wake-from-GPIO is demonstrated; the pin is not

The report wakes the module from Suspend-to-RAM with BTN1 on the carrier, and the kernel reports
`ti-sci 44043000.system-controller: ti_sci: wakeup source:0x80, pin:0x75, mode:0x0` with two
`WAKEUPGPIO` interrupt lines. So the *mechanism* — a GPIO edge waking Deep Sleep — is proven on
this module. **Which `X1` pin BTN1 reaches is not in the report**, so `docs/mcu.md` §5.5's
conclusion (buttons stay on the MCU) is unchanged: the route exists but its pin number does not.

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

The green board in the same photo is one of this repo's own adapters (`pcb/35p-adapter-a/`).
Its `J3` is that board's own 35-pin panel connector (`X03A10L35G`), **not** the mainboard's
16-pin `J3` — which R2 has deleted (`pcb/r2-mainboard/docs/fpga.md` §15.2).

**No adapter in this repo uses the mainboard's 16-pin connector at all.** Grepping all ten
adapter projects — `34p-adapter-a/b`, `35p-adapter-a`, `39p-adapter-b/c`, `40p-adapter-ab`,
`50p-adapter-b/c`, `mega_adapter`, `u133_adapter` — finds zero 16-pin FPC parts; every one of
them mates with the 50-pin `J6` alone. So the 16-pin connector was unused by the entire
adapter ecosystem that shipped with R1, which is the fifth independent line of evidence that
deleting it costs nothing for any panel these adapters support.

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
