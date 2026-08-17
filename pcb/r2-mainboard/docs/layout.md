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
2. **⚠ Where the SoM sits, and on which side — STILL OPEN, and now the only blocker.** The
   `PCM-071` is **32 × 43 mm** and stands **5 mm** off the board on its connectors. Against the
   cell's 7.0 mm and the panel's 1.93 mm, the SoM is the thickest thing in the device, so which
   side it is on decides the enclosure's thickness and whether it sits behind the cell or beside it.
3. ~~**Battery cell size and position**~~ — size **closed** (60 × 90 × 7.0 mm). Position follows
   from decision 2.

**Three new placement facts that arrived with the panel**, none of them blocking:

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
crosses `X1` is DPI at ~101 MP/s, USB 2.0, SPI, UART and MMC1. **Recommendation: 4 layers, R1's
stackup**, and only revisit if the `X1` escape proves tight — which is unlikely, because 115 of the
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

### 3.2 `footprints:PCM-071_2xBTH-060-01-L-D-A-K` — the SoM ⚠

**This one should not be built by hand, and I have not.** It is two `BTH-060-01-L-D-A-K-TR`
patterns (2×60, 0.5 mm pitch) at a fixed spacing set by the module. A 0.5 mm error anywhere in it
produces a board the module does not fit, and the error would not show up until the boards arrive.

What Figure 6 of `L-1038e.A5` gives as **printed dimensions** — these are read off the drawing's
own numerals, not measured:

| | |
| --- | --- |
| SOM outline | **32.000 × 43.000 mm** |
| Between the two connectors | **22.400 mm** |
| Mounting-hole offset from the lower edge | **4.800 mm** |
| Mounting holes | 2×, lower-left and upper-right, **M2.5** |
| Stacking height | **5 mm** |
| Pin-row order, left to right | **B A** then **D C** |
| Pin 1 / pin 60 | pin 1 at the bottom, pin 60 at the top |
| Board-side part | `BTH-060-01-L-D-A-K-TR` |
| Module-side part | `BSH-060-01-L-D-A-TR` |
| Recommended hardware | 2× M2.5×5 mm F-F standoffs, 4× M2.5×4 mm screws, 4× washers |

**The authoritative footprint exists and is free.** The manual's "Symbols/cells of the SOM
connector are available here" links to
<https://www.snapeda.com/parts/phyCORE-AM62x/Phytec/view-part/>. Samtec also publish the
`BTH-060-01-L-D-A-K-TR` land pattern directly. Either is a better source than a drawing measured
off a PDF, so **this is an owner task: download it, drop it in `r2.pretty`, and the name in the
symbol will resolve.** The symbol already names it, so nothing else changes.

## 4. Escape and net classes

115 of the SoM's 240 pins are no-connects, so the `X1` escape is far smaller than the pin count
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

1. ~~**Board outline, SoM position, cell size**~~ — **§1: two of the three are answered.** The
   panel and cell now have dimensions; **only the SoM's position and side still block placement.**
2. **The `PCM-071` footprint** — §3.2, an owner download rather than a build.
3. **The `TPS63802` footprint** — §3.1, buildable here.
4. **`EPD_THROT` still occupies `U41.M16`** and nothing drives it (`fpga.md` §2.1).
   `NOTES-R2-plan.md` says decide before Stage D: reclaim the ball or keep it reserved.
5. ~~**WP6 is not drawn.**~~ **Both sheets are drawn as of 2026-08-17** — `io_expansion`
   2026-08-15, `frontlight` captured today. The netlist is final apart from `FL_INT#`, which has no
   MCU pin yet (`frontlight.md` §10.3), and the DNP touch/pen connectors whose pad order is still a
   vendor question (`io-expansion.md` §5).
6. **A PDS impedance simulation** for the FPGA rails is still the honest answer to `fpga.md` §11.5,
   and is a Stage-D item rather than a defect.
