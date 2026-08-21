# `power.kicad_sch` — rail tree — R2 work package 2

Status: **reviewed once; review-1 fixes applied.** Last updated 2026-08-11.

**§10 answers the points raised in `../manual-analysis/Analysis_power.md` and lists what changed in
the schematic as a result. Read that section first if you are coming from those notes.** One of them
found a real error: the `TPS61022` *does* have true output disconnect in shutdown, so the
`TPS22965` load switch that §2.2 existed to justify has been deleted. Everything here cites either a
datasheet in `../datasheets/` (with the page or table), the LCSC catalogue, or a file in this repo.
Estimates are marked **(est.)** and are the things a bench measurement has to replace.

The sheet has been hand-edited and saved in Eeschema, so **`power.kicad_sch` — not
`tools/gen_power.py` — is the source of truth.** Review-1 was applied with
`tools/patch_power_review1.py`, which patches the file in place and refuses to run twice.

This is the sheet R2 exists for. R1's `pcb/mainboard/power.kicad_sch` wires every buck's `~SHDN`
pin to `+5V`, so 82 % of idle power sits on rails no firmware can switch off (`NOTES-STATUS.md`).
Here **every rail below `+3V3_AON` has a named enable net, a named owner, and a pull-down that makes
"off" the state the board powers up in.**

---

## 1. Rail tree

```
+VSYS  (charger power-path output, battery.kicad_sch; 3.0-4.4 V)
  |
  +-- U10  TPS7A0233   LDO        -> +3V3_AON_DCDC   always on          ~25 nA Iq
  +-- U12  TPS61022    boost      -> +5V_DCDC        MCU_EN_5V
  +-- U13  TPS63802    buck-boost -> +3V3_DCDC       MCU_EN_3V3
  +-- U14  TPS62A02    buck       -> +1V2_DCDC       MCU_EN_FPGA_CORE
  +-- U15  TPS62A02    buck       -> +1V5_DCDC      MCU_EN_DDR
```

`U11` is deliberately absent: it was a `TPS22965` load switch in front of the boost, deleted in
review 1 (§2.2, §10.7). Its reference is not reused, so that the git history and the review notes
stay legible.

`*_DCDC` is R1's naming convention: the converter output goes to a shunt on `power_mon`, and the
load-side net that comes back out of that shunt is the plain rail name. So this sheet ends at
`+3V3_AON_DCDC` / `+5V_DCDC` / `+3V3_DCDC` / `+1V2_DCDC` / `+1V5_DCDC`, and `power_mon` produces
`+3V3_AON`, `+5V`, `+3V3`, `+1V2_FPGA`, `+1V5`. Keeping the convention makes WP4's port of
`power_mon` from R1 a straight copy.

| Rail | Topology | Part | LCSC | Stock | Enable | Loads |
| --- | --- | --- | --- | --- | --- | --- |
| `+3V3_AON_DCDC` | LDO 200 mA | `TPS7A0233DBVR` | `C5142805` | 433 | none (EN tied to IN) | STM32G0, I²C pull-ups, buttons, charger/gauge I²C |
| `+5V_DCDC` | boost 5.0 V | `TPS61022RWUR` | `C915088` | 39457 | `MCU_EN_5V` | SoM `VIN`, EPD HV chain |
| `+3V3_DCDC` | buck-boost 2 A | `TPS63802DLAR` | `C2845237` | 1338 | `MCU_EN_3V3` | FPGA `VCCO`/`VCCAUX`, config NOR, panel logic |
| `+1V2_DCDC` | buck 2 A | `TPS62A02DRLR` | `C5350187` | 3202 | `MCU_EN_FPGA_CORE` | Spartan-6 `VCCINT` |
| `+1V5_DCDC` | buck 2 A | `TPS62A02DRLR` | `C5350187` | 3202 | `MCU_EN_DDR` | DDR3L, FPGA DDR bank `VCCO` |

Four rails, four identical control patterns: one `MCU_EN_*` net, one 100 kΩ pull-down, one
enable pin. That uniformity is a review-1 result — before it, the 5 V rail was the odd one out.

Not on this sheet: the frontlight boost (`frontlight.kicad_sch`, WP6 — an LED driver runs from
`+VSYS` directly, one conversion instead of two), the EPD HV chain (`epd_power.kicad_sch`, WP4,
from `+5V`), and `+3V3_TOUCH` / `+3V3_PEN` (`io_expansion.kicad_sch`, WP6).

## 2. Two findings that changed the plan — and one that was wrong

### 2.1 A 1S cell cannot buck to 3.3 V — `+3V3` needs a buck-boost

`NOTES-R2-plan.md` says "run the bucks from the cell, not from a 5 V intermediate", and for 1.2 V
and 1.5 V that is exactly right. It does not work for 3.3 V: `+VSYS` runs from about 4.4 V down to
3.0 V, so a step-down converter drops out somewhere around half the discharge curve and the FPGA's
I/O rail sags with the battery.

Three ways out, and why the third wins:

| | Efficiency | Cost |
| --- | --- | --- |
| Buck from `+5V_DCDC` | ~92 % boost × ~92 % buck = **~85 %** | ties `+3V3` to the 5 V rail — R1's mistake in a new place |
| LDO from `+5V_DCDC` | 3.3/5.0 = **66 %** | worse |
| **Buck-boost from `+VSYS`** | **~93 %** across the whole cell range | one extra part type |

`TPS63802` also brings **true shutdown with load disconnect** (datasheet §1): when disabled it
isolates the output instead of leaking through a body diode. That matters for standby — see §8.

### 2.2 The boost needs no load switch — **corrected in review 1**

This section previously argued that "a boost passes its input through when disabled", that
`TPS61022`'s high-side body diode would leave ~3.4 V on the SoM's `VIN`, and that a `TPS22965`
(`U11`) was therefore needed on the boost's input. **That was wrong, and `U11` has been deleted.**

`tps61022.pdf` says the opposite three times:

- **p.1 Features:** "**True disconnection between input and output during shutdown**."
- **p.1 Description:** "During shutdown, the load is completely disconnected from the input power."
- **§7.3.2:** "When the voltage at the `EN` pin is below 0.4 V, the internal enable comparator turns
  the device into shutdown mode. In the shutdown mode, the device is entirely turned off. **The
  output is disconnected from input power supply.**"

And §6.5 quantifies it in the direction that matters most: `IVOUT_LKG`, "Leakage current into `VOUT`
pin", is **1 µA typ / 3 µA max** measured at "IC disabled, `VIN` = 0 V, `VSW` = 0 V, `VOUT` = 5.5 V".
Forcing 5.5 V onto a dead `VOUT` and seeing 1 µA proves the isolation blocks `VOUT → VIN` as well as
`VIN → VOUT`; a body-diode path in either direction would show milliamps.

The physics is consistent with the claim. §7.3.5 and Table 5-1 name the high-side device a **PMOS**;
in a synchronous boost built for true shutdown its source sits on `SW`, so its body diode faces
`VOUT → SW` and blocks the `VIN → L → SW → VOUT` path. The price is that the part cannot rectify
through a diode, only through the channel — which is why it is synchronous-only. §7.3.5, the section
the old text cited, describes pass-through while the device is **enabled** and `VIN` exceeds the
setpoint. It says nothing about the disabled state; citing it for the disabled state was the mistake.

So `MCU_EN_5V` now drives `U12.EN` directly, with `R20` 100 kΩ as its pull-down, and the boost runs
from `+VSYS` directly. `VSYS_SW` no longer exists. What the deletion cost and did not cost:

| | |
| --- | --- |
| saved | one 6 A load switch, `C23` (`CT`), `C24` (`VBIAS`) |
| saved, reading state | `VBIAS` quiescent 30–50 µA ‡ (`tps22965.pdf` §7.5/§7.6) ≈ 0.15 mW |
| saved, at load | `RON` 16 mΩ ‡ × (2.3 A **(est.)** input) ² ≈ **85 mW** and 37 mV of drop |
| lost | the switch's quick-output-discharge, a 225 Ω pull-down on its output ‡ §9.3.2 |
| lost | `CT`-programmed 800 µs inrush ramp — see §3.4 for what replaces it |
| not lost | shutdown leakage: `U11` was ≤ 2 µA ‡, `U12` alone is 0.25 µA typ / 3.5 µA max ‡ §6.5 |

The one thing worth watching on a bench: with nothing pulling `+5V_DCDC` down, the rail decays
through the SoM's and the EPD chain's input leakage rather than being discharged. `C26`+`C27` are
44 µF nominal, so the decay is fast if that leakage is tens of µA and slow if it is nanoamps.
**Needs a hardware test.** If it turns out slow enough to matter, the fix is one resistor to `GND`,
not a load switch.

## 3. Arithmetic

### 3.1 Feedback dividers

`VOUT = VFB × (1 + R_top / R_bot)`.

| Rail | VFB | R_top | R_bot | Result | Source |
| --- | --- | --- | --- | --- | --- |
| `+5V_DCDC` | 0.600 V | `R21` 732 k | `R22` 100 k | 0.600 × (1 + 7.32) = **4.992 V** | `tps61022.pdf` §6.5, §8.2.2.1 |
| `+3V3_DCDC` | 0.500 V | `R24` 511 k | `R25` 91 k | 0.500 × (1 + 5.615) = **3.308 V** | `tps63802.pdf` Table 10-5 — TI's own row for 3.3 V |
| `+1V2_DCDC` | 0.600 V | `R29` 100 k | `R30` 100 k | 0.600 × 2 = **1.200 V** | `tps62a01.pdf` §8.2.2.1 |
| `+1V5_DCDC` | 0.600 V | `R33` 150 k | `R34` 100 k | 0.600 × (1 + 1.50) = **1.500 V** | as above |

All E96, all 1 %, all stocked at LCSC in 0402 (checked 2026-08-06).

Margin checks. SoM `VIN` is 4.5–5.5 V; 4.992 V ±2.5 % reference tolerance gives 4.87–5.12 V, inside
with room for load regulation.

**The DDR bank is 1.5 V, not 1.35 V — changed in WP5, 2026-08-12.** The binding number is
not the DRAM's but the FPGA's: `ds162.pdf` Table 7 specifies `SSTL15_II` over VCCO **1.425–1.575 V**
(VREF 0.69–0.81 V), and Caster's UCF constrains all 48 DDR pins to that standard. The previous
1.344 V sat 81 mV below the minimum, and Spartan-6 has no 1.35 V I/O standard to relabel to. At
1.500 V the two windows coincide exactly — DDR3 1.5 V ±0.075 V is also 1.425–1.575 V — which is no
accident, since `SSTL15` exists to drive DDR3. `mt41k64m16.pdf` p.1 makes it legal on the memory
side: "Backward compatible to VDD = VDDQ = 1.5V ±0.075V", so `MT41K64M16TW` stays the fitted part
and simply runs in its 1.5 V compatible mode. **One consequence to carry into WP5:** that same page
says "Refer to the DDR3 (1.5V) SDRAM data sheet specifications when running in 1.5V compatible
mode", so the AC/DC tables in `mt41k64m16.pdf` no longer apply and Micron's DDR3 datasheet is
needed for `fpga_ddr`'s timing and termination work.

`R_bot` is held at or below 100 kΩ everywhere, which is what all three datasheets ask for
(noise sensitivity, and keeping divider current at least 100× the FB leakage). Worst case is
`+3V3_DCDC`: 0.5 V / 91 k = 5.5 µA against 100 nA max FB leakage — 55×, so the 91 k value is TI's
own trade and is kept rather than raised.

### 3.2 Inductors

Ratings re-read off the LCSC catalogue 2026-08-11, because the schematic's `Value` fields said
"/6A" and no inductor here is rated for that (§10.11):

| Ref | Rail | Value | Part | LCSC | Size | Isat | Irms | Rdc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `L10` | `+5V_DCDC` | 1 µH | `DFE322512F-1R0M` | `C3224227` | 1210 | 4.8 A | 3.8 A | 32 mΩ |
| `L11` | `+3V3_DCDC` | 0.47 µH | `DFE252012F-R47M` | `C703140` | 1008 | 7.4 A | 4.9 A | 23 mΩ |
| `L12` | `+1V2_DCDC` | 1 µH | `DFE322512F-1R0M` | `C3224227` | 1210 | 4.8 A | 3.8 A | 32 mΩ |
| `L13` | `+1V5_DCDC` | 1 µH | `DFE322512F-1R0M` | `C3224227` | 1210 | 4.8 A | 3.8 A | 32 mΩ |

Values: 1 µH for the boost (`tps61022.pdf` Fig. 8-1), 0.47 µH for the buck-boost
(`tps63802.pdf` Table 10-1), 1 µH for both bucks (`tps62a01.pdf` Table 8-3, row `1.2 ≤ VOUT < 1.8`).

Boost peak current, worst case (`tps61022.pdf` eq. 1–3), at `VIN` = 3.0 V, `VOUT` = 5.0 V,
`IOUT` = 1.5 A **(est.)**, η = 0.9:

```
I_L,dc = 5.0 × 1.5 / (3.0 × 0.9)          = 2.78 A   -> vs Irms 3.8 A, 37 % margin
D      = (5.0 − 3.0) / 5.0                = 0.40
ΔI_L   = 3.0 × 0.40 / (1 µH × 1 MHz)      = 1.20 A p-p
I_L,pk = 2.78 + 0.60                      = 3.38 A   -> vs Isat 4.8 A, 42 % margin
```

**Correction to the previous text, which claimed `DFE322512F` is rated "above `TPS61022`'s 6.5 A
minimum valley current limit". It is not: Isat is 4.8 A.** Under an output overload the inductor
therefore soft-saturates before the IC's own limit acts. That is tolerable rather than wrong,
because `DFE322512F` is a metal-composite part: Murata's Isat is the −30 % inductance point and the
roll-off is gradual, so the consequence is more ripple and an earlier valley-limit trip, not the
thermal runaway a ferrite would give. In normal operation the peak is 42 % below Isat. **If the
SoM's `VIN` current comes back from PHYTEC materially above 1.5 A, re-run this block** — at
`IOUT` = 2.0 A the peak is 4.31 A and the margin is gone.

The two bucks are nowhere near their inductors' limits. R1 measured `FPGA CORE` at 165.6 mW active
(`NOTES-STATUS.md`) — about 138 mA at 1.2 V — and `FPGA DDR` at 101.5 mW, about 75 mA at 1.35 V. At
`fSW` = 2.4 MHz ‡ and 1 µH, ΔI_L is 0.36 A p-p and the peak is ~0.32 A, a fifteenth of Isat. The
1210 part is kept anyway because it covers `TPS62A02`'s own 2.7–3.4 A high-side current limit ‡
§6.5, i.e. an output short cannot saturate it, and because three of the four inductors are then one
line item.

### 3.3 Capacitors — all from the datasheets' own tables

| Ref | Value | Where | Source |
| --- | --- | --- | --- |
| `C20`, `C21` | 1 µF/16 V | `U10` in, out | `tps7a02.pdf` §6.3 Recommended Operating Conditions: `CIN` 1 µF nom, `COUT` 1 µF nom (1 µF min, 22 µF max, ≥ 0.5 µF effective for stability) |
| `C22` | 22 µF/10 V | `+VSYS` bulk | not a datasheet requirement; bulk at the rail entry, and the boost draws ~2.8 A pulses at 1 MHz off this plane |
| `C25` | 22 µF/10 V | `U12` in | `tps61022.pdf` §8.2.2.5 — "a 10-µF input capacitor is sufficient for most applications, larger values may be used"; Fig. 8-1 draws 10 µF |
| `C26`, `C27` | 22 µF/10 V | `U12` out | §8.2.2.3 asks for 10–50 µF **effective**; 2 × 22 µF derates into that band at 5 V |
| `C28` | 100 pF/50 V **DNP** | `U12` feedforward | §8.2.2.4: `C3` = 1/(2π·fFFZ·R1) = 1/(2π · 2 kHz · 732 k) = 109 pF, and the 2 kHz zero is only wanted above 40 µF effective — see §10.9 |
| `C29` | 10 µF/10 V | `U13` in | `tps63802.pdf` §10.2.2.4 |
| `C30` | 22 µF/10 V | `U13` out | §10.2.2.3, single 22 µF for VOUT ≤ 3.6 V |
| `C31`, `C33` | 4.7 µF/10 V | `U14`, `U15` in | `tps62a01.pdf` §8.2.2.3 and Table 8-2 |
| `C32`, `C34` | 22 µF/10 V | `U14`, `U15` out | Table 8-3, the `++` recommended combination; 10 V per Table 8-2 (§10.12) |

`C23` and `C24` were `U11`'s `CT` and `VBIAS` parts and are deleted with it (§2.2). The reference
numbers are not reused.

### 3.4 Inrush — now the boost's own, not a load switch's

With `U11` deleted (§2.2) the 800 µs `CT` ramp is gone and `TPS61022`'s own start-up sequence is what
limits the current the cell sees. `tps61022.pdf` §7.3.2 and §6.5:

1. Below `VOUT` = 0.4 V, the pre-charge current is `ILIM_CHG` = **400 mA min / 700 mA typ**.
2. Above 0.4 V and until `VOUT` reaches `VIN`, it charges with "output current capability to drive a
   1 Ω resistance load", bounded by `ILIM_CHG_max` = **2.0 A min / 2.4 A typ**.
3. Only then does it start switching. Typical `tSS` is 700 µs to regulation with 30 µF effective and
   no load.

So the worst case the cell must supply on a 5 V enable is ~2.4 A for a few hundred µs, against
~115 mA over 800 µs before. At a 5000 mAh cell's ~50–100 mΩ ESR that is a **120–240 mV dip on
`+VSYS`**, plus whatever the charger's `SYS` impedance adds. Everything on the board tolerates it:
`+3V3_AON`'s LDO has 270 mV dropout at 200 mA ‡ and `+VSYS` sits at 3.0 V worst case with 3.3 V
wanted — so a dip while the cell is nearly flat is the one case to watch — and the other three
converters have their own UVLOs well below (`TPS63802` 1.25 V ‡, `TPS62A02` 2.3 V ‡).

`C22` + `C25` = 44 µF nominal on `+VSYS` at the boost input is what holds that dip down, which is why
`C22` is kept even though it no longer belongs to a load switch. **Needs a hardware test:** enable
the 5 V rail with the cell at 3.3 V and scope `+VSYS`. If the dip is a problem the answer is more
input bulk, or firmware enabling the rail before the panel rails rather than after.

## 4. Control and status

| Net | Direction | Drives | Default with the MCU unpowered | Guaranteed-on / guaranteed-off |
| --- | --- | --- | --- | --- |
| `MCU_EN_5V` | in | `U12.EN` | **low** — `R20` 100 k pull-down | ≥ 1.2 V / ≤ 0.35 V ‡ `tps61022.pdf` §6.5 |
| `MCU_EN_3V3` | in | `U13.EN` | **low** — `R26` 100 k pull-down | ≥ 1.2 V / ≤ 0.4 V ‡ `tps63802.pdf` §8.5 |
| `MCU_EN_FPGA_CORE` | in | `U14.EN` | **low** — `R31` 100 k pull-down | ≥ 1.2 V / ≤ 0.4 V ‡ `tps62a01.pdf` §6.5 |
| `MCU_EN_DDR` | in | `U15.EN` | **low** — `R35` 100 k pull-down | as above |
| `PG_3V3` | out | `U13.PG` | open-drain, `R28` 470 k to `+3V3_AON` | |
| `PG_1V2` | out | `U14.PG` | open-drain, `R32` 470 k to `+3V3_AON` | |
| `PG_1V5` | out | `U15.PG` | open-drain, `R36` 470 k to `+3V3_AON` | |

Every one of those four `EN` pins carries an explicit "do not leave floating" instruction in its
datasheet, and a pull-down satisfies it in the safe direction. The rails come up **only** because
firmware asked. There is no series resistor in any enable path, so an `MCU_EN_*` pin driven high sits
at the full `+3V3_AON` — 3.3 V against a 1.2 V threshold and a 6.5 V absolute maximum ‡. Held low, the
pull-down has to sink only the pin's own leakage: 100 nA max ‡ × 100 kΩ = **10 mV**, and 0.2 µA ‡ ×
100 kΩ = 20 mV on the `TPS63802`, both far under the 0.35–0.4 V guaranteed-off level. See §10.1.

Three details worth stating:

- **Pull-ups are 470 kΩ, not the 100 kΩ TI draws.** A power-good pin is low whenever its rail is off,
  which in standby is all of them. TI's own figures use 100 kΩ (`tps63802.pdf` Fig. 10-1 `R3`,
  `tps62a01.pdf` Fig. 8-2 `R4` at 499 kΩ), which here would burn 3 × 33 µA = 0.33 mW — about 3 % of
  the ~10 mW standby target, for nothing. At 470 k it is 3 × 7 µA = 0.07 mW. The honest size of the
  win is 0.26 mW; the reason to take it is that it costs no margin at either end. See §10.6 for the
  `VOL` and rise-time arithmetic.
- **They pull up to `+3V3_AON`**, the one rail that is always present, so the MCU can read them
  before it enables anything. Both parts allow a pull-up rail different from their own `VIN`
  (`tps62a01.pdf` §7.4.2: "a pullup resistor to any voltage up to the recommended input voltage
  level"; `tps63802.pdf` §9.3.10: "any voltage rail less than 5.5 V"). §10.4 works through the one
  caveat that comes with that — `VIN` must be present for `PG` to read low — and why it is satisfied
  here.
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
`MCU_EN_DDR`.

~~**Whether Spartan-6 actually requires that order or merely prefers it is not verified here.**~~
**Closed in WP5, 2026-08-12: the order is advisory, not required.** `ds162.pdf` is now in
`../datasheets/`, and note 2 under Table 6 says it in one sentence: *"Spartan-6 devices do not have
a required power-on sequence."* So no interlock is needed and firmware's ordering is a preference —
R1 bringing all rails up together was not getting away with something.

**But DS162 replaces that question with a stricter one nobody has checked: Table 6 requires each
supply to ramp within 0.20–50.0 ms.** It applies to `VCCINT`, `VCCAUX` and `VCCO2` alike (`VCCINTR`,
`VCCAUXR`, `VCCO2` — all "0.20 to 50.0 ms"). A rail that ramps *too slowly* is a violation, not just
an inelegance, and nothing in this document has yet been checked against it: the soft-start times of
`U13` (`TPS63802`), `U14`/`U15` (`TPS62A02`) and the `+3V3` buck-boost all need comparing against
that 50 ms ceiling, including the worst case of a nearly-flat cell. **New open item in §9.**

Two smaller requirements from the same table, both already satisfied: `VCCO2` must be ≥ 1.65 V for
power-on reset and configuration (bank 2 is on `+3V3`, so fine), and `VCCO2` is explicitly *not*
required for data retention.

`+3V3_AON` needs no sequencing: it is up whenever `+VSYS` is, which is whenever a cell or USB is
present.

### 5.1 ⚠ SoM rail order — `+5V_SOM`, then `+3V3`, and reset held across both

**Revised 2026-08-15, and the earlier version of this section was wrong in the dangerous
direction.** It concluded "`MCU_EN_3V3` and `PG_3V3` before `MCU_EN_5V`". That is backwards, and it
violates a requirement `L-1038e.A5` §5.4 states as **mandatory**:

> "It is **mandatory to avoid driving the I/O pins of the phyCORE-AM62x SOM when the SOM is not
> fully powered up.** Prematurely driving the pins may cause current to flow through the I/O pins
> before the processor is properly powered, potentially resulting in damage or unknown behavior
> after power-up or reset. Therefore, the peripheral carrier board power should be switched
> on/enabled by the `X_PGOOD` signal … This should be used to sequence the baseboard power supplies
> (3.3V, 1.8V, etc.)."

`+3V3` is `VCCO` for FPGA banks 0/1/2, and bank 1 is the twenty-two DPI lines that face the SoM. So
bringing `+3V3` up first is exactly the case PHYTEC says can damage the module. The old text
reached the opposite conclusion because it optimised for one constraint (below) without checking
whether the SoM had a rule of its own. **It did, in the same manual, three sections earlier.**

**The other constraint is still real.** Two of the eighteen DPI signals — `DPI_R7` and `DPI_R6` —
land on the module's `BOOTMODE_9`/`BOOTMODE_8`, part of the **primary boot mode selection**
(`L-1038e.A5` Table 31 states the mapping outright: `VOUT0_DATA16` → `X1 D2` →
`X_GPMC0_AD8/BOOTMODE_8`, `VOUT0_DATA17` → `X1 D4` → `X_GPMC0_AD9/BOOTMODE_9`, both 100 kΩ pullup
on the SOM). An FPGA whose `VCCO` is off does not present a high impedance — its input ESD
structure clamps toward the unpowered rail, and a forward-biased clamp diode beats a 100 kΩ
pull-up. If `+3V3` is down when the SoM **samples** boot mode, `BOOTMODE_9` latches 0 instead of 1.

**Both are satisfiable, because "the SoM is powered" and "the SoM samples boot mode" are two
different instants** — separated by cold reset, which we already control. `X_nRESET_IN` (`X1 C52`,
10 kΩ pullup + 100 nF on the SOM, Table 13) is the cold system reset input, and `mcu.md` §4 has
declared `SOM_RESET#` as an open-drain GPIO on `PA15` since WP3. Hold it low across the 5 V ramp:

| # | Step | Which rule it serves |
| --- | --- | --- |
| 1 | `SOM_RESET#` asserted low (open-drain, so it sinks; no injection into an unpowered pin) | — |
| 2 | `MCU_EN_5V` high → `+5V_SOM`. SoM PMIC sequences. `+3V3` still **off**, so every FPGA pin facing the SoM is unpowered and drives nothing | **PHYTEC §5.4** |
| 3 | Wait for `X_PGOOD` (`X2` C54, open-drain, 100 kΩ pullup on the SOM) | **PHYTEC §5.4** |
| 4 | `MCU_EN_3V3` high, wait `PG_3V3` → FPGA `VCCO` up | — |
| 5 | Release `SOM_RESET#`. The SOM's own 10 kΩ × 100 nF ≈ 1 ms RC delays the actual release, then `BOOTMODE_8/9` are sampled with `+3V3` already stable | **BOOTMODE** |

The manual gives the latch criterion exactly, which is better than "before reset releases": *"The
BOOTMODE signals must be held at the desired configuration **until `X_PORz_OUT` goes high** to be
properly latched into the system"* (§6.3). Holding `X_nRESET_IN` low holds `PORz` asserted, so
`X_PORz_OUT` (`X1 C57`) cannot go high until step 5 — the sequence satisfies the stated condition by
construction rather than by timing luck. `X_PORz_OUT` is an output and could be brought to the MCU
as a confirmation, but it is not needed to *make* the sequence correct, only to observe it.

Step 4 also keeps the Spartan-6 preference above intact (`MCU_EN_FPGA_CORE` → `MCU_EN_3V3` →
`MCU_EN_DDR`); it simply moves that whole group after the SoM instead of before it. The 100 nF on
`X_nRESET_IN` is a gift here — it makes step 5 self-delaying rather than something firmware has to
time.

**This adds one signal to the design, and it is not drawn yet.** `X_PGOOD` must reach the MCU:

> **`PG_SOM`** — `X2` C54 → a spare MCU GPIO. `PC8` is the suggestion (a plain GPIO; the four
> ADC-capable spares are worth keeping for analogue). The pin is open-drain with its pull-up on the
> SOM's own 3.3 V, so when the SoM is unpowered the net floats — **enable the MCU's internal
> pull-down** so "no SoM" reads as "not good" rather than as noise. A pull-down is the safe
> direction: it sinks, it does not inject.

That is a WP8 item on `som.kicad_sch` and a small edit to `mcu.kicad_sch`, listed in `mcu.md` §9's
open items rather than made silently on a reviewed sheet.

**No hardware interlock is proposed**, though PHYTEC's Figure 20 shows one (a load switch on the
baseboard rails, enabled by `X_PGOOD`). Ours is firmware sequencing against `PG_SOM`, which costs
no parts and keeps firmware's ability to run the SoM with the FPGA rail down — a state the reading
architecture may want. The trade is that a firmware bug can now do what a load switch would have
prevented, so the sequence above is a **hard requirement on `power.c`, not a preference**.

**Not verified on hardware.** Two distinct failure modes now, and they differ in severity: getting
step 4 before step 2 risks *module damage* (PHYTEC's wording), and getting step 5 before step 4
gives an *intermittent wrong boot device*. The first is why this correction matters more than the
original note did.

One ordering consequence of deleting `U11` (§2.2): the boost no longer has to wait for a switched
input to cross its 1.8 V start-up UVLO ‡, so `MCU_EN_5V` high starts it immediately. Firmware's
5 V step is now a plain "assert, wait `tSS` ≈ 700 µs ‡ plus margin, read the rail on `power_mon`" —
there is no `PG_5V` (below), so the 5 V rail is the one step that is confirmed by measurement
rather than by a pin. With `PG_SOM` added, the *SoM* side of that step does get a pin.

## 6. Deviations from `NOTES-R2-plan.md`

| Plan | Here | Why |
| --- | --- | --- |
| `+5V_SOM`, enable `MCU_EN_SOM` | `+5V_DCDC`, enable `MCU_EN_5V` | the rail feeds the SoM *and* the EPD HV chain, so naming it after one consumer misleads |
| "needs a load switch on the boost input" | no load switch | the plan's premise — that a disabled boost passes its input through — is not true of `TPS61022`. §2.2, §10.7 |
| `+3V3_SYS` and `+3V3_FPGA_IO` as two rails | one `+3V3_DCDC` | each 3.3 V rail costs a whole buck-boost (§2.1), and the plan itself says not to build around powering a `VCCO` bank down while the die is configured. Per-rail *measurement* is not lost: `power_mon`'s shunts can still split them |
| bucks direct from the cell | true for 1.2 V and 1.5 V; 3.3 V is buck-boost | §2.1 |
| `+5V2_FL` in the rail table | moved to `frontlight.kicad_sch` | an LED boost from `+VSYS` is one conversion, not two |

## 7. Footprints

Three of the four ICs land on stock KiCad 10 footprints, checked against the package names in each
datasheet's orderable-devices table:

| Part | Package | Footprint |
| --- | --- | --- |
| `TPS7A0233DBVR` | DBV | `Package_TO_SOT_SMD:SOT-23-5` |
| `TPS61022RWUR` | RWU0007A | `Package_DFN_QFN:Texas_RWU0007A_VQFN-7_2x2mm_P0.5mm` |
| `TPS62A02DRLR` | DRL | `Package_TO_SOT_SMD:SOT-563` |
| `TPS63802DLAR` | DLA0010A | **`r2:Texas_DLA0010A_VSON-HR-10_2x3mm_P0.5mm` — does not exist yet** |

Three things to settle before layout:

1. **Author the `DLA0010A` footprint** from `tps63802.pdf`'s mechanical drawing (VSON-HR, 2 × 3 mm,
   0.5 mm pitch, 1 mm max height). VSON-HR has no exposed pad — KiCad's own
   `Texas_VSON-HR-8_1.5x2mm_P0.5mm` numbers pads 1–8 and nothing else, confirming the family
   convention. This is the only footprint that has to be drawn from scratch, and it is the one
   `footprint_link_issues` warns about in ERC today.
2. ~~**`Texas_RWU0007A_VQFN-7_2x2mm_P0.5mm` leaves its thermal-pad segments unnumbered**, so the
   netlist does not connect them and `TPS61022`'s heat path is not tied to `GND`.~~
   **WRONG — withdrawn 2026-08-22. No fix needed; do not "correct" this footprint.**
   The six unnumbered pads are **`F.Paste` only**. They are stencil apertures, not copper: each of
   the three large pads is split into two paste openings to control solder volume, which is the
   standard KiCad idiom for a pad this size. Read off the placed footprint:

   | pad | layers | net |
   | --- | --- | --- |
   | *(six unnumbered)* | `F.Paste` | — |
   | `1` | `F.Cu` `F.Mask` | `GND` |
   | `2` | `F.Cu` `F.Mask` | `Net-(U12-SW)` |
   | `3` | `F.Cu` `F.Mask` | `+5V_DCDC` |
   | `4`–`7` | `F.Cu` `F.Mask` `F.Paste` | `FB`, `MCU_EN_5V`, `MODE`, `+VSYS` |

   Every copper pad is numbered and netted. Pin 1 *is* the thermal path (‡ Table 5-1) and it is on
   `GND`. The original note was written from a pad list that did not show the layer field, and it
   would have sent someone to copy a correct library footprint into `r2.pretty` and renumber paste
   apertures into copper — creating the short it was trying to prevent. §11.2 item 5 amended to
   match.
3. **Both inductor footprints are placeholders.** KiCad has no land pattern for either Murata DFE
   series, so `L10`/`L12`/`L13` currently carry `Inductor_SMD:L_1210_3225Metric` and `L11` carries
   `Inductor_SMD:L_1008_2520Metric`. Those are the right body sizes — 3.2 × 2.5 mm and
   2.5 × 2.0 mm — but a generic chip land is not a molded-inductor land. Check both against
   Murata's recommended pattern and copy corrected versions into `r2.pretty`. Two pads each; low
   risk, but it is a guess until checked.

Deleting `U11` (§2.2) removed the `Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm` line item and
with it one of the three `footprint_link_issues`-adjacent worries; the remaining thermal-pad problem
is item 2 above.

## 8. What this sheet costs

Converter overhead only; loads are elsewhere. Quiescent figures are datasheet typicals, load
figures are **(est.)**.

**Standby — `MCU_EN_*` all low, only `+3V3_AON` alive:**

| | typ | max |
| --- | --- | --- |
| `U10` `TPS7A0233` Iq | 25 nA | |
| `U12` `TPS61022` shutdown, `ISD` into `VIN`+`SW` ‡ §6.5 | 0.25 µA | 3.5 µA |
| `U13` `TPS63802` shutdown ‡ §8.5 | 45 nA | 600 nA |
| `U14`, `U15` `TPS62A02` shutdown ‡ §6.5 | 2 × 0.01 µA | 2 × 2 µA |
| three 470 k `PG` pull-ups, all rails low | 21 µA | |
| **total** | **~21.3 µA ≈ 0.08 mW** | ~29 µA |

That is 1.5 µA *higher* than the number this section carried before `U11` was deleted, because `U11`
used to be the thing isolating `U12`'s `VIN` and now `U12` sits on `+VSYS` and leaks its own 0.25 µA.
Against `U11`'s own ≤ 2 µA of `VBIAS` shutdown current it is a wash, and against the ~10 mW standby
target the whole rail tree is still under 1 %.

Every feedback divider is on a converter *output*, and all three switchers actively discharge their
outputs when disabled (`TPS62A02` names the current: 60–76 mA on `SW` ‡ §6.5), so no divider draws
anything in standby. That is why the number is dominated by the `PG` pull-ups — and why they are
470 k, not TI's 100 k.

**Reading state — all rails on, converters idling:** `U12` 27 µA from `VOUT` ‡ + 0.9 µA from `VIN` ‡,
`U13` 11 µA ‡, `U14`/`U15` 20–23 µA each ‡, plus ~13 µA of divider current and 21 µA of `PG`
pull-up — call it **0.4 mW** against a 135–235 mW budget. Deleting `U11` took ~0.15 mW of `VBIAS`
quiescent out of that. Conversion *loss* under load is the number that actually matters, and it is a
property of the load, not of this sheet — except that `U11`'s 16 mΩ is no longer in series with the
boost's 2.3 A **(est.)** input current, which was ~85 mW at full load.

### 8.1 The `+5V_DCDC` load budget — checked 2026-08-15, and it holds

§3.2 sized `L10` against `IOUT` = 1.5 A **(est.)** and left an explicit trigger: *"if the SoM's
`VIN` current comes back from PHYTEC materially above 1.5 A, re-run this block."* It has come back,
from three places in `L-1038e.A5`, and it is **1.0 A** — below the estimate, not above.

| Load on `+5V` | mA @ 5 V | Source |
| --- | ---: | --- |
| SoM `VIN`, **design bound** | **1000** | §5.1: *"must be supplied with … a minimum 1 A capacity"*, *"in testing the current draw of the SOM did not exceed 1 A"*; Table 12 *"Draw 5 W (1 A)"* |
| SoM, measured under heavy load ‡ | 651 | Table 4 `IVIN` — and that load was `memtester 500M` + `iperf3` over ETH0 + 4 × `yes`, with **two Ethernet cables, two USB drives and HDMI attached**. Glider has none of those |
| SoM, measured idle ‡ | 324 | Table 4 `IVIN`, "idle in Linux, external interfaces down" |
| SoM, measured idle ‡ | 297 | `lowpowermode_phytec.pdf` — an independent run, 8 % apart, which is a useful cross-check |
| SoM, Suspend-to-RAM ‡ | 25.7 | same |
| EPD HV chain, R1 measured active ‡ | 14.4 | `NOTES-STATUS.md`, 71.8 mW on the `EPD HV` channel |
| microSD | **0** | it runs from the SoM's own `SoC_VDDSHV5_SDIO`, not from this sheet — `som.md` §4 |

Worst realistic case is the SoM's 1.0 A design bound **plus** an EPD refresh, which do coincide: the
page is being rendered while the panel is driven. Taking the EPD chain's peak at a generous ~10×
its measured average gives ≈ **1.3 A**, inside the 1.5 A the inductor was sized for.

Re-running §3.2's block with the datasheet's own duty equation (eq. 2, which includes η — the
earlier text used `(VOUT−VIN)/VOUT` and so understated the ripple), at `VIN` = 3.0 V:

| `IOUT` | `I_L,dc` | `I_L,pk` | vs `Isat` 4.8 A |
| ---: | ---: | ---: | --- |
| 1.00 A — SoM alone | 1.85 A | 2.54 A | Isat is **89 %** above the peak |
| **1.30 A — SoM + EPD refresh (est.)** | 2.41 A | **3.10 A** | Isat is **55 %** above the peak |
| 1.50 A — the design point | 2.78 A | 3.47 A | Isat is 38 % above the peak |
| 2.00 A — "margin is gone" | 3.70 A | 4.39 A | Isat is 9 % above the peak |

D = 0.460, ΔI_L = 1.38 A p-p. The IC itself is nowhere near: eq. 1 with `ILIM_SW` = 6.5 A min ‡
gives `IOUT(CL)` = **3.88 A** before current limiting, and TI's own reference design in §8.2 is this
exact application (Li-ion → 5 V) at **3 A**. The inductor remains the binding element, as §3.2 said.

**Two numbers to carry forward.** `VIN` tolerance: Table 4 gives 4.5 / 5.0 / **5.5 V**, but §5.1
recommends designing to **5 V ±5 %** (4.75–5.25 V). Our 4.992 V ±2.5 % reference = 4.87–5.12 V,
inside the tighter of the two with ~120 mV each side for load regulation and ripple — so the ±50 mV
output ripple TI designs for still fits, but there is not room for much more. And `IVBAT` = **40 nA**
into the SoM's `VBAT` (B2, RTC backup): trivially small, but it is a rail somebody has to supply,
and it is a `som.kicad_sch` decision (§`som.md` §3), not one this sheet makes.

The honest comparison to R1 is not a percentage. R1's problem was never converter efficiency; it was
that four bucks could not be turned off at all. The result here is that they can.

## 9. Open

- **No rail on this sheet has been checked against Spartan-6's supply ramp-time window.** DS162
  Table 6 requires `VCCINT`, `VCCAUX` and `VCCO2` each to ramp in **0.20–50.0 ms** — a rail that
  comes up *too slowly* violates it. Compare the soft-start of `U13` (`TPS63802`), `U14`/`U15`
  (`TPS62A02`) and the `+3V3` buck-boost against that ceiling, worst case being a nearly-flat cell
  where a buck-boost takes longest to reach regulation. Opened by WP5 (§5); it belongs to this sheet
  because the converters are here.
- ~~**Bank 3's voltage is under review and may move `+1V35_DCDC`.**~~ **Closed 2026-08-12: the rail
  is now 1.500 V and the net is `+1V5_DCDC`.** `R33` 124 k → 150 k; see §3.1's margin check.
  Decided by the hardware owner once `ds162.pdf` and `mt41k64m16.pdf` were both in hand.
- ~~**The 1.5 V decision costs ~1.9 mW of standby.**~~ **Revised 2026-08-14 — it probably costs
  nothing, and may save.** That estimate compared `mt41k64m16.pdf`'s `IDD6` at 1.35 V (8 mA Rev. G
  / 12 mA Rev. J → 10.8–16.2 mW) against an assumed 1.5 V figure, because the DDR3L datasheet does
  not specify 1.5 V operation — it says "refer to the DDR3 (1.5V) SDRAM data sheet". That datasheet
  is now in `datasheets/MT41J.pdf`, and it gives **`IDD6` = 7 mA for all speed grades** (Table,
  notes 1–3: TC ≤ 85 °C, ASR and SRT disabled) → **10.5 mW at 1.5 V**, at or below the DDR3L part's
  own 1.35 V figure.
  ⚠ **This is a proxy, not a spec for the fitted part.** `MT41J64M16` and `MT41K64M16` are
  different orderable devices; the board fits the `MT41K` running in its "1.5 V compatible mode",
  and nobody publishes that combination's `IDD6`. It is the closest published number — same
  density, same organisation, same family, the voltage we actually run at — and it moves the
  1.5 V decision from "small cost" to "no measurable cost".
  **Worth a decision at BOM time:** the MIG is configured for `MT41J64M16` (`mig.prj`), we run the
  bank at 1.5 V, and DDR3L's 1.35 V capability is therefore unused — so fitting the `MT41J` would
  make the datasheet match the design exactly. Against that, the `MT41K` is what R1 proves and what
  is priced and stocked at LCSC (`C2060943`, $4.49). Check `MT41J` availability before changing
  anything.
- ~~The DDR in self-refresh is the **largest single term** in the reading state.~~ **Not any
  more.** PHYTEC measured the SoM at **128.6 mW** in Suspend-to-RAM (`NOTES-R2-hardware-facts.md`
  §4.6), which is 6–12× the DDR rail and 51–66 % of the whole reading budget. The 10.5 mW here is
  now a minor term. **The architectural lever noted below still stands** and is still worth having:
  if the SoM re-pushed the framebuffer on wake, `MCU_EN_DDR` could be off in the reading state and
  the whole term would go, at the cost of resume latency and a full redraw. That is a WP8 question,
  noted here because this is where the number lives — but it is no longer the biggest one.
- ~~**This doc still owes a "Layout guidelines" section.**~~ **Written — §11.**
- ~~**`U10`'s output must be renamed to `+3V3_AON_DCDC`.**~~ **Done by the reviewer** in the
  2026-08-11 save: `#PWR205` now reads `+3V3_AON_DCDC`, so `power_mon`'s `U22` ch2 shunt (`R208`) has
  a real upstream net and `+3V3_AON` is the load side. Verified in the exported netlist.
- ~~**`battery.kicad_sch`'s `+3V3_AON` `PWR_FLAG` is an ERC error, delete it.**~~ **Withdrawn — keep
  it.** That ask was correct only while `U10.OUT` sat on `+3V3_AON`. Now that `U10` drives
  `+3V3_AON_DCDC`, the only thing feeding `+3V3_AON` is `R208`, a passive shunt, so the flag is the
  net's *sole* ERC driver. Deleting it would turn one `pin_to_pin` warning into a
  `power_pin_not_driven` error on every `+3V3_AON` load — the STM32G0's `VDD`/`VBAT` and three
  `INA3221` `VS`/`VPU` pins. `#FLG04` at (360.68, 205.74) stays. The `pin_to_pin` violation is gone
  either way; ERC now reports **nothing at all** on `/power/` and nothing on `/battery/` except the
  `CHG_QON#` item that waits on the MCU sheet.
- **Rail load estimates.** Every current in §1 and §3.2 is an estimate. The SoM figure in particular
  waits on PHYTEC; **if `VIN` peak is materially above 1.5 A, re-run §3.2's peak calculation** — at
  2.0 A the boost inductor's Isat margin is gone.
- **`+5V_DCDC` decay when disabled.** New with the `U11` deletion (§2.2): nothing actively discharges
  the rail. Needs a hardware test.
- **`+VSYS` dip at 5 V enable.** New with the `U11` deletion (§3.4): the boost's own pre-charge can
  pull ~2.4 A for a few hundred µs. Needs a hardware test with the cell near 3.3 V.
- ~~**`+5V` for the EPD HV chain.**~~ **Answered in WP4** (`epd-port.md` §4.1): no. The `LGS5145`
  is a buck with a 4.5 V minimum input, run here as an inverting buck-boost. In steady state its
  `GND` pin sits on the negative rail so it sees ~25 V, but **at startup that rail is at 0 V** and
  the part sees `+VSYS` alone — 3.0 V from a flat cell will not start it. The 5 V feed stays.
- **Spartan-6 sequencing** — §5.
- **The `DLA0010A` footprint** — §7. (The `RWU0007A` thermal pad was also listed here; that
  concern was wrong and is withdrawn — §7 item 2.)
- **BOM fields.** `MPN` and `LCSC` symbol properties are not populated on any sheet yet; §10.13 says
  why that is deliberate and when it happens.

## 10. Review 1 (2026-08-11) — the analysis notes, answered

Source: `../manual-analysis/Analysis_power.md`. ‡ = read out of `../datasheets/tps62a01.pdf`
(SLUSEG9E, which covers `TPS62A01` **and** `TPS62A02`), `../datasheets/tps63802.pdf` (SLVSEU9D),
`../datasheets/tps61022.pdf` (SLVSDX7D), `../datasheets/tps22965.pdf` (SLVSBJ0F),
`../datasheets/tps7a02.pdf` (SBVS277C) or `../datasheets/bq25890.pdf` (SLUSC86D).

Also read back in this round: your edits to the sheet. You renamed `#PWR205` to `+3V3_AON_DCDC`
(standing ask #2 — done, §9), rearranged the `+1V2` block, and pasted TI's Table 8-2 rows into the
`Description` fields of `C31`, `C32` and `L12`. The netlist is otherwise unchanged from what was
captured; nothing was broken by the rearrangement, and ERC reports zero violations on `/power/`.

### 10.1 `TPS62A02` `EN` — yes, exactly right. **Correct as drawn.**

Your description is the circuit. `MCU_EN_FPGA_CORE` goes to `U14.EN` and to `R31` 100 kΩ to `GND`,
with nothing else in the path — confirmed in the netlist, `/power/MCU_EN_FPGA_CORE` = `R31.1` +
`U14.4(EN)` and nothing more. When the MCU drives the pin high the pin sits at the full `+3V3_AON`,
3.3 V; when the MCU drives it low, or is in reset with its GPIOs high-impedance, `R31` holds `EN` at
ground and the rail is off. "Off is the state the board powers up in" rests entirely on that resistor.

The numbers that make it safe, from ‡ §6.5 and ‡ §7.4.1:

| | |
| --- | --- |
| `VEN(R)`, guaranteed enabled above | **1.2 V** (min) |
| `VEN(F)`, guaranteed disabled below | **0.4 V** (max) |
| `VEN(LKG)`, `EN` input leakage at 5 V | 100 nA (max) |
| absolute maximum on `VIN`, `EN`, `PG` | −0.3 to **6.5 V** |
| ‡ pin table | "Logic high enables … **Do not leave the pin floating.**" |

3.3 V is 2.75× the guaranteed-on threshold and half the absolute maximum. Held low, `R31` has to sink
only 100 nA, so `EN` sits at 100 nA × 100 kΩ = **10 mV** — a factor of 40 below the 0.4 V guaranteed-off
level. 100 kΩ is comfortable; it could be 1 MΩ and still work, and the reason not to go higher is
noise pickup on a long trace, not leakage.

One thing your description implies that is worth making explicit: this only works because `+3V3_AON`
and the MCU come up **before** anything asks for a rail. The MCU cannot accidentally enable a rail it
has not been told to, but it also cannot *disable* one before it boots — the pull-down is what covers
the gap between `+VSYS` appearing and firmware running.

### 10.2 "Write down all layout guidelines, not just for this chip." **Done — §11.**

That section was already owed (old §9, first bullet) and is now written: one subsection per
regulator, every rule traced to its datasheet's own layout section, plus the board-level rules that
only make sense across the whole sheet. Nothing in it is actionable until Stage D, and
`glider-r2-layout-reminder` in my memory says to raise it again when we get there.

### 10.3 `R29` and TI's 200 kΩ — **you were reading the 1.8 V circuit. Correct as drawn.**

TI's Figures 8-1/8-2/8-3 all draw `R1` = 200 kΩ, `R2` = 100 kΩ ‡ — and all three are labelled
**`VOUT` = 1.8 V**. The equation is ‡ §8.2.2.1 eq. 2:

```
R1 = R2 × (VOUT / VFB − 1),  VFB = 0.6 V

1.8 V:  R1 = 100 k × (1.8/0.6 − 1) = 100 k × 2 = 200 k     <- TI's figure
1.2 V:  R1 = 100 k × (1.2/0.6 − 1) = 100 k × 1 = 100 k     <- R29
1.50 V: R1 = 100 k × (1.50/0.6 − 1) = 100 k × 1.50 = 150 k  -> exactly 1.500 V, R33
```

So 200 kΩ is right for 1.8 V and wrong for 1.2 V; `R29` = 100 kΩ is the same equation at our voltage.
`R30` = 100 kΩ is at the datasheet's ceiling — ‡ §8.2.2.1: "`R2` must not be higher than 100 kΩ to
provide acceptable noise sensitivity" — so the divider is as high-impedance as TI allows, which is
what we want for standby.

### 10.4 `R32` pulling `PG` to a different rail than `VIN` — **yes, and the datasheet says so. Correct as drawn.**

‡ §7.4.2: "The `PG` pin is an open-drain output that requires a pullup resistor to **any voltage up to
the recommended input voltage level**." The recommended `VIN` range is 2.5–5.5 V ‡ §6.3, so a 3.3 V
pull-up is inside it, and the absolute maximum on `PG` is 6.5 V ‡ anyway. `TPS63802` puts it even more
plainly for `U13`: "any voltage rail less than 5.5 V" ‡ §9.3.10. An open-drain output has no internal
pull-up to `VIN`, so there is nothing for the two rails to fight over.

**But there is a real caveat in the same paragraph, and it is worth knowing why it does not bite us.**
‡ §7.4.2 continues: "`PG` is low when the device is turned off due to `EN`, UVLO, or thermal shutdown.
**`VIN` must remain present for the `PG` pin to stay low.**" So the guarantee "rail off ⇒ `PG` reads
low" is conditional on `U14`'s own `VIN` being alive. If `+VSYS` were absent while `+3V3_AON` was
present, `PG_1V2` would float high through `R32` and firmware would read "rail good" on a dead rail.

That combination cannot occur here: `+3V3_AON` is generated *from* `+VSYS` by `U10`, so `+3V3_AON`
present implies `+VSYS` present. The dependency runs the safe way round. It is worth recording
because it is the kind of thing that breaks if a later revision ever moves `+3V3_AON` to a coin cell
or a separate input — then the pull-up rail would have to move with it.

### 10.5 `TPS63802` `AGND` and `GND` — **must be connected, and TI deleted the advice to separate them. Correct as drawn.**

`U13.3(AGND)` and `U13.8(GND)` are both on `GND` in the netlist, which is right. They are one net
electrically; the question is only how the copper is arranged, and TI changed its own mind about that
between revisions. ‡ Revision History, Rev B → Rev C, both lines on p.28:

- "**Deleted** layout guideline to separate `AGND` and `PGND`."
- "**Changed** *Use a common-power GND, but connect `AGND` and `PGND` through via at a different
  layer* **to** *Use a common ground node for power ground and a different one for control ground to
  minimize the effects of ground noise. Connect these ground nodes at any place close to one of the
  ground pins of the IC*."

So the current advice ‡ §12.1 item 2 is: one plane, but do not let the control-ground return share
copper with the power-ground return on its way there — join them at the IC. That is a placement rule,
not a netlist rule, and it is written up in §11.3. Splitting them into two nets with a stitching link
would be *worse* than what is drawn, and it is what TI removed.

### 10.6 `R28`/`R32`/`R36` at 470 kΩ where TI draws 100 kΩ — **correct as drawn, but the win is smaller than the old text claimed.**

You found TI's `R3` = 100 kΩ in ‡ `tps63802.pdf` Figure 10-1 — which is also the figure our whole
3.3 V divider comes from (`R1` 511 k, `R2` 91 k, `C1` 10 µF, `C2` 22 µF, `L1` 0.47 µH: every one of
those is what the sheet carries). So the question is fair: why deviate on the one component?

Standby current. A `PG` pin is low whenever its rail is off, so in standby all three pull-ups are
conducting continuously:

| `Rp` | current each | three of them | as power |
| --- | --- | --- | --- |
| 10 kΩ | 330 µA | 990 µA | 3.3 mW |
| 100 kΩ (TI) | 33 µA | 99 µA | **0.33 mW** |
| 470 kΩ (ours) | 7.0 µA | 21 µA | **0.07 mW** |

**Correction to §4's earlier wording, which said 10 kΩ would cost "a third of the entire standby
budget".** That is true of 10 kΩ but it was arguing against a value nobody proposed. Against TI's
actual 100 kΩ the saving is **0.26 mW out of a ~10 mW standby target — about 2.6 %.** Real, but not
dramatic. The reason to take it is that it costs nothing at either end:

- **Low level.** ‡ specifies `VOL` = 400 mV max at `ISINK` = 1 mA, i.e. an on-resistance of at most
  400 Ω. At 7 µA that gives `VOL` ≈ **2.8 mV**. The `TPS63802` is specified the same way ‡ §8.5.
- **High level.** `IPG(LKG)` = 100 nA max at 5 V ‡, and the STM32G0's I/O leakage is of the same
  order. 150 nA × 470 kΩ = 70 mV of droop, so the MCU sees ≥ 3.23 V against a `VIH` of
  0.7 × 3.3 = 2.31 V ‡ `stm32g0b1.pdf`. Nearly a volt of margin.
- **Speed.** 470 kΩ into ~10 pF of trace is τ = 4.7 µs, so ~10 µs of rise. `PG` rising delay is
  itself 10 µs ‡, and firmware polls `PG` on millisecond waits, so the RC is invisible.

The one thing 470 kΩ does cost is noise immunity on a high-impedance node, which is why §11.6 says to
keep the three `PG` traces away from the `SW` and `L1`/`L2` nodes.

### 10.7 "Explain why the `TPS22965` is used in tandem with the `TPS61022`." — **it should not be. `U11` deleted.**

This is the question that changed the sheet, and the honest answer is that the justification in §2.2
was wrong. The full evidence is in the rewritten §2.2; the short form:

`tps61022.pdf` advertises "**True disconnection between input and output during shutdown**" in its
p.1 feature list, repeats it in the Description, states it again in §7.3.2, and quantifies it in §6.5
with `IVOUT_LKG` = 1 µA typ / 3 µA max measured with `VOUT` held at 5.5 V while `VIN` = 0 V. The old
text's claim that a disabled boost leaves `VSYS − 0.3 V` on the output is the general behaviour of
boosts with an NMOS synchronous rectifier; this part uses a **PMOS** high-side (‡ Table 5-1, §7.3.5)
oriented so that its body diode blocks the path. The §7.3.5 citation in the old text was a misreading:
pass-through is what the part does when it is **enabled** and `VIN` is above the setpoint.

So `U11` was buying a disconnect the boost already has, at the price of 16 mΩ in series with ~2.3 A
(≈ 85 mW at full load), 30–50 µA of `VBIAS` quiescent while reading, three parts, and a
non-uniform enable pattern. It is gone. `MCU_EN_5V` now drives `U12.EN` directly with `R20` as its
pull-down, `C22` and `C25` both stay on `+VSYS` as boost input bulk, and `VSYS_SW` no longer exists.

Two things `U11` did that are genuinely lost, both now open items in §9: the 225 Ω quick-output
discharge on its output ‡ §9.3.2, and the `CT`-programmed 800 µs inrush ramp (§3.4 works out what
replaces it — the boost's own 2.4 A pre-charge limit, which is a much harder edge on the cell).

### 10.8 "Doesn't `+VSYS` have to be defined via an input flag?" — **it is, on the battery sheet. Correct as drawn.**

Two things make this work, and the second is the one that is easy to miss.

**Power symbols are global, not sheet-local.** `+VSYS` on this sheet and `+VSYS` on
`battery.kicad_sch` are the same net *today*, even though the root sheet is still unwired. Only
hierarchical labels and sheet pins are sheet-local — which is exactly why `MCU_EN_5V` here and
`MCU_EN_5V` on `mcu.kicad_sch` are still two different nets and `+VSYS` is not. The exported netlist
confirms it: `+VSYS` carries `U1.15`/`U1.16(SYS)` from `battery` alongside `U10.1`, `U12.7`, `U13.10`,
`U14.3` and `U15.3` from here.

**And ERC's driver requirement is already met.** `U1`'s `SYS` pins are typed `passive` in the
symbol, so they do not count as a driver; `battery.kicad_sch` supplies a `PWR_FLAG` (`#FLG00`…) for
that reason. One flag per net for the whole design is correct — adding a second on this sheet would
produce `pin_to_pin: Pins of type Power output and Power output are connected`, which is precisely the
error the redundant `+3V3_AON` flag used to cause (§9). ERC currently reports **nothing** on
`/power/`, which is the check.

The two `PWR_FLAG`s this sheet *does* carry are on `+1V2_DCDC` and `+1V5_DCDC`, and they are needed
for a different reason: those rails are the far side of an inductor, so no pin on them is a driver
either. The other two rails need none because `U12.3(VOUT)` and `U13.6(VOUT)` are typed `power_out`.
The on-sheet note under "ERC power flags" says exactly this.

### 10.9 `TPS61022` capacitors — `C1` is `C25`, and two output caps are right at our current. **Correct as drawn.**

**`C1`.** Yes — your reading is right. TI's Figure 8-1 `C1` is the boost's input capacitor and on our
sheet that is `C25`, 22 µF sitting at `U12`'s `VIN`. TI draws 10 µF there; ‡ §8.2.2.5 says "while a
10-µF input capacitor is sufficient for most applications, **larger values may be used to reduce
input current ripple without limitations**", so 22 µF is above the requirement, not a substitute for
something missing. (The old §3.3 cited "Fig. 8-2" for this; Figure 8-2 is the feedforward variant, and
the citation is now §8.2.2.5. Since `U11` went, `C22`'s 22 µF is on the same net, so the boost sees
44 µF nominal — §3.4 explains why that matters more now than it did.)

‡ §8.2.2.5 also carries a warning worth keeping in mind at layout: a ceramic-only input fed "through
long wires" can ring at `VIN` on a load step. Ours is fed from a plane a few millimetres away, so this
does not apply — but it is one more reason `+VSYS` must be a plane and not a trace (§11.6).

**`C2` — three 22 µF in TI's figure, two here.** TI's Figure 8-1 is a **5 V at 3 A** design ‡
Table 8-1. Ours is 1.5 A **(est.)**. What the datasheet actually requires is a band, not a count —
‡ §8.2.2.3: "TI recommends using the X5R or X7R ceramic output capacitor in the range of **10 µF to
50 µF effective capacitance**. … If the output capacitor is below the range, the boost regulator can
potentially become unstable." And ‡ §8.2.2.3 also warns "a ceramic capacitor can lose more than 50 %
of its capacitance at its rated voltage".

```
2 × 22 µF, 10 V X7R 0805, at 5 V DC bias, ~-45 % derating  ->  ~24 µF effective   in band
3 × 22 µF (TI)                                             ->  ~36 µF effective   in band

ripple, eq. 8:  V = IOUT × DMAX / (fSW × COUT)
  ours, 1.5 A, D = 0.4, 1 MHz, 24 µF   ->  25 mV
  TI's, 3.0 A, D = 0.4, 1 MHz, 36 µF   ->  33 mV   (spec was ±50 mV)
```

So two parts put us inside the stability window with ~24 µF effective and give *better* ripple than
TI's own design, because the current is half. Adding a third would move us to ~36 µF, still inside —
there is nothing wrong with it, it just buys ripple we do not need and 2 mm² we would rather keep.

**And the third cap has a knock-on.** ‡ §8.2.2.4: "For large output capacitance more than 40 µF
application, TI recommends a feedforward capacitor to set the zero frequency to 2 kHz." At ~24 µF
effective we are below that threshold, which is why `C28` is **DNP**. Its value is not a guess: if the
loop ever needs it, ‡ eq. 10 gives `C3` = 1/(2π · 2 kHz · 732 kΩ) = **109 pF**, and the pad carries
100 pF. Fit a third output cap and you cross 40 µF, and then `C28` should be fitted too.

**If PHYTEC comes back with a `VIN` current well above 1.5 A**, re-run both this and §3.2 — the
capacitor count and the inductor's saturation margin move together.

### 10.10 `VBIAS` = `+VSYS`, the `+VSYS` voltage, and the 10:1 ratio — answered for the record; `U11` is gone either way

These three questions are about a part that §10.7 deleted, but two of the answers matter regardless.

**Was `VBIAS` = `VIN` = `+VSYS` legal?** Yes, and it was the *preferred* arrangement. ‡ §7.3
Recommended Operating Conditions gives `VIN` = 0.8 V **to `VBIAS`** — `VIN` may not exceed `VBIAS` —
and `VBIAS` = 2.5 V to 5.7 V. ‡ §10.1.4 spells out the consequence: "For optimal `RON` performance,
make sure `VIN` ≤ `VBIAS`. The device is still functional if `VIN` > `VBIAS` but it exhibits `RON`
greater than …". Tying them together satisfies `VIN` ≤ `VBIAS` with equality, which is the best you
can do from one rail. `+VSYS`'s 3.0 V floor is above the 2.5 V `VBIAS` minimum, so it was in range at
every point on the discharge curve.

**What is the `+VSYS` voltage?** This one is still live, since every part on the sheet runs from it.
From ‡ `bq25890.pdf` and `battery.md` §2:

| Condition | `+VSYS` |
| --- | --- |
| battery only, cell full | ≈ 4.2 V minus the `BATFET` drop (`V(FWD)` 30 mV at 10 mA ‡) |
| battery only, cell at cut-off | ≈ **3.0 V** — the floor everything must work at |
| charging | up to ≈ **4.4 V** — the worst case for absolute maximums |
| input present, cell flat or absent | held at `SYS_MIN`, **3.5 V default ‡**, by the switcher |

So **3.0–4.4 V**, and the two numbers that do design work are the 3.0 V floor (which is why 3.3 V
cannot be a buck — §2.1) and the 4.4 V ceiling, which is comfortably under every `VIN` absolute
maximum on the sheet: 6.5 V on `TPS7A02` ‡ §6.1, 7.0 V on `TPS61022` ‡ §6.1, 6.5 V on `TPS62A02`
‡ §6.1, 6.0 V on `TPS63802` ‡ §8.1.

**The 10:1 `CIN`:`CL` ratio.** You read it correctly and it is worth recording what it was for,
because the old §3.3 cited it as the reason `C22` was 22 µF and that was a muddle. ‡ §10.1.2 gives
1 µF as a **minimum** ("`CIN` … 1 µF" in the Recommended Operating Conditions table is a MIN column,
not a sufficiency claim), and then two separate recommendations:

- ‡ §10.1.2: "When switching heavy loads, it is recommended to have an input capacitor about 10 times
  higher than the output capacitor **to avoid excessive voltage drop**" — a dip specification.
- ‡ §10.1.3: "Because of the integrated body diode in the NMOS switch, a `CIN` greater than `CL` is
  highly recommended. A `CL` greater than `CIN` can cause `VOUT` to exceed `VIN` when the system
  supply is removed" — a back-feed specification. And then, explicitly: "a 10 to 1 ratio for
  capacitance **is not required for proper functionality of the device**. A ratio smaller than 10 to
  1 (such as 1 to 1) could cause slightly more `VIN` dip upon turn-on … This can be mitigated by
  increasing the capacitance on the `CT` pin for a longer rise time."

Had `U11` stayed: `CIN` is everything on the `+VSYS` node, not just `C22` — `C20` 1 µF + `C22` 22 µF +
`C24` 0.1 µF + `C29` 10 µF + `C31` 4.7 µF + `C33` 4.7 µF ≈ 42.5 µF on this sheet alone, plus `C4`/`C5`
on the battery sheet — against `CL` = `C25` 22 µF. So `CIN` > `CL` was satisfied about 2:1 at node
level, and the dip was handled by `C23`'s 800 µs ramp rather than by brute capacitance, exactly as
§10.1.3 suggests. Nothing was wrong; the citation was just attached to the wrong component.

**And `C24` was never part of `CIN`.** It was the `VBIAS` bypass — a supply-pin decoupler, which is
why 100 nF. TI's own Figure 35 draws `VBIAS` from a second supply with no bypass shown at all, so it
was good practice rather than a requirement. Both parts are deleted with `U11`.

### 10.11 Inductor ratings — **you were right to look. `Value` fields changed.**

Not one of your questions, but it came out of the `Description` you pasted onto `L12`. All four
inductors carried `Value` strings ending "/6A", and no inductor on this sheet is rated for 6 A.
Re-queried on LCSC 2026-08-11:

| LCSC | MPN | Size | L | Isat | Irms | Rdc | Stock | Unit price |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `C3224227` | `DFE322512F-1R0M` | 1210 | 1 µH | 4.8 A | 3.8 A | 32 mΩ | 2838 | $0.20 |
| `C703140` | `DFE252012F-R47M` | 1008 | 470 nH | 7.4 A | 4.9 A | 23 mΩ | 2914 | $0.18 |

Both are JLCPCB *extended* parts, not basic — one setup fee each, and a reason to keep three of the
four the same line item.

Applied: `L10`/`L12`/`L13` → **`1uH/3.8A`**, `L11` → **`0.47uH/4.9A`** — Irms, the continuous rating,
which is the conservative one to put on a schematic. The full figures went into the `Description`
fields.

**This also falsified a claim in §3.2**, which said `DFE322512F` is rated "above `TPS61022`'s 6.5 A
minimum valley current limit, so the inductor does not saturate before the IC's own protection acts".
Isat is 4.8 A, so it saturates first. §3.2 now says so and explains why it is tolerable (metal
composite, −30 % soft knee) rather than quietly acceptable.

### 10.12 `C31`/`C32`/`L12` — the `Description`s you pasted are TI's demo BOM, not ours. **Changed.**

The three strings you added are ‡ Table 8-2 verbatim, which is a good place to have looked. Two
things follow from that, in opposite directions.

**`C32`'s row proved a value wrong, in our favour.** Your `Description` says "22 µF … **10 V** …
GRM21BZ71A226KE15L" while the `Value` field said `22uF/6.3V`. TI's Table 8-2 specifies 10 V. 6.3 V
would work at a 1.2 V output, but there is no reason to deviate from the datasheet's own part for a
capacitor that costs the same. Applied: **`C32` and `C34` → `22uF/10V`.**

**But the MPNs themselves should not stay in the schematic.** I searched LCSC for both Murata
capacitor part numbers on 2026-08-11: **neither `GRM21BR71A475KA73L` nor `GRM21BZ71A226KE15L` is
stocked.** They are TI's evaluation-board choices, so a BOM pass would either fail to match them or
silently substitute. `L12`'s row is worse than merely unstocked — it names *two* parts,
`DFE252012F-1R0M (1A)` and `XGL3520-102MEC (2A)`, because TI lists one for the 1 A `TPS62A01` and one
for the 2 A `TPS62A02`; neither is the `DFE322512F-1R0M` this board actually fits.

Applied, so the schematic says what we fit:

- `C31`, `C33` → "4.7 µF 10 V X7R 0805 — TPS62A02 input cap, tps62a01.pdf Table 8-2"
- `C32`, `C34` → "22 µF 10 V X7R/X5R 0805 — TPS62A02 output cap, tps62a01.pdf Table 8-3"
- `L10`, `L12`, `L13` → the `DFE322512F-1R0M` line with its ratings and LCSC code
- `L11` → the `DFE252012F-R47M` line with its ratings and LCSC code

The inductors keep their MPN because that choice *is* made and the part *is* stocked. The capacitors
get an electrical description instead, because the specific part is a sourcing decision that has not
been made yet — which is §10.13.

One detail to check when it is: TI's table calls `GRM21BZ71A226KE15L` **X7R**, but Murata's `Z7`
characteristic code is not `R7`. A 22 µF 0805 in true X7R barely exists; the high-capacitance parts in
that case size are X5R or X7T. ‡ §8.2.2.3 accepts "X7R or X5R", so this is not a problem — but do not
carry TI's "X7R" label onto a part you have not checked the dielectric of.

### 10.13 Part numbers and the BOM — **not in `Description`, and not yet. Here is the plan.**

You are right that JLCPCB assembly needs a BOM CSV with a part number per line. Three parts to the
answer.

**Not the `Description` field.** KiCad treats `Description` as human prose inherited from the library
symbol, and it is the field most likely to be overwritten when a symbol is updated from its library.
The convention that survives is **dedicated properties**: an `MPN` field and an `LCSC` field on each
symbol. `kicad-cli sch export bom --fields "Reference,Value,Footprint,MPN,LCSC,${QUANTITY}"` then
produces the CSV directly, and JLCPCB's uploader wants exactly a "LCSC Part #" column. `Description`
stays what it is: the sentence a human reads.

**Not per sheet, and not yet.** I would rather do this in **one pass across the whole design after
capture is complete**, for a concrete reason: stock moves. `battery.md` §1 exists because the
`BQ25896` had 127 units in stock; `docs/power.md` §1 records stock figures dated 2026-08-06. If we
populate `LCSC` fields sheet by sheet over the coming weeks, the early sheets get re-checked anyway
before ordering, so the work is done twice. Doing it once, immediately before Stage E's DFM review,
means every line is checked against live stock at the moment it matters. The `bom` and `lcsc` skills
automate the lookup and write the fields back.

**What is not deferred** is the *decision*. Where a part is chosen it is written down now, with its
LCSC code, in these docs — §1 for the ICs, §3.2 for the inductors — and now also in the inductors'
`Description` fields. The gap is only the passives: every resistor and capacitor on this sheet has a
value, a tolerance and a package but no chosen MPN. That is genuinely fine for 0402 resistors and
0805 X7R capacitors, where the part is a commodity and the choice is "whatever JLCPCB has as a basic
part in that value" — which is a decision best made against the basic-parts list at order time, since
a basic part costs no setup fee and an extended one does.

**So: I will do it, in one pass, and it will not be in `Description`.** The one thing to avoid in the
meantime is what happened here — pasting a specific MPN from a datasheet's demo BOM into the
schematic, where it looks like a decision.

---

## 11. Layout guidelines — collected now, to be applied at Stage D

Recording these while the datasheets are open; **none of them are actionable until layout**, and I
will raise this section again when we get there. Same shape as `battery.md` §11. Five switching or
regulating parts, and they do not all want the same thing.

### 11.1 The rule all four converters share

Every one of these datasheets opens its layout section with the same instruction in different words:
**put the input capacitor, the output capacitor and the inductor as close to the IC as the package
allows, and land the capacitors' grounds on the IC's ground pin, not on a plane somewhere else.**

- `tps61022.pdf` §10.1: "The input capacitor needs not only to be close to the `VIN` pin, but also to
  the `GND` pin in order to reduce input supply ripple. … the output capacitor not only must be close
  to the `VOUT` pin, but also to the `GND` pin."
- `tps63802.pdf` §12.1 item 1: "Place input and output capacitors as close as possible to the IC.
  Traces need to be kept short."
- `tps62a01.pdf` §8.4.1: "Place the input and output capacitors and the inductor as close as possible
  to the IC. … **Connect the low side of the input and output capacitors properly to the `GND` pin to
  avoid a ground potential shift.**"
- `tps7a02.pdf` §8.4.1: "Place input and output capacitors as close to the device as possible."

The reason is the same in each case and it is worth stating once rather than four times: the loop
that carries the chopped current has an area, that area is an inductance, and that inductance
converts every switching edge into a voltage spike on the IC's own ground reference. Nothing else in
this section matters as much.

### 11.2 `U12` `TPS61022` — the boost, and the loudest thing on the sheet

The boost is the part to place first: it runs at 1 MHz ‡ with up to 3.4 A of peak inductor current
(§3.2) and 12 mΩ/18 mΩ FETs ‡, so its edges are fast and its currents are large.

1. **The critical loop is not the input loop.** ‡ §10.1: "The most critical current path for all
   boost converters is from the switching FET, through the rectifier FET, then the output capacitors,
   and back to ground of the switching FET. This high current path contains nanosecond rise and fall
   time and must be kept as short as possible." So `C26`/`C27` → `U12.3(VOUT)` and `U12.1(GND)` is
   the loop to minimise, ahead of everything else. Put both output caps on the top layer, immediately
   at the pins, with ground stitched straight down.
2. **`SW` is the aggressor.** ‡ §10.1: "Minimize the length and area of all traces connected to the
   `SW` pin, and always use a ground plane under the switching regulator." `L10` sits directly
   against `U12.2(SW)`; nothing sensitive on any layer beneath it. On this sheet `SW` is the node
   between `L10` and `U12` — note the rail is the far side of `L10`, so it is a *short* net by
   construction if `L10` is placed tight.
3. **`C25` at `VIN` and `GND` both**, per §11.1. `C22` is the bulk further back on the `+VSYS` plane
   and can be placed for convenience; `C25` cannot.
4. **`FB` is a 732 k/100 k divider**, i.e. a ~5 µA, high-impedance node. Route `R21`/`R22` and the
   `Net-(U12-FB)` trace short and away from `SW` and from `L10`'s body. `C28`'s DNP pad sits across
   `R21`; keep it adjacent so fitting it later does not need a long stub.
5. **The thermal pad must be connected.** ‡ Table 5-1 makes `GND` (pin 1) the thermal path. The
   footprint is fine as it stands — §7 item 2 used to claim otherwise and is withdrawn — so this is
   purely a layout instruction: pin 1 is the heat path as well as the return, so give it copper on
   `F.Cu` and stitch it down to `In1.Cu` with several vias directly under and beside the pad, not a
   single via on a neck.
6. **Thermals.** ‡ §10.3 gives `PD(max)` = (125 − TA)/RθJA. At ~1.5 A out and ~94 % efficiency the
   part dissipates a few hundred mW in a 2 × 2 mm package; it wants copper, and it is the one part on
   this sheet where that is true.

### 11.3 `U13` `TPS63802` — the buck-boost, and it has **two** switching nodes

A buck-boost has an inductor with both ends switched. `L1` (pin 9) and `L2` (pin 7) are *both*
aggressors, which is the one way this part differs from everything else here.

1. **Keep `L11` between the two pins, as short as physically possible**, and treat both nodes as
   `SW`. ‡ §12.1 item 4: "The sense trace connected to `FB` is signal trace. Keep these traces away
   from `L1` and `L2` nodes."
2. **Grounds: one plane, joined at the IC.** ‡ §12.1 item 2, quoted in full in §10.5: a common node
   for power ground and a different one for control ground, "connect these ground nodes at any place
   close to one of the ground pins of the IC". Concretely: `U13.8(GND)` is the power return and takes
   `C29`'s and `C30`'s grounds directly; `U13.3(AGND)` is the control return and takes `R25`
   (the divider bottom) and `R27` (`MODE`); the two meet at the IC, not out on the plane. **Do not**
   split them into separate nets or bridge them through a via on another layer — TI deleted that
   advice in Rev C (§10.5).
3. **`FB` at 511 k/91 k** is the highest-impedance sense node on the sheet at 5.5 µA. Short, quiet,
   ground-referenced, nowhere near `L1`/`L2`.
4. **`C29` (10 µF in) and `C30` (22 µF out)** both at the pins per §11.1.
5. The footprint does not exist yet (§7 item 1) and VSON-HR has no exposed pad, so unlike the boost
   there is no thermal-pad question — but there is also no thermal pad to help, so give the `VIN` and
   `VOUT` copper some width.

### 11.4 `U14`, `U15` `TPS62A02` — the two bucks, in SOT-563

Small package, 2.4 MHz ‡, and low current in our application (~140 mA and ~75 mA, §3.2), so these are
the easy ones. ‡ §8.4.1, all four bullets:

1. Input cap (`C31`/`C33`), output cap (`C32`/`C34`) and inductor (`L12`/`L13`) as close to the IC as
   possible; short, direct, wide power traces.
2. "Connect the low side of the input and output capacitors properly to the `GND` pin to avoid a
   ground potential shift" — SOT-563 has a single `GND` pin and no pad, so this is the whole ground
   strategy for these parts. Both capacitor grounds meet at pin 1.
3. "The sense traces connected to `FB` is a signal trace. … Keep these traces away from `SW` nodes."
   `R29`/`R30` and `R33`/`R34` are 100 k/100 k, so `FB` is a 6 µA node sitting a couple of millimetres
   from a 2.4 MHz edge. This is the rule most likely to be violated by accident when the divider is
   tucked in beside the inductor.
4. "Use a common ground. `GND` layers can be used for shielding." ‡ Figure 8-24 shows the intended
   arrangement for the SOT-563 part specifically.
5. `+1V5_DCDC` feeds DDR3L, so the two circuits are not interchangeable at layout time even though
   they are identical on the schematic: `U15` goes near the DDR3L/FPGA bank it supplies, `U14` near
   the FPGA core pins. That is a WP5 constraint, recorded here so it is not discovered late.

### 11.5 `U10` `TPS7A0233` — the always-on LDO

The quietest part on the sheet and the only one that is never switched off, which changes what
matters about it: not noise, but that its 25 nA quiescent current is a *measured* budget line
(`power_mon` `U22` ch2 watches it through `R208`).

1. `C20` and `C21` at the pins ‡ §8.4.1.
2. ‡ §8.4.1 also says "use copper planes for device connections to optimize thermal performance" and
   "place thermal vias around the device" — both are about the DQN package. We use **DBV
   (SOT-23-5)**, which has no thermal pad, so the "no via directly beneath the thermal pad" warning
   does not apply to us. Worth noting because it is easy to copy the wrong bullet across.
3. `EN` is tied to `IN` at the part (netlist: both on `+VSYS`) — keep that a local tie so the LDO
   cannot be accidentally gated by a plane cut.
4. **Its output is `+3V3_AON_DCDC`, which then goes off-sheet to a shunt and comes back as
   `+3V3_AON`.** At layout that means the LDO output does *not* fan out here; it goes to `R208` on
   the `power_mon` block and the fan-out happens on the far side. Getting that backwards would
   short the shunt out.

### 11.6 Board-level, across the sheet

1. **`+VSYS` is a plane, not a trace.** `battery.md` §11.2 item 9 already says this from the charger's
   end; from this end the reason is that four converters and up to ~2.8 A of boost input current share
   it. A trace would put all four converters' ripple onto each other.
2. **The boost's input current is the largest thing on this sheet.** ~2.8 A DC at `VIN` = 3.0 V
   (§3.2), pulsed at 1 MHz. Its path from the `+VSYS` plane through `C22`/`C25` to `U12` is a power
   path and wants real copper, not a 0.25 mm trace.
3. **Keep the three `PG` nets away from the switching nodes.** They are 470 kΩ pull-ups (§10.6), so
   they are the highest-impedance signals here, and they run to the MCU. `PG_1V2` and `PG_1V5` in
   particular leave their converters right past `L12`/`L13`.
4. **`MCU_EN_5V` now runs the length of the 5 V block** (a consequence of deleting `U11` — `R20`
   stayed where it was and the net reaches across to `U12.EN`). On the schematic that is fine; at
   layout, do not let that trace become the long antenna next to `SW`. Better: place `R20` next to
   `U12` in the layout regardless of where the symbol sits on the sheet.
5. **Four `MCU_EN_*` and three `PG_*` all go to the STM32G0.** They will want to leave this block as
   a bundle towards the MCU, so plan the block's orientation with the MCU's position in mind rather
   than placing the converters first and routing the control signals afterwards.
6. **Thermal**: the boost dominates. The two bucks at ~140 mA and ~75 mA dissipate tens of mW; the
   buck-boost at 3.3 V and whatever the FPGA I/O bank draws is the second-hottest. Copper on the
   `VIN`/`VOUT` sides of both, and no need to do anything special for the LDO.
7. **`power_mon`'s shunts are the reason any of this is checkable.** Every `*_DCDC` net on this sheet
   ends at a shunt on another sheet; keep the Kelvin sense pairs for those shunts in mind when
   deciding where each converter's output leaves the block (`epd-port.md` §3).

## 12. Conventions

Reference designators on this sheet start at 10 (`U`, `L`) and 20 (`R`, `C`), and its `#PWRnnn`
symbols at 200. KiCad requires references to be unique across the whole design, not per sheet, and
`battery.kicad_sch` already owns `U1`–`U3`, `C1`–`C8`, `R1`–`R19` and `L1`. Each new sheet should
take its own block the same way rather than relying on a global re-annotate, which would renumber
the sheets that are already reviewed.

`U11`, `C23` and `C24` were deleted in review 1 and **their references are not reused.** A gap in the
sequence is cheaper than a designator that means one thing in the git history and another on the
board.

## 13. Verification — what was actually run

Re-run 2026-08-11 against the reviewed sheet, with `~/Apps/kicad-10.0.4/usr/bin/kicad-cli`:

- **ERC on the whole project: 491 violations, exactly one of them on this sheet.** Read from the
  **JSON** report (`kicad-cli sch erc --severity-all --format json`), not the text one: the text
  report files `footprint_link_issues`, `isolated_pin_label` and `four_way_junction` under
  `***** Sheet /` regardless of which child sheet the item actually sits on, which is misleading. The
  JSON report attributes per sheet:

  | sheet | count | what |
  | --- | --- | --- |
  | `/` | 473 | 208 `footprint_link_issues` (the owner's global library tables — standing ask 3), 164 `isolated_pin_label` + 91 `pin_not_connected` (root sheet unwired), 9 `four_way_junction`, 1 `lib_symbol_mismatch` (`MAX17048`, WP1) |
  | `/battery/` | 1 | `pin_not_driven` on `CHG_QON#`, waiting on `mcu` |
  | `/epd/` | 2 | `power_pin_not_driven`, root unwired |
  | `/epd_power/` | 8 | 6 `power_pin_not_driven`, 1 `pin_not_driven` (`U7.ON`), 1 `multiple_net_names` (`SHDN`/`EPD_POS_EN`) — WP4 items |
  | `/power_mon/` | 7 | 6 `power_pin_not_driven`, 1 `pin_not_driven` (`U21.SCL`) |
  | **`/power/`** | **0** | |

  Because the nine `four_way_junction` warnings are filed against the root, I resolved each one's
  item UUIDs against the sheet files: **seven are on `epd_power`, one on `power_mon`, and one is on
  this sheet** — at (259.08, 86.36), where `U12.4(FB)`,
  `R21`, `R22` and the DNP `C28` all meet on `Net-(U12-FB)`. It is a legibility warning about a node
  that genuinely has four members, it predates this review, and it is left alone; splitting it into
  two three-way junctions would be cosmetic. So: nothing on `/power/` that KiCad files as an error or
  as a real defect, and one style warning that is correct.

  **The `pin_to_pin` violation that §9 used to list is gone**, resolved by the `+3V3_AON_DCDC` rename
  rather than by deleting a flag.
- **`kicad-cli sch export netlist` diffed node-by-node against the pre-patch netlist**, so every
  change is accounted for and nothing else moved. The intended diff and the whole diff are the same
  set: `U11`/`C23`/`C24` removed; `+VSYS` gains `C25.1`, `L10.1(1_1)` and `U12.7(VIN)`;
  `/power/MCU_EN_5V` = `R20.1` + `U12.5(EN)`; `/power/VSYS_SW` and `Net-(U11-CT)` gone; `GND` loses
  exactly `C23.2`, `C24.2`, `U11.5(GND)`, `U11.9(EP)`; four `Value` fields and six `Description`
  fields changed. **No new `unconnected-*` net appeared** — the check that caught a real bug during
  this patch, when an earlier version of `tools/patch_power_review1.py` had an off-by-one in its
  symbol-span helper and silently deleted five neighbouring power symbols along with the three it
  was asked to. The netlist diff showed it as `unconnected-(R32-Pad1)`; ERC did not.
- **Confirmed by reading the netlist**, as of this round:
  - `+VSYS` = `C20.1, C22.1, C25.1, C29.1, C31.1, C33.1, C4.1, C5.1, L1.2, L10.1, R72.2, U1.15,
    U1.16, U10.1(IN), U10.3(EN), U12.7(VIN), U13.10(VIN), U14.3(VIN), U15.3(VIN), U22.2` — one global
    net across `battery`, `power` and `power_mon`, which is §10.8's point.
  - `+3V3_AON_DCDC` = `C21.1, R208.2, U10.5(OUT), U22.15(IN+2)` and `+3V3_AON` = `R208.1,
    U22.14(IN-2)` plus every always-on load. The shunt is in the path, not bypassed.
  - `Net-(U12-FB)` = `C28.2, R21.2, R22.1, U12.4` — divider midpoint with the DNP feedforward.
  - `+1V2_DCDC` = `C32.1, L12.2, R29.1` and `+1V5_DCDC` = `C34.1, L13.2, R33.1` — the rail is the
    far side of the inductor, not the `SW` pin.
  - `GND` picks up `U13.3(AGND)` + `U13.8(GND)`, which is §10.5.
  - Every `MCU_EN_*` net is exactly its pull-down plus one enable pin; every `PG_*` is exactly its
    pull-up plus one power-good pin.
- **The sheet was rendered and looked at.** `kicad-cli sch export pdf` → page 3 → `pdftoppm` at
  400 dpi, then inspected: the rewired 5 V block has no overlapping symbols, no stranded label and no
  text collision, the `+VSYS` rail is continuous through the space `U11` used to occupy, and the
  `MCU_EN_5V` run reaches `U12.EN` cleanly past `R23`. The `+1V2` block as you rearranged it also
  checks out.
- **Divider arithmetic in §3.1** recomputed from the E96 values actually in the file.
- **Inductor ratings** re-queried from LCSC, §10.11.

Not verified, and not verifiable here: nothing on this sheet has been built or measured. The standby
and reading-state figures in §8 are arithmetic on datasheet typicals. The two new open items in §9 —
`+5V_DCDC`'s decay when disabled and the `+VSYS` dip at 5 V enable — are consequences of deleting
`U11` and **both need a hardware test**; neither can be settled from a datasheet.
