# Glider-R2 Stage 1 — SoM and video link selection

Date **2026-08-02**. This is the gating decision for the R2 board: nothing else can be designed
until the video link and the SoM are fixed. Every number below is **traced to a datasheet
page** — no device-class guesses. Sources are listed at the bottom.

Companion document: the R2 architecture plan (block diagram, power tree, budget).
Context for why R2 exists at all: `NOTES-STATUS.md`.

---

## Terms used here

| Term | What it means |
| --- | --- |
| **MPN** | Manufacturer Part Number — the exact orderable code, e.g. `XC6SLX16-2FTG256C`. Distinct from the *value* shown on a schematic, which is often just a family name like `XC6SLX-FTG256`. Without an MPN you cannot check price, stock or whether a part is discontinued. "0/356 MPN coverage" means none of R1's 356 BOM entries records one. |
| **BOM** | Bill of Materials — the list of every part needed to build one board. |
| **DPI** | Display Pixel Interface. 24 wires carrying one pixel at a time, plus clock and control. Simple to receive. |
| **LVDS** | Low-Voltage Differential Signalling. Each signal uses a *pair* of wires carrying opposite voltages; the receiver looks at the difference. Immune to noise picked up equally by both wires, so it runs much faster over longer distances than a single wire. |
| **OLDI** | OpenLDI — a standard way of packing 24-bit pixels onto 4 LVDS pairs, sending 7 bits per pair per pixel. Same thing panels use as "FPD-Link". |
| **TMDS** | The signalling HDMI and DVI use. Also differential, but packs a pixel onto 3 pairs at 10 bits each, so it runs faster still — too fast for this FPGA. |
| **Speed grade** | A suffix on an FPGA part number (`-2`, `-3`) recording how fast that individual die tested. Higher number = faster = more expensive. Same silicon, sorted by test result. |
| **Basic vs Extended (JLCPCB)** | JLCPCB keeps *Basic* parts loaded in its machines permanently — no setup charge. *Extended* parts must be loaded specially for your order, costing roughly $3 per distinct part number, regardless of how many boards you build. |
| **Obsolete / EOL / NRND** | Manufacturer lifecycle status. *Obsolete* and *End Of Life* mean it is no longer made; *Not Recommended for New Designs* means it still is, but will not be for long. Distributors can still hold stock of an obsolete part — that stock just never gets replenished. |
| **Self-refresh** | A low-power state for DRAM where the chip keeps its own contents alive without the controller talking to it. Uses milliwatts instead of hundreds. |
| **Suspend-to-RAM** | The computer copies its state into DRAM, powers nearly everything else off, and the DRAM self-refreshes. Waking is far faster than a cold boot. |

---

## The requirement

Caster has **no image framebuffer**. The 3.0 MB in DDR3 is the per-pixel *waveform state* word
(`frame_bytes = tcon_hact * 4 * tcon_vact * 2`, `fw/User/caster.c`); the target colour comes
from the live video stream every frame. `caster.v` ties `vin_ready = s1_active`, so the video
input is consumed in lockstep with the panel scan — **input frame rate and panel frame rate are
the same thing**.

So the link must sustain the panel's frame rate:

| Panel rate | Total 1528×1110 | Pixel clock | DPI | OLDI/LVDS 4-lane 7:1 | TMDS 10:1 |
| --- | --- | --- | --- | --- | --- |
| 75 Hz (current) | 1.696 M | **127.2 MHz** | 127 MHz | **890 Mb/s** | **1272 Mb/s** |
| 60 Hz | 1.696 M | 101.8 MHz | 102 MHz | 713 Mb/s | 1018 Mb/s |
| 50 Hz | 1.696 M | 84.8 MHz | 85 MHz | 594 Mb/s | 848 Mb/s |

---

## What the Spartan-6 can actually receive

`DS162 v1.11`, Table 25 *Interface Performances* — speed grades are **-4 / -3 / -3N / -2 / -1L**
(note: `-2` is the *slowest standard* grade in this family, not a fast one):

| Interface | -4 | -3 | -3N | **-2** | -1L |
| --- | --- | --- | --- | --- | --- |
| SDR LVDS receiver (ISERDES2, DATA WIDTH 2–8) | 1080 | 1080 | 1050 | **950** | 500 Mb/s |
| DDR LVDS receiver (ISERDES2, DATA WIDTH 2–8) | 1080 | 1080 | 1050 | **950** | 500 Mb/s |

Also `DS162` Table 3: **`CIN` die input capacitance at the pad = 10 pF max.**

Verdict per link, at 75 Hz:

| Link | Needs | Spartan-6 -2 | Spartan-6 -3 | Result |
| --- | --- | --- | --- | --- |
| DPI (parallel LVCMOS) | 127 MHz | not serdes-limited | not serdes-limited | **works** — but see the load problem below |
| OLDI / LVDS 4-lane | 890 Mb/s | 950 Mb/s | 1080 Mb/s | **works**, 6 % margin on -2, 18 % on -3 |
| TMDS straight in | 1272 Mb/s | 950 Mb/s | 1080 Mb/s | **out of spec on every grade** |

The TMDS option is now settled on paper: **1272 Mb/s needed against 1080 Mb/s on the fastest
Spartan-6 speed grade.** Dropping to 60 Hz still needs 1018 Mb/s, which only a `-3`/`-4` part
would take, with 6 % margin. Not a design to build.

> **Resolved from the part marking on the dev kit (photo, 2026-08-02):** the fitted device is
> `XC6SLX16` / `FTG256DIV1829` / `2C` — i.e. **XC6SLX16-2FTG256C**. The schematic only records
> the ambiguous value `XC6SLX-FTG256`, so this was not knowable from the design files.
>
> Two consequences: the part is an **LX16, not the LX9** assumed earlier (≈14 600 logic cells
> instead of ≈11 400 — useful headroom for fitting a DPI *and* an OLDI receiver), and it is
> the **`-2` speed grade**, so the differential receiver limit is **950 Mb/s** — the slowest
> standard grade, and the one where OLDI at 75 Hz has only 6 % margin.

---

## SoM candidates — verified

| Candidate | 24-bit RGB DPI on the connector? | Max pixel clock | LVDS/OLDI | Suspend-to-RAM | Verdict |
| --- | --- | --- | --- | --- | --- |
| **TI AM62x — PHYTEC phyCORE-AM62x** | **Yes** — 24-bit RGB parallel VOUT as Parallel MIPI DPI 2.0 | **165 MHz** | 2× OLDI, 4 lanes each | SoC deep sleep **14.62 mW** (LPDDR4) | **PASS — recommended** |
| TI AM62x — Toradex Verdin AM62 | **No** — connector carries OLDI + MIPI DSI only. On some variants the AM62's DPI port is consumed *internally* by a Toshiba TC9594XBG RGB→DSI bridge | — | 1× OLDI (2-channel) | module-level **59.7 mW** (Solo 512 MB) to 133 mW (WiFi variants) | fails on DPI; **passes on OLDI** |
| Rockchip RK3566 (Radxa CM3) | **No** — parallel video out is `VOP_BT1120` (16-bit YCbCr 4:2:2) and `VOP_BT656` (8-bit) only; display outputs are HDMI/DSI/LVDS/eDP | — | Yes | not characterised | **fails filter 1** |
| NXP i.MX6ULL (the Kobo-class part) | Yes — eLCDIF 24-bit | **85 MHz** | No | excellent | **fails** at 75 and 60 Hz. 50 Hz needs 84.8 MHz against an 85 MHz ceiling — zero margin |

### AM62x DPI, from the datasheet

`AM625 SPRSP58C` (June 2022, rev. October 2025), **Table 6-46 DSS Switching Characteristics**:

| No. | Parameter | Min | Max | Unit |
| --- | --- | --- | --- | --- |
| D1 | `tc(pclk)` cycle time, `VOUT0_PCLK` | **6.06** | | ns → **165 MHz max** |
| D4 | `td(pclkV-dataV)` PCLK→`VOUT0_DATA[23:0]` | −0.68 | 1.78 | ns |
| D5 | `td(pclkV-ctrlL)` PCLK→VSYNC/HSYNC/DE | −0.68 | 1.78 | ns |

165 MHz against 127 MHz needed is **30 % headroom** — the only candidate with real margin.

### AM62x power, from TI's own measurements

`SPRADG1 AM62x Power Consumption`, measured on the Starter Kit EVM with the on-board INA
monitors (same method as Glider's `sensor` command):

| Mode | DDR4-1400 | DDR4-1000 | **LPDDR4-1000** |
| --- | --- | --- | --- |
| **Deep Sleep** (suspend-to-RAM, DRAM in self-refresh) | 24.44 | 32.51 | **14.62 mW** |
| MCU Only | 65.50 | 55.59 | 54.91 mW |
| OS Idle @ 200 MHz | 383.54 | 315.58 | 316.26 mW |
| Dhrystone, 4 cores | 1241.14 | 872.72 | 856.07 mW |

---

## Two corrections to the R2 plan's estimates

**1. The SoM suspend estimate was optimistic at module level.** The plan assumed 20–40 mW.
The *SoC* achieves 14.62 mW, but Toradex's measured *module* suspend is **59.7 mW** for the
leanest Verdin AM62 (Solo 512 MB) and 117–133 mW for the WiFi variants — the delta is the PMIC,
DDR, eMMC, Ethernet PHY and radio. Budget **~60 mW for a module**, not 20–40, unless a
bare-SoC design is on the table. phyCORE-AM62x has not been measured yet; obtain PHYTEC's
figure before finalising.

**2. Idle is not a usable state.** Toradex measure Verdin AM62 idle without a screen at
**0.89–1.20 W**. That is more than the entire current Glider board draws in retain. The reading
state therefore depends *entirely* on suspend-to-RAM working reliably with a fast resume —
"SoM sits idle between page turns" is not an option at any point in this design.

Revised reading-state budget (SoM suspended, FPGA scan stopped, EPD rails off):

| Consumer | Was estimated | Now |
| --- | --- | --- |
| SoM suspend-to-RAM | 20–40 mW | **~60 mW** (module-level, measured) |
| everything else on the Glider side | 65–130 mW | unchanged (still estimates) |
| **Reading-state total** | 85–170 mW | **~125–190 mW** |

At one page turn per 30 s (~100 mW averaged burst), that is **~225–290 mW → 54–70 h** from a
15.7 Wh cell. Still roughly 8–11× the R1 baseline of 6.4 h; the conclusion holds, the margin is
thinner than the plan claimed.

---

## The open question: DPI or OLDI

Choosing DPI was correct on the information available at the time. Two facts found during
Stage 1 make OLDI/LVDS competitive, and they should be weighed before Stage 2 starts.

**The DPI load problem.** `AM625` Table 6-44 *DSS Timing Conditions* specifies the conditions
under which the D1–D5 timings above are valid:

| Parameter | Min | Max |
| --- | --- | --- |
| `CL` output load capacitance | 1.5 | **5 pF** |
| `td(Trace Mismatch Delay)` across all traces | | **100 ps** |

A Spartan-6 input pad is up to **10 pF** on its own (`DS162` Table 3) — **twice TI's maximum
spec'd load before a single millimetre of trace is added.** This does not mean DPI will not
work; it means TI's published −0.68/+1.78 ns data-valid window does not apply, the setup/hold
budget becomes unknown, and capture timing has to be closed by phase-tuning the FPGA's capture
clock on the bench. At 127 MHz the period is 7.87 ns, so there is not much to give away.

The 100 ps trace-mismatch limit is also a hard layout constraint: **all 28 DPI signals matched
to ~17 mm on FR4**, which drives the floorplan.

**OLDI comparison.** 4 data pairs + 1 clock pair = 10 signals instead of 28. Differential and
100 Ω terminated, so the 10 pF single-ended load issue largely disappears. 890 Mb/s sits inside
the Spartan-6 `-2` rating with 6 % margin, `-3` with 18 %. It also keeps **both** AM62x modules
in play rather than just phyCORE. The cost is real: ISERDES2 plus a bit-alignment/training
state machine in the FPGA, versus DPI's "latch 24 bits on a clock edge".

| | DPI | OLDI / LVDS |
| --- | --- | --- |
| Signals | 28 | 10 |
| FPGA RTL | trivial capture + phase tune | ISERDES2 + word alignment + training |
| Electrical risk | **load 2× over TI spec**; 100 ps match across 28 nets | in spec; differential |
| Layout | SoM must sit adjacent to the FPGA bank | routable across the board |
| Modules that work | phyCORE-AM62x only | phyCORE **and** Verdin AM62 |
| Margin at 75 Hz | 165 vs 127 MHz (30 %) | 950 vs 890 Mb/s (6 %, `-2`) / 1080 (18 %, `-3`) |

Neither is clearly better. DPI trades electrical risk for RTL simplicity; OLDI trades RTL work
for a clean electrical story and a second source of modules.

---

## Sourcing check — DigiKey API, 2026-08-02

Queried live via the Product Information v4 API (EUR/DE locale, marketplace sellers excluded).
Prices are unit price at qty 1. **This is the check that R1 never had** — its BOM has
**0/356 MPN coverage**, so nothing in the design was ever lifecycle-checked.

### R1 parts, carried over or deleted

| Query | Resolved MPN | Status | Stock | Unit € | Note |
| --- | --- | --- | --- | --- | --- |
| XC6SLX9-2FTG256C | XC6SLX9-2FTG256C | Active | 536 | 35.41 | **Still available.** Keeping Spartan-6 is viable |
| MT41K64M16TW-107 | MT41K64M16TW-107 IT:J | Active | **0** | 26.67 | R1's DDR3L is not stocked |
| MT41K256M16TW-107 | MT41K256M16TW-107 XIT:P | Active | 523 | 39.40 | 4 Gbit alternative that *is* stocked |
| INA3221AIRGVR | INA3221AIRGVR | Active | 76 585 | 3.03 | Keep all three |
| TPS22914BYFPR | TPS22914BYFPR | Active | 14 731 | 0.31 | VCOM switches, fine |
| LM321MF | LM321MFX/NOPB | Active | 60 870 | 0.44 | VCOM sense, fine |
| **W25Q32JVSSIQ** | W25Q32JVSSIQ | **Obsolete** | **0** | — | **R1's SPI flash is dead.** Not stocked |
| STM32H750VBT6 | STM32H750VBT6TR | Active | 349 | 9.87 | Being replaced by a G0 anyway |
| FUSB302BMPX | FUSB302BMPX | Active | 25 239 | 0.96 | |
| USBLC6-2P6 | USBLC6-2P6 | Active | 0 | 0.57 | |
| PTN3460BS | PTN3460BS/F6Y | Active | 9 245 | 5.54 | Deleted in R2 |
| ADV7611BSWZ | ADV7611BSWZ-P-RL | Active | **0** | 15.49 | Not stocked. Deleted in R2 |
| CBTL02043ABS | — | **no results** | — | — | Deleted in R2 |

Three things fall out:

1. **The Spartan-6 is fine.** 536 in stock of the `-2` grade at €35.41. Note that the stocked
   grade is `-2`, i.e. the **950 Mb/s** LVDS receiver — the one with only 6 % margin on OLDI at
   75 Hz. That reinforces DPI-primary.
2. **`W25Q32JV` is obsolete.** R1 is already carrying a dead part. R2 replaces it anyway;
   `W25Q128JVSIQ` is Active with 86 736 in stock at €3.45 and gives 16 MB — ample for the FPGA
   bitstream plus config, and it is what the new FPGA self-boot flash should be.
3. **The DDR3L needs re-picking.** R1's exact part is at zero stock. `MT41K256M16TW-107` is
   stocked but €39.40 for 512 MB, of which the design uses 3.0 MB. Worth a proper search for a
   cheaper, better-stocked 1–2 Gbit DDR3L in Stage 3.

### The EPD high-voltage chain is not on DigiKey at all

| Query | Result |
| --- | --- |
| LGS5145 | no results |
| LGS6302B5 | no results |
| MT9700 | no results |
| SY8113C | no results |
| JW3651 | no results |

**Every part in the EPD power chain and every switching regulator on R1 is China-sourced and
reachable only through LCSC/JLCPCB.** The R2 plan says "carry the EPD HV chain over unchanged"
— that is still the right engineering call, but it comes with a single-distributor supply
dependency that was not visible before. Two consequences for Stage 3:

- Confirm LCSC stock for the whole HV chain before committing (the `lcsc` skill needs no API
  key), and identify Western second sources for at least the boost/inverter controllers.
- Since R2 replaces the always-on SY8113C bucks anyway, choose their replacements from parts
  with real distributor coverage — that removes five of the single-sourced parts for free.

### R2 candidate parts — all Active

| Function | MPN | Status | Stock | Unit € |
| --- | --- | --- | --- | --- |
| Battery charger + power path | BQ25896RTWR | Active | 5 137 | 2.79 |
| Fuel gauge | MAX17048G+T10 | Active | 19 850 | 3.69 |
| Housekeeping MCU | STM32G0B1CBT6 | Active | 0 | 4.01 |
| Ultra-low-Iq buck (always-on rail) | TPS62840DLCR | Active | 8 | 1.88 |
| FPGA config flash | W25Q128JVSIQ | Active | 86 736 | 3.45 |
| phyCORE-AM62x SoM | — | not carried by DigiKey | — | — |

`STM32G0B1CBT6` and `TPS62840DLCR` are Active but thin/zero stock at DigiKey right now — both
have close siblings, so this is a Stage 3 substitution exercise, not a blocker. The SoM is
direct-from-PHYTEC.

## Sourcing check — LCSC / JLCPCB, 2026-08-02

Queried via the free jlcsearch community API (no key needed). This matters because **JLCPCB
assembles from the LCSC catalogue** — if a part is not on LCSC, JLCPCB cannot place it and it
has to be hand-soldered or supplied separately.

Note the API's real response shape differs from the `lcsc` skill's documentation: `price` is a
plain float, `extra` comes back empty, and the tier field is `is_basic` / `is_preferred` rather
than `basic`. Worth knowing before writing anything against it.

### Every R1 part is available on LCSC — including the five DigiKey does not carry

| Part | LCSC | JLC tier | Stock | US$ @1 | Package |
| --- | --- | --- | --- | --- | --- |
| XC6SLX16-2FTG256C | C39313 | extended | 693 | **5.96** | FBGA-256 |
| MT41K64M16TW-107 AIT:J | C2060943 | extended | 1 949 | **4.49** | FBGA-96 |
| W25Q32JVSSIQ | C179173 | extended | 23 365 | 0.55 | SOIC-8 |
| INA3221AIRGVR | C181255 | extended | 1 694 | 0.82 | QFN-16 |
| TPS22914BYFPR | C1848394 | extended | 1 487 | 0.039 | DSBGA-4 |
| LM321MF | C668208 | extended | 289 305 | 0.035 | SOT-23-5 |
| **LGS5145** | C5123971 | extended | 139 488 | 0.154 | SOT-23-6 |
| **LGS6302B5** | C5123975 | extended | 11 058 | 0.185 | SOT-23-5 |
| **MT9700-N** | C42441843 | extended | 44 035 | 0.031 | SOT-23-5 |
| **SY8113C1ADC** | C6338414 | extended | 2 067 | 0.174 | TSOT23-6 |
| **JW3651QFNE#TRPBF** | C5444670 | extended | 2 982 | 0.939 | QFN-15 |
| FUSB302BMPX | C132291 | extended | 627 | 0.687 | WFQFN-14 |
| USBLC6-2P6 | C2827693 | extended | 27 085 | 0.103 | SOT-666 |
| STM32H750VBT6 | C404010 | extended | 1 483 | 4.28 | LQFP-100 |

**The single-source worry from the DigiKey pass is resolved** — the whole EPD high-voltage
chain (bold rows) is stocked on LCSC in quantity. The dependency is real but it is a *JLCPCB
build*, which is the intended route anyway.

Price deltas against DigiKey are large enough to change build cost materially:

| Part | DigiKey | LCSC | Ratio |
| --- | --- | --- | --- |
| XC6SLX16-2FTG256C | €35.41 (536 in stock) | $5.96 (693) | ~6× |
| MT41K64M16TW-107 | €26.67 (**0** in stock) | $4.49 (1 949) | ~6×, and actually available |
| STM32H750VBT6 | €9.87 | $4.28 | ~2.3× |

Treat LCSC pricing on late-life Xilinx silicon with some caution — that is a surplus/broker
market — but the availability is real and it is the same catalogue JLCPCB assembles from.

> **`W25Q32JV` caveat:** DigiKey reports it **Obsolete**, yet LCSC still shows 23 365 in stock.
> Both are true — the manufacturer has discontinued it while distributor inventory remains.
> Do not design it into R2 regardless; that stock is finite and unreplenished.

### R2 candidates on LCSC

| Function | Part | LCSC | JLC tier | Stock | US$ @1 |
| --- | --- | --- | --- | --- | --- |
| Battery charger + power path | BQ25896RTWR | C181475 | extended | 127 | 1.40 |
| Fuel gauge | MAX17048G+T10 | C2682616 | extended | 4 403 | 2.32 |
| Housekeeping MCU | STM32G0B1CBT6 | C2847904 | extended | 12 153 | 1.75 |
| Ultra-low-Iq buck | TPS62840DLCR | C2071859 | extended | 5 531 | 0.94 |
| **FPGA config flash** | W25Q128JVSIQ | C97521 | **BASIC** | 110 435 | 1.22 |
| DDR3L alternative | MT41K256M16TW-107 IT:P | C367428 | extended | 376 | 5.06 |
| Adjustable boost (HV candidate) | SGM6603-ADJYN6G | C79688 | extended | 5 074 | 0.87 |
| Touch controller | GT911 | — | **no results** | — | — |

`BQ25896` at only 127 in stock is thin for a charger; find a second candidate in Stage 3.
**GT911 is not on LCSC under that name** — the capacitive touch controller needs a fresh search,
and it may have to come with the touch panel from the panel supplier instead.

### JLCPCB assembly cost note

Exactly **one** part in the whole list is a JLCPCB **Basic** part (`W25Q128JVSIQ`). Everything
else is **Extended**, which on JLCPCB carries a per-unique-part setup fee (roughly $3 each) on
top of the component cost. With R1's 65 unique parts that is on the order of $200 in setup fees
per order, largely independent of how many boards are built — so it hurts most on small runs.
Worth substituting Basic parts for the passives during Stage 3, where it is free to do so.

## Sources

- TI, *AM625, AM625-Q1, AM623, AM620-Q1 Sitara Processors Datasheet*, SPRSP58C, rev. Oct 2025 —
  Table 6-44 (DSS timing conditions), Table 6-45 (external pixel clock), Table 6-46 (DSS
  switching characteristics); features p. 1 "Up to 165MHz pixel clock … OLDI (4 lanes LVDS - 2x)
  and DPI (24-bit RGB LVCMOS)". <https://www.ti.com/lit/ds/symlink/am625.pdf>
- TI, *AM62x Power Consumption*, SPRADG1 — §4.1.2 Deep Sleep, summary table, §5.1 measurement
  discrepancy note. <https://www.ti.com/lit/an/spradg1/spradg1.pdf>
- Xilinx, *Spartan-6 FPGA Data Sheet: DC and Switching Characteristics*, DS162 v1.11 —
  Table 3 (`CIN`), Table 25 (interface performances).
- Toradex, *Verdin AM62 Power Consumption* — measured idle and suspend per module variant.
  <https://developer.toradex.com/hardware/hardware-resources/power-consumption/verdin-am62-power-consumption/>
- Toradex, *Verdin AM62 V1.2 HW Datasheet* — §5.2 Display; connector pinout showing `OLDI0_*`
  and MIPI DSI, no parallel RGB; note on the Toshiba TC9594XBG RGB→DSI bridge.
- PHYTEC, *phyCORE-AM62x* documentation — "one 24-bit RGB parallel video output (VOUT) …
  Parallel MIPI DPI 2.0 … two OLDI display ports".
- Rockchip, *RK3566 Datasheet* V1.0 — §1.2.13 Video Output Processor; pin mux showing
  `VOP_BT1120_*` / `VOP_BT656_*` only.
- NXP i.MX6ULL datasheet — eLCDIF max 85 MHz display clock (via NXP community confirmation;
  **re-verify against the NXP PDF directly**, nxp.com blocked automated download).

## Verification gaps

- **phyCORE-AM62x module-level suspend power is not measured** — only the bare SoC (14.62 mW)
  and Toradex's different module (59.7 mW). Get PHYTEC's number before finalising the budget.
- **i.MX6ULL's 85 MHz is second-hand** (NXP community and a third-party SoM manual), because
  nxp.com blocks scripted downloads. It only matters if the 50 Hz fallback is revisited.
- **Resume latency is unmeasured for every candidate.** It sets the page-turn feel and no
  datasheet states it — this needs a bench test on an eval board.
- **`phyCORE-AM62x` pricing and lead time are unknown** — carried by neither DigiKey nor LCSC;
  quote from PHYTEC directly.
- **No capacitive touch controller has been found on LCSC.** `GT911` returns nothing. Likely it
  comes bonded with the touch panel from the panel supplier — confirm before Stage 4.
- The **schematic's component values are not real part numbers** for most of the BOM, so this
  sourcing pass covered the ICs only. Passives (191 capacitors, 83 resistors) were not checked;
  they are generic and cheap, but they are also where JLCPCB Basic-part substitutions would
  save the most in assembly setup fees.
- A cheaper, better-stocked **DDR3L** than `MT41K256M16TW-107` (€39.40 for 512 MB, of which
  3.0 MB is used) should be searched for in Stage 3.

## Decisions taken

- **Video link: route both, bring up DPI first.** DPI's weakness is timing margin against an
  out-of-spec capacitive load, and margin is recoverable by phase-tuning the capture clock or
  simply running at 50/60 Hz first and pushing up. OLDI's weakness is that it must re-lock its
  PLL and re-train bit alignment on *every page turn*, because the power strategy depends on
  the SoM shutting its display controller off between pages — the same class of hazard as the
  CSR-on-video-clock trap in `NOTES-power-analysis.md` §9, sitting directly on the critical
  path. Both links are routed; OLDI is the no-respin fallback. Cost is ~38 pins of ~186, and
  Spartan-6 LVDS receivers are powered from `VCCAUX` with optional on-die 100 Ω termination
  (`DS162` Table 3), so LVDS and LVCMOS inputs can share a bank with no supply conflict.
- **SoM: PHYTEC phyCORE-AM62x**, the only candidate exposing 24-bit RGB DPI on its connector
  with clock headroom (165 MHz vs 127 MHz needed). Toradex Verdin AM62 is the OLDI-path
  fallback and second vendor.

---

# Stage 2 — already done upstream (2026-08-03)

**The DPI receiver the R2 plan schedules as "Stage 2, the riskiest change" already exists in
Caster, and it is the path the board runs on today.** Verified from the sources, not inferred:

| Evidence | File | What it shows |
| --- | --- | --- |
| `vin_dpi.v` (203 lines) | `Caster/rtl/spartan6/vin_dpi.v` | A complete DPI receiver: `IBUFG` + `DCM_SP` on `dpi_pclk`, IOB-packed capture registers, a DE-edge phase detector that picks between two pixel alignments, and a 2:1 pixel pack so the core runs at half the pin rate |
| `vin.v:101` | `Caster/rtl/spartan6/vin.v` | `vin_dpi` is **instantiated** and is `SRC_DPI = 3'd1` in the source mux, alongside `SRC_INTERNAL` and `SRC_FPDLINK` |
| `top.v:56-60` | `Caster/rtl/spartan6/top.v` | Top-level ports `DPI_PCLK`, `DPI_DE`, `DPI_VSYNC`, `DPI_HSYNC`, `DPI_PIXEL[17:0]` |
| `constraint.ucf:16-17` | same dir | `TIMESPEC TS_DPI_CLK = PERIOD "DPI_CLK" 165 MHz HIGH 50%` — the DPI clock is **already constrained to 165 MHz** |
| `constraint.ucf:228-255` | same dir | All 22 DPI pins placed, `IOSTANDARD = LVCMOS33`, with `# R7 # G6 # B2 …` comments naming the RGB bit each carries |
| `pcb/mainboard/tmds_in.kicad_sch` | R1 schematic | The 22 nets `DPI_PCLK/DE/HS/VS/R2..R7/G2..G7/B2..B7` originate on the **ADV7611 sheet** and land in `fpga_io.kicad_sch` |

So the ADV7611 does not feed Caster over anything exotic — it decodes HDMI and hands the FPGA a
plain 18-bit parallel RGB bus. **R2 does not add a video path; it deletes the chip in front of an
existing one.**

Consequences for the plan:

1. **Stage 2 is closed.** No Verilator work, no new RTL, no sim campaign. The single largest
   schedule risk in the plan does not exist. Gateware changes for R2 reduce to a `vin_source_ctrl`
   default and whatever the SoM's sync polarity turns out to need.
2. **The DPI bus is 18 data bits, not 24.** RGB666. `vin.v:117-123` expands it to RGB888 by
   replicating each channel's top two bits, and the panel is mono or 4-bit grey anyway, so the
   6 discarded bits cost nothing visible. **22 signals total**, not 28 — a materially smaller
   connector and an easier floorplan than the plan assumed.
3. **165 MHz is already the declared timing target**, against 127 MHz needed at 75 Hz and 85 MHz
   at 50 Hz. The ISE timing report from any existing build is the proof that the capture path
   closes — no new analysis needed, just read `par/*.twr` after the next gateware build.
4. **The core runs at half the pin rate.** `vin_dpi` packs two pixels per word and hands the EPDC
   `v_halfpclk` = `dpi_pclk/4`. That is why a 127 MHz input does not need a 127 MHz fabric.
5. **FPD-Link (LVDS) ingest also already exists** — `vin_fpdlink.v`, 6 lanes, `SRC_FPDLINK`. The
   "route both DPI and OLDI" decision costs nothing in gateware either. Note the existing module
   is FPD-Link (the PTN3460's output format), and OLDI/JEIDA differs in bit mapping and lane
   count — a `CH_INVERT`/remap parameter change, not a rewrite.

---

# The module attachment question — resolved (2026-08-03)

The blocker was: the hardware owner wants **one board that arrives finished from JLCPCB**, and
cannot hand-solder a module. Facts gathered from the LCSC/JLCPCB catalogue:

| Part | LCSC | Stock | US$ @1 | Meaning |
| --- | --- | --- | --- | --- |
| `DF40C-40DS-0.4V(51)` board-to-board | C424644 | 5 554 | 0.51 | **Available.** A normal SMD connector — JLCPCB solders it, the module plugs in |
| 200-pin SO-DIMM socket | — | **none** | — | Not in the catalogue under any spelling. Would need consignment |
| `T113-S3` (Allwinner, 2×A7, **128 MB DDR3 in package**) | C5197687 | 1 810 | 5.60 | **Available.** No external DRAM to route at all |
| `T507` (Allwinner, 4×A53) | C669217 | 278 | 8.05 | Available, needs external DDR3/4 |
| `A40i-H` (Allwinner, 4×A7) | C2921072 | 90 | 6.73 | Available but thin stock |
| `AXP2101` PMIC | C3036461 | 1 443 | 1.40 | The matching Allwinner PMIC — available |
| `AM6254ATCGGAALW` | C6120421 | 205 | 19.42 | Available, but its **LPDDR4 is not** |
| `RK3566` | C2943786 | 95 | 13.96 | Same problem — LPDDR4 not in the catalogue |
| `MT41K64M16TW-107` (R1's own DDR3L) | C2060943 | 1 949 | 4.49 | DDR3L is well stocked; LPDDR4 is not |

**The decisive asymmetry: LCSC stocks DDR3/DDR3L and does not stock LPDDR4.** Every modern
low-power application processor (AM62x, RK3566, i.MX8M) is an LPDDR4 part. So "bare SoC on the
main board, fully assembled by JLCPCB" is only reachable with a DDR3-era or RAM-in-package SoC.

Three routes, and why the socket one is not what it sounded like:

- **A. SoM on a board-to-board connector (DF40).** JLCPCB assembles the whole board *including the
  connector*; the module is a separate purchase that **plugs in by hand with no soldering**. This
  is the route the plan assumed, and the "SO-DIMM" wording was the problem, not the concept — a
  SO-DIMM edge connector is 69.6 × 35 mm of module hanging off a bulky socket, which is genuinely
  wrong for a thin reader. DF40 is ~4 × 20 mm and 0.4 mm pitch. Mechanically this is one board.
- **B. RAM-in-package SoC soldered down (T113-S3 + AXP2101).** Everything on one board, everything
  in LCSC, nothing to plug in. Cost: 2×Cortex-A7 at 1.2 GHz and 128 MB — enough for a framebuffer
  reader, not for much else — and the T113's parallel-RGB clock ceiling is **unverified** and is
  the thing that would kill it.
- **C. Bare AM62x + LPDDR4 soldered down.** Requires consignment of the DRAM to JLCPCB, a PMIC
  sequencing design, and LPDDR4 fly-by routing on a 6-layer stack-up. This is the "real product"
  answer and the wrong first prototype.

**Recommendation: A, with the R2 board designed so B remains possible.** Reasons: it keeps the
verified 165 MHz DPI path and the AM62x's measured 60 mW suspend, both of which the whole battery
estimate rests on; it needs no soldering skill; and it decouples the risky part (the compute
module) from the part that is already proven (the Caster half of the board, every part of which
was confirmed in-catalogue in the Stage-1 LCSC pass).
