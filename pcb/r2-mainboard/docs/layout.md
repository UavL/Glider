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
   `panel.md` §0, `battery.md` §9.1.
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
| Cell | **90 × 60 mm**, beside the board | matches `PL706090` exactly (60 × 90 × 7.0 mm, `battery.md` §9.1) ✓ |
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
`frontlight.md` §7.2 — the tail is `LED1±`/`LED2±`, bare anodes and cathodes, and the vendor has not
given the per-string current. The 8-pin FPC is on the board and the `LM3630A` drives it; what is
missing is a number for the bench to confirm, not a circuit.

**Three placement facts that arrived with the panel**, none of them blocking:

- **A new connector, `J24`** — the 8-pin frontlight FPC (`frontlight.md` §7.2). It joins `J6`,
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

### 3.2 `r2:PCM-071_2xBTH-060-01-L-D-A-K` — the SoM

> **BUILT 2026-08-20** by `tools/gen_som_footprint.py`, into **`r2.pretty`** (the project library,
> not the `pcb_common` submodule — it is an R2-only part). 240 SMD pads `A1`–`D60`, 4 NPTH
> alignment holes, 2 M2.5 mounting holes.
>
> **Rebuilt the same day on PHYTEC's own DXF**, which arrived with the 3D archive. The full
> derivation, the numbers, and the one apparent contradiction that had to be resolved are in
> **`som.md` §11**; this section keeps only what a person placing the board needs.

The previous text here said this one "should not be built by hand" and pointed at SnapEDA. That was
right when the only source was a picture. It is not the situation any more:
`PCM-071_1573-1.dxf` is vector, numeric, gives the pad columns and the module outline directly, and
PHYTEC's README names it authoritative. **The generator now asserts its own output against the
DXF's numbers**, so this footprint is checked rather than measured.

| | |
| --- | --- |
| module outline | **32.000 × 43.000 mm**, `BOARD_OUTLINE`, exact |
| connector centrelines | x = **4.800** and **27.200** — 22.400 apart, symmetric about 16.000 |
| pads, left connector | y = **9.150 … 38.650** |
| pads, right connector | y = **4.350 … 33.850** — staggered **4.800 mm** lower |
| pitch / span | **0.500** / **29.500**, exact |
| rows, left to right | **B A** then **D C**; pin 1 at the bottom |
| M2.5 mounting holes | (2.800, 2.800) and (29.200, 40.200); ⌀2.600 drill, ⌀4.000 plating |
| stack height | 5 mm, set by two M2.5 F-F standoffs |

Both outer rows land **0.990 mm** inside the module's edges, with 0.0 µm of skew. That symmetry is
not imposed by the generator — it falls out of the DXF's centrelines — so it is a real check.

**Two deliberate departures, both in the generator's docstring:**

1. **The courtyard encloses the connectors, not the module.** The module does not sit on the board;
   it stands 5 mm off it, so low parts may live underneath, and a 32 × 43 courtyard would forbid
   that. ⚠ **DRC therefore will not police component height under the SoM.** The outline is on
   `F.Fab` and `User.Drawings` with silk corner ticks, and *"nothing tall under the module"* is a
   manual check. Measure against the assembled stack, not the 5 mm number — the standoffs set it,
   and the module carries components on its underside too.
2. **The alignment holes come from Samtec, not from the DXF**, and `som.md` §11.1 explains why the
   DXF's four `MOUNTING_HOLES_LAYER` circles are the *plug's* locating holes rather than ours.
   Trusting them would have put both connectors 0.62 mm out.

⚠ **The two receptacles are a BOM line the schematic does not generate** — 2 × `BTH-060-01-L-D-A-K-TR`,
LCSC `C3646540`, of which LCSC has **60**, i.e. 30 boards. `som.md` §10. This is the tightest line
on the whole BOM and it is not on it.

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

## 5. Placement order, once there is an outline

Fixed points first, then the things whose position is dictated by them:

1. **`J6`** the panel connector, and **`J1`** USB-C — both are enclosure-fixed.
2. **The SoM**, because it is 32 × 43 mm and everything routes to or past it.
3. **The FPGA and its DRAM**, together, with the DDR3 group kept short. `fpga.md` §11.1.
4. **The four converters** on `power`, each with its input capacitor loop closed before anything
   else is placed near it. `power.md` §11.1.
5. **The HV chain**, near `J6`, with §11.1's two islands laid out deliberately.
6. **The MCU**, its crystal, and the buttons — the crystal wants quiet, so it is placed against the
   constraint rather than in the space that is left.
7. Everything else.

## 6. Open

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
   specify the frontlight, so the per-string current is a bench measurement (`frontlight.md` §7.2,
   D-8). Not a layout blocker; the connector and the `LM3630A` are placed either way.
