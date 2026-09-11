# Handoff — Octavo OSD62x-PM vs OSD62x as R2's compute module

Written **2026-09-10** by a claude.ai web session that had **no local access**: it read the repo
from a shallow clone of `Board-Design` @ **`512cd73`** ("routing", 2026-09-08) and the vendor
documents over the web. DigiKey/Mouser product pages could not be opened, so live stock/price at
distributors is **not** verified here.

**Nothing in the repo has been changed.** This file proposes; the hardware owner decides.

> **Status, 2026-09-11 — read this first.** The owner **confirmed the switch to the `OSD62x-PM`** on
> 2026-09-11; the work plan is **`NOTES-R2-osd62x-plan.md`**. Checked against the board and repo since
> this file was written, four of its premises were wrong or incomplete:
>
> 1. **R2 is a six-layer, 0.8 mm board**, not the four-layer sig/gnd/gnd/sig assumed in §2 and §4.2 —
>    owner-confirmed; `datasheets/PCB/6-layers PCB_3313.pdf`, `layout.md` §4.1.1. `In2.Cu` is a power
>    layer, so §4.2's "real conflict" does not arise.
> 2. R2 wires **48 signal nets** through the SoM, including **USB1** (the second host) as well as USB0 —
>    so both USB PHY rail groups stay (cf. S11).
> 3. The SoM corner was still unrouted on 2026-09-10 (1 of 99 connected `J501`/`J502` pads had a track).
> 4. `OSD6254-1G-IPM` is **not on LCSC**; the owner reports 100+ across DigiKey and Mouser. On LCSC,
>    `TPS6521903` had 6 in stock and `TPS6521901` 2853 (2026-09-10).
>
> The vendor facts below are still this session's reading and have not been re-read locally.

Tags used below, matching `CLAUDE.md`'s "verified / inferred / needs a hardware test" rule:

| Tag | Meaning |
| --- | --- |
| **[V]** | verified from a vendor source listed in §11, on the date above |
| **[R]** | read from the repo at `512cd73` — a repo claim, not re-verified |
| **[I]** | inferred / computed by the web session — check before relying on it |
| **[H]** | needs a hardware test — nobody can confirm it without a board |

---

## 0. First steps for the local instance

1. Read `CLAUDE.md` (ground rules), then `NOTES-R2-plan.md`, `pcb/r2-mainboard/docs/som.md`,
   `power.md` §1/§5.1/§8.1, `mcu.md` §5.5–§5.9, `layout.md` §1.1/§4.
2. Create `pcb/r2-mainboard/datasheets/SoM Octavo OSD62x/` and put the §11 documents there
   (or ask the owner to, if you have no web access). **The AM62x datasheet `SPRSP58` is not in the
   repo today** — only PHYTEC's manuals are — and it is the binding source for sequencing.
3. Do the §10.4 task list in order. Do not edit any `.kicad_*` file while KiCad is open.

---

## 1. TL;DR

- **Same silicon, same software story.** Both Octavo parts carry the AM6254 + DDR4, so every DPI
  conclusion already in `NOTES-R2-hardware-facts.md` §2 (RGB666 on `DATA[17:0]`, 165 MHz DPI,
  `BOOTMODE_8/9` on `DATA16/17`, 3.3 V LVCMOS) still applies. **[V]/[R]**
- **Only the `-PM` is actually orderable today.** Octavo lists `OSD6254-1G-IPM` at **$22.50** with
  a datasheet (v2.0, 2026-01-16) and seven app notes. The full **OSD62x** page offers only
  *"BETA Sign Up"* and *"Request Sample"* — no order table, no datasheet, no app notes. **[V]**
- **The full OSD62x fits R2's board rules; the `-PM` does not, as they stand.** OSD62x is
  21×21 mm, 437 balls, **1.0 mm pitch**, PMIC + EEPROM + oscillators inside, single 3.3 V input.
  The `-PM` is 9×14 mm, 500 balls, **0.5 mm pitch**, and needs ~0.09–0.1 mm trace/space and
  0.25/0.15 mm vias locally plus an external PMIC. R2 is now a **4-layer sig/gnd/gnd/sig** board
  with 0.11 mm class clearance and 0.45/0.3 mm vias. **[V] + [R] + [I]**
- **Price and thickness are the reasons to switch.** €250 `PCM-071` + 2 × `BTH-060` ($12.98)
  and a 5.0 mm stack → ~$22.50 SiP + PMIC + a few parts, 1.3 mm tall. **[V]/[R]**
- **Reading-state power is not proven better.** PHYTEC measured `PCM-071` Suspend-to-RAM at
  **128.6 mW** [R]. Octavo's own `OSD62-PM-BRK` measures **~50 mA at 5 V (~0.25 W)** in Deep Sleep,
  but Octavo says that board was not designed for low power [V]. TI's SoC+DDR rails measure
  25–34 mW [V]. A custom design can plausibly beat 128.6 mW **[I]** — it has to be measured **[H]**.
- **Decision the owner has to make** (§10.2): keep `PCM-071` for the R2 prototype and take the
  `-PM` as the R3/production path, **or** switch R2 now while the SoM corner is still unrouted.

---

## 2. Where the repo stands (what this decision lands on) [R]

| Item | State at `512cd73` | Where |
| --- | --- | --- |
| Module | **`PCM-071`** (connectorised) chosen 2026-08-13; €250 @1–9, MOQ 1; `PCL-071` = "second revision target" | `NOTES-R2-hardware-facts.md` §3, `som.md` §9 item 7 |
| Module measurements | Idle 1485.7 mW, **Suspend-to-RAM 128.6 mW** @ 5.004 V `VIN`, wake ≈150 ms, 237 ms suspend+resume round trip; two DP83867 GbE PHYs on module; M4F must be stopped before suspend | facts §4.6 (`lowpowermode_phytec.pdf`) |
| Panel / link | `GDEP103TC2-FT11` 10.3" 1872×1404; link designed for **40–50 Hz** (113 MP/s @ 40 Hz) | `panel.md` §0–§3 |
| Capture | Stage C complete, 14 sheets, root wired; WP6–8 drawn, not owner-reviewed | plan |
| Layout | 327 footprints placed/imported; SoM `X500`+`J501`+`J502` placed top-right, back face; **DDR3 fanout being routed** (530 segments, 54 vias on 2026-09-03) | `session-prompt-layout.md` |
| Stack-up | **1.0 mm 4-layer, sig / gnd / gnd / sig**, PCBWay 1 oz outer (changed 2026-09-03). KiCad's Physical Stackup not yet updated | `layout.md` §4.1.1–§4.1.2 |
| Rules | class clearance **0.11 mm**, DRC floor 0.10 mm, vias 0.45/0.3 (signal) and 0.6/0.3 (default) | `layout.md` §4.1–§4.2 |
| Outline | ≈90×70 mm intended; placeholder rectangle in `Edge.Cuts` | `session-prompt-layout.md` |
| Thickness | back face +**5.0 mm** for the SoM stack; cell 7.0 mm in its own area; depth = larger stack | `layout.md` §1.1 |
| Power tree | `+VSYS` 3.0–4.4 V → `U10` LDO `+3V3_AON`; `U12` TPS61022 `+5V_DCDC` (SoM `VIN`, EPD HV, USB1 host); `U13` TPS63802 2 A `+3V3_DCDC` (FPGA VCCO/VCCAUX, NOR, panel logic); `U14`/`U15` TPS62A02 `+1V2`/`+1V5` | `power.md` §1 |
| SoM sequencing | 5-step firmware sequence: `SOM_RESET#` low → `MCU_EN_5V` → wait `X_PGOOD` (`PG_SOM`, `PC8`) → `MCU_EN_3V3` → release reset. Driven by PHYTEC §5.4 "mandatory" + BOOTMODE_8/9 latch | `power.md` §5.1 |
| SoM ↔ MCU | `SOM_IRQ#` A57 / `SOM_WAKE#` A58 (`MCU_GPIO0_13/14`), `SOM_MCU_NRST` A59 / `SOM_MCU_BOOT0` A60 (`MCU_MCAN1_TX/RX`, via `Q400`/`R407`) | `som.md` §5, `mcu.md` §5.8 |
| Boot | module eMMC primary, microSD `J500` on `MMC1` fallback, card powered from module `SoC_VDDSHV5_SDIO` | `som.md` §4 |
| Cost model | SoM is "the whole game"; costing doc already names "bare AM62x + our own DDR ≈ €35 of silicon" as the long-term path, "explicitly not an R2 change" | `NOTES-production-costing.md` §4.2, §5 |

---

## 3. The two Octavo parts, side by side [V unless marked]

| | **OSD62x-PM** | **OSD62x** (full) |
| --- | --- | --- |
| Contents | AM62x + DDR4 + passives | AM62x + DDR4 + **TPS65219 PMIC + EEPROM + oscillators** + passives |
| Package | **9 × 14 × 1.3 mm**, 500-ball BGA, 18 rows × 28 cols | **21 × 21 mm**, 437-ball BGA (height not published) |
| Ball pitch / ball / land | **0.5 mm** / 0.25 mm ball / 0.20 mm land (0.17 mm min) | **1.0 mm** (ball/land not published) |
| Power input | every AM62x + DDR rail exposed — **you design the PMIC** | **single 3.3 V input**, all sequencing internal, "rails available for system user" |
| Memory | 1 GB x16 DDR4 orderable; datasheet says up to 2 GB; DDR4 max 1600 MT/s | DDR4 (page body text still says LPDDR4 — inconsistent, ask) |
| Display | 2× 1080p60; OLDI + 24-bit RGB parallel | same |
| Temperature | −40…85 °C case | 0…85 or −40…85 °C case |
| Orderable PN / price | **`OSD6254-1G-IPM`, $22.50** (Octavo list). CNX, Aug 2025: DigiKey $29.23, Mouser $35.58, $24.68 @100+ | **none listed** — "BETA Sign Up", "Request Sample" |
| Datasheet | **v2.0, 2026-01-16** (Mouser mirror is Rev 1.0, 2025-06-01) | not published |
| App notes | schematic checklist, pin mapping, thermal, **layout guide**, boot chain & debug, **power app note**, **power design & budgeting** | none |
| Reference board | `OSD62-PM-BRK`, open hardware, 4-layer, single-sided, 101.6×30.48 mm; DDR config on GitHub `octavosystems/osd62-pm-ddr` | none |
| Still needed on our board | PMIC (+ load switch), 25 MHz crystal/osc (required), 32 kHz (optional), eMMC or SD boot, BOOTMODE straps, ferrites, optional EEPROM, optional VPP LDO | 3.3 V supply, eMMC or SD boot, BOOTMODE straps (verify) |

Both need **external eMMC** (or SD-only boot): neither integrates flash. **[V]**

---

## 4. Fit to R2's board

### 4.1 `-PM` escape against JLCPCB capability and R2's rules

Octavo layout guide **[V]**:

- Min trace/space: **3.5 mil** with 0.20 mm land, **4 mil** with 0.17 mm land. Recommended for
  1 oz: 0.20 mm land, **10 mil (0.254 mm) finished via**, 3.2/3.2 mil.
- Max via, one via between balls: 0.3547 / 0.3293 / 0.3039 mm at 3/3, 3.5/3.5, 4/4 mil.
- Max via when a trace must pass **between two vias** (needed to escape row 4 while row 3 uses
  vias): **0.2714 / 0.2333 / 0.1952 mm** at 3/3, 3.5/3.5, 4/4 mil.
- Outer 2 rows escape on top; rows 3–4 go to another layer (bottom on a 4-layer). All SoC I/O is
  in the outer 4 rows; ~100 GND balls, one via per GND ball is enough; no caps needed under the part.
- BRK stack: L1 signals, **L2 GND**, **L3 3.3 V plane + power routing** (VDD_CORE and VDDS_DDR
  routed out of one corner), L4 signals + GND flood. 3/3 mil, 4 mil drill / 3 mil ring vias.

JLCPCB capability **[V]**: multilayer 1 oz trace/space **0.09/0.09 mm**, 3 mil tolerated in BGA
fan-outs, **min via 0.15/0.25 mm**, 0.20–0.25 mm BGA pads require **ENIG**, BGA pad-to-trace
≥0.10 mm (0.09 mm locally on multilayer). Free resin-filled via-in-pad only on **6–20 layers**
(third-party summary). **PCBWay's equivalents were not checked** — the owner is currently using
PCBWay's stack-up.

Arithmetic for R2 **[I]**:

| Check | Result |
| --- | --- |
| One trace between two 0.20 mm pads (0.30 mm gap) at R2's **0.11 mm** clearance | 0.30 − 0.22 = 0.08 mm trace — **below** JLC's 0.09 mm min. Needs a local rule: **0.10 trace / 0.10 clearance** fits exactly |
| Via centred between four balls: centre-to-pad 0.354 mm | 0.25 mm via → 0.354 − 0.125 − 0.10 = **0.129 mm** clearance ✓ · R2's 0.45 mm via → 0.029 mm ✗ |
| Trace between two vias (row-4 escape) at JLC's 0.25 mm min via | needs ≤0.233 mm via at 3.5/3.5 mil → **not possible**; only at 3/3 mil (≤0.271 mm), JLC "BGA fan-out" exception |
| R2's own escape need | ~45 signals (DPI 22, SPI 5, UART 2, USB 2–4, MMC1 ~8, reset/PG/wake ~6, PMIC I²C/INT/STBY) — **a partial escape may avoid the row-4-between-vias case** if these balls sit in rows 1–3. Check against the pin-mapping app note |

So the `-PM` is **manufacturable on 4 layers at JLC's advanced limits** [I], with a KiCad rule
area around the part (0.10/0.10 mm, 0.25/0.15 mm vias, ENIG). Expect a fab surcharge; confirm
with PCBWay if staying there.

### 4.2 The real `-PM` conflict is the stack-up, not the pitch [I]

Octavo's 4-layer escape relies on **L3 as a 3.3 V plane with power routing** for `VDD_CORE`
(group max **2.7 A** [V]; BRK nominal 913 mA at 0.75 V [V]) and `VDDS_DDR` (max 800 mA [V]).
R2 deliberately made **both inner layers ground** (`layout.md` §4.1.1) for the DDR3 return path.
Routing ~1–2.7 A core current on the outer layers through the same via field used for signal
escape is the hard part. Options, all needing an SI review against `layout.md` §7.2:

1. Power island on `In2.Cu` confined to the SoM corner, away from the FPGA/DDR3 corner.
2. Put the PMIC's buck1/buck3 directly beside the SiP's core/DDR corner and pour on `B.Cu`.
3. 6-layer board (free via-in-pad at JLC) — reopens the 2026-09-03 stack-up decision.

### 4.3 The full OSD62x fits the rules R2 already has [I]

1.0 mm pitch is the same as the Spartan-6 `FTG256` already escaped on this board. One 0.15–0.20 mm
trace between balls at 0.11 mm clearance and 0.45/0.3 mm vias between balls both fit. The PMIC
is inside, so no power island is needed beyond one 3.3 V feed. **It is blocked on availability
and a datasheet, not on geometry.**

### 4.4 Thickness [R] + [I]

`layout.md` §1.1: back face carries **+5.0 mm** for the `PCM-071` stack. The `-PM` is **1.3 mm**
[V]. After a swap the tallest back-side part (likely the USB-C receptacle) and the **7.0 mm cell**
would set the depth [I] — so the gain is real but capped by the cell, roughly 5 mm → ~1 mm on the
board stack.

### 4.5 BOM delta [V prices / I totals]

| Remove | Add (`-PM`) | Add (full OSD62x) |
| --- | --- | --- |
| `PCM-071` €250 | `OSD6254-1G-IPM` $22.50 | price unknown |
| 2 × `BTH-060-01-L-D-A-K-TR` $12.98 | TPS65219 (`TPS6521903` in Octavo's reference; `…04` was $3.19 at DigiKey in 2025) | — |
| module eMMC 32 GB, EEPROM, 2 × GbE PHY | `TPS22965` load switch (already in `datasheets/Power/`), 25 MHz crystal/osc, 32 kHz (opt.), ferrites, eMMC or SD-only boot, BOOTMODE resistors | eMMC or SD-only boot, BOOTMODE resistors |

LCSC availability of `TPS6521903` and of an eMMC in a routable package is **not checked**.
Memory prices are elevated (PHYTEC's surcharge note in facts §3), so eMMC price will move.

---

## 5. Power sequencing — the requirement the datasheet points to

The `-PM` datasheet says its rails have sequencing requirements and defers to the **AM62x
datasheet** and the **OSD62x-PM Power Application Note**. What follows is everything those (plus
TI's FAQ and the TPS6521903 NVM manual) state. **Still extract the "Power-Up Sequencing" figure and
"Supply / Signal Assignments" table from `SPRSP58` into the repo** — Octavo's sequencing figure is
an image, and the order below comes from TI's validated PMIC configuration, not from a table.

### 5.1 Hard rules [V]

| # | Rule | Source |
| --- | --- | --- |
| S1 | Follow the datasheet's power-up order. **No minimum delay between groups**, but each group must finish ramping before the next starts | TI FAQ 1301305 |
| S2 | **Slew rate < 18 mV/µs** on every rail during power-up (ESD clamp protection; not defined for power-down) | Octavo power note §2.1.3; TI FAQ |
| S3 | All rails valid before `MCU_PORz` release; recommended delay supplies-valid → `MCU_PORz` release **> 9.5 ms**; release must be glitch-free | Octavo power note §2.1.5, §3 |
| S4 | `VDDR_CORE` must never exceed `VDD_CORE` + 0.18 V, up or down. At **0.75 V** core: `VDD_CORE` up before / down after `VDDR_CORE`. At **0.85 V** core: both from one source, ramp together | Octavo §2.1.5; TI FAQ |
| S5 | If `VDD_CANUART` is always-on, `VDD_CORE` ≤ `VDD_CANUART` + 0.18 V; otherwise ramp together (Partial-IO not used) | Octavo §2.1.5 |
| S6 | No residual voltage: **all rails < 0.3 V** before a new power-up. The TPS65219 enforces a discharge check below the short-circuit threshold before sequencing | Octavo §3; TI FAQ; SLVUCJ2A §2.9 |
| S7 | Power-down: assert `MCU_PORz` as soon as the first rail drops below its recommended minimum. IO rails may stay up until the last core rail is off, but **not for long** (TI validated 10 ms) | TI FAQ |
| S8 | **Many AM62x pins are not fail-safe**: no potential may be applied until the pin's own IO rail has ramped | TI FAQ |
| S9 | `VPP` (OTP) must be **0 V** at power-up and in normal use; leave unconnected if OTP is never programmed | Octavo §2.1 Table 2-2 note 1, §2.1.9 |
| S10 | `VMON_VSYS` input range 0–1 V (divider); `USBx_VBUS` 0–3.465 V (divider) | Octavo power design note §7.3 |
| S11 | Unused USB → `VDDA_CORE_USB`, `VDDA_1P8_USB`, `VDDA_3P3_USB` may go to GND. Unused CSI → `VDDA_CORE_CSIRX0`, `VDDA_1P8_CSIRX0` to GND. **R2 uses USB0, so keep USB rails** | Octavo Table 2-6 |
| S12 | No dynamic voltage scaling: **0.75 V core → A53 up to 1.2–1.25 GHz; 1.4 GHz needs 0.85 V** | Octavo Tables 2-3, 4-2 |
| S13 | "The same voltage rail powers both the device and the IO domain it connects to" — Octavo's rule for peripherals on switched 3.3 V | Octavo power design note §3.3 |

Rail table (max currents) **[V]**, Octavo power note Table 2-2:

| Rail | Voltage | Max |
| --- | --- | --- |
| `VDD_CORE` + `VDDA_CORE_CSIRX0` + `VDDA_CORE_USB` | 0.75 or 0.85 V | 2700 mA |
| `VDD_CANUART` | = core | 10 mA |
| `VDDR_CORE` | 0.85 V | 150 mA |
| `VDDS_DDR` (SoC DDR PHY + DDR4 VDD/VDDQ, joined inside) | 1.2 V | 800 mA |
| `DDR_VPP` | 2.5 V | (LDO4 in reference) |
| `VDDS_OSC0` | 1.8 V | 5 mA |
| `VDDA_MCU` | 1.8 V | 30 mA |
| `VDDA_PLL0..2`, `VDDA_1P8_*`, `VDDA_TEMP` | 1.8 V | 150 mA group |
| `VDDA_3P3_USB` | 3.3 V | 50 mA |
| `VDDSHV0..4`, `VDDSHV6` | 1.8/3.3 V | 150 mA group |
| `VDDSHV_MCU` | 1.8/3.3 V | 30 mA |
| `VDDSHV_CANUART`, `VDDSHV5` | 1.8/3.3 V | 10 / 30 mA |
| `VPP` | 1.8 V only during OTP programming, else 0 | 400 mA |

### 5.2 TI's validated sequence for exactly this case — `TPS6521903` [V]

NVM target: **AM62/AM64, 0.75 V core, DDR4, `VSYS` = 3.3 V**. I²C address `0x30`.
`EN/PB/VSENSE` = push-button with **First Supply Detection** on, so it powers up when `VSYS`
appears. `MODE/STBY` = MODE+STBY, **low → STBY**. `MODE/RESET` = warm reset. **Every rail and GPO2
stays enabled in STBY.** LDO3/LDO4 use the ~3 ms slow ramp. EEPROM load ≈2.3 ms. Source: SLVUCJ2A.

| Power-up slot | Duration | Turns on | AM62x domain |
| --- | --- | --- | --- |
| 0 | 10 ms | **GPO2** → external TPS22965 | **DVDD3V3** (`VDDSHVx` 3.3 V, `VDDSHV_MCU`) |
| 1 | 0 ms | — | — |
| 2 | 3 ms | BUCK2 1.8 V, LDO1 3.3/1.8 V (bypass), LDO3 1.8 V, LDO4 2.5 V | DVDD1V8, `VDDA_1V8`, `VDDSHV5_MMC`, DDR4 VPP |
| 3 | 1.5 ms | BUCK3 1.2 V | `VDDS_DDR` |
| 4 | 1.5 ms | BUCK1 0.75 V | `VDD_CORE` |
| 5 | 1.5 ms | LDO2 0.85 V (fed from BUCK2 — Octavo: not from BUCK3, for sequencing) | `VDDR_CORE` |
| 6 | 10 ms | GPO1, GPIO | — |
| 7 | 1.5 ms | — | — |
| 8 | 10 ms | **nRSTOUT** | **`MCU_PORz`** |

| Power-down slot | Duration | Turns off |
| --- | --- | --- |
| 0 | 10 ms | nRSTOUT (`MCU_PORz`), BUCK3 (DDR), LDO2 (`VDDR_CORE`), GPO1, GPIO |
| 2 | 10 ms | BUCK1 (core), BUCK2, LDO1, LDO3, LDO4, **GPO2 (3.3 V IO)** |

Read as an order: **3.3 V IO → 1.8 V / 2.5 V → 1.2 V DDR → 0.75 V core → 0.85 V VDDR_CORE →
`MCU_PORz`**, and the reverse-ish on the way down with PORz first. This satisfies S3, S4 and S7 by
construction. Alternatives Octavo lists as DDR4-compatible: `TPS6521901`, `…04`, `…07`; `…05` is
blank/user-programmable. **Which one matches 0.85 V core (1.4 GHz) and a non-3.3 V `VSYS` is an
open check** (§10.4 task 4).

### 5.3 Reference PMIC ↔ SoC wiring [V] (Octavo power design note §4)

| Signal | Connection |
| --- | --- |
| `I2C0` SCL/SDA | to PMIC; pull-ups to the **switched** 3.3 V (the `VDDSHV0` rail) |
| `RESETSTATz` | → PMIC `MODE/RESET` |
| `PMIC_LPM_EN0` | → PMIC `MODE/STBY`, pull-up to the `VDDSHV_CANUART` rail. Keeps PMIC active until `MCU_PORz` releases; low = STBY / auto-PFM for Deep Sleep |
| `MMC1_SDWP` | → `VSEL_SD` (UHS-I switching of LDO1); pull-up |
| PMIC `nINT` | → `EXTINTn` |
| PMIC `nRSTOUT` | → `MCU_PORz` (1.8 V fail-safe input per SLVUCJ2A Fig. 2-3) |
| PMIC `GPO2` | → TPS22965 `EN`; switched 3.3 V feeds `VDDSHV1-4` **and all 3.3 V peripherals** |
| SD card VDD | separate IO-controlled TPS22918 so the card can be power-cycled |
| `VPP` | IO-controlled TLV75518 (only if OTP programming is wanted) |

### 5.4 What the sequencing means for R2 specifically

1. **The PHYTEC-driven 5-step sequence in `power.md` §5.1 would be replaced, not edited.**
   Its two drivers were PHYTEC §5.4 (`X_PGOOD` gating) and the module's own BOOTMODE pull-ups.
   With the `-PM`, the SoC's 3.3 V IO comes up **first** (slot 0) and `MCU_PORz` releases last
   (slot 8). **[V] order / [I] consequence**
2. **Put FPGA `VCCO` bank 1 (DPI) and the SoC's `VDDSHV3` on the same switched 3.3 V rail** (S13).
   Then there is never a state where the FPGA side is powered and the SoC IO is not (S8), nor the
   reverse at BOOTMODE sampling. That removes both failure modes `power.md` §5.1 was built around.
   Check against Spartan-6: `ds162.pdf` Table 6 — no required order, but **each supply must ramp in
   0.20–50 ms** [R], which a TPS22965 with a `CT` cap and S2's ≥183 µs minimum (3.3 V / 18 mV/µs)
   can both satisfy **[I]**.
3. **BOOTMODE straps move onto our board.** `VOUT0_DATA16/17` are still `GPMC0_AD8/9` =
   `BOOTMODE_8/9` (SoC-level mux) [R: facts §3.1]. We now choose every strap resistor.
   - Re-derive values from the AM62x TRM boot-mode table and the Octavo "Boot Chain and Debug" note.
   - Straps must dominate Spartan-6 configuration pull-ups (`HSWAPEN`) on `DPI_R6`/`DPI_R7`.
   - Keep the rule that nothing else loads those two nets. **[I]**
4. **S8 applies to every SoC input driven by an always-on part.**
   - `MCU_TXD` → SoC UART RX is already flagged in `mcu.md` §4 (reconfigure before cutting the rail) [R].
   - Re-check `SOM_WAKE#`, `SOM_IRQ#`, CSR SPI `FPGA_MISO`, and `USB0_VBUS` from `J1` (needs a divider, S10).
5. **`MCU_PORz` becomes the MCU's reset handle.** It is fail-safe, so an MCU open-drain can
   wire-AND with PMIC `nRSTOUT` in place of `SOM_RESET#` → `X_nRESET_IN` [I]. `PG_SOM` has no
   direct equivalent: the TPS65219 has `nRSTOUT` and `nINT`, not a PGOOD pin. Options are to read
   `nRSTOUT`/`MCU_PORz` or query the PMIC over I²C [I].
6. **SD card decay (S6).** TI's FAQ calls out exactly R2's arrangement — a card that switched to
   1.8 V signalling and was not power-cycled below 0.3 V. `som.md` §4 deliberately omitted the
   card load switch. With a `-PM` design, either add the switch (Octavo does) or pin `VDDSHV5` at
   3.3 V and never enable UHS-I [I].
7. **`+5V_DCDC` loses its largest load.** The SoM's 1.0 A design bound leaves `power.md` §8.1.
   Remaining: EPD HV chain + USB1 host (565 mA limit). Also the boost no longer has to run during
   the reading state for the SoC to keep DDR in self-refresh [I].

### 5.5 Power-tree integration options for R2 [I — evaluate, don't adopt]

| | Option A — mirror TI/Octavo | Option B — PMIC bucks from `+VSYS` | Option C — full OSD62x |
| --- | --- | --- | --- |
| PMIC input | `TPS6521903` `VSYS`/`PVIN` from a 3.3 V buck-boost | `PVIN_Bx` from `+VSYS` 3.0–4.4 V (one conversion); `PVIN_LDO1` from 3.3 V (bypass mode requires PVIN = VSET) | internal |
| 3.3 V IO | PMIC `GPO2` → TPS22965 → SoC `VDDSHV*` + FPGA `VCCO` + NOR + panel logic | same | "rails available for system user" — **unknown what** |
| Concern | `U13` TPS63802 is 2 A and already carries FPGA + panel. Octavo's worst case is 3004 mA on `VIN-3P3` incl. 1145 mA of board load, i.e. SiP ≈1.9 A worst case → **needs its own buck-boost or a bigger one** | NVM `…03` assumes `VSYS` = 3.3 V; check UV/OV thresholds and whether another NVM or `…05` is required | 3.3 V input tolerance, current and Deep Sleep support all unpublished |
| MCU control | `MCU_EN_3V3` (or a new `MCU_EN_SOC`) powers PMIC; PMIC sequences itself | same, plus a PMIC `EN/PB` handle | one enable on the 3.3 V feed |

For every option, check that the chosen 3.3 V converter meets S2 (≤18 mV/µs) and S6 (active
discharge below 0.3 V). `TPS63802`'s soft-start and discharge behaviour is in
`datasheets/Power/tps63802.pdf`.

---

## 6. Reading state and low power

| Measurement | Value | Conditions | Tag |
| --- | --- | --- | --- |
| `PCM-071` Suspend-to-RAM | **128.6 mW** | whole module at 5 V `VIN`, two GbE PHYs present, PHYTEC carrier, BSP PD25.1.1 | [R] facts §4.6 |
| `PCM-071` wake | ≈150 ms; 237 ms full round trip | same | [R] |
| `OSD62-PM-BRK` Deep Sleep | **~50 mA @ 5 V ≈ 0.25 W** | whole BRK: TLV62595 5→3.3 V, oscillators, camera connector, ADCs. "Not designed to support all low power modes" | [V] Octavo power design note §8 |
| `OSD62-PM-BRK` OS idle | 300 mA (1.4 GHz) / 290 mA (400 MHz) @ 5 V | same | [V] |
| `OSD62-PM-BRK` stress-ng | 450 mA @ 5 V | same | [V] |
| AM62x SoC + DDR4 rails, Deep Sleep | 25–34 mW | TI EVM, SoC rails incl. the DRAM on `VDD_DDR4` | [V] SPRADG1 |

**Deep Sleep in the Octavo/TI framing [V]:** supplies stay on, on-chip domains off except
always-on, DDR in self-refresh, context saved to DDR. Wake sources are RTC, MCU (WKUP) GPIO,
Main I/O daisy chain (Main GPIO / Main UART), USB, WKUP UART, and CANUART daisy chain.
`SOM_WAKE#` on `MCU_GPIO0_14` stays a valid choice [R+V]. With `TPS6521903` all rails remain
enabled in STBY; `PMIC_LPM_EN0` only moves the PMIC to auto-PFM.

**Where a custom `-PM` design can save power versus the BRK and the PHYTEC module [I]:**
- no GbE PHYs;
- no 5 V intermediate stage;
- a **crystal instead of the BRK's 25 MHz oscillator** (4.5 mA at 1.8 V ≈ 8 mW, always on);
- no camera/ADC/EEPROM on the switched rail;
- PMIC in STBY / PFM;
- eMMC in its lowest state;
- `+5V_DCDC` off while reading.

**None of this is a number.** Do not put a `-PM` reading-state figure into
`NOTES-R2-hardware-facts.md` until measured **[H]**.

⚠ **Correction to the earlier web chat:** it estimated "~30–50 mW" for an AM62x SiP on our own
power tree and built battery-life tables on it. That was an estimate, and Octavo's own measured
BRK figure is 0.25 W. Treat those tables as unverified.

---

## 7. Software, BSP, provisioning [V where cited, else I]

- Octavo: the `-PM` is compatible with all AM62 software; TI Linux BSP, MCU+ SDK, Octavo
  Yocto/Debian images for the BRK; DDR4 timing parameters published on GitHub
  (`octavosystems/osd62-pm-ddr`) — these must go into our U-Boot SPL/`tiboot3` build. [V]
- PHYTEC's BSP (PD25.1.1) and its low-power quirks (stop the M4F before suspend, facts §4.6) are
  PHYTEC-specific; the M4F issue should be re-checked on TI SDK **[H]**.
- `system-overview.md` §6 provisioning (factory microSD → write eMMC → flash MCU over UART →
  write FPGA NOR over SPI) still works if the board gains an eMMC and keeps the SD slot **[I]**.
  The "module arrives with a demo image" premise disappears — the board ships blank.
- TI's U-Boot board detection on SKs reads an EEPROM; whether Octavo's BSP requires one for the
  `-PM` is an open question (§10.1).

---

## 8. Repo impact if R2 switches to the `-PM` [R file list, I impact]

| File / tool | Impact |
| --- | --- |
| `som.kicad_sch`, `dpi_in.kicad_sch`, `docs/som.md` | rewrite: SiP symbol from Octavo pin map, PMIC + load switch, crystal, straps, eMMC, SD switch |
| `datasheets/SoM Phycore AM62x/som_pinout.json`, `tools/parse_som_pinout.py`, `gen_som_symbol.py`, `gen_som_footprint.py`, `patch_som_mcu_recovery.py` | PHYTEC-table-specific; historical. New generator from Octavo's pin-mapping note |
| `tools/check_pcb_connectors.py` | asserts `J501`/`J502` geometry — retire or replace with a SiP-footprint check |
| `power.kicad_sch`, `docs/power.md` §1, §5.1, §8.1 | rail tree, sequence and 5 V budget change (§5.4, §5.5) |
| `mcu.kicad_sch`, `docs/mcu.md` §5.5–§5.9 | `PG_SOM`/`SOM_RESET#` semantics; A57–A60 remapped to the same SoC signals on new balls |
| `layout.md` §1.1 (5.0 mm), §3.2, §4.1 (new fine-pitch rule area), §6.3, `r2.kicad_dru` | SoM corner re-placed; USB pair still wants the SiP beside `J1` |
| `NOTES-R2-plan.md` constraint 1 & architecture, facts §3, `NOTES-production-costing.md` §1–§4, `libraries.md`, `system-overview.md` §1/§6 | module identity, cost line, provisioning premise |
| **Unaffected** | `fpga_*`, `epd*`, `power_mon`, `battery`, `frontlight`, `io_expansion` (except `+5V` load note), Caster gateware, DDR3 routing already done |

**Refdes:** new parts on the `som` page take `U5xx`/`R5xx`/`C5xx` per `CLAUDE.md`. Do not
string-replace BTH pin names (`A1`–`D60`) — they vanish with the connectors, but `layout.md` §9.5
still applies to FPGA ball names.

---

## 9. Stale or inconsistent docs spotted while reading (independent of this decision) [R]

1. `NOTES-R2-plan.md` — "Three board-level consequences of the **DSC** footprint" (cut-out,
   4.5–5.5 V) still reads as current although `PCM-071` was chosen 2026-08-13.
2. `NOTES-R2-hardware-facts.md` header says "Last updated 2026-08-03"; content runs to at least
   2026-08-18. `power.md` header says 2026-08-11 with content to 2026-08-30.
3. `system-overview.md` §2 block map uses pre-renumbering refdes (`X2`, `U41`, `U52`, `U20`,
   `J21`, `J24`) against the page scheme (`X500`, `U700`, `U800`, `U400`, `J500`…).
4. `layout.md` status line and §1 say placement is blocked and the stack-up "matches R1 byte for
   byte"; `session-prompt-layout.md` says the SoM is placed, DDR3 is being routed and the stack-up
   changed 2026-09-03. §2 table still says "90 × 80 mm, outline undecided".
5. `layout.md` §4.1.2/§4.2 name `U1` **BQ25792**; `battery.kicad_sch` and `r2.kicad_pcb` carry
   **BQ25892RTW(R)**. Typo in the doc, not the board (check the 0.125 mm pad-gap figure is for the right part).
6. `NOTES-session-handoff.md` (2026-08-17) says Stage D has not started — superseded, as its own
   header warns.
7. `som.md` §8 layout note gives DPI as "~101 MP/s actual at 1448×1072@60" — pre-panel-change
   number; `panel.md` now says 113 MP/s at 40 Hz for 1872×1404.

---

## 10. Open items

### 10.1 Questions for Octavo (sales + the free-ish Design Review Service they advertise)

1. **OSD62x (full):**
   - When is it orderable? Part numbers, price at 1/10/100, and a date for the datasheet.
   - DDR4 or LPDDR4? (the page says both)
   - Package height, ball/land size.
   - Which TPS65219 NVM is inside, and what core voltage (1.2 vs 1.4 GHz)?
   - Is `PMIC_LPM_EN0` wired to STBY internally? **Is AM62x Deep Sleep supported and measured?**
   - Allowed 3.3 V input range and current.
   - Exactly which "rails available for system user", and with what current and sequencing slot?
   - Are the `VDDSHV` domains fixed at 3.3 V or selectable?
2. **OSD62x-PM:**
   - Current DigiKey/Mouser stock and lead time.
   - Orderable 2 GB part number.
   - What changed from datasheet 1.0 to 2.0?
   - A Deep Sleep figure on a low-power-optimised design, as opposed to the BRK.
   - Recommended TPS65219 NVM for a **1S Li-ion system** (`VSYS` 3.0–4.4 V), or is `…03` behind a 3.3 V buck-boost the intended route?
   - Can rows 3–4 be escaped with 0.25/0.15 mm vias and 3.5 mil rules, given we need only ~45 IO?
   - Is an EEPROM required by their BSP?

### 10.2 Owner decisions

1. **R2 prototype: stay `PCM-071`, or switch to `OSD62x-PM` now?**
   - *Stay:* no schedule hit, Lyra kit and PHYTEC measurements remain directly applicable, `-PM` becomes R3.
   - *Switch:* ~€240 less per board, ~4 mm thinner board stack, no connectors. Cost is re-capturing 4 sheets and a fine-pitch rule area, and the §4.2 stack-up question — before the SoM corner gets routed.
2. If switching: **Option A/B** power tree (§5.5), **0.75 V vs 0.85 V core**, eMMC vs SD-only boot,
   keep UHS-I or pin `VDDSHV5` at 3.3 V.
3. Stay at PCBWay (check their fine-pitch limits) or move the fab to JLCPCB for this board.
4. Buy an `OSD62-PM-BRK` (was ~$115, open hardware) as the `-PM` software/bring-up platform.

### 10.3 Bench tests that only hardware can answer [H]

- Deep Sleep power of a `-PM` design **on our power tree**, and resume-to-valid-DPI latency.
- Whether `SOM_WAKE#`'s ball wakes Deep Sleep on TI SDK.
- DPI 18-bit link integrity at 40–50 Hz into the Spartan-6 on the new routing.
- `MCU_PORz` / BOOTMODE latch correctness with FPGA `VCCO` on the shared switched 3.3 V.

### 10.4 Task list for the local instance, in order

1. Put the §11 documents into `pcb/r2-mainboard/datasheets/SoM Octavo OSD62x/`.
2. From **`SPRSP58`**, extract the Power-Up and Power-Down Sequencing figures, the Supply/Signal
   Assignment tables and all notes. Cross-check §5.1–§5.2 above. Record the source page numbers.
3. From Octavo's **pin-mapping** note, list the balls for everything R2 wires:
   - `VOUT0_DATA0-17`, `PCLK`, `DE`, `HSYNC`, `VSYNC`;
   - `SPI0`, `UART0`, `MMC0`/`MMC1`, `USB0`, `I2C0`;
   - `PMIC_LPM_EN0`, `EXTINTn`, `MCU_PORz`, `RESETSTATz`;
   - `MCU_GPIO0_13/14`, `MCU_MCAN1_TX/RX`, all `GPMC0_AD0-15`/BOOTMODE, all supply balls.

   Mark each ball's row index from the edge, and **report whether all needed signals are in rows 1–3** (§4.1).
4. From **`tps65219.pdf`** and the NVM manuals for `…01/03/04/07`, tabulate core voltage, `VSYS`
   assumption, sequence and STBY enables. Pick the candidate for 0.85 V core and Li-ion `VSYS`, or show that `…05` is needed.
5. Re-run `power.md` §8.1's style of budget for the 3.3 V rail under Option A (SiP ≈1.9 A worst
   case [I] + FPGA + panel logic) against `TPS63802`'s 2 A.
6. Check `TPS63802`/`TPS22965` ramp vs S2 (≤18 mV/µs) and Spartan-6's 0.20–50 ms ramp window; check active discharge vs S6.
7. Draft (do not apply) a `som.md`-style spec for the `-PM` variant. Wait for the owner's §10.2 decision before touching any sheet.
8. Fold verified items into `NOTES-R2-hardware-facts.md` with the tags; leave [I] items out of it.

---

## 11. Sources

**Octavo** (pages read 2026-09-10; product pages show modified 2026-09-03)
- OSD62x-PM product page (order table, features): https://octavosystems.com/octavo_products/osd62x-pm/
- OSD62x product page (beta/sample, features): https://octavosystems.com/octavo_products/osd62x/
- OSD62x-PM Datasheet v2.0: https://octavosystems.com/docs/osd62-pm-datasheet/ · Rev 1.0 mirror: https://www.mouser.com/pdfDocs/OSD62x-PM-DS.pdf
- OSD62x-PM Power Application Note: https://octavosystems.com/app_notes/osd62x-pm-power-application-note/
- OSD62x-PM Power Design and Budgeting: https://octavosystems.com/app_notes/osd62x-pm-power-design-and-budgeting/
- OSD62x-PM Layout Guide: https://octavosystems.com/app_notes/osd62x-pm-layout-guide/
- OSD62x-PM Schematic Checklist: https://octavosystems.com/app_notes/osd62x-pm-schematic-checklist/
- OSD62x-PM to AM62x Pin Mapping: https://octavosystems.com/app_notes/osd62x-pm-to-am62x-pin-mapping/ (the datasheet links `…/osd62x-pm-pin-mapping-to-am62x/`)
- OSD62x-PM Boot Chain and Debug, Thermal Guide: from the product page's Application Notes list
- OSD62-PM-BRK (open hardware, design files, getting started): https://octavosystems.com/octavo_products/osd62-pm-brk/ · https://octavosystems.com/app_notes/osd62-pm-brk-getting-started-guide/
- DDR parameters: https://github.com/octavosystems/osd62-pm-ddr
- DigiKey OSD62x highlight (DDR4 + TPS65219 + EEPROM + oscillators): https://www.digikey.com/en/product-highlight/o/octavo-systems/osd62x-system-in-package
- CNX Software, 2025-08-28 (DigiKey/Mouser prices then): https://www.cnx-software.com/2025/08/28/octavo-osd62x-pm-sip-combines-texas-instruments-am62x-soc-with-up-to-2gb-ddr4-in-a-tiny-14x9mm-bga-package/

**TI**
- AM625/AM62x datasheet **SPRSP58** (binding for sequencing): https://www.ti.com/lit/pdf/SPRSP58
- TPS6521903 NVM Technical Reference Manual **SLVUCJ2A** (sequence slots above): https://www.ti.com/lit/ug/slvucj2a/slvucj2a.pdf
- TPS65219 datasheet: https://www.ti.com/lit/ds/symlink/tps65219.pdf
- NVM manuals `…01` SLVUCH3, `…04` SLVUCL1A, `…07` SLVUCL9A; `…05` datasheet + programming guide SLVUCM5
- Powering AM62x with TPS65219, SLVAFD0B: https://www.ti.com/lit/an/slvafd0b/slvafd0b.pdf
- Discrete power for AM62x, SLUAAK2: https://www.ti.com/lit/an/sluaak2/sluaak2.pdf
- AM625 Schematic Design Guidelines & Checklist SPRAD21; HW design considerations SPRAD05; PDN SPRAC76; power estimation SPRAD31 / AM62X-PET-CALC; max power SPRADA6
- E2E FAQ 1301305, AM62x power-up/power-down sequencing: https://e2e.ti.com/support/processors-group/processors/f/processors-forum/1301305/
- AM62x power consumption SPRADG1: https://www.ti.com/lit/pdf/SPRADG1

**Fab**
- JLCPCB BGA design guide (0.09/0.09 mm, 3 mil fan-out, 0.15/0.25 mm via, ENIG for 0.2–0.25 mm pads): https://jlcpcb.com/blog/bga-pcb-design-complete-guide-layout-and-routing-guidelines
- JLCPCB BGA guidelines (via-in-pad filled): https://jlcpcb.com/help/article/BGA-Design-Guidelines---PCB-Layout-Recommendations-for-BGA-packages
- Free POFV on 6–20 layers (third-party summary; confirm on jlcpcb.com): https://www.schemalyzer.com/en/blog/manufacturing/jlcpcb/jlcpcb-design-rules
- PCBWay fine-pitch capability: **not checked**

---

## 12. Corrections to claims made earlier in the web chat

| Earlier claim | Status |
| --- | --- |
| "JLC's free via-in-pad on 6–20 layers is the stack-up Stage D already budgets" | **Stale.** It was based on an old copy of the plan; R2 went to **4 layers** on 2026-09-03 |
| AM62x SiP on our own power tree "~30–50 mW" asleep, and the battery tables built on it | **Unverified estimate.** Octavo's measured BRK is ~0.25 W; see §6 |
| "Octavo OSD62x (21×21) … announced with 1 mm pitch" | **Confirmed** on Octavo's page: 437 balls, 1.0 mm. But the part is beta/sample only |
| Octavo `-PM` "$29.23 at DigiKey" | 2025 figure. Octavo's own list price is now **$22.50**; distributor stock not re-checked |
| "PHYTEC module-level deep sleep is unpublished" | **Stale** for the repo: PHYTEC measured 128.6 mW / ≈150 ms for `PCM-071` (facts §4.6) |
