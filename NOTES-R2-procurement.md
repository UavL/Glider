# Glider-R2 — what to buy and what to ask, with sources

Written 2026-08-03 on branch `Board-Design`. Companion to `NOTES-R2-som-selection.md`.

Everything below was verified against a primary source — PHYTEC's own hardware manual, the
LCSC/JLCPCB catalogue, or the Caster sources — not from device-class knowledge. Where a fact is
*not* verified it says so.

> **Revised 2026-08-03 against the current manuals.** The first pass used `L-1038e.A1`, the
> revision PHYTEC's website links. The hardware owner supplied **`L-1038e.A5`** (PCM-071,
> connectorised) and **`L-1041e.A3`** (PCL-071, DSC solder-down), both dated 2026. Three
> corrections and one new hazard, detailed in the next section:
> idle power is **1.62 W**, not 1.47 W; the two Samtec connectors are one logical connector
> **X1 with columns A–D**, not "X1 and X2"; and **`VOUT0_DATA16..23` double as the
> `BOOTMODE_8..15` straps**, which the manual says must not be driven during reset.

---

## Correction pass against L-1038e.A5 / L-1041e.A3

### The block diagram does show the interface — under the name "DPI"

PHYTEC's [block diagram](https://www.phytec.eu/en/fileadmin/phytec_base/images/01-Products/Block-Diagrams/Block-diagram-phyCORE-AM62x.png)
has no line labelled "RGB". It has one labelled **`DPI`**, immediately below `OLDI/LVDS`, running
from the SoC to the left-hand Samtec connector. **DPI *is* parallel RGB** — Display Pixel
Interface, the MIPI name for the 24-bit-plus-sync parallel bus that everyone else calls "RGB
parallel" or "TTL". Both names appear in PHYTEC's own material: the product page says "24-bit RGB
parallel", the block diagram says "DPI", the pinout tables say `VOUT0_*`. Same pins.

### Idle power was revised upward

| Revision | `IVIN` idle | Stated idle power |
| --- | --- | --- |
| `L-1038e.A1` | 293 mA | 1.47 W |
| **`L-1038e.A5`** | **324 mA** | **1.62 W** |
| `L-1041e.A3` (DSC) | — | **1.6 W** |

A5's changelog says "Idle and Underload currents updated in Table 4". Under load it is now 651 mA
(3.26 W), up from 490 mA. **The reading state cannot be idle** — this only sharpens the point that
everything depends on suspend-to-RAM, which is still unpublished in either manual.

### Connector naming

PHYTEC treats the **240-pin interconnect as a single logical connector `X1` with four columns
A, B, C, D** (Tables 7–10), physically realised as two 2×60 Samtec `BSH-060-01-L-D-A-TR`. So the
earlier "DATA16..23 are on the second connector X2" should read **"column D"**. The floorplan
consequence is unchanged — the red channel arrives on a different column from green and blue.

### The new hazard: the top 8 RGB bits are the boot-mode straps

`L-1038e.A5` Table 31 / `L-1041e.A3` Table 30. Every one of `VOUT0_DATA16..23` is shared:

| Signal | X1 (PCM-071) | DSC pin (PCL-071) | Shared with | Pull on SOM |
| --- | --- | --- | --- | --- |
| `VOUT0_DATA16` | D2 | 12 | `GPMC0_AD8` / `BOOTMODE_8` | 100 K **up** |
| `VOUT0_DATA17` | D4 | 13 | `GPMC0_AD9` / `BOOTMODE_9` | 100 K **up** |
| `VOUT0_DATA18` | D5 | 14 | `GPMC0_AD10` / `BOOTMODE_10` | 100 K **up** |
| `VOUT0_DATA19` | D6 | 15 | `GPMC0_AD11` / `BOOTMODE_11` | 100 K **down** |
| `VOUT0_DATA20` | D7 | 16 | `GPMC0_AD12` / `BOOTMODE_12` | 100 K **up** |
| `VOUT0_DATA21` | D8 | 17 | `GPMC0_AD13` / `BOOTMODE_13` | 100 K **up** |
| `VOUT0_DATA22` | D10 | 18 | `GPMC0_AD14` / `BOOTMODE_14` | 100 K **down** |
| `VOUT0_DATA23` | D11 | 19 | `GPMC0_AD15` / `BOOTMODE_15` | 100 K **down** |

The manual footnotes all eight: *"This signal should not be driven during reset."*

**Why this bites us specifically.** With TI's RGB888 mapping, `DATA23..16` is the **red channel**,
and Caster's 18-bit input wants the top six bits of each channel — `R7..R2` = `DATA23..18`. That is
six of the eight strapped pins, including all three with 100 K pull-**downs**.

Our side of the link is an FPGA *input*, so we never drive it. The risk is subtler: **Spartan-6
I/O have weak pull-ups enabled during configuration**, before `DONE` goes high. A Spartan-6
internal pull-up is far stronger than 100 K. If the FPGA is powered and unconfigured while the SoM
comes out of reset, it could pull `BOOTMODE_11/14/15` high and **boot the module into the wrong
mode**. Same failure class as the CSR-on-video-clock trap in `NOTES-power-analysis.md` §9: a
power-sequencing dependency that only appears at one specific moment.

Options, cheapest first — to be settled with PHYTEC's [pinmux tool](https://pinmux.phytec.com/)
before schematic capture:

1. **Ask the DSS for an 18-bit output mapping that avoids the strap group.** If `VOUT0` can emit
   RGB666 on `DATA17..0`, only `DATA16/17` are straps — and both are 100 K pull-**ups**, which a
   Spartan-6 pull-up *agrees* with, so no conflict at all. This is the clean answer if it exists.
2. **Set the bitstream so those pins float during configuration** (`-g UnusedPin:Pullnone` plus
   explicit no-pull constraints on the six nets). Verify against UG380 — Spartan-6's
   configuration-time I/O state needs checking, it is not something to assume.
3. **Sequence the rails**: hold the FPGA unpowered or in `PROG_B` reset until the SoM has booted.
   Costs an enable net, which the R2 power tree has anyway.
4. Series resistors on the six nets — crude, and it degrades a 127 MHz edge. Last resort.

### I/O voltage is jumper-selectable, and the default is what we want

The `3.3V1` footnote in both manuals: *"The voltage level for this signal is configurable for
1.8 V or 3.3 V. The default voltage level is listed here."* All the `VOUT0_*` signals sit in the
**`VDDSHV3`** domain (Table 6, jumper `J4`) together with the `GPMC0_*` group. Default is 3.3 V,
which matches Caster's `IOSTANDARD = LVCMOS33`. **Specify 3.3 V on `VDDSHV3` when ordering** —
one jumper moves the whole group, so this is a build-configuration item, not a board choice.

### The DSC variant is now the more attractive of the two

`L-1041e.A3` puts the same 24 `VOUT0` bits on plain numbered castellated pads — `PCLK` 27,
`VSYNC` 29, `HSYNC` 30, `DE` 28, `DATA0..15` on 46–31, `DATA16..23` on 12–19 — on a **270-pin,
0.8 mm pitch castellated edge, 40 × 40 mm**, idle 1.6 W, same 4.5–5.5 V `VIN`. Castellated edges
are ordinary reflow soldering, so **JLCPCB could in principle place it**, which removes the
`BTH-060` stock risk and the mated-height stack. It becomes a consigned part rather than a
catalogue one. Worth pricing alongside `PCM-071` — see Request 1.

---

## Summary of what changed while checking these

Three findings that move the design, before the request list itself:

1. **The SoM is 5 V input, not battery-direct.** `L-1038e` Table 4: `VIN` 4.5–5.0–5.5 V.
   A 1S Li-ion cell is 3.0–4.2 V, so the module needs a **boost converter**, and the R2 plan's
   "run the bucks straight from the cell, remove a conversion stage" applies to everything
   *except* the SoM. Boost efficiency (~92 %) has to be folded into the budget.
2. **PHYTEC publishes an idle figure of 1.62 W** (`L-1038e.A5` Table 3, calculated from
   `IVIN` = 324 mA at 5 V, "idle in Linux with external interfaces down"). That is *worse* than
   the 0.89–1.20 W the plan assumed, and it confirms the design cannot live in idle. **No
   suspend-to-RAM figure is published anywhere in the manual.** The entire battery estimate
   rests on a number PHYTEC has not stated — this is the single most important thing to ask.
3. **Do not design a touch controller onto the board.** LCSC carries no multi-touch capacitive
   controller IC at all — `GT911`, `GT9110`, `FT5316`, `FT6336`, `CST328`, `CST816`, `GSL1680`
   all return zero results. That is not a gap in the catalogue, it is how the part is sold:
   the controller is bonded to the touch film's own flex tail (chip-on-flex). R2 should carry an
   **FPC connector for a finished touch module** — I²C, `INT`, `RST`, 3V3 — and nothing else.
   This removes the item from the blocked list rather than leaving it open.

---

## Verified: the module's parallel RGB reaches the connector at the right voltage

From `L-1038e.A5` §8.1 Table 31 "VOUT Connections at the phyCORE-Connector":

| Fact | Evidence |
| --- | --- |
| All of `X_VOUT0_PCLK`, `_DE`, `_HSYNC`, `_VSYNC`, `_DATA0…DATA23` are on the SOM connector | 69 pin rows matching `X_VOUT0_*` in the pinout tables |
| Every one of them is on the **3.3 V** I/O domain (`3.3V1`) | pinout column "3.3V1"; power-domain table lists them under `VDDSHV3` |
| Caster's DPI pins are `IOSTANDARD = LVCMOS33` | `Caster/rtl/spartan6/constraint.ucf:229-237` |

**So no level shifting is needed between the SoM and the FPGA.** That was an open risk; it is
closed. Note that `DATA0…15` sit on connector X1 **columns A/B** and `DATA16…23` on **column D**,
so the red channel comes off a different column — a floorplan constraint, since
Caster wants `R7..R2` from `DATA23..18`.

## Verified: the carrier-side connector is buyable and JLCPCB-placeable

| Side | Part | Where | Stock | US$ @1 |
| --- | --- | --- | --- | --- |
| On the SOM (PHYTEC fits these) | `BSH-060-01-L-D-A-TR` ×2 | — | — | — |
| **On our board** | **`BTH-060-01-L-D-A-K-TR` ×2** | **LCSC `C3646540`** | **63** | **5.56** |

PHYTEC names the mating part explicitly: *"Mount the SOM into the mating carrier board using two
BTH-060-01-L-D-A-K-TR 0.5 mm 2×60 Samtec connectors"* (`L-1038e` §4.2). It is a normal SMD part
in LCSC's catalogue, so **JLCPCB solders it and the module plugs in by hand.**

⚠ **63 in stock, and each board needs two.** Samtec is not a part LCSC restocks quickly. Buy a
handful early or plan on consignment.

This also supersedes the DF40 recommendation in `NOTES-R2-som-selection.md` — DF40 was the right
*idea* (small board-to-board instead of a bulky SO-DIMM edge socket) but the wrong part, because
the module dictates its mate. Module is **43 × 32 × 3.8 mm**, against Verdin AM62's 69.6 × 35 mm.

---

# Request 1 — PHYTEC (the compute module). Highest priority.

**Who:** PHYTEC Messtechnik GmbH, Mainz, Germany — the manufacturer. Neither DigiKey nor LCSC
carries this module; it is a direct sale.
**Where:** "Request your quote" form at <https://www.phytec.eu/en/produkte/system-on-modules/phycore-am62x/>
Technical sales, phone **+49 (0) 6131 9221-32** (German or English).

**Products to ask about**

| Order code | What it is | Ask for |
| --- | --- | --- |
| **`PCM-071`** | phyCORE-AM62x, the **connectorised** module (2× Samtec BSH-060). This is the one R2 designs around. | Price at 1, 10 and 100 pcs; lead time; the exact variant string for the configuration you want |
| `PCL-071` | phyCORE-AM62x-**DSC**, the solder-down variant (270-pin, 0.8 mm edge, 40 × 40 mm) | Price only — as a fallback, not the plan |
| **`KPB-07124`** | phyBOARD-AM62x Development Kit, **US$ 349**, ships with 2 GB DDR4 / 32 GB eMMC | Price in EUR, and **question 4 below before ordering** |
| `PB-07124` | the bare phyBOARD-AM62x carrier alone | only if the kit is not sold separately |

**Configuration to specify when asking for the `PCM-071` quote.** The module is
build-to-order; these are the axes:
- SoC variant: **AM6254** (4× Cortex-A53) — or ask whether a lower-core AM6231/AM6232 is cheaper
  and still has the same DSS display subsystem. We need the display block, not the cores.
- RAM: **1 GB DDR4 is plenty** (Caster holds the framebuffer, not Linux). Default is 2 GB — ask
  whether 1 GB is a cheaper option, since idle DRAM power scales with it.
- eMMC: smallest offered (default 32 GB is far more than KOReader needs).
- Temperature grade: commercial, not industrial, if it is cheaper.
- WiFi/BT: **yes if it is a module option** — the reader needs it and an on-module radio is
  pre-certified, which saves a lot of pain versus adding one to our board.

**Questions to send them.** Copy-paste; they are ordered by how much each answer would change
the design.

> 1. **What is the module's power consumption in suspend-to-RAM (Linux `mem` / DDR in
>    self-refresh, wake sources armed)?** Your hardware manual L-1038e.A5 gives idle as 1.62 W
>    (324 mA at 5 V) but does not state a suspend figure. Our product is a battery e-reader that
>    spends almost all of its life suspended with the display content retained externally, so
>    this single number decides the battery life. A measured figure in mA at `VIN` is ideal.
> 2. **What is the wake-to-usable latency from that suspend state?** Specifically, time from a
>    GPIO/RTC wake event to the display controller producing valid pixel output. We need under
>    ~500 ms for a page turn to feel instant.
> 3. **Can the module be powered from ~3.4 V directly, or is the 4.5 V `VIN` minimum hard?**
>    We run from a single Li-ion cell (3.0–4.2 V). If 5 V is mandatory we add a boost stage; we
>    would rather not, for efficiency.
> 4. **Does the phyBOARD-AM62x carrier (`PB-07124`) bring the 24-bit parallel RGB signals
>    (`VOUT0_PCLK/DE/HSYNC/VSYNC/DATA0..23`) out to any connector or expansion header?** Your
>    product page lists only an LVDS display connector. We need to bench-test the parallel RGB
>    output at ~127 MHz pixel clock before committing to a board design, so if the kit does not
>    expose it, please tell us which carrier or adapter does.
> 5. **What is the maximum verified pixel clock for the parallel RGB (DPI) output on this
>    module?** Your website says "up to 200 MHz for 2K"; the TI AM625 datasheet (SPRSP58C)
>    rates DPI at 165 MHz. We need 127 MHz at 75 Hz, 85 MHz at 50 Hz. Is 127 MHz a
>    supported/validated operating point on the module, including its I/O routing?
> 6. **Is the parallel RGB output supported in your mainline-based BSP** (DRM/KMS, arbitrary
>    custom timings via device tree, Wayland)? We drive a non-standard 1448×1072 timing.
> 7. **Do you have a 1 GB RAM / small-eMMC variant**, and is an on-module WiFi/BT option
>    available? Please quote with and without.
> 8. Lead time and MOQ for `PCM-071` at 10 and 100 pieces.
> 9. **`VOUT0_DATA16..23` are shared with `GPMC0_AD8..15` / `BOOTMODE_8..15`** and your manual
>    says they must not be driven during reset. We need the top six bits of each colour channel,
>    which with the standard RGB888 mapping means `DATA23..18` — six strapped pins, three of them
>    with 100 K pull-downs on the SOM. **Can the DSS be muxed to output 18-bit RGB666 on
>    `DATA17..0` instead**, so the strap group is avoided? If not, what do you recommend for a
>    carrier that has an FPGA (with weak pull-ups active during its own configuration) on the
>    other end of those nets?
> 10. Please confirm we can order the module with **`VDDSHV3` set to 3.3 V** (jumper J4 default),
>     since that domain carries all the `VOUT0` signals and our FPGA is LVCMOS 3.3 V.
> 11. Please **also quote `PCL-071` (DSC)**. Its 270-pin castellated edge can be reflow-soldered
>     by a normal assembly house, which for us removes a connector-stock risk. Same questions 1,
>     2, 5, 6 apply to it.

**What a good outcome looks like:** a suspend figure under ~100 mW and a resume under 500 ms.
If suspend comes back above ~250 mW, the AM62x route is in trouble and the fallback in
`NOTES-R2-som-selection.md` (RAM-in-package `T113-S3`, everything on one JLCPCB-assembled board)
becomes the serious option instead of the backup.

---

# Request 2 — the mating connectors. Buy these now, do not wait.

**Where:** LCSC, <https://www.lcsc.com> — search `C3646540`.
**What:** `BTH-060-01-L-D-A-K-TR`, Samtec, **2 per board**, $5.56 each.
**Why now:** 63 in stock of a part LCSC does not routinely restock. If R2 is ever built in
quantity these are the long pole. Buying ~10 costs ~$56 and removes the risk.

Second source if LCSC runs out: Samtec sells direct at <https://www.samtec.com> with free
samples for evaluation quantities, and Mouser/DigiKey both carry the BTH series.

---

# Request 3 — the display, touch film and pen sensor. One supplier, one enquiry.

**First, identify the panel you actually have.** The model is printed on the flex tail near the
connector, e.g. `ED060KC1`. The firmware runs 1448 × 1072, which is the 6″ 300 ppi family:
`ED060KC1`, `ED060KD1`, `ED060KG1`, `ED060KH*`, or Kaleido colour `EC060KH1/KH3/KH5`
(README's panel table, lines ~1305-1320). Everything below depends on that string, so read it
off before writing to anyone.

**Where to ask** — in the order worth trying:

| Supplier | What they are | Link |
| --- | --- | --- |
| **Good Display** (Dalian) | E Ink's largest module partner; sells panels *with touch and frontlight already bonded* and will quote small quantities. Best first stop. | <https://www.e-paper-display.com> — sales@e-paper-display.com |
| **E Ink official kit shop** | Sells `ED060KC1` bare; useful as a price reference and to confirm the part is still in production | <https://shopkits.eink.com> |
| **Unisystem** (Poland) | EU-based E Ink distributor; easier shipping/VAT from Germany, will quote bonded assemblies | <https://unisystem.com> |
| AliExpress / eBay | ~$45–55 for a bare `ED060KC1`, ~$55 for one with touch. Fine for a prototype panel, useless for a datasheet or a pinout. | — |

**Questions to send them:**

> 1. We use a **1448 × 1072 6″ E Ink panel, model `<your model>`** with a **TTL/parallel EPD
>    interface** on a 34-pin flex. Can you supply this panel **with a capacitive touch film
>    already bonded**, and if so what is the part number of the complete assembly?
> 2. For the touch layer: what **controller IC** is on the touch flex, what is its **interface**
>    (I²C address, `INT` and `RST` pins), what is the **flex connector pitch and pin count**, and
>    can you send its **datasheet and a pinout drawing**? We need to design the FPC connector on
>    our board around it.
> 3. Does the touch controller support a **low-power gesture/wake mode**, and what is its
>    current draw in that mode? Our device sleeps between page turns.
> 4. Can the assembly also include a **frontlight**, and what are its LED forward voltage,
>    current and connector pinout?
> 5. Do you offer an **EMR (electromagnetic resonance) digitizer sensor** — Wacom-style, battery-
>    free pen — that mounts behind this panel? If so: sensor part number, controller IC and its
>    interface (UART or I²C), power consumption while scanning, and the mechanical stack-up.
> 6. Minimum order quantity and price at 1, 10 and 100 pieces, shipped to Germany.

**Expectation-setting on the pen.** Question 5 is the one most likely to come back "no". EMR
sensors are generally sold into ODM programmes, not to individuals, and they are matched to a
specific panel size and stack. If it comes back negative, the honest fallback is to route the
digitizer interface on R2 as an unpopulated FPC connector (a UART, an interrupt and a gated
rail — costs a few square millimetres) and revisit it later, rather than blocking the board.

---

# Request 4 — nothing. These are now closed.

| Was open | Now |
| --- | --- |
| "Prove DPI ingest in the gateware (Stage 2)" | **Already exists and already runs** — `vin_dpi.v`, `SRC_DPI` in `vin.v`, 22 pins in `constraint.ucf` at 165 MHz. See `NOTES-R2-som-selection.md`. |
| "Find a capacitive touch controller on LCSC" | **Wrong question.** The controller comes bonded to the touch film. Board carries an FPC connector, not an IC. |
| "Does the SoM's DPI need level shifting to the FPGA?" | **No.** Both are 3.3 V LVCMOS. |
| "Which connector attaches the module?" | `BTH-060-01-L-D-A-K-TR` ×2, LCSC `C3646540`, in catalogue. |

---

## Order of operations

1. Read the panel model off the flex. (5 minutes, unblocks Request 3.)
2. Send Request 1 to PHYTEC and Request 3 to Good Display the same day — both have multi-day
   turnarounds and they are independent.
3. Order the two connectors from LCSC while waiting (Request 2).
4. **Do not start schematic capture until PHYTEC answers questions 1 and 2.** The suspend power
   and the resume latency are what decide whether this architecture is the right one at all; a
   bad answer sends the design to the `T113-S3` route, which is a different board.

## Still unverified after this pass

- **phyCORE-AM62x suspend power and resume latency** — the point of Request 1. Not published.
- **Whether the `phyBOARD-AM62x` dev kit can drive parallel RGB at all** — its product page
  lists only LVDS. Request 1 question 4. Until this is answered there is no way to bench-test
  the link before committing to a board.
- **`PCM-071` price** — PHYTEC publishes none. The $349 kit price is the only public number.
- **Whether 1 GB DDR4 and a WiFi option exist** as module variants — assumed from PHYTEC's
  usual configurability, not confirmed.
- **The panel model on the actual dev kit** — not recorded anywhere in this repo.

## Sources

- **PHYTEC, *phyCORE-AM62x System on Module Hardware Manual*, `L-1038e.A5`** (PCM-071, supplied
  by the hardware owner) — §4.2 (mating connectors), Table 3 (43 × 32 mm, **1.62 W** idle),
  Table 4 (`VIN` 4.5–5.5 V, `IVIN` **324 mA** idle / 651 mA loaded), Table 6 (voltage domains,
  `VDDSHV3` jumper J4), Tables 7–10 (connector X1 columns A–D), **Table 31** (VOUT pinout,
  3.3 V domain, `BOOTMODE` sharing and the "not driven during reset" footnote).
- **PHYTEC, *phyCORE-AM62x DSC Hardware Manual*, `L-1041e.A3`** (PCL-071) — 270-pin 0.8 mm
  castellated edge, 40 × 40 mm, 1.6 W idle, Table 30 VOUT pinout on numbered pads.
- PHYTEC block diagram, showing `DPI` and `OLDI/LVDS` as separate lines to the Samtec connector:
  <https://www.phytec.eu/en/fileadmin/phytec_base/images/01-Products/Block-Diagrams/Block-diagram-phyCORE-AM62x.png>
- PHYTEC pin-mux tool (to settle question 9): <https://pinmux.phytec.com/>
- Earlier revision `L-1038e.A1` (linked from phytec.eu, superseded) gave 293 mA / 1.47 W idle.
  <https://www.phytec.eu/fileadmin/phytec_base/images/04-Support/L-1038e.A1_phyCORE-AM62xx_HW_Manual.pdf>
- PHYTEC product pages: phyCORE-AM62x (`PCM-071`, `PCL-071`, 43 × 32 × 7.6 mm mated, "24-bit RGB
  parallel, OLDI/LVDS"), phyCORE-AM62x-DSC, phyBOARD-AM62x (`PB-07124`), phyBOARD-AM62x
  Development Kit (`KPB-07124`, $349).
- LCSC / JLCPCB catalogue queried 2026-08-03: `C3646540` BTH-060-01-L-D-A-K-TR (63 @ $5.56);
  zero results for every capacitive touch controller IC searched.
- `Caster/rtl/spartan6/constraint.ucf`, `vin.v`, `vin_dpi.v`, `top.v` — DPI pin placement,
  `IOSTANDARD = LVCMOS33`, 165 MHz `TIMESPEC`.
- `README.md` panel compatibility table — 1448 × 1072 family and flex pin counts.
