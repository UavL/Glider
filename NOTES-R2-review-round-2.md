# R2 review round 2 — the owner's WP6–8 notes, triaged

Source: `pcb/r2-mainboard/manual-analysis/*.md`, written 2026-08-10 … 2026-08-19.
Triaged 2026-08-19. Roughly fifty questions across seven sheets.

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

| # | Change | Sheet | Source |
| --- | --- | --- | --- |
| 1 | `R225` 22 kΩ → **20.5 kΩ** — the one value the `GDEP103TC2` forces | `epd_power` | `epd-port.md` §10.3 |
| 2 | Five sense-divider caps carry LCSC codes for the wrong value (`C91`, `C163`, `C164`, `C168`, `C169`) | `power_mon` | `NOTES-R2-plan.md`, commit `77469bb` |
| 3 | `+5V2_FL` is orphaned — `J6.7`, `J6.44`, `C147` and no source | `epd` | commit `564cc48` |
| 4 | Ten duplicate `#PWR` references | `fpga_*` | `fpga.md` §9.5 |
| 5 | `J3` deletion — **you approved this in `Analysis_fpga.md`** | `epd` | `epd-port.md` §9.3 |
| 6 | `Specter` → `Reflow` rename, 13 title blocks + the generators | all | naming |

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

## C. Queued — real work, not yet done

| # | Item | From | Notes |
| --- | --- | --- | --- |
| C-1 | Every `TPS62A02` / `TPS63802` / `TPS22965` / `TPS61022` component-value question — `R29` vs the datasheet's 200 k, `R3` 470 k vs 100 k, `C_IN` 22 µF + 100 nF vs the app note's 1 µF, `C2` 2×22 µF vs the typical 3×, `C1` omission, `AGND`/`GND` tie, `R32`'s two different `VIN`s | `Analysis_power.md` | Each needs the datasheet section quoted and the arithmetic shown. `power.md` §3.1 already does this for the feedback dividers; extend the same treatment. **Biggest single block of work.** |
| C-2 | Charger questions: `CHG_PSEL` polarity, `TS` behaviour with a non-103AT NTC or none, `CHG_PG` pin 3 on the '892 vs the '890, I²C pull-up placement and which rail, `R_ILIM`/`K_ILIM` arithmetic, what `BATFET` and ship mode are | `Analyse_battery.md` | `battery.md` covers some; the pin-mismatch sweep between BQ25890/2/5/6 is genuinely new and matters for the second-source field. |
| C-3 | `MAX17048`: `CELL` pin not connected, and whether hardware `QSTRT` is wanted | `Analyse_battery.md` | `CELL` unconnected is flagged by the analyzer too (`U2.CELL` single-pin net). Check against the datasheet before assuming it is correct. |
| C-4 | Frontlight: `FL_INT#` appears unconnected; `IN` cap 4.7 µF + 100 nF vs the datasheet's "2.2 µF or greater"; `COUT` 2.2 µF vs the layout example's 1 µF; why half of `J24`'s pins are unused | `Analysis_Frontlight.md` | `FL_INT#` needs checking against the netlist first — `mcu.md` §5 reserved a GPIO with EXTI for it. |
| C-5 | `C42` — "isn't this capacitor one too many?" | `Analysis_mcu.md` | Check against ST Figure 15's per-pin decoupling table. |
| C-6 | `DPI_xy` label scheme, and the `X_VOUT0_SYNC` prose fix | `Analysis_dpi_and_som.md` | Cosmetic. Do it with the `Specter` → `Reflow` rename. |
| C-7 | How to flash and reconfigure the MCU | `Analysis_mcu.md` | Partly written — `mcu.md` §5.7. The honest answer is bound up with D-2. |

## D. Owner decisions — ⏳ means it cannot be taken after fabrication

**D-1 ⏳ — Populate touch?** You bought a panel with a touch layer and the GT911 datasheet is now in
`parts/Display/`. `io_expansion` was drawn for exactly this and is entirely DNP: `J22`, `U54`, and
their passives. Populating is a stuffing change, **not** a board change — *provided* `J22`'s 6-pin
pinout matches your specific panel's flex. `io-expansion.md` §4 calls that pinout "the only guess on
this sheet". **Check the flex against `J22` before fab.** If it disagrees, the connector has to
change, and that is a board change. This also decides B-2: "enter via touchscreen" needs touch.

**D-2 ⏳ — Two SoM GPIO to `MCU_NRST` and `BOOT0`.** Still the sharpest deadline. Today SWD via
`J20` is the only way into the MCU and it needs the case open. The factory USART bootloader is
already on the right pins (`PA9`/`PA10`, with the SoM on the far end), so two GPIO turn a
case-opening operation into a firmware update. Free now, impossible after fabrication.
`mcu.md` §5.7, WP8.

**D-3 ⏳ — `USB1`.** Unused, four pins, already on the connector (B-3). Second port or not.

**D-4 — The `X2` footprint.** `footprints:PCM-071_2xBTH-060-01-L-D-A-K` does not exist. The Samtec
drawings are committed and give what a generator needs: 0.5 mm pitch, pad 1.448 × 0.305, row
spacing 1.986, and the `-A` option's 1.016 mm NPTH holes. **The last footprint gap, and it blocks
Stage D.** Offered; say the word.

**D-5 — SoM position and side.** The only other Stage D blocker.

**D-6 — `U41` speed grade.** LCSC `C39313` is `XC6SLX16-**2**FTG256C`; `fpga.md` §2 specifies
`-**3**`, verified against `caster.xise`. One of the two is wrong and Caster's timing closure
depends on which.

**D-7 — Separate PCB for the panel connector?** From `Analysis_epd_files.md`. Modos put the display
connector on its own small board. Real trade-off: a separate board allows several panel sizes off
one mainboard and keeps the 0.5 mm FPC away from the main assembly, at the cost of a second PCB,
a board-to-board connector and its assembly. **Architectural — decide before layout, not during.**

**D-8 — Panel supplier silence.** Noted, no action available from here. Bench measurement when the
panel arrives is the fallback, as you say.
