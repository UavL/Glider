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

**Side: not stated, and the recommendation is the side facing *away* from the panel.** The reasoning
is thickness, and it changed when the sketch arrived. Previous revisions of this section called the
SoM "the thickest thing in the device"; the sketch shows the cell **beside** the board, not under
it, so the two stacks are independent and the SoM no longer competes with the 7.0 mm cell:

| Stack | Height |
| --- | ---: |
| panel module | 1.93 mm |
| mainboard, panel side | PCB ~1.0 mm + whatever is placed there |
| mainboard, back side | + **5.0 mm** if the SoM goes here, + module PCB |
| the cell, in its own footprint beside the board | 7.0 mm |

Putting the SoM on the back keeps the panel-facing side flat, which matters because the panel is
216.7 × 174.4 mm and sits directly over the board. Putting it on the panel-facing side would force
a cut-out or a spacer through the largest, most fragile component in the device. **Confirm this
before placement — it is the last thing on the critical path**, and it also decides which side `J1`
(USB-C) mounts on, because a mid-mount or through-hole socket has a side.

**One thing the position costs, and it is not free.** Top-right is also where the panel's own tails
want to be (§1.2), and `epd-port.md` §11 needs the HV chain near `J6`. Those two groups now compete
for the same corner. The resolution is in `Project_description.md`'s favour: the SoM's USB pair is
the timing-critical one, the HV chain is DC, so **the HV chain moves and the SoM does not**.

### 1.2 The rest of the sketch — recorded, with the parts that still need confirming

Read off the owner's hand sketch of 2026-08-20. Dimensions are approximate where the sketch says so.

| Object | Sketch | Against what is already known |
| --- | --- | --- |
| Enclosure | ≈ **220 × 180 mm** | panel module is 216.7 × 174.4 mm ‡ — so the case is the panel plus ~3 mm of bezel each way. Consistent. |
| Mainboard | ≈ **90 × 70 mm**, *"the same as R1 but can be made bigger"* | R1 is 90 × 80 mm. So R2 is R1's footprint or slightly smaller, with room to grow. |
| Cell | **90 × 60 mm**, beside the board | matches `PL706090` exactly (60 × 90 × 7.0 mm, `battery.md` §9.1) ✓ |
| Power switch | right-hand edge, marked `ON` / `OFF` | this is `SW20` (`mcu.md` §5.5). An edge slider, not the recessed pinhole the doc left open. |
| Touch | its own small board | consistent with `io-expansion.md` §4 — the `GT9110H` is on its own PCB, not on the panel flex. |
| *"TTL Interface"* | its own block, ≈ **40 × 37 mm** | **⚠ this is decision D-7 and it needs confirming.** |

**The `TTL Interface` block is the open question.** If it is a *separate PCB* carrying `J6` and the
HV chain, then D-7 is answered "yes, separate" and that is a significant architectural change: the
50-pin 0.5 mm FPC leaves the main assembly, several panel sizes become one mainboard, and the cost
is a board-to-board connector carrying `+VP`, `+VGH`, `-VCOM`, `-VGL`, `-VN` — five high-voltage
nets across a connector, which is not a trivial thing to specify. If it is instead a *region of the
mainboard*, D-7 is answered "no" and nothing changes. The sketch draws it inside the mainboard
outline, which argues for a region — but it is drawn with its own border and its own dimensions,
which argues for a board. **Not inferred here; ask.**

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

## 3. The two missing footprints

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

> **BUILT 2026-08-20** by `tools/gen_som_footprint.py`. 240 SMD pads `A1`–`D60`, 4 NPTH alignment
> holes, 2 M2.5 mounting holes. It went into **`r2.pretty`**, the project library, not into
> `pcb_common` — it is an R2-only part and `pcb_common` is a submodule shared with the read-only R1
> project. **The symbol's `Footprint` property therefore changes from `footprints:` to `r2:`.**

The previous text here said this one "should not be built by hand" and pointed at SnapEDA. That was
right when it was written and is worth keeping as the standing rule for connectors of this pitch —
but it rested on the only source being a picture. Two drawings have since landed in
`datasheets/SoM Phycore AM62x/` that between them **over-determine** the geometry, which is a
different situation from measuring one:

- `bth-xxx-xx-x-d-xx-footprint.pdf` — Samtec's own recommended PCB layout, REV D, one connector.
- `L-1038e.A5` **Figure 7, "Carrier Board Alignment Hole Placement"** (p.19) — a carrier-board
  drawing, dimensioning the two connectors against the module outline. Figure 6 (p.18) adds the row
  order and pin-1 end.

Samtec's sheet is **vector**, so the numerals were not the only source: the PDF content stream was
parsed and the pad rectangles measured. Every measurement matched a printed dimension to under
1 µm, and two printed dimensions that the drawing does not otherwise explain fell out of it:

| Quantity | Measured | Printed | Agrees |
| --- | --- | --- | --- |
| pitch | 0.50000 mm | `.01969 [0.5000]` TYP | ✓ |
| pad | 1.4478 × 0.3048 mm | `.0570 [1.448]` × `.0120 [0.305]` | ✓ |
| row centre spacing | 6.1723 mm | = `.3000 [7.620]` − 1.448 | ✓ |
| NPTH | 1.0138 mm | ⌀ `.0400 [1.016]`, `-A` option | ✓ |
| hole to hole | 33.4818 mm | Table 1 "A" for −60 = 33.482 | ✓ |
| hole to nearest pad centre, along the row | — | `.0782 [1.986]` REF = (33.482 − 29.507)/2 | ✓ |
| hole to nearest **row**, across | 1.0538 mm | `.0415 [1.054]` | ✓ |

**The last row is the one that makes the assembly solvable, and it is easy to miss.** The alignment
hole is *not* on the connector's centreline — it sits 1.054 mm from one pad row and 5.118 mm from
the other. Figure 7 dimensions the **holes**, so without that offset the rows cannot be placed at
all, and a footprint built on the assumption of a centred hole would be 2.06 mm out.

Figure 7, with the module outline's lower-left corner as origin:

| | |
| --- | --- |
| SOM outline | 32.000 × 43.000 mm |
| left alignment column | x = 2.760 |
| right alignment column | x = 2.760 + **22.400** = 25.160 |
| left connector, upper hole | y = 43.000 − 2.420 = 40.580 |
| right connector | **4.800 mm lower** — the two are staggered, which Figure 6 also shows |
| hole to hole, either connector | 33.482 |
| M2.5 mounting holes | (2.800, 2.800) and (29.200, 40.200); ⌀2.600 drill, ⌀4.000 plating |
| row order, left to right | **B A** then **D C**; pin 1 at the bottom, pin 60 at the top |

**The check worth trusting is the one nothing forces.** Combine the Samtec offsets with Figure 7's
placement and the `B` row lands **0.982 mm** inside the module's left edge while the `C` row lands
**0.998 mm** inside the right. 16 µm of asymmetry across 32 mm, out of two independently printed
dimensions — that is the drawing being self-consistent, and it would not survive a wrong row order
or a mirrored hole offset. `check()` in the generator asserts it, along with the mirrored-orientation
case (which puts `C` 0.4 mm off the edge of the module) and hole-to-pad clearance.

Two deliberate departures, both recorded in the generator's docstring:

1. **Pitch is laid at exactly 0.500 mm, centred on the hole pair**, rather than Samtec's
   inch-derived 0.5001. The holes are the mechanical datum and 0.5 mm is the design intent; the
   disagreement with Samtec's own tabulated span is 5 µm at the end pads.
2. **The courtyard encloses the connectors, not the module.** The module does not sit on the board
   — it stands 5 mm off it, so low parts may live underneath. A 32 × 43 mm courtyard would forbid
   that. ⚠ **The consequence is that DRC will not police component height under the SoM**; the
   32 × 43 outline is on `F.Fab` and `User.Drawings` with silk corner ticks, and *"nothing taller
   than ~4 mm under the module"* is a manual check at Stage D. The two M2.5 standoffs are what set
   the real clearance, so measure against the assembled stack, not against the 5 mm number.

**Still worth doing before fabrication:** download the SnapEDA or Samtec pattern anyway and diff the
pad coordinates against this one. It costs ten minutes and it is the only fully independent check
available; everything above shares one source per number even where two numbers cross-check.

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

1. ~~**Board outline, SoM position, cell size**~~ — **all three answered.** Panel and cell have
   dimensions; the SoM's position is §1.1 (top right, beside the USB ports). **Its side is
   recommended, not decided** — see §1.1.
2. ~~**The `PCM-071` footprint**~~ — **built 2026-08-20**, §3.2. One task left with it: the
   `Footprint` property on the `PCM-071` symbol still reads `footprints:…` and must become
   `r2:…` — six places across `som.kicad_sch`, `dpi_in.kicad_sch`, `r2.kicad_sym` and three
   generators.
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
8. **D-7, the separate panel-connector PCB**, is now half-answered by the owner's sketch and needs
   one word back from them — §1.2.
