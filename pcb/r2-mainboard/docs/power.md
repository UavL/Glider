# `power.kicad_sch` — rail tree — R2 work package 2

Status: **drawn, review in progress by the hardware owner.** Companion to `battery.md`, which has
now been through one review round — its §10 shows the format the answers take: each point restated,
answered from a datasheet with the page or table cited, and closed with either "changed, here is
what and why" or "correct as drawn, here is the evidence". Do the same here. Everything here cites either a datasheet
in `../datasheets/` (with the page or table), the LCSC catalogue, or a file in this repo. Estimates
are marked **(est.)** and are the things a bench measurement has to replace.

This is the sheet R2 exists for. R1's `pcb/mainboard/power.kicad_sch` wires every buck's `~SHDN`
pin to `+5V`, so 82 % of idle power sits on rails no firmware can switch off (`NOTES-STATUS.md`).
Here **every rail below `+3V3_AON` has a named enable net, a named owner, and a pull-down that makes
"off" the state the board powers up in.**

---

## 1. Rail tree

```
+VSYS  (charger power-path output, battery.kicad_sch; 3.0-4.4 V)
  |
  +-- U1  TPS7A0233   LDO        -> +3V3_AON     always on         ~25 nA Iq
  |
  +-- U2  TPS22965    load sw    -> VSYS_SW      MCU_EN_5V
  |     +-- U3  TPS61022  boost  -> +5V_DCDC     (enabled by VSYS_SW)
  |
  +-- U4  TPS63802    buck-boost -> +3V3_DCDC    MCU_EN_3V3
  +-- U5  TPS62A02    buck       -> +1V2_DCDC    MCU_EN_FPGA_CORE
  +-- U6  TPS62A02    buck       -> +1V35_DCDC   MCU_EN_DDR
```

`*_DCDC` is R1's naming convention: the converter output goes to a shunt on `power_mon`, and the
load-side net that comes back out of that shunt is the plain rail name. So this sheet ends at
`+5V_DCDC` / `+3V3_DCDC` / `+1V2_DCDC` / `+1V35_DCDC`, and `power_mon` produces `+5V`, `+3V3`,
`+1V2_FPGA`, `+1V35`. Keeping the convention makes WP4's port of `power_mon` from R1 a straight
copy. `+3V3_AON` is not shunted — see §9.

| Rail | Topology | Part | LCSC | Stock | Enable | Loads |
| --- | --- | --- | --- | --- | --- | --- |
| `+3V3_AON` | LDO 200 mA | `TPS7A0233DBVR` | `C5142805` | 433 | none (EN tied to IN) | STM32G0, I²C pull-ups, buttons, charger/gauge I²C |
| `VSYS_SW` | load switch 6 A | `TPS22965DSGR` | `C122837` | 3504 | `MCU_EN_5V` | feeds U3 only |
| `+5V_DCDC` | boost 5.0 V | `TPS61022RWUR` | `C915088` | 39457 | via `VSYS_SW` | SoM `VIN`, EPD HV chain |
| `+3V3_DCDC` | buck-boost 2 A | `TPS63802DLAR` | `C2845237` | 1338 | `MCU_EN_3V3` | FPGA `VCCO`/`VCCAUX`, config NOR, microSD, panel logic |
| `+1V2_DCDC` | buck 2 A | `TPS62A02DRLR` | `C5350187` | 3202 | `MCU_EN_FPGA_CORE` | Spartan-6 `VCCINT` |
| `+1V35_DCDC` | buck 2 A | `TPS62A02DRLR` | `C5350187` | 3202 | `MCU_EN_DDR` | DDR3L, FPGA DDR bank `VCCO` |

Not on this sheet: the frontlight boost (`frontlight.kicad_sch`, WP6 — an LED driver runs from
`+VSYS` directly, one conversion instead of two), the EPD HV chain (`epd_power.kicad_sch`, WP4,
from `+5V`), and `+3V3_TOUCH` / `+3V3_PEN` (`io_expansion.kicad_sch`, WP6).

## 2. Two findings that changed the plan

### 2.1 A 1S cell cannot buck to 3.3 V — `+3V3` needs a buck-boost

`NOTES-R2-plan.md` says "run the bucks from the cell, not from a 5 V intermediate", and for 1.2 V
and 1.35 V that is exactly right. It does not work for 3.3 V: `+VSYS` runs from about 4.4 V down to
3.0 V, so a step-down converter drops out somewhere around half the discharge curve and the FPGA's
I/O rail sags with the battery.

Three ways out, and why the third wins:

| | Efficiency | Cost |
| --- | --- | --- |
| Buck from `+5V_DCDC` | ~92 % boost × ~92 % buck = **~85 %** | ties `+3V3` to the 5 V rail — R1's mistake in a new place |
| LDO from `+5V_DCDC` | 3.3/5.0 = **66 %** | worse |
| **Buck-boost from `+VSYS`** | **~93 %** across the whole cell range | one extra part type |

`TPS63802` also brings **true shutdown with load disconnect** (datasheet §1), which a boost cannot:
when disabled it isolates the output instead of leaking through a body diode. That matters for
standby — see §2.2 and §8.

### 2.2 A boost passes its input through when disabled — hence `U11`

`TPS61022` has no load disconnect. Disabled, its high-side FET body diode conducts and the output
sits at roughly `VSYS − 0.3 V` — the datasheet describes the same path deliberately as "pass-through
mode" when the output is above the setpoint (§7.3.5). So switching the boost off would leave about
**3.4 V on the SoM's `VIN` pin**, which is specified for 4.5–5.5 V. Undervoltage on a module's main
input is a partial-power condition, not an off condition, and R2's whole point is a real off state.

`U11` (`TPS22965`) puts the disconnect on the boost's **input**, upstream of both the inductor and
the IC's `VIN` pin, so nothing downstream is fed at all. The switch's NMOS body diode faces
`VOUT → VIN` (datasheet §10.1.3), which is the harmless direction: it blocks `VIN → VOUT`, which is
what we need.

`U12`'s own `EN` is then tied to `VSYS_SW`, its own switched input. One GPIO controls the pair, and
"off" is unambiguous. `U12` will not start until `VSYS_SW` passes its 1.7 V rising UVLO
(`tps61022.pdf` §6.5), which happens naturally during `U11`'s slew.

## 3. Arithmetic

### 3.1 Feedback dividers

`VOUT = VFB × (1 + R_top / R_bot)`.

| Rail | VFB | R_top | R_bot | Result | Source |
| --- | --- | --- | --- | --- | --- |
| `+5V_DCDC` | 0.600 V | `R21` 732 k | `R22` 100 k | 0.600 × (1 + 7.32) = **4.992 V** | `tps61022.pdf` §6.5, §8.2.2.1 |
| `+3V3_DCDC` | 0.500 V | `R24` 511 k | `R25` 91 k | 0.500 × (1 + 5.615) = **3.308 V** | `tps63802.pdf` Table 10-5 — TI's own row for 3.3 V |
| `+1V2_DCDC` | 0.600 V | `R29` 100 k | `R30` 100 k | 0.600 × 2 = **1.200 V** | `tps62a01.pdf` §8.2.2.1 |
| `+1V35_DCDC` | 0.600 V | `R33` 124 k | `R34` 100 k | 0.600 × (1 + 1.24) = **1.344 V** | as above |

All E96, all 1 %, all stocked at LCSC in 0402 (checked 2026-08-06).

Margin checks. SoM `VIN` is 4.5–5.5 V; 4.992 V ±2.5 % reference tolerance gives 4.87–5.12 V, inside
with room for load regulation. DDR3L wants 1.35 V ±5 % = 1.283–1.417 V; 1.344 V sits 0.4 % low,
which leaves the whole +5 % for the power-save-mode output rise the datasheet warns about.

`R_bot` is held at or below 100 kΩ everywhere, which is what all three datasheets ask for
(noise sensitivity, and keeping divider current at least 100× the FB leakage). Worst case is
`+3V3_DCDC`: 0.5 V / 91 k = 5.5 µA against 100 nA max FB leakage — 55×, so the 91 k value is TI's
own trade and is kept rather than raised.

### 3.2 Inductors

| Ref | Rail | Value | Part | LCSC | Why |
| --- | --- | --- | --- | --- | --- |
| `L10` | `+5V_DCDC` | 1 µH | `DFE322512F-1R0M` | `C3224227` | see peak calculation below |
| `L11` | `+3V3_DCDC` | 0.47 µH | `DFE252012F-R47M` | `C703140` | `tps63802.pdf` §8.1 / Table 10-1 |
| `L12` | `+1V2_DCDC` | 1 µH | `DFE322512F-1R0M` | `C3224227` | `tps62a01.pdf` Table 8-3, row `1.2 ≤ VOUT < 1.8` |
| `L13` | `+1V35_DCDC` | 1 µH | `DFE322512F-1R0M` | `C3224227` | as above |

Boost peak current, worst case (`tps61022.pdf` eq. 5–7), at `VIN` = 3.0 V, `VOUT` = 5.0 V,
`IOUT` = 1.5 A **(est.)**, η = 0.9:

```
I_L,dc = 5.0 × 1.5 / (3.0 × 0.9)          = 2.78 A
D      = (5.0 − 3.0) / 5.0                = 0.40
ΔI_L   = 3.0 × 0.40 / (1 µH × 1 MHz)      = 1.20 A p-p
I_L,pk = 2.78 + 0.60                      = 3.38 A   -> want Isat ≥ 4.4 A
```

`DFE322512F` at 1 µH is rated well above that, and above `TPS61022`'s 6.5 A minimum valley current
limit, so the inductor does not saturate before the IC's own protection acts. Three of the four
inductors are the same part number deliberately — one line item, and the extra 0.5 mm of body on the
two bucks costs nothing on a board this size.

### 3.3 Capacitors — all from the datasheets' own tables

| Ref | Value | Where | Source |
| --- | --- | --- | --- |
| `C20`, `C21` | 1 µF/16 V | `U10` in, out | `tps7a02.pdf` §6.5 test conditions |
| `C22` | 22 µF/10 V | `+VSYS` bulk at `U11` | 10:1 CIN:CL ratio, `tps22965.pdf` §10.1.3 |
| `C23` | 470 pF/50 V | `U11` `CT` | rise time, §3.4 below |
| `C24` | 100 nF/16 V | `U11` `VBIAS` | bypass |
| `C25` | 22 µF/10 V | `U12` in | `tps61022.pdf` Fig. 8-2 |
| `C26`, `C27` | 22 µF/10 V | `U12` out | §8.2.2.3 asks for 10–50 µF **effective**; 2 × 22 µF derates into that band at 5 V |
| `C28` | 100 pF/50 V **DNP** | `U12` feedforward | §8.2.2.4; fitted only if the loop shows duty-cycle jitter |
| `C29` | 10 µF/10 V | `U13` in | `tps63802.pdf` §10.2.2.4 |
| `C30` | 22 µF/10 V | `U13` out | §10.2.2.3, single 22 µF for VOUT ≤ 3.6 V |
| `C31`, `C33` | 4.7 µF/10 V | `U14`, `U15` in | `tps62a01.pdf` §8.2.2.3 |
| `C32`, `C34` | 22 µF/6.3 V | `U14`, `U15` out | Table 8-3, the `++` recommended combination |

### 3.4 Inrush

`U11`'s `CT` pin sets the output slew: `SR = 0.38 × C_T + 34` µs/V (`tps22965.pdf` eq. 1). At
`C_T` = 470 pF the datasheet's own table gives ~654 µs at 3.3 V, so ~800 µs across a 4.2 V cell.
Charging `C25`'s 22 µF over that ramp draws `22 µF × 4.2 V / 800 µs ≈ 115 mA` — small enough that
the cell's `+VSYS` node does not dip when the SoM rail comes up. `C23` is 50 V rated because the
datasheet notes `CT` can swing to 12 V and asks for 25 V minimum.

## 4. Control and status

| Net | Direction | Drives | Default with the MCU unpowered |
| --- | --- | --- | --- |
| `MCU_EN_5V` | in | `U2.ON` | **low** — `R20` 100 k pull-down |
| `MCU_EN_3V3` | in | `U4.EN` | **low** — `R26` 100 k pull-down |
| `MCU_EN_FPGA_CORE` | in | `U5.EN` | **low** — `R31` 100 k pull-down |
| `MCU_EN_DDR` | in | `U6.EN` | **low** — `R35` 100 k pull-down |
| `PG_3V3` | out | `U4.PG` | open-drain, `R28` 470 k to `+3V3_AON` |
| `PG_1V2` | out | `U5.PG` | open-drain, `R32` 470 k to `+3V3_AON` |
| `PG_1V35` | out | `U6.PG` | open-drain, `R36` 470 k to `+3V3_AON` |

Every one of those four `EN` pins carries an explicit "do not leave floating" instruction in its
datasheet, and a pull-down satisfies it in the safe direction. The rails come up **only** because
firmware asked.

Three details worth stating:

- **Pull-ups are 470 kΩ, not the reflexive 10 k.** A power-good pin is low whenever its rail is off,
  which in standby is all of them; 10 k would burn 3 × 330 µA = 3.3 mW, a third of the entire
  standby budget, doing nothing. At 470 k the sink is 7 µA each and `VOL` is far below the 0.4 V
  spec, which is quoted at a 1 mA sink.
- **They pull up to `+3V3_AON`**, the one rail that is always present, so the MCU can read them
  before it enables anything. All three parts allow a pull-up above their own rail
  (`tps62a01.pdf` p.4: up to 5.5 V; `tps63802.pdf` Table 7-1: open-drain).
- **There is no `PG_5V`.** `TPS61022` has no power-good pin — it is a 7-pin part with no room for
  one. The 5 V rail's health is read from its `INA3221` bus-voltage channel on `power_mon` instead,
  which is a measurement the board already has to make.

**`MODE` pins are tied low through a 0 Ω link** (`R23` on `U12`, `R27` on `U13`), selecting automatic
power-save mode on both. This is a hardwired pin, which is the thing R1 got wrong — the difference
is that it is hardwired to the *low-power* state, and no operating mode of this board wants forced
PWM on a rail that spends its life at light load. The 0 Ω link rather than a direct tie leaves a
place to lift it if a bench measurement ever disagrees.

## 5. Sequencing

Enable order is firmware's, and it is not interlocked in hardware — no supervisor, no
enable-chaining. The MCU asserts, waits for `PG`, then asserts the next.

Xilinx recommends `VCCINT → VCCAUX → VCCO` for Spartan-6, which for this board means
`MCU_EN_FPGA_CORE`, then `MCU_EN_3V3` (which carries both `VCCAUX` and `VCCO`), then
`MCU_EN_DDR`. **Whether Spartan-6 actually requires that order or merely prefers it is not verified
here** — DS162 is not in `datasheets/`. WP5 must read it and either confirm the ordering is
advisory or add the interlock. R1 brings all rails up together and works, which is evidence but not
proof.

`+3V3_AON` needs no sequencing: it is up whenever `+VSYS` is, which is whenever a cell or USB is
present.

## 6. Deviations from `NOTES-R2-plan.md`

| Plan | Here | Why |
| --- | --- | --- |
| `+5V_SOM`, enable `MCU_EN_SOM` | `+5V_DCDC`, enable `MCU_EN_5V` | the rail feeds the SoM *and* the EPD HV chain, so naming it after one consumer misleads |
| `+3V3_SYS` and `+3V3_FPGA_IO` as two rails | one `+3V3_DCDC` | each 3.3 V rail costs a whole buck-boost (§2.1), and the plan itself says not to build around powering a `VCCO` bank down while the die is configured. Per-rail *measurement* is not lost: `power_mon`'s shunts can still split them |
| bucks direct from the cell | true for 1.2 V and 1.35 V; 3.3 V is buck-boost | §2.1 |
| `+5V2_FL` in the rail table | moved to `frontlight.kicad_sch` | an LED boost from `+VSYS` is one conversion, not two |

## 7. Footprints

Four of the five ICs land on stock KiCad 10 footprints, checked against the package names in each
datasheet's orderable-devices table:

| Part | Package | Footprint |
| --- | --- | --- |
| `TPS7A0233DBVR` | DBV | `Package_TO_SOT_SMD:SOT-23-5` |
| `TPS22965DSGR` | DSG0008A | `Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm` |
| `TPS61022RWUR` | RWU0007A | `Package_DFN_QFN:Texas_RWU0007A_VQFN-7_2x2mm_P0.5mm` |
| `TPS62A02DRLR` | DRL | `Package_TO_SOT_SMD:SOT-563` |
| `TPS63802DLAR` | DLA0010A | **`r2:Texas_DLA0010A_VSON-HR-10_2x3mm_P0.5mm` — does not exist yet** |

Three things to settle before layout:

1. **Author the `DLA0010A` footprint** from `tps63802.pdf`'s mechanical drawing (VSON-HR, 2 × 3 mm,
   0.5 mm pitch, 1 mm max height). VSON-HR has no exposed pad — KiCad's own
   `Texas_VSON-HR-8_1.5x2mm_P0.5mm` numbers pads 1–8 and nothing else, confirming the family
   convention. This is the only footprint that has to be drawn from scratch, and it is the one
   `footprint_link_issues` warns about in ERC today.
2. **`Texas_RWU0007A_VQFN-7_2x2mm_P0.5mm` leaves its thermal-pad segments unnumbered**, so the
   netlist does not connect them and `TPS61022`'s heat path is not tied to `GND`. Copy it into
   `r2.pretty` and number those pads `1` (the `GND` pin) before layout.
3. **Both inductor footprints are placeholders.** KiCad has no land pattern for either Murata DFE
   series, so `L10`/`L12`/`L13` currently carry `Inductor_SMD:L_1210_3225Metric` and `L11` carries
   `Inductor_SMD:L_1008_2520Metric`. Those are the right body sizes — 3.2 × 2.5 mm and
   2.5 × 2.0 mm — but a generic chip land is not a molded-inductor land. Check both against
   Murata's recommended pattern and copy corrected versions into `r2.pretty`. Two pads each; low
   risk, but it is a guess until checked.

`Texas_DSG0008A_...` does number its exposed pad `9`, which is why `TPS22965DSG` carries an `EP`
pin — without it the pad would be unrouted.

## 8. What this sheet costs

Converter overhead only; loads are elsewhere. Quiescent figures are datasheet typicals, load
figures are **(est.)**.

**Standby — `MCU_EN_*` all low, only `+3V3_AON` alive:**

| | |
| --- | --- |
| `U10` `TPS7A0233` Iq | 25 nA |
| `U11` `TPS22965` shutdown (`VBIAS` still on `+VSYS`) | ≤ 2 µA |
| `U12` `TPS61022` — input disconnected | ~0 |
| `U13` `TPS63802` shutdown | 45 nA (600 nA max) |
| `U14`, `U15` `TPS62A02` shutdown | 2 × 0.01 µA (2 µA max each) |
| three 470 k `PG` pull-ups, all rails low | 21 µA |
| **total** | **~24 µA ≈ 0.09 mW** |

Every feedback divider is on a converter *output*, and all three switchers actively discharge their
outputs when disabled, so no divider draws anything in standby. That is why the number is dominated
by the `PG` pull-ups — and why they are 470 k.

Against `NOTES-R2-plan.md`'s ~10 mW standby target, the rail tree's own overhead is about 1 %.

**Reading state — all rails on, converters idling:** roughly 0.6 mW of quiescent and divider
current across all five converters, against a 135–235 mW budget. Conversion *loss* under load is
the number that actually matters, and it is a property of the load, not of this sheet.

The honest comparison to R1 is not a percentage. R1's problem was never converter efficiency; it was
that four bucks could not be turned off at all. The result here is that they can.

## 9. Open

- **This doc still owes a "Layout guidelines" section**, in the shape of `battery.md` §11 — the
  switching-return / quiet-return separation, hot-loop minimisation and `SW`-node rules, per
  regulator. To be written with the review of this sheet, while the datasheets are open. Nothing
  in it is actionable until Stage D, but it has to be captured before the datasheets are closed.
- **`+3V3_AON` is now current-monitored — and this sheet needs a one-net change for it.** WP4 gave
  `U22` ch2 to the always-on domain (`epd-port.md` §3), freed by deleting the video rails. For that
  shunt to have an upstream net, **`U10`'s output must be renamed from `+3V3_AON` to
  `+3V3_AON_DCDC`** — one power symbol, matching the `*_DCDC` convention every other rail follows.
  Left for this sheet's reviewer rather than edited underneath them; until it is done,
  `+3V3_AON_DCDC` has no source and ERC says so.
- **Rail load estimates.** Every current in §1 and §3.2 is an estimate. The SoM figure in particular
  waits on PHYTEC; if `VIN` peak is materially above 1.2 A, re-run §3.2's peak calculation.
- ~~**`+5V` for the EPD HV chain.**~~ **Answered in WP4** (`epd-port.md` §4.1): no. The `LGS5145`
  is a buck with a 4.5 V minimum input, run here as an inverting buck-boost. In steady state its
  `GND` pin sits on the negative rail so it sees ~25 V, but **at startup that rail is at 0 V** and
  the part sees `+VSYS` alone — 3.0 V from a flat cell will not start it. The 5 V feed stays.
- **Spartan-6 sequencing** — §5.
- **The `DLA0010A` footprint and the `RWU0007A` thermal pad** — §7.
- **`battery.kicad_sch`'s `+3V3_AON` `PWR_FLAG` is now an ERC error, and it is the only one.**
  WP1 added it because nothing sourced that rail yet; `U10`'s `OUT` pin is a real `power_out`, so
  ERC reports `pin_to_pin: Pins of type Power output and Power output are connected` between
  `#FLG04` and `U10.5`. The fix is to delete that one symbol — it sits at (360.68, 205.74) on the
  battery sheet, the rightmost of the five flags, labelled `+3V3_AON`. Left in place deliberately:
  the battery sheet is out for review and editing it underneath an open Eeschema session would
  throw away unsaved work.

## 10. Conventions

Reference designators on this sheet start at 10 (`U`, `L`) and 20 (`R`, `C`), and its `#PWRnnn`
symbols at 200. KiCad requires references to be unique across the whole design, not per sheet, and
`battery.kicad_sch` already owns `U1`–`U3`, `C1`–`C8`, `R1`–`R19` and `L1`. Each new sheet should
take its own block the same way rather than relying on a global re-annotate, which would renumber
the sheets that are already reviewed.

## 11. Verification — what was actually run

- **ERC on the whole project: 25 violations, one of them real.** 19 `pin_not_connected` (the sheet
  pins on the parent, 12 from `battery` and 7 from here), 3 `isolated_pin_label` + 1
  `pin_not_driven` on `CHG_QON#` (WP1, waiting on the MCU sheet), 1 `footprint_link_issues` (the
  `DLA0010A` footprint, §7), and 1 `pin_to_pin` — the redundant `+3V3_AON` flag in §9.
- **`kicad-cli sch export netlist` read node by node.** Every net on this sheet was checked against
  the intent, which is how WP1's three missing pull-downs were caught: ERC cannot see a pin that is
  connected to exactly one other thing and should not be. Confirmed:
  - `VSYS_SW` = `C25.1, L10.1, U11.7, U11.8, U12.5(EN), U12.7(VIN)` — the switched node feeds the
    boost's input *and* its enable, which is the §2.2 arrangement.
  - `Net-(U12-FB)` = `C28.2, R21.2, R22.1, U12.4` — divider midpoint with the DNP feedforward.
  - `+1V2_DCDC` = `C32.1, L12.2, R29.1` and `+1V35_DCDC` = `C34.1, L13.2, R33.1` — the rail is the
    far side of the inductor, not the `SW` pin.
  - `GND` picks up `U11.5` + `U11.9(EP)` and `U13.3(AGND)` + `U13.8(GND)`.
  - Every `MCU_EN_*` net is exactly its pull-down plus one enable pin; every `PG_*` is exactly its
    pull-up plus one power-good pin.
- **Divider arithmetic in §3.1** recomputed from the E96 values actually in the file.
- **Every pin number in `r2.kicad_sym`'s four new symbols** checked against the datasheet pin table
  cited in `tools/gen_r2_symbols.py`.

Not verified, and not verifiable here: nothing on this sheet has been built or measured. The
standby figure in §8 is arithmetic on datasheet typicals, not a bench result.
