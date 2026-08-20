# Layout — R2 Stage D

Status: **preparation done, placement blocked on ONE owner decision (§1) — where the SoM sits.**
The panel and cell choices of 2026-08-17 closed the other two. Nothing has been placed;
`r2.kicad_pcb` does not exist yet.

This is the board-level plan. The *circuit-level* rules live with their sheets, and they were
written while each datasheet was open rather than reconstructed now:

| Sheet | Guidelines | The one thing that matters most |
| --- | --- | --- |
| `battery` | `battery.md` §11 | the grounds are not all the same net |
| `power` | `power.md` §11 | four converters, one rule they share; `TPS63802` has **two** switching nodes |
| `mcu` | `mcu.md` §11 | the 32.768 kHz crystal is the most layout-sensitive circuit on that sheet |
| `epd`, `epd_power`, `power_mon` | `epd-port.md` §11 | ⚠ **two ICs have a `GND` pin that is not ground** |
| `fpga_io`, `fpga_ddr`, `fpga_config` | `fpga.md` §11 | 666 MT/s against a 1066 part — the margin is the useful fact |
| `som`, `dpi_in` | `som.md` §8 | MMC1 length-match 12.7 mm; `DPI_R6`/`R7` carry no components |

**Read `epd-port.md` §11.1 before placing anything on the HV chain.** `U9` and `U26` are inverting
buck-boosts: their `GND` pins sit on `-VGL` (−20 V) and `-VN` (−15 V), verified from the exported
netlist. Each needs a local copper island with the plane cut away beneath it, and connecting either
to the ground plane destroys the part. It is the only thing on this board that a competent person
would "fix" into failure.

---

## 1. What blocks placement, and what does not

**Revised 2026-08-17. Two of the three are answered; one remains.**

1. **Board outline — the two objects that set it are now known.** The panel module
   (`GDEP103TC2-FT11`) is **174.4 × 216.7 × 1.93 mm**, 110 g ‡, with a 157.25 × 209.66 mm active
   area; the cell (`PL706090`) is **60 × 90 × 7.0 mm**. Those bound the enclosure, and the board has
   to fit in what is left behind the panel and beside the cell. R1 is **90 × 80 mm** for reference —
   so R1's area fits behind this panel with room over, and **thickness, not area, is the binding
   dimension.** The outline itself is still the owner's to draw, but it is no longer unconstrained.
   `panel.md` §0, `battery.md` §8.1.
2. ~~**Where the SoM sits, and on which side**~~ — **position ANSWERED 2026-08-20, side inferred.**
   See §1.1.
3. ~~**Battery cell size and position**~~ — size **closed** (60 × 90 × 7.0 mm). Position follows
   from decision 2.

### 1.1 The SoM goes top-right, beside the USB ports — owner, 2026-08-20

From the owner's layout sketch and its covering note: *"The SoM should be located near the top right
where I would place the USB ports."* Everything else on that sketch is recorded in §1.2.

**Position: top right, adjacent to the USB connectors.** This is the right call for a reason the
sketch does not say out loud, and it is worth writing down because it constrains everything after
it: the `X2` escape carries `USB_DP`/`DM` as a 90 Ω pair (§4), and USB 2.0 high-speed is the one
signal group on this board that is genuinely intolerant of a long, stubby, via-laden route. Putting
the module next to the socket makes that pair short and straight. Nothing else on the module's
escape has that property — DPI is 22 slow single-ended lines, MMC1 is length-matched but short, and
the rest is SPI and UART.

**Side: the face pointing *away* from the panel. Confirmed by the owner 2026-08-20.** The panel is
216.7 × 174.4 mm and sits directly over the board, so a 5 mm module on the panel-facing side would
force a cut-out or a spacer through the largest and most fragile component in the device. The back
face has nothing above it but the case.

The thickness bookkeeping, since it also fixes the enclosure's depth:

| Stack | Height |
| --- | ---: |
| panel module | 1.93 mm |
| mainboard, panel side | PCB ~1.0 mm + whatever is placed there |
| mainboard, back side | + **5.0 mm** for the SoM's stack height, + the module's own PCB |
| the cell, in its own area of the enclosure | 7.0 mm |

**The cell and the SoM do not stack.** The sketch draws the board and the cell as two separate
rectangles that do not overlap in plan — the cell has its own patch of the enclosure beside the
board, rather than sitting behind it. So the device's depth is the *larger* of the two stacks, not
their sum, and the SoM is no longer "the thickest thing in the device" the way earlier revisions of
this section claimed.

**This also decides which side `J1` mounts on** — a mid-mount or through-hole USB-C socket has a
side, and `USB1` (`NOTES-R2-review-round-2.md` D-3) would join it.

**One thing the position costs, and it is not free.** Top-right is also where the panel's own tails
want to be (§1.2), and `epd-port.md` §11 needs the HV chain near `J6`. Those two groups now compete
for the same corner. The resolution is in `Project_description.md`'s favour: the SoM's USB pair is
the timing-critical one, the HV chain is DC, so **the HV chain moves and the SoM does not**.

### 1.2 The rest of the sketch — recorded, and what each thing constrains

Read off the owner's hand sketch of 2026-08-20. Dimensions are approximate where the sketch says so.

| Object | Sketch | Against what is already known |
| --- | --- | --- |
| Enclosure | ≈ **220 × 180 mm** | panel module is 216.7 × 174.4 mm ‡ — so the case is the panel plus ~3 mm of bezel each way. Consistent. |
| Mainboard | ≈ **90 × 70 mm**, *"the same as R1 but can be made bigger"* | R1 is 90 × 80 mm. So R2 is R1's footprint or slightly smaller, with room to grow. |
| Cell | **90 × 60 mm**, beside the board | matches `PL706090` exactly (60 × 90 × 7.0 mm, `battery.md` §8.1) ✓ |
| Power switch | right-hand edge, marked `ON` / `OFF` | this is `SW20` (`mcu.md` §5.5). An edge slider, not the recessed pinhole the doc left open. |
| Touch | its own small board | consistent with `io-expansion.md` §4 — the `GT9110H` is on its own PCB, not on the panel flex. |
| *"TTL Interface"* | a block ≈ **40 × 37 mm** | **not a board** — see below |

**The `TTL Interface` block is not a second PCB — it is where the panel's flex lands.** The owner,
2026-08-20: *"the TTL interface is just the flex cable that is bent under the display and that's
about where it lands on the PCB, so the connector can be fit accordingly."* **This closes D-7 as
"no separate board"**, and it turns the block from an architectural question into the most useful
kind of layout constraint: a fixed landing zone.

So `J6` is **enclosure-fixed, and now positionally fixed too**. It is not free to move to wherever
routing prefers; it goes where the folded tail arrives, facing the fold. Two consequences worth
carrying into placement:

- The **HV chain has to follow `J6`** (`epd-port.md` §11), and §1.1 already said the HV chain is
  what moves when it competes with the SoM. That is now settled in both directions: the SoM is
  fixed at top-right by USB, `J6` is fixed by the flex, and the HV chain fits around both.
- The connector's **orientation matters as much as its position.** A tail folded under the panel
  arrives from one direction only; a horizontal FPC connector facing the wrong way adds a 180° loop
  in a 0.5 mm flex, which is a reliability problem, not a routing one.

**`J22`/`J23`, touch and pen, are the same story.** The owner: *"touch is also a flexible connector
that is folded under."* So they join `J6` and `J24` in the enclosure-fixed group and want the same
treatment — landing zone first, orientation second, routing last. `io-expansion.md` §4's open item
is unaffected: it is about the *pin order* on the `GT9110H`'s tail, which is still a vendor
question, not about where the connector sits.

**`J24`, the frontlight, is the one that is still undrawn.** The owner: *"the frontlight I still
haven't drawn because the schematics in the display docs don't define it."* That is consistent with
`frontlight.md` §6.2 — the tail is `LED1±`/`LED2±`, bare anodes and cathodes, and the vendor has not
given the per-string current. The 8-pin FPC is on the board and the `LM3630A` drives it; what is
missing is a number for the bench to confirm, not a circuit.

**Three placement facts that arrived with the panel**, none of them blocking:

- **A new connector, `J24`** — the 8-pin frontlight FPC (`frontlight.md` §6.2). It joins `J6`,
  `J22` and `J23` in the enclosure-fixed group, because all four tails emerge from the panel.
  That corner is now four connectors plus a DSBGA boost.
- **`frontlight`'s layout rules changed completely.** `power.md` §11.2 no longer applies to that
  sheet — different part, different topology, and asynchronous, so the diode is in the hot loop.
  `frontlight.md` §9 is the replacement.
- **`epd_power` gains one changed resistor**, `R225` (`epd-port.md` §10). No geometry consequence.

**Not blocking, and worth saying so:** the layer count. R1 runs *this same* DDR3-666 and Spartan-6
on **4 layers** (`F.Cu / In1.Cu / In2.Cu / B.Cu`, 0.127 prepreg / 0.6 core / 0.127 prepreg, ~1.0 mm),
and it works. R2 adds the SoM, but the module carries its own DDR4 and eMMC internally; what
crosses `X2` is DPI at ~101 MP/s, USB 2.0, SPI, UART and MMC1. **Recommendation: 4 layers, R1's
stackup**, and only revisit if the `X2` escape proves tight — which is unlikely, because 115 of the
240 pins are no-connects and need no escape at all (§4).

## 2. Where the design stands

| | R1 | R2 |
| --- | --- | --- |
| Board | 90 × 80 mm, 4 layers | outline undecided |
| Footprints placed | 379 (333 front, 46 back) | **312 parts, 0 without a footprint** |
| Footprints that do not resolve | — | **2** (§3) |
| Netlist | — | 504 nets, hierarchy fully connected, 0 dangling |

The footprint audit is the useful result: **every one of the 312 parts has a footprint assigned,
and only two do not resolve against the project's own libraries.** The project `fp-lib-table` is
healthy and points at `pcb_common/footprints.pretty` (204 footprints) and `r2.pretty`; the broken
tables are the *global* ones, which are the owner's and do not affect this project.

## 3. Footprints — both gaps closed

### 3.1 ~~`r2:Texas_DLA0010A_VSON-HR-10_2x3mm_P0.5mm`~~ — **built 2026-08-15**

From `datasheets/tps63802.pdf` drawing **4223750/D**, the LAND PATTERN EXAMPLE on p.36, read off
the drawing's printed numerals. KiCad ships the 8-pin sibling (`Texas_VSON-HR-8_1.5x2mm_P0.5mm`)
but not this one, and the generic `WSON-10-1EP_2x3mm` is **not** a substitute — VSON-HR has no
central exposed pad and its pads are deliberately asymmetric.

| Pins | Size | Centre x | Function |
| --- | --- | ---: | --- |
| 1–5 | 0.60 × 0.25 | −0.90 | `EN`, `MODE`, `AGND`, `FB`, `PG` — signals |
| 6, 7, 9, 10 | 0.90 × 0.25 | +0.75 | `VOUT`, `L2`, `L1`, `VIN` — power |
| **8** | **1.30** × 0.25 | +0.55 | **`GND`** — the switching return, hence the widest |

Pitch 0.5 mm, 2.0 mm span, body 2 × 3 mm. **Two independent checks passed**: every pad's outer
edge lands on ±1.20 mm — which is what makes the three different widths and three different centres
consistent rather than arbitrary — and the width tiers match the pin functions exactly, signal
narrow and power-ground widest. The generator asserts both.

### 3.2 The SoM: two connector footprints plus a module outline

> **Built 2026-08-20**, and **restructured the same day** when the owner chose two connector symbols
> over one 240-pin module symbol. `tools/gen_som_footprint.py` now emits three footprints into
> `r2.pretty`. The full derivation and the verification are in **`som.md` §10 and §11**; this
> section keeps what a person placing the board needs.

| Footprint | Ref | Pads | Origin, in the module frame |
| --- | --- | --- | --- |
| `r2:BTH-060-01-L-D-A-K_AB` | `J26` | 120 (`A1`–`A60`, `B1`–`B60`) + 2 NPTH | (4.800, 23.900) |
| `r2:BTH-060-01-L-D-A-K_CD` | `J27` | 120 (`C1`–`C60`, `D1`–`D60`) + 2 NPTH | (27.200, 19.100) |
| `r2:PCM-071_Module` | `X2` | **none** — outline and 2× M2.5 only | module centre |

Pads keep the **module's** names, not Samtec's `1`–`120`, so a pad reads straight against
`L-1038e.A5` Tables 7–10 while routing.

| | |
| --- | --- |
| module outline | **32.000 × 43.000 mm**, `BOARD_OUTLINE`, exact |
| connector centrelines | x = **4.800** and **27.200** — 22.400 apart, symmetric about 16.000 |
| stagger | `J27` sits **4.800 mm** lower than `J26` |
| pitch / span | **0.500** / **29.500**, exact |
| rows, left to right | **B A** then **D C**; pin 1 at the bottom |
| M2.5 mounting holes | (2.800, 2.800) and (29.200, 40.200); ⌀2.600 drill, ⌀4.000 plating |
| stack height | 5 mm, set by two M2.5 F-F standoffs |

Both outer rows land **0.990 mm** inside the module's edges, with 0.0 µm of skew — a real check,
since it falls out of the DXF rather than being imposed.

⚠ **`tools/check_pcb_connectors.py` must pass before every fab order.** Nothing in KiCad ties the
three footprints together, so it asserts `J26` = `X2` + (−11.200, −2.400), `J27` = `X2` +
(+11.200, +2.400), same side, same rotation, 122 pads on each receptacle and 2 on the module. It
exits non-zero, so it can gate a release script.

**Two things layout has to know:**

1. **The courtyards cover the connectors, not the module.** The module stands 5 mm off the board, so
   low parts may live underneath — and `X2` has no courtyard at all. ⚠ **DRC will not police
   component height under the SoM.** The 32 × 43 outline is on `F.Fab` and `User.Drawings` with silk
   corner ticks, and *"nothing tall under the module"* is a manual check. Measure against the
   assembled stack, not the 5 mm number.
2. **The alignment holes come from Samtec, not from the DXF** — `som.md` §11.1 explains why the
   DXF's four `MOUNTING_HOLES_LAYER` circles are the *plug's* locating holes rather than ours.
   Trusting them would have put both connectors 0.62 mm out.

**Sourcing:** 2 × `BTH-060-01-L-D-A-K-TR`, LCSC `C3646540`, **60 in stock on 2026-08-20** — 30
boards, the tightest line on the BOM. Plus `MK20`, PHYTEC's M2.5 kit.

## 4. Escape and net classes

115 of the SoM's 240 pins are no-connects, so the `X2` escape is far smaller than the pin count
suggests: about **40 signals plus 3 `VIN` and 45 grounds**. The grounds are what the escape is
really made of, and they are all one net, so they can via straight down.

Proposed net classes, derived from the per-sheet guidelines rather than invented here:

| Class | Nets | Why it is its own class |
| --- | --- | --- |
| `DDR3` | 48 bank-3 nets | length-matched per byte lane; `fpga.md` §11.1 |
| `DDR3_CLK` | `DRAM_CKP`/`CKN` | differential, `R100` 100 Ω at the DRAM end |
| `DPI` | the 22 `DPI_*` | ~101 MP/s, over continuous ground; `DPI_R6`/`R7` carry **no** components |
| `USB` | `USB_DP`/`DM` | 90 Ω differential |
| `MMC1` | the 8 microSD nets | length-match within 12.7 mm; `som.md` §8 |
| `HV` | `+VP`, `+VGH`, `-VCOM`, `-VGL`, `-VN` | not plane nets; clearance, not width |
| `PWR` | `+VSYS`, `+5V_SOM`, `+3V3`, `+1V2_FPGA`, `+1V5` | width for current |
| default | everything else | |

`DRAM_ADDR13`/`ADDR14` must be **excluded** from the `DDR3` class (`fpga.md` §11.1): they are the
inert density-expansion nets, and a net-class length-match rule would drag the real group's
tolerance around for two dead traces.

## 5. Placement order

Superseded by **§6.3**, which has the same order plus the fixed points the panel's folded flex and
the SoM decision have since pinned down, and the instruction to lock each one as it goes.

## 6. Starting the board in KiCad — the order that avoids rework

Nothing here is drawn yet: `r2.kicad_pcb` does not exist. These steps are in the order that stops
you redoing them, which is not the order the menus suggest.

### 6.1 Create the board and set it up **before** importing anything

1. **Open the project** (`r2.kicad_pro`) and click **PCB Editor**. That creates `r2.kicad_pcb`.
2. **File → Board Setup → Physical Stackup.** Set **4 layers**, and copy R1's stack, which runs this
   same DDR3-666 and Spartan-6 and works (§2): `F.Cu` / `In1.Cu` / `In2.Cu` / `B.Cu`, 0.127 mm
   prepreg / 0.6 mm core / 0.127 mm prepreg, ≈ **1.0 mm** finished.
   **`In1.Cu` is the ground plane and `In2.Cu` the power plane** — decide that now, because §8's
   rules about "continuous reference" all mean `In1.Cu`.
3. **Board Setup → Constraints.** Start at **0.2 mm track / 0.2 mm clearance, 0.6 mm via / 0.3 mm
   drill** — comfortably inside JLCPCB's 4-layer capability and cheap. Do **not** start at their
   0.09 mm minimum; you will not need it, and it changes the price band.
4. **Board Setup → Net Classes.** Create the seven in §4 now. Assigning them after routing means
   re-routing, and the DDR3 and DPI groups are exactly the ones you do not want to do twice.

### 6.2 Import, then draw the outline

5. **Tools → Update PCB from Schematic** (**F8**). Everything arrives in a heap off to one side.
   That is normal.
6. **Draw the outline on `Edge.Cuts`** before placing. The sketch says ≈ **90 × 70 mm** (§1.2) —
   draw it as a rectangle to start; it can grow. Add the mounting holes the enclosure needs.
7. **Run `python3 tools/check_pcb.py`.** At this point it should report every part present and
   nothing extra. That is the cheapest moment to catch a footprint that did not come across.

### 6.3 Place in this order, and lock as you go

The first three are not free choices — they are fixed by the enclosure, and everything else
arranges around them. **Lock each one once placed** (select → `L`), so a later drag cannot nudge it.

| | What | Why it is fixed |
| --- | --- | --- |
| 1 | **`J6`**, the panel connector | the folded flex lands there (§1.2); its *orientation* matters as much as its position |
| 2 | **`J22`/`J23`/`J24`** — touch, pen, frontlight | same corner, same reason; all three tails emerge from the panel |
| 3 | **`J1`** USB-C, and `USB1` if fitted | case opening |
| 4 | **`X2` + `J26` + `J27`**, the SoM | top right, on the face **away from the panel** (§1.1). Place `X2` first, then the two receptacles against it, then run `tools/check_pcb_connectors.py` |
| 5 | **`U41` + `U52`**, FPGA and DRAM, together | the DDR3 group wants to be short; place them as a pair before anything competes for the space |
| 6 | **The four converters** on `power` | each with its input-capacitor loop closed before anything else is placed near it |
| 7 | **The HV chain** on `epd_power`, near `J6` | with §7's two islands laid out deliberately |
| 8 | **`U20`**, its crystal, and the buttons | the crystal is placed *against* its constraint, not into the space that is left |
| 9 | Everything else | |

### 6.4 Route in this order

1. **DDR3** — `DDR3_CLK` first as a proper differential pair, then each byte lane. It has no margin
   at the FPGA (§8), and it is the group that dictates where everything else can go.
2. **`USB_DP`/`DM`** — 90 Ω differential, `J1` → `U3` → `J26`. Short is the whole point (§1.1).
3. **`DPI`** — 22 signals, `J26`/`J27` → FPGA bank 1, over continuous ground.
4. **The switching loops** — by hand, deliberately, per §7. Never autoroute these.
5. **`MMC1`**, then everything else.
6. **Pour `In1.Cu` (GND) last**, and check what it did under the HV islands (§7.1).

## 7. ⚠ The five things that destroy the board

Everything in the per-sheet docs matters. These five are the ones where the failure is *permanent*,
*silent in every file*, and *not caught by DRC*. Read them before placing anything.

### 7.1 `U9` and `U26` have a `GND` pin that is not ground

`epd-port.md` §11.1, and it is the single most dangerous item in this project.

| Part | Pin 2, labelled `GND` | Actually sits at |
| --- | --- | --- |
| `U9` `LGS5145` | `-VGL` | **≈ −20 V** |
| `U26` `LGS5145` | `-VN` | **≈ −15 V** |

Both are inverting buck-boosts, so the IC's ground reference *is* its negative output. Each needs
its **own local copper island**, with the plane **cut away beneath it** — not merely avoided on the
outer layer. Connect either to the ground plane and the part sees its full input across the wrong
terminals.

> **Silkscreen both islands.** This is the one thing on the board that a competent person will
> "fix". `tools/check_pcb.py` refuses a copper zone on `-VGL` or `-VN`, which catches the
> commonest version of the mistake but not a stray plane stitch.

### 7.2 The DDR3 bus has no margin *at the FPGA*

`fpga.md` §1.1 and §11.1. The `-2` part's MCB is rated **667 Mb/s**; this design runs **666.67**.
The DRAM's 1066 rating is irrelevant — you do not get to spend its headroom.

Match within a byte lane (`DQ[7:0]`+`LDM`+`LDQS`/`#`, then `DQ[15:8]`+`UDM`+`UDQS`/`#`); the two
lanes need not match each other. Address/command matched to the clock pair. **Keep the whole bus
over one continuous `In1.Cu`** — a split under it is the classic way to lose the margin.

⚠ **`DRAM_ADDR13`/`ADDR14` must be excluded from the matched set.** They are inert at both ends and
look exactly like address lines to a net-class rule; matching them drags the real group around.

### 7.3 The crystal is the easiest thing here to break with copper

`mcu.md` §11.3. `Y20` is a 250–630 nA oscillator. `Y20`, `C46`, `C47` hard against pins 4/5, same
layer, **no vias in `OSC32_IN`/`OSC32_OUT`**, a ground guard ring around the whole circuit and solid
ground beneath. Nothing switching crosses or runs beside it on **any** layer — specifically not
`MCU_SWCLK`, the I²C pair, `FL_PWM1/2`, or anything from `power`. The symptom is an RTC that gains
or loses time, which is a miserable bug to chase.

### 7.4 Every switching converter: the input loop, before the inductor

`power.md` §11.1, which is the same sentence from four different TI datasheets. **The capacitor's
ground must land on the IC's own ground pin, not on a plane somewhere else.** The loop that carries
the chopped current has an area, that area is an inductance, and that inductance turns every edge
into a spike on the IC's own reference.

Two riders worth having in front of you:

- **`U12` `TPS61022`: the critical loop is the *output* loop**, not the input — FET → rectifier →
  output caps → back to the FET's ground (`power.md` §11.2 item 1).
- **`U13` `TPS63802` has *two* switching nodes**, `L1` and `L2`. Both are aggressors
  (`power.md` §11.3).

### 7.5 The 20 mΩ shunts need Kelvin connections

`epd-port.md` §11.5. At 20 mΩ, **1 mΩ of trace is a 5 % error**. Sense traces leave from the
**inside edges** of the shunt pads, symmetrically, as a tight pair, routed together and away from
the converters. A shunt sensed at the wrong end of its own pad measures the pad.

## 8. The review loop

**`python3 tools/check_pcb.py`** — run it after every session, not at the end. It exits non-zero on
a failure and it carries each rule's source, so a complaint tells you which doc to read. It checks:

1. every schematic part is on the board, and nothing extra;
2. `X2`/`J26`/`J27` hold PHYTEC's geometry (delegates to `check_pcb_connectors.py`);
3. **33 proximity rules** taken from the per-sheet guidelines — the decoupling and hot-loop
   distances, which are the ones that quietly drift during placement;
4. no copper zone on `-VGL`, `-VN`, `+DRAM_VREF` or `+3V3_VREF`;
5. the seven net classes of §4 exist;
6. DRC, via `kicad-cli`.

**What it cannot check, and therefore what a human review is for:** loop *area* rather than
component distance; whether the plane is actually continuous under the DDR3 group; what the pour did
beneath the HV islands; whether a "quiet" trace is genuinely quiet; length matching; and every
mechanical question. That list is short, and it is exactly §8 plus the per-sheet docs.

### 8.1 The per-sheet detail, indexed

`check_pcb.py` encodes the numbers. These carry the reasoning, and each was written with the
datasheet open:

| Sheet | Guidelines | The one thing that matters most |
| --- | --- | --- |
| `battery` | `battery.md` §11 | the grounds are not all the same net |
| `power` | `power.md` §11 | four converters, one shared rule; `TPS63802` has **two** switching nodes |
| `mcu` | `mcu.md` §11 | the 32.768 kHz crystal |
| `epd`, `epd_power`, `power_mon` | `epd-port.md` §11 | ⚠ **two ICs have a `GND` pin that is not ground** |
| `fpga_*` | `fpga.md` §11 | no margin at the controller; `M5` (`ZIO`) gets **no copper** |
| `som`, `dpi_in` | `som.md` §8, §10.4 | MMC1 within 12.7 mm; `DPI_R6`/`R7` carry no components |
| `frontlight` | `frontlight.md` §9 | it belongs next to `J24`, not next to `U12` |
| `io_expansion` | `io-expansion.md` §7 | enclosure-fixed, and the load switches follow their connectors |

## 9. ⚠ If the PCB editor says 305 footprints are missing

**Diagnosed 2026-08-20, and it is not a project problem.** The first `Update PCB from Schematic`
produced 305 `Error: Cannot add … (footprint '…' not found)` — every one of them from a *stock*
KiCad library (`Resistor_SMD`, `Capacitor_SMD`, `Package_TO_SOT_SMD`, `Connector_USB` …), while
every `footprints:` and `r2:` footprint resolved. That split is the whole diagnosis: the two project
libraries are found by relative path, and the global table is broken.

**The cause.** `~/.config/kicad/10.0/fp-lib-table` holds a single entry:

```
(lib (name "KiCad") (type "Table")
     (uri "/tmp/.mount_kicadremp4722615889122143643/share/kicad/template/fp-lib-table"))
```

`/tmp/.mount_<random>` is where an **AppImage mounts itself while it runs** — a new name every launch,
gone the moment it exits. The owner does *not* run the AppImage now: KiCad lives as an extracted
AppDir at `~/Apps/kicad-10.0.4` (a symlink to `./AppDir`) and is launched through `AppRun`. So this
is a leftover, written once during an AppImage run before the extraction, and dead ever since. The
symbol table never broke because it was written with absolute paths — compare
`sym-lib-table`, which points straight at `/home/lum/Apps/kicad-10.0.4/share/kicad/symbols/…`.

This is also standing ask 3: the 305 `footprint_link_issues` in every ERC run since WP1 are this
same fault, dismissed as cosmetic because they had only ever been seen in the schematic.

**The fix is `tools/fix_kicad_paths.sh`.** It is idempotent, backs up everything it replaces with a
timestamp, verifies all 155 library paths exist *before* installing, and **refuses to run while
KiCad is open** — KiCad rewrites these files on exit and would silently undo it.

```bash
# close KiCad first
./tools/fix_kicad_paths.sh
```

It does three things: writes the stock library table with absolute paths taken from the running
install; sets `KICAD10_FOOTPRINT_DIR`, `KICAD10_3DMODEL_DIR` and `KICAD10_SYMBOL_DIR` in
`kicad_common.json` (they were literally `"vars": null`); and probes four representative footprints
plus the 3D model tree to prove the result.

Then in KiCad: reopen the project, `F8`, and `python3 tools/check_pcb.py` — presence should read
327 of 327.

**That is also why the 3D viewer is empty**, and it is the larger half of it: every stock footprint
carries `(model "${KICAD10_3DMODEL_DIR}/…")`, so with the variable unset there is no model to load
even for the parts that *did* place. The other half is that this project's own generated footprints
had no `(model …)` at all until now — §9.1.

⚠ **If footprints vanish again after a KiCad update, run the script again** and look at that file
first. Nothing in this project can cause it.

### 9.1 3D models — 322 of 327, and why the other five are honest

After `fix_kicad_paths.sh` set `KICAD10_3DMODEL_DIR`, **311 of 327 footprints resolved on their
own.** `tools/add_3d_models.py` deals with the rest and makes the project self-contained: every
model it uses ends up in `3dmodels/` referenced by `${KIPRJMOD}`, so the 3D view works on any
machine that clones the repo. Re-runnable, backs the board up, refuses to run while KiCad is open.

**Three different reasons a model was missing, needing three different answers.**

**1 — a real model exists, but the path was somebody else's machine.** `pcb_common` keeps its 66
STEP files *next to* the footprints rather than in a `.3dshapes` directory, which is why a search
for 3D directories finds nothing. Several are referenced absolutely: `J24`'s pointed at
`/Users/wenting/Documents/projects/Enchanter/…`. Copied into `3dmodels/` and re-pointed — **these
are the real parts**:

| Ref | Model |
| --- | --- |
| `J1` | `HRO_TYPE-C-31-M-12.step` — the actual USB-C receptacle. In `pcb_common` its filename has a **double space**, which is the sort of thing that breaks quietly on another filesystem; renamed on the way in |
| `J24` | `FPC-SMD_8P-P0.50_HC-FPC-05-09-8RLTAG.step` |
| `J21` | `HY-TF1007B.STEP` — the microSD socket |
| `J6` | `FPC-SMD_50P-P0.50_FPC-05F-50PH20.step` — the panel connector |
| `X2`, `J26`, `J27` | PHYTEC's and Samtec's own downloads |

**2 — no model exists anywhere, so a dimensional stand-in.** `footprints:Xilinx_FTG256` is a
`pcb_common` custom footprint whose model lived on the Modos author's KiCad 6 install — hence
`${KICAD6_3DMODEL_DIR}`, a variable nothing defines any more — and KiCad's own library has no
`Xilinx_FTG256` either.

| Ref | Stand-in matches | Does not match |
| --- | --- | --- |
| **`U41`** Spartan-6 | `BGA-256_17.0x17.0mm_Layout16x16_P1.0mm` — **the FTG256's exact geometry** | generic BGA, no marking |
| `U1` charger | 4 × 4 mm, 24 pins, 0.5 mm | exposed pad 2.7 vs 2.6 mm |
| `U2` gauge | 2 × 2 mm, 8 pins, 0.5 mm | exposed pad 0.6 vs 0.8 mm |
| `U12` boost | 2 × 2 mm, 0.5 mm | 8 pins drawn where the part has 7 |
| `U21`×3 `INA3221` | 4 × 4 mm, 16 pins, 0.65 mm | exposed pad 2.7 vs 2.1 mm |
| `SW20` | 4.2 × 3.2 mm, same actuator class | different maker — **check actuator height against the enclosure rather than trusting this** |
| `U13` buck-boost | 2 × 3 mm, 10 pins, 0.5 mm | VSON-HR has no exposed pad |

⚠ **A stand-in is for clearance and collision, not for identity.** The body outline and height are
right; pin detail, markings and often the exact pad field are not. Never read a stand-in as
confirmation that the correct part is fitted — that is the BOM's job.

**3 — nothing suitable exists, so nothing is faked.** Five remain, and each is reported by name
every time the tool runs:

| Ref | Why | Where a real one would come from |
| --- | --- | --- |
| `X1` | KiCad ships no `ASE-4Pin` model | Abracon |
| `L1` | no `NR-30xx` model anywhere | Taiyo Yuden publish STEP |
| `J2` | only 1.25 mm PicoBlade exists, a *different* connector — and this one sits at the board edge, where a wrong body would mislead the enclosure check | Molex publish STEP for 504050 |
| `U53` | 1.9 mm DSBGA, nothing dimensionally close | cosmetic at this size |
| `J25` | bare copper solder pads | **correctly has none** |

**One thing worth knowing about KiCad here:** a footprint edited in the library does **not**
propagate to a board that already has it placed. `X2` kept the model-less copy it was imported with
long after the generator started emitting one. `add_3d_models.py` refreshes every `r2:` footprint's
model from its library file for exactly that reason — so if a model looks stale, run it again.

**To attach one yourself:** right-click the part → *Open in Footprint Editor* →
*Footprint Properties → 3D Models → Add*, then set offset / scale / rotation against the live
preview. Put the file in `3dmodels/` and write the path as `${KIPRJMOD}/3dmodels/<file>` so it is
not machine-specific. KiCad reads `.step`, `.stp` and `.wrl`.

⚠ **The `BTH-060` model's rotation is still a guess** — Samtec draw the connector along X and this
board stands it along Y, so `MODEL_CONN_ROT` is `(0, 0, 90)`. Check it in the viewer and flip to
−90 if it faces the wrong way. Nothing electrical depends on it.

### 9.2 ⚠ If `kicad-cli` says &ldquo;Failed to load board&rdquo;

Found 2026-08-21, and it had been silently true from the first board: **`kicad-cli pcb` could not
open `r2.kicad_pcb` at all.** Every `pcb` subcommand — DRC, drill, gerber, render — refused it.

**The cause was ours.** `gen_som_footprint.py` wrote `(layer "User.Drawings")`. That is KiCad's
*display alias*; the canonical name in a board file is **`Dwgs.User`**. The footprint editor accepts
the alias — the library exports to SVG fine — but the board parser does not. On import, Pcbnew put
those three rectangles on a layer literally named **`"Rescue"`**, which is not in the board's layer
list, and from then on its own CLI would not read the file it had just written.

Fixed in the generator, and the placed copy was repaired in place. The lesson generalises:
**write canonical layer names in generated footprints**, and if the CLI ever refuses a board,
compare the layers a footprint uses against the board's `(layers …)` block.

⚠ **This also invalidated a number reported earlier.** `check_pcb.py` was loading
`/tmp/r2-drc.json` without checking that the run had succeeded, so it reported the *previous* run's
results — a board that would not open was described as having 4250 DRC violations. The script now
deletes the report first, checks the exit status, and says `DRC: DID NOT RUN` rather than inventing
a number. A check that reports stale data is worse than no check.

## 10. Open

1. ~~**Board outline, SoM position, cell size**~~ — **all answered.** Panel and cell have
   dimensions; the SoM is top-right beside the USB ports, on the face pointing **away from the
   panel** (owner, 2026-08-20). §1.1. **Nothing blocks placement any more.**
2. ~~**The `PCM-071` footprint**~~ — **built and then rebuilt on PHYTEC's DXF, 2026-08-20**, §3.2
   and `som.md` §11. The `footprints:` → `r2:` rename is done. ⚠ **What replaced it as an open
   item is the connector BOM line** — 2 × `C3646540` per board, 60 in stock, `som.md` §10.
3. ~~**The `TPS63802` footprint**~~ — **stale, it exists**: `r2:Texas_DLA0010A_VSON-HR-10_2x3mm_P0.5mm`,
   §3.1. A full audit on 2026-08-20 resolved every `Footprint` property in all 14 sheets against
   `r2.pretty` (4 footprints) and `pcb_common/footprints.pretty` (139), plus 37 KiCad stock
   libraries. **`PCM-071` was the only gap, and it is closed.**
4. **`EPD_THROT` still occupies `U41.M16`** and nothing drives it (`fpga.md` §2.1).
   `NOTES-R2-plan.md` says decide before Stage D: reclaim the ball or keep it reserved.
5. ~~**WP6 is not drawn.**~~ **Both sheets are drawn as of 2026-08-17.** `FL_INT#` now has a pin —
   `PB12`, `mcu.md` §3.4 — leaving only the DNP touch/pen connectors, whose pad order is a vendor
   question (`io-expansion.md` §5).
6. **A PDS impedance simulation** for the FPGA rails is still the honest answer to `fpga.md` §11.5,
   and is a Stage-D item rather than a defect.
7. **⚠ New, and it is a placement constraint rather than a footprint one: the DDR3 bus has no
   margin at the FPGA.** `fpga.md` §1.1 — the `-2` part's MCB is rated 667 Mb/s against the
   666.67 Mb/s this design runs. §11.1's "666 MT/s is a lot of margin" is true of the DRAM only.
8. ~~**D-7, the separate panel-connector PCB**~~ — **CLOSED 2026-08-20: there is no second board.**
   The sketch's "TTL Interface" block is where the panel's flex lands after folding under the
   display. `J6` gains a fixed position and, more importantly, a fixed **orientation**; `J22`/`J23`
   are the same. §1.2.
9. **`J24`, the frontlight tail, is drawn but its current is undefined** — the display docs do not
   specify the frontlight, so the per-string current is a bench measurement (`frontlight.md` §6.2,
   D-8). Not a layout blocker; the connector and the `LM3630A` are placed either way.
