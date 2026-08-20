# R2 review round 2 — the owner's WP6–8 notes, triaged

Source: `pcb/r2-mainboard/manual-analysis/*.md`, written 2026-08-10 … 2026-08-19.
Triaged 2026-08-19.

⚠ **Scope, corrected by the owner 2026-08-19.** Only two of those seven files are new for WP6–8:
**`Analysis_dpi_and_som.md`** and **`Analysis_Frontlight.md`**. The other five
(`Analyse_battery`, `Analysis_epd_files`, `Analysis_fpga`, `Analysis_mcu`, `Analysis_power`) belong
to earlier review rounds, and their answers should already be in the sheet specs. The first triage
of this file treated all seven as open, which over-stated the queue — bucket C below is marked
accordingly. **Before working any C item, check the sheet's own doc first; most are already
answered there.**

Four buckets. **A** is already answered in the specs and just needs a pointer. **B** is answered
here, now. **C** needs real work and is queued. **D** is an owner decision, and the ones marked ⏳
cannot be taken after fabrication.

---

## A. Already answered in the specs — the doc got there first

| Question | Where it is answered |
| --- | --- |
| `Y20` — "doesn't the doc say 8 MHz?" | `mcu.md` §11.3. **`Y20` is the LSE; the 8 MHz belongs to the HSE**, which is not fitted. Table 42 (HSE, 4/8/48 MHz) vs Table 43 (LSE, 32.768 kHz), Figure 20 vs Figure 21. `PF0`/`PF1` are free for `MCU_EN_5V`/`MCU_EN_3V3` precisely *because* no HSE is fitted. |
| `FB20` — "where in the doc does it call for this?" | `mcu.md` §10.2 and §11.2, and the answer is **it does not**. The doc says so in as many words: "`FB20` is not a datasheet requirement, and the review was right to ask." It is R1's `FB3` carried across to the one pin still eligible. §5.2 gives the two reasons it stays; §10.2 gives the DCR constraint that makes it safe. |
| Battery connector is too tall | `battery.md` §9.2. JST-PH was **already rejected** for exactly this reason. `J2` is now a Molex Pico-Lock 504050-0391 (1.5 mm pitch, right-angle, 2.00 mm mated height), **and** `J25` is three bare copper solder pads on the same three nets (`+VBAT`, `CHG_TS`, `GND`) for soldering the cell directly. Both options are already on the board — this is a stuffing choice, not a redesign. |
| Touch controller wiring | `io-expansion.md` §4. The sheet was drawn **against the GT911**. It lists `GDEY075T7-T01` / GT911 / 6-pin FPC with pinout 1 `GND`, 2 `VCC`, 3 `RESET`, 4 `INT`, 5 `SDA`, 6 `SCL`, and `J22` carries exactly those six signals. Enabling touch is a **populate**, not a redesign — see D-1. |
| Layout guidelines, all chips | They are written, one "Layout guidelines" section per sheet doc. They surface at Stage D, before placement. `epd-port.md` §11 is the fullest example. |
| Part numbers for the BOM | **Done 2026-08-19**, commit `77469bb`. MPN + Manufacturer are in the schematic symbol properties, which is what a fab reads. 60 of 99 BOM lines; see `NOTES-R2-plan.md` for the five that were deliberately left out. |

## B. Answered here

**B-1 — "Will the buttons wake everything with the MCU unpowered?"**
`SW21`/`SW22` will not; `SW20` will. This is visible in the power tree: `SW21`/`SW22` sit on
`+3V3_AON` behind 100 k pull-ups `R42`/`R43` and go to MCU GPIO, so they need the MCU alive.
`SW20` does not touch an MCU rail at all — it goes straight to the charger's `QON` pin, which is
why it can bring the board out of ship mode when nothing else is powered. That asymmetry is
deliberate (`mcu.md` §2.2) and it is the reason the always-on rail can be as small as it is.

**B-2 — "Only two buttons for the final product, prev and next."**
That is already what the board has for paging. `SW21`/`SW22` *are* prev/next; `SW20` is the power
button and is not one of the two. So no change is needed — but see D-1, because "enter is done with
the touchscreen" only holds if touch is populated.

**B-3 — "Upgrade to USB 3 for fast file transfer."**
**Not possible on this module.** Verified against the SoM's own 240-pin table
(`datasheets/SoM Phycore AM62x/som_pinout.json`): the only USB pins are `X_USB0_DP/DM/VBUS/DRVVBUS`
and `X_USB1_*`. There are no SuperSpeed differential pairs, no PCIe and no SERDES pins anywhere on
the connector. USB 3 would need an external bridge on a bus the module does not expose.

**Useful consequence, though: `USB1` is completely unused.** Four pins, already broken out, costing
nothing today. If a second port is wanted — OTG host for a keyboard, or a dedicated
file-transfer socket — the pins are there. Worth deciding with the other ⏳ pin questions rather
than after.

For transfer speed specifically: USB 2.0 high-speed is ~40 MB/s in practice. A 30 MB EPUB library
copies in about a second. The case for USB 3 on an e-reader is weak, and here it is moot.

**B-4 — "Did the KiCad crash erase changes?"**
No. Checked directly: the "deleted" datasheets in `git status` were the six files **you moved** into
`datasheets/SoM Phycore AM62x/` at 14:53 — all present, byte-for-byte. The 19 k-line schematic diff
is KiCad rewriting every sheet on save; a netlist export before and after has the **same 518 nets
with identical pin membership**, and the MPN properties written earlier that day are all still
there. Nothing was lost.

One real casualty, now fixed (commit `058e9b9`): `parse_som_pinout.py`, `gen_som_symbol.py` and
`gen_dpi_in.py` all hardcoded `datasheets/<name>`, so the move broke them silently. They now find
any datasheet-derived file at any depth under `datasheets/`.

**B-5 — "Were there changes you wanted to make to already-reviewed sheets?"**
Yes, six, and they have been accumulating:

| # | Change | Sheet | Status |
| --- | --- | --- | --- |
| 1 | `R225` 22 kΩ → **20.5 kΩ**, LCSC `C57105` — the one value the `GDEP103TC2` forces | `epd_power` | **DONE 2026-08-19** |
| 2 | Five sense-divider caps → `C1523` (`0402B102K500NT`, 1 nF 50 V X7R, JLC Basic) | `power_mon` | **DONE** |
| 2b | `R88`/`R224` → `C54920667`, 14 units in stock was not orderable | `epd_power` | **DONE** |
| 3 | `+5V2_FL` orphan — `C147` set **DNP**, footprint kept | `epd` | **DONE**, see below |
| 4 | Ten duplicate `#PWR` references | `battery` | **DONE** — renumbered to `#PWR1112`–`#PWR1121` |
| 5 | `J3` deletion | `epd` | **already done 2026-08-15**, `epd-port.md` §9.3 |
| 6 | `Specter` → `Reflow` | 22 files | **DONE** — 14 sheets, 7 generators, 1 project file |

All six verified together: netlist exported before and after has **518 nets with identical pin
membership**, and `epd_power` and `epd` were rendered and checked by eye.

**On `C147`, a deliberate departure from "delete it".** `panel.md` §7 had already ruled that
`J6.7`/`J6.44` stay — *"an unconnected connector pin is not an error. No change to this frozen
sheet."* That ruling covered the pins but not the capacitor sitting on the dead net, which is a
real BOM and pick-and-place line doing nothing. Deleting the symbol would leave dangling wires and
a stray `GND` symbol on a reviewed sheet; marking it **DNP** keeps the topology untouched and leaves
the footprint on the board in case a future panel drives that rail. A `BOM Comments` property on the
part records why.

⚠ **Correction, 2026-08-20:** the text above said "DNP with `in_bom no`". `C147` is `(dnp yes)` but
**`(in_bom yes)`** — it was never set to `in_bom no`, and it still is not. That is the ordinary
KiCad arrangement and it is fine: the part appears on the BOM *flagged as do-not-populate*, which is
what a fab wants to see, rather than vanishing. But it does mean **`C147` will be on the order
unless whoever prepares it honours the DNP flag**, so check that before ordering rather than
assuming the part is gone.

**B-6 — "Why did `J3` exist on the original Caster design?"**
It is the 16-pin half of Caster's two-connector panel interface. The 50-pin `J6` covers 8- and
16-bit parallel panels; `J3` adds four LVDS pairs plus a clock for MiniLVDS panels and 32/64-bit
modes — the very large or very fast panels Caster was also meant to drive. A 6″–8″ reader panel is
8- or 16-bit, so `J3` would never be populated here. The stronger argument for deleting it:
**no `LOC` line in Caster's `constraint.ucf` assigns any of `J3`'s ten signals**, so it could not
have worked even with a MiniLVDS panel attached (`fpga.md` §2.1).

**B-7 — "`X_VDOUT0_VSYNC` doesn't exist, it's `X_VOUT0_SYNC`."**
You are right, and it was my error in prose, not in the schematic — the netlist uses the module's
real name. Worth one pass over `som.md` §2 to correct the text.

**B-8 — "Why `DPI_xy` labels instead of `data0`–`15`?"**
Because the SoM's DPI pins are named by *colour channel and bit weight* (`X_VOUT0_DATA0` … but
grouped R/G/B), while the FPGA end wants a flat bus. The label carries which colour lane a wire
belongs to so the RGB666 mapping is checkable by eye. Fair criticism though — a flat `DPI_D0..17`
with the colour mapping in a table would read better. Cosmetic, no electrical effect; queued as C-6.

**B-9 — "I don't see the physical connectors the SoM sits on."**
Correct — there is one symbol, `X2`, and it represents **both** Samtec `BTH-060-01-L-D-A-K-TR`
receptacles as a single 240-pin part. That is why its reference is `X`, not `U`. The two physical
connectors appear at layout time, through the footprint — which is the one footprint still missing
(D-4).

## B★. The vendor product page and the TCON manual — added 2026-08-19

The owner found the `GDEP103TC2-FT11` listing on buy-lcd.com and the shipped TCON board manual
(`parts/Display/EN-DEJA-TC103.pdf`). Four things settle out of it.

**B★-1 — The frontlight guess is now confirmed, not inferred.** The listing says
*"Two circuits, 9 LEDs in series per circuit"*, 18 LEDs total, front-light connector 8-pin,
operating voltage 27 V. `frontlight.md` §2 had "18 LEDs, 2 × 9 series" from the product page but
hedged: *"9 LEDs in series is inferred … it could equally be 8 series at 3.4 V."* **Strike the
hedge.** 2 × 9 is confirmed, the `LM3630A`'s 10-series limit keeps one LED of headroom, and the
8-pin front-light connector is `J24` — which is why four of its eight pins are `NC`
(`frontlight.md` §2: `LED1+`, `LED1−`, NC, NC, `LED2+`, `LED2−`, NC, NC). That answers the
"why are half the pins unused" question in `Analysis_Frontlight.md` outright.

**B★-2 — 1404 vs 1400 is deliberate, not a mistake.** The listing says 1404 × 1872; `panel.md` §4
says the same and then pads *down* to 1872×1400 for Caster, because 1872 × 1400 ÷ 128 = 20 475
exactly and 1404 does not divide. The cost is 4 unused lines — 0.45 mm at the 112 µm pitch, 0.28 %
of the height. Already reasoned through; no change.

**B★-3 ⚠ — The touch connector is 2×14, and that is fine, because the GT9110 is not on the panel.**
This is the important one. The listing gives *Touch IC GT9110H, Touch Connector 2×14 pin*, which
looks incompatible with `J22`'s 6 pins. It is not. `EN-DEJA-TC103.pdf` §4.4.2 explains the
topology: *"since the touchscreen uses an external GT9110 touch board"*, and that board presents
**`TOUCH_SDA`, `TOUCH_SCL`, `TOUCH_INT`, `TOUCH_RST`** — four signals plus power and ground.

So the chain is: **panel ITO sensor → 2×14 FFC → external GT9110 touch board → 6-signal I²C →
`J22` on R2.** The 2×14 connector never touches the mainboard; it is between the sensor and its
own controller board. `io-expansion.md` §4's six-signal guess is **right**.

Two things still to confirm, and they are questions for the vendor, not design work:
- Does the GT9110 touch board ship with the panel, or is it a separate order?
- What is *its* output connector — pin count, pitch and **pin order**? `J22`'s order is
  1 `GND`, 2 `VCC`, 3 `RESET`, 4 `INT`, 5 `SDA`, 6 `SCL`. A different order is a reroute, not a
  redesign, but it has to be known before layout.

Also update `io-expansion.md` §4: it cites the **GT911**; this panel uses the **GT9110H**, the
larger-panel variant. Same I²C interface, different part.

**B★-4 — The DEJA-TC103 is not something R2 needs.** The owner suggested putting it on the PCB.
It is an **IT8951-based TCON** — it drives TTL parallel e-paper over SPI or USB from an Arduino or
ESP32. That is the job R2's FPGA already does, and does far better: Caster exists precisely to beat
the latency of controllers like the IT8951. Putting one on R2 would duplicate the display pipeline.

It is still worth keeping, for a different reason: it is a **ready-made way to bench-test the panel
before R2 exists** — power it over USB-C, push an image from a PC, confirm the panel and its
frontlight work. Its reserved 27 V front-light interface makes it a way to check the 2 × 9 string
arrangement on real hardware too. Good for bring-up, not for the BOM.

## C. Queued — real work, not yet done

**Most of C comes from earlier review rounds** (see the scope note at the top). Check the sheet's
own doc before starting any of them — `battery.md`, `mcu.md` and `power.md` already carry review
answers, and the first triage did not account for that.

| # | Item | From | Notes |
| --- | --- | --- | --- |
| ~~C-1~~ | ~~Every `TPS62A02` / `TPS63802` / `TPS22965` / `TPS61022` component-value question~~ | `Analysis_power.md` | **CLOSED 2026-08-20 — it was already done.** Every question in that file has a `power.md` §10.x answer with the datasheet section quoted and the arithmetic shown; see the mapping below. This entry was the "biggest single block of work" in the queue and it was an artefact of the first triage not checking the sheet doc, exactly as the scope note at the top warns. |
| C-2 | Charger questions: `CHG_PSEL` polarity, `TS` behaviour with a non-103AT NTC or none, `CHG_PG` pin 3 on the '892 vs the '890, I²C pull-up placement and which rail, `R_ILIM`/`K_ILIM` arithmetic, what `BATFET` and ship mode are | `Analyse_battery.md` | `battery.md` covers some; the pin-mismatch sweep between BQ25890/2/5/6 is genuinely new and matters for the second-source field. |
| C-3 | `MAX17048`: `CELL` pin not connected, and whether hardware `QSTRT` is wanted | `Analyse_battery.md` | `CELL` unconnected is flagged by the analyzer too (`U2.CELL` single-pin net). Check against the datasheet before assuming it is correct. |
| C-4 | Frontlight: `FL_INT#` appears unconnected; `IN` cap 4.7 µF + 100 nF vs the datasheet's "2.2 µF or greater"; `COUT` 2.2 µF vs the layout example's 1 µF; why half of `J24`'s pins are unused | `Analysis_Frontlight.md` | `FL_INT#` needs checking against the netlist first — `mcu.md` §5 reserved a GPIO with EXTI for it. |
| C-5 | `C42` — "isn't this capacitor one too many?" | `Analysis_mcu.md` | Check against ST Figure 15's per-pin decoupling table. |
| C-6 | `DPI_xy` label scheme, and the `X_VOUT0_SYNC` prose fix | `Analysis_dpi_and_som.md` | Cosmetic. Do it with the `Specter` → `Reflow` rename. |
| C-7 | How to flash and reconfigure the MCU | `Analysis_mcu.md` | Partly written — `mcu.md` §5.7. The honest answer is bound up with D-2. |

### C-1, checked line by line 2026-08-20

`Analysis_power.md` has eleven questions. All eleven are answered, and none of the answers is a
hand-wave — each quotes the datasheet section and shows the arithmetic:

| Question in `Analysis_power.md` | Answered in | Verdict there |
| --- | --- | --- |
| `TPS62A02` `EN` — pulled high by `MCU_EN_FPGA_CORE`, low via the resistor? | `power.md` §10.1 | yes, exactly right — correct as drawn |
| "Write down all layout guidelines, not just for this chip" | §10.2 → §11 | done, one section per converter |
| `R29` vs the typical application's 200 kΩ | §10.3 | you were reading the 1.8 V circuit — correct as drawn |
| `R32`: `VIN` differs for the `VIN` pin and the `PG` pin | §10.4 | yes, and the datasheet says so — correct as drawn |
| `TPS63802` `AGND` and `GND` tied together | §10.5 | **must** be connected; TI deleted the advice to separate them |
| `R3` 470 kΩ where TI draws 100 kΩ | §10.6 | correct as drawn — 0.26 mW of standby, with the `VOL`/leakage/RC margins worked |
| Why `TPS22965` in tandem with `TPS61022` | §10.7 | **it should not be. `U11` deleted** — this question changed the sheet |
| Does `+VSYS` need an input flag | §10.8 | it has one, on `battery.kicad_sch` |
| `TPS61022` `C1` absent, and `C2` 2×22 µF vs the typical 3× | §10.9 | `C1` is `C25`; two output caps are right at our current |
| `VBIAS` = `+VSYS`, the `+VSYS` voltage, the 10:1 `CIN`:`CL` ratio, `C_IN` 22 µF + 100 nF vs 1 µF | §10.10 | 1 µF is a **MIN** column, not a sufficiency claim; `CIN` is the whole node (~42.5 µF), not `C22` |
| Part numbers and the BOM | §10.11–§10.13 | plan written; **executed 2026-08-19**, commit `77469bb` |

Two of those answers were substantive rather than confirmatory — §10.7 deleted a part, and §10.11
changed the inductors' `Value` fields — so the review round earned its keep. **Nothing is owed on
this item.**

## D. Owner decisions — ⏳ means it cannot be taken after fabrication

**D-1 ⏳ — Populate touch?** **Largely resolved by B★-3** — `J22`'s six signals are the right
interface, because the GT9110H sits on its own board, not on the panel flex. What remains is a
*sourcing* question, not a design one: get the GT9110 touch board's output connector pinout from
the vendor and check the pin **order** against `J22` before layout. The decision itself is simply
whether to populate `J22`/`U54` — and since "enter via touchscreen" (B-2) depends on it, the answer
is presumably yes.

**D-2 ✅ — Two SoM GPIO to `MCU_NRST` and `BOOT0`. APPROVED and specified 2026-08-19.**
Pins proposed and reasoned in **`mcu.md` §5.8**: **A59 `X_MCU_MCAN1_TX` → `SOM_MCU_NRST`** and
**A60 `X_MCU_MCAN1_RX` → `SOM_MCU_BOOT0`**, both in `VDDSHV_CANUART` — the same module jumper (J14)
that `SOM_IRQ#`/`SOM_WAKE#` already depend on, so no new dependency — and adjacent to them at
A57/A58, making one contiguous block of four.

Two things came out of specifying it that were not obvious from "just add two GPIO":

- **`NRST` needs an N-FET, not a wire.** The MCU gates the SoM's own supply, so "SoM off, MCU
  alive" is the normal standby state; a direct tie risks an unpowered A59 clamping `MCU_NRST` low
  and holding the MCU in reset forever. An `AO3400A` (already on the BOM as `Q6`) plus a 100 kΩ
  gate pull-down makes it one-way and fail-safe.
- **`BOOT0` is fine as a 1 kΩ series link** — `R40`'s pull-down already defines the safe state, and
  the 1 kΩ doubles as the contention limit against an ST-LINK on the shared `SWCLK` pin.

**Still to confirm, and it decides the factory story:** whether a blank STM32G0 runs its ROM
bootloader regardless of `BOOT0`. If yes, a virgin board needs only an SD card. If no, each board
needs one SWD touch to clear `nBOOT_SEL` first. AN2606 / RM0444, not in the repo.

**DRAWN 2026-08-19**, `tools/patch_som_mcu_recovery.py`: `Q9` `AO3400A`, `R510` 100 kΩ gate
pull-down and `R511` 1 kΩ series on `mcu`; A59/A60 no-connects dropped on `som`; two sheet pins on
each root box. 518 nets before and after, only the intended membership changes. **WP8 closed.**

**And the empty-check question is answered from source.** RM0444 Rev 5 §3.3.1 (p.67): the `EMPTY`
flag "allows easy programming of virgin devices by the boot loader" — a blank part boots System
memory instead of Main Flash, so **a virgin board needs only an SD card, no SWD**. Two riders: the
first programming must be followed by a power cycle or `OBL_LAUNCH` to reload option bytes, or the
part keeps re-entering the bootloader; and the `BOOT0` pin still earns its keep for *recovery*,
where flash is not blank and `EMPTY` is clear.

**D-3 ⏳ — `USB1`, a second USB-C port.** Unused, four pins, already on the connector (B-3). The
owner's position, 2026-08-20: *"I think two USB-C ports is a good thing and should be pursued if
possible."* **Recommendation: do it.** The analysis, so the decision is made on numbers.

**It cannot be retrofitted and it is the cheap half of a port.** `X_USB1_DP`/`DM`/`VBUS`/`DRVVBUS`
are on `X2` today at zero cost; everything else is ordinary parts. What a Type-C *host* port needs,
and what R2 already has:

| Need | Part | Status |
| --- | --- | --- |
| Receptacle | `C165948` `TYPE-C-31-M-12` | **already the BOM line for `J1`** — second unit, no new line |
| ESD on `D±` | `USBLC6-2SC6` `C7519` | **already the BOM line for `U3`** |
| VBUS switch, current-limited | `SY6280AAC` `C55136`, SOT-23-5, adjustable limit, auto-restart, 233 k stock, $0.097 — or `TPS2051BDBVR` `C24593` for a fixed 500 mA at $0.194 | **new**, 1 line |
| Source advertisement | 2 × **56 kΩ** `Rp`, one per `CC` pin, to the switched 5 V | new, 2 passives |
| VBUS bulk + bypass | 10 µF + 100 nF | new, 2 passives |

≈ **$0.60 and one new BOM line.** `DRVVBUS` drives the switch's enable directly — that is what the
pin is for — so the SoM owns when the port is live and there is no standby cost at all: with
`+5V_DCDC` down, the `Rp` resistors have nothing to pull up to.

⚠ **`Rp` is 56 kΩ and not 5.1 kΩ, and getting that backwards is the classic way to build a port
that does nothing.** `J1` has 5.1 kΩ `Rd` on both `CC` pins (`battery.md` §181) because it is a
*sink*. A source presents `Rp` **to VBUS**: 56 kΩ = "Default USB", i.e. 500 mA, which is the right
advertisement for a bus-powered dongle. One resistor per `CC` pin, never bridged — same rule as
`J1`.

**The one number that needs watching is the boost's inductor, not the boost.** `power.md` §8.1
budgets `+5V_DCDC` at 1.3 A worst realistic (SoM design bound 1.0 A + an EPD refresh) against a
1.5 A design point, and `L10`'s `Isat` is 4.8 A against a 3.10 A peak — 55 % of margin. A port
current-limited at 500 mA takes the worst case to 1.8 A and the peak to ≈ 4.0 A, leaving **≈ 20 %**.
That is still margin, and the coincidence it assumes — a 500 mA sink *and* an EPD refresh *and* the
SoM at its design bound, simultaneously — is not a realistic reading state. A keyboard/mouse dongle
is 25–100 mA, not 500. **500 mA is the limit the port advertises, not the load it carries.** If that
20 % is judged too thin, the answer is not to drop the port: it is either to set `SY6280`'s
adjustable limit lower (a resistor) or to re-run `power.md` §3.2 for a higher-`Isat` `L10`.

**What it actually costs is board edge and a case opening, and the sketch says there is room.** The
receptacle is 8.94 mm wide; the SoM takes 32 mm of a ~90 mm top edge (`layout.md` §1.2), leaving
~58 mm for two of them.

**Two things worth saying against it, neither decisive:**

1. **Two identical-looking C ports that behave differently is a usability trap.** Only `J1`
   charges — the charger's `VBUS` input is on `J1` alone, and ORing a second inlet is not worth it.
   Mark them, or accept that users will try the wrong one.
2. **Most legacy dongles are USB-A**, so a C-to-A adapter is in the loop. USB-A would avoid that but
   its receptacle is 14.5 × 5.7 mm against C's 8.94 × 3.26 — real thickness in a device whose panel
   is 1.93 mm. **C is right**; the adapter is the buyer's problem, and C hubs and dongles are now
   ordinary.

**The alternative that does not need `USB1` was checked and is worse.** `J1` could in principle be
dual-role: `CHG_OTG` is already declared and wired to `PB3`, and the `BQ25892` boosts `VBUS` in OTG
mode. But it needs *more* parts than `USB1`, not fewer — a DRP `CC` controller to swap `Rd` for
`Rp`, plus `C2` on `PMID` raised from its 8.2 µF no-OTG value (`battery.md` §312) — and it makes
hosting and charging mutually exclusive, which is exactly when someone wants both.

**The asymmetry is the argument.** Fitting the port and never using it costs $0.60 and a connector.
Not fitting it and later wanting a keyboard costs a respin. *(Raised in `Analyse_battery.md`, an
earlier round, not WP6–8 — but still open and still has a fabrication deadline.)*

**D-4 ✅ — The `X2` footprint. BUILT and then RESTRUCTURED, 2026-08-20.**

Built first as one 240-pad footprint from PHYTEC's own DXF, which is vector and numeric where
`L-1038e.A5` Figure 7 is a raster picture. It agreed with a Figure-7-derived first attempt to 8 µm
in x and **61 µm in y** — worth correcting, since 61 µm is 20 % of a 0.305 mm pad's width. Two traps
found on the way, both in `som.md` §11:

- **"Row spacing 1.986" was wrong** — 1.986 mm is the end pad to alignment hole offset *along* the
  row. Row-to-row is **6.172 mm**.
- **The alignment hole is not on the connector's centreline** (1.054 mm from one row, 5.118 from the
  other), and the DXF's own four holes are the **plug's**, not ours. Trusting them would have put
  both connectors 0.62 mm out.

Then **restructured at the owner's decision** into two connector symbols and three footprints —
`BTH-060-01-L-D-A-K_AB`, `..._CD` and `PCM-071_Module`. `som.md` §10 has the whole argument; the
short version is that one 240-pad footprint could not be assembled, because a position file has one
row per reference and there is no single part covering 240 pads.

Verified by an exact acceptance test: the netlist is **identical except every `X2.<pin>` became
`J26.<pin>` or `J27.<pin>`** — 517 nets, 270 named nets with identical membership, 247 unconnected
pins. ERC unchanged at 32.

⚠ **`C3646540` had 60 in stock — 30 boards.** The tightest line on the BOM.

**D-5 ✅ — SoM position and side. FULLY CLOSED by the owner 2026-08-20.** Top right beside the USB
ports, on the face pointing **away from the panel**. `layout.md` §1.1, with the rest of the layout
sketch in §1.2. The USB 2.0 high-speed pair is why that position is right and not merely a
preference; the panel sitting directly over the board is why that side is.

**D-6 ✅ — `U41` speed grade. ANSWERED by the owner 2026-08-20: `-2`.** And on investigation it
was never really a choice — full write-up in `fpga.md` §1.1:

- **LCSC has no `-3` in FTG256 at all.** Every FTG256 option is `-2` (`C39313`, 2 058 in stock,
  $7.79; `C415800` industrial, 431). The only `-3` on the catalogue is CSG324 — a different package
  with a different ball map, i.e. a redesign.
- **Nobody ever chose `-3`.** In `caster.xise` the device and package are marked
  `valueState="non-default"`, but every speed-grade property is `valueState="default"` — ISE's
  untouched built-in value, carried into `ise_flow.sh`'s command line.
- ⚠ **But `-2` runs the DDR3 at exactly its rated ceiling.** `ds162.pdf` Table 25 gives the MCB's
  DDR3 maximum as 800 Mb/s on `-3` and **667 Mb/s on `-2`**; Caster's MIG is generated for
  `C3_MEMCLK_PERIOD = 3000` ps = **666.67 Mb/s**. That is **0.05 % of margin**.

**One thing to do before the fab order, and it is free.** Retarget `par/ise_flow.sh` (two lines,
`-ftg256-3` → `-ftg256-2`) and build on the ISE VM. The MCB is a hard macro and will not fail
timing the way fabric does — the numbers to read are `TS_CLK33` and the 165 MHz `DPI_PCLK` path,
because a `-2` part is roughly 10–15 % slower in the fabric. Two fallbacks exist if it does not
close and neither is a respin: drop `DPI_PCLK` (§16 shows the panel needs far less), or lengthen
`C3_MEMCLK_PERIOD`.

**D-7 ✅ — Separate PCB for the panel connector? CLOSED 2026-08-20: no.** The owner: *"the TTL
interface is just the flex cable that is bent under the display and that's about where it lands on
the PCB, so the connector can be fit accordingly."* The block on the sketch was never a board — it
is a **landing zone**, which is a more useful thing to have.

So `J6` is fixed in **position and orientation**, not just enclosure-fixed. `J22`/`J23` (touch, pen)
are the same — the owner confirms touch is also a folded flex. A horizontal FPC connector facing the
wrong way puts a 180° loop in a 0.5 mm flex, which is a reliability problem rather than a routing
one, so orientation is worth deciding before placement rather than during. `layout.md` §1.2.

None of the high-voltage worry in the previous version of this entry applies: `+VP`, `+VGH`,
`-VCOM`, `-VGL` and `-VN` never leave the mainboard.

**D-8 — Panel supplier silence.** Noted, no action available from here. Bench measurement when the
panel arrives is the fallback, as you say.

---

## Sourcing fix: `R88` / `R224`, the 390 kΩ

`C25782` (`0402WGF3903TCE`) has **14 units** at LCSC and the board needs two per unit. `R224` is not
a part that can be substituted loosely — `epd-port.md` §10.2 puts it in the `VGH` feedback divider,
`VGH = 1.2 × (1 + 390/18.033)`, so it must stay 390 kΩ ±1 % in 0402.

Two candidates were checked against LCSC's parametric table rather than by name, which matters here:

| Code | Part | Package | Actual value | Stock | Verdict |
| --- | --- | --- | --- | --- | --- |
| `C23150` | `0603WAF3903T5E` | **0603** | 390 kΩ ±1 % | **16** | ✗ wrong package, and less stock than we have |
| `C44937` | `0402WGF390K TCE` | 0402 | **3.9 Ω** ‼ | 25 397 | ✗ the `390K` in the name is not 390 kΩ |
| `C2909352` | `FRC0402F3903TS` | 0402 | 390 kΩ ±1 %, 62.5 mW, 50 V | 40 540 | ✓ would have worked |
| **`C54920667`** | **`HRC0402F3903DNTO`** | 0402 | **390 kΩ ±1 %** | **20 000** | ✓ **fitted — this is what is on the board** |

**Superseded 2026-08-19** — `C54920667` was fitted instead, and `epd-port.md` §10 records it.
`C2909352` is a fine second source. Leaving both here because the *reasoning* is the durable part:

`C44937` is the same trap as the five capacitors: a part number that reads like the value it is not.
FOJAN is already a supplier on this board (`FRL0805FR020TS`, the 20 mΩ shunts). $0.0196 against
$0.0019 is ten times the price and four cents a board — irrelevant.

## Running `/ultrareview` on this branch

The raw branch diff is 25 727 lines against a limit of 8 000. `.gitattributes` (commit `e9ead0f`)
already cut it from 2 053 615, and the rest has to be sliced. Four branches exist for that; the
`review-*` branches have **exactly the same tree as `Board-Design`**, so switching to one changes
nothing on disk and is safe with KiCad open.

| To review | Command | Size |
| --- | --- | --- |
| The sheet specs — the engineering reasoning | `git switch review-docs` then `/ultrareview review-base-docs` | 5 947 lines |
| The `NOTES-*` planning and evidence files | `git switch review-notes` then `/ultrareview review-base-notes` | 1 802 lines |

Then `git switch Board-Design` to come back. The branches can be deleted any time with
`git branch -D review-docs review-base-docs review-notes review-base-notes`.
