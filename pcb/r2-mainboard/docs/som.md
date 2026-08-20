# `som`, `dpi_in` — the PCM-071 module — R2 work packages 7 and 8

Status: **drawn 2026-08-15 — `som.kicad_sch` and `dpi_in.kicad_sch` both exist, and the
hierarchy has no dangling interfaces left.** Not yet reviewed by the owner. Companion to `power.md`, `mcu.md`, `fpga.md` and
`epd-port.md`.

The module is a **`PCM-071`** — the connectorised phyCORE-AM62x, chosen over the solder-down
`PCL-071` on 2026-08-13 for cost, MOQ and the ability to unplug it. Its 240 pins arrive on **one
logical connector `X2`**, in four columns `A`–`D`, across **two Samtec `BTH-060-01-L-D-A-K-TR`**
board-side parts (module side: `BSH-060-01-L-D-A-TR`).

**The binding document is `datasheets/L-1038e.A5_phyCORE-AM62x_HW Manual.pdf`.** As with the FPGA,
the acceptance criterion is not "does it look right" — a wrong pin on a 240-pin module is a dead
board that ERC calls perfectly legal. `tools/parse_som_pinout.py` extracts Tables 7–10 into
`datasheets/som_pinout.json` (240 pins, 177 distinct AM62x balls, verified 60-per-column with no
ball claimed twice), and `check_pinout.py` will assert the schematic against it the way
`check_ucf.py` does for the gateware.

> **Key on pin numbers, never on PHYTEC's signal names.** The manual contradicts itself twice:
> `A5` is `X_VOUT0_VSYNC` in Table 7 and `X_VOUT0_SYNC` in Table 31; `A15` is `X_VOUT0_DE` and
> `X_VOUT_DE`. The pin numbers agree in both places.

---

## 1. What R2 uses, and what it leaves alone

Of 240 pins, R2 connects a minority. 45 are ground and 4 are supply; of the remaining 191 signal
pins the design uses **about 40**.

| Group | Pins | Sheet | §|
| --- | ---: | --- | --- |
| `VIN` ×3, `VBAT`, `GND` ×45 | 49 | `som` | §3 |
| DPI / `VOUT0` — 18 data + `PCLK`/`DE`/`HSYNC`/`VSYNC` | 22 | `dpi_in` | §2 |
| microSD on `MMC1` + `SoC_VDDSHV5_SDIO` | 9 | `som` | §4 |
| CSR SPI to the FPGA + NOR chip select (`SPI0`) | 5 | `som` | §5 |
| UART to the MCU (`UART0`) | 2 | `som` | §5 |
| Reset, power-good, wake (`X_nRESET_IN`, `X_PGOOD`, GPIO) | 4 | `som` | §5 |
| USB 2.0 to `J1` (`USB0`) | 2–4 | `som` | §5 |
| **everything else** — OLDI, CSI, RGMII ×2, MDIO, MCASP, MCAN ×2, `MMC2`, most of GPMC, ECAP/EPWM/EQEP, JTAG | ~150 | `som` | no-connect |

Nothing here is Ethernet, and that matters beyond the pin count: the module carries **two Gigabit
PHYs Glider never uses**, and they are the only identified headroom against the 128.6 mW
Suspend-to-RAM figure that now dominates the reading budget.

## 2. The DPI link, and the two pins that are also boot straps

18-bit RGB666. AM62x TRM Figure 12-471: 18-bit mode drives `DATA[17:0]` only, packed
`data[17:12]` = red, `data[11:6]` = green, `data[5:0]` = blue. Caster's UCF maps the same 18 to
`DPI_PIXEL[17:0]` with a comment column naming them `R2..R7 G2..G7 B2..B7`, so the two ends agree.

`L-1038e.A5` Table 31 gives the pin map. `DATA0`–`DATA15` are on columns **A and B**;
`DATA16`/`DATA17` are on column **D**, and they are not video pins by default:

| Caster | AM62x | `X2` | SOM signal |
| --- | --- | --- | --- |
| `DPI_R7` | `VOUT0_DATA17` | **D4** | `X_GPMC0_AD9/BOOTMODE_9` — 100 kΩ **pullup** on SOM |
| `DPI_R6` | `VOUT0_DATA16` | **D2** | `X_GPMC0_AD8/BOOTMODE_8` — 100 kΩ **pullup** on SOM |

`BOOTMODE[9:3]` is the **primary boot mode selection** (Table 17). Two consequences:

1. **Nothing on our board may load `DPI_R6` or `DPI_R7`.** No pull-up, no pull-down, no series
   termination. PHYTEC's own scale for *deliberately* overriding a strap is a 1 kΩ pull-up or 10 kΩ
   pull-down against their 100 kΩ, so ordinary routing is not a threat — a "helpful" resistor is.
2. **`+3V3` must be up before `X_PORz_OUT` goes high**, because an FPGA with `VCCO` off clamps its
   inputs through the ESD structure and a forward-biased diode beats a 100 kΩ pull-up. This is a
   rail-order requirement and it interacts with a *mandatory* rule pointing the other way;
   `power.md` §5.1 has the resolved five-step sequence.

**Because the DPI group spans columns A, B and D, `dpi_in` and `som` share one physical part.**
That is the same shape as the FPGA's six units across three sheets, and it is why the symbol is
split by function rather than by the manual's four columns (§7).

**All 22 signals are 3.3 V by default.** Table 6: `VOUT0_DATA0..15`, `PCLK`, `DE`, `VSYNC`, `HSYNC`
and every `GPMC0_AD*` sit in voltage domain **`VDDSHV3`**, solder jumper `J4`, default 3.3 V —
matching the FPGA's `+3V3` `VCCO`. Verified, not assumed; the module can be ordered with that
domain at 1.8 V and then nothing would work.

## 3. Power

| Rail | `X2` | Direction | Figure | Source |
| --- | --- | --- | --- | --- |
| `VIN` | **A1, A2, A3** | in | 5 V ±5 % recommended (Table 4 allows 4.5–5.5), **1 A** | §5.1, Table 12 |
| `VBAT` | **B2** | in | 1.2–5.5 V, **40 nA** for the RTC | Table 4, Table 12 |
| `SoC_VDDSHV5_SDIO` | **B1** | **out** | delivers 0.33 W (100 mA) at 3.3 V or 1.8 V per `VSEL_SD` | Table 12 |
| `GND` | 45 pins, listed in Table 12 | — | — | — |

"Connect **all** available 5 V input pins" and "all ground pins to ground" (§4.6) — all three `VIN`
and all 45 grounds, no exceptions. The `+5V` budget is checked in `power.md` §8.1 and holds: 1.0 A
for the module plus an EPD refresh is ≈ 1.3 A against the 1.5 A `L10` was sized for.

**`VBAT` is an open decision, deliberately left to review.** 40 nA is nothing, but it is the RTC's
keep-alive when everything else is off, and there are three options: tie it to `+3V3_AON` (the RTC
then dies with the main cell, which for a reader is arguably correct), fit a coin cell or
supercapacitor, or leave it unconnected and let the RTC lose time on every full discharge. The
first costs nothing and is the default unless the reviewer disagrees.

## 4. The microSD — added 2026-08-15 at the owner's request

**PHYTEC recommend exactly this**, in §4.6's minimum requirements: *"The phyCORE-AM62x SOM provides
an on-board eMMC, but it is recommended to support another boot source for development and
debugging. PHYTEC suggests SD boot."* Figure 22 is their reference circuit for it, on `MMC1`.

It is also the answer to a question that had been open since WP7 opened — **which boot device R2
uses.** Table 17's defaults, as strapped on the module:

| Field | Default | Meaning |
| --- | --- | --- |
| `BOOTMODE[9:3]` primary | `0XX_1001` | **eMMC boot** |
| `BOOTMODE[13:10]` backup | `1101` | **MMC1** |
| `BOOTMODE[2:0]` PLL ref | `011` | 25 MHz |

The manual states it in words: *"the default configuration on the SOM … is to boot from eMMC with
SD card as a backup."* **So R2 changes no straps at all.** Fitting a microSD on `MMC1` gives
eMMC-primary with SD-card-fallback for free — which is precisely what bring-up wants — and it means
we keep relying on the module's own pull-ups, which is why §2's "nothing may load `DPI_R6/R7`" rule
is load-bearing rather than cautionary.

### 4.1 The circuit

`J21` = `MICRO_SD(TFC-WPAPR-08)`, footprint `footprints:TFC-WPAPR-08` — **already in
`pcb_common`, and the same socket R1 fits as `J7`.** No new symbol, no new footprint, no new
supplier.

| Socket | Net | `X2` | Notes |
| --- | --- | --- | --- |
| `CLK/SCLK` | `SD_CLK` | **D26** | 49.9 kΩ pulldown on SOM |
| `CMD/DI` | `SD_CMD` | **D25** | |
| `DAT0/DO` | `SD_DAT0` | **C25** | |
| `DAT1/RES` | `SD_DAT1` | **C26** | |
| `DAT2/RES` | `SD_DAT2` | **D28** | |
| `CD/DAT3/CS` | `SD_DAT3` | **D29** | |
| card-detect switch | `SD_CD#` | **C23** | `X_MMC1_SDCD`, 10 kΩ pullup on SOM — the switch only has to close to ground |
| `VDD` | `+3V3_SDIO` | **B1** | see below |
| `VSS`, shell | `GND` | — | |
| — | *(not connected)* | C22 | `X_MMC1_SDWP`. **microSD has no write-protect switch** — that is a full-size-SD feature. The SOM's 10 kΩ pullup defines it as "not protected" |

**The card is powered from the module, not from `+3V3`.** `SoC_VDDSHV5_SDIO` (B1) is an *output*
that "delivers 0.33 W (100 mA)", and its level tracks `VSEL_SD`. Three things fall out, and all
three are why this is the right rail:

- The card rail follows the SoM's own SDIO I/O domain, so a future move to 1.8 V UHS is a software
  change rather than a respin. Running the card from a fixed `+3V3` while the SoM switched its I/O
  to 1.8 V would be a level clash.
- It is only alive when the module is alive, so the card cannot be back-powered through its I/O
  when the SoM is off, and it costs nothing in standby.
- `power.md`'s rail-tree row for `+3V3_DCDC` used to list "microSD" as a load. **It is not one**,
  and that row has been corrected.

Pull-ups per PHYTEC's Figure 22 ("an SD-card reader with CMD/DATA line pullups"): **47 kΩ on `CMD`
and `DAT0`–`DAT3`, to `+3V3_SDIO`** — referenced to the card's own rail so they track the
1.8 V/3.3 V switch rather than fighting it. Five resistors. Decoupling at the socket: 10 µF + 100 nF,
which matters more than usual because the 100 mA ceiling is a real one and a card's write burst is
the load that finds it.

**No load switch, and PHYTEC's Figure 23 shows one — so this is a deliberate deviation.** Its
purpose is to power-cycle a wedged card, which the SD specification does require as the only reset
of last resort. We can do that by cycling the whole module (`MCU_EN_5V`), which is heavier but needs
no part and no GPIO, and `SoC_VDDSHV5_SDIO` dies with the module anyway. **Two consequences to put
in front of the reviewer rather than bury:**

1. If the card is meant as a *user* feature (sideloading books) rather than a dev/boot aid, it stays
   fitted for the product's life, and **whether `SoC_VDDSHV5_SDIO` stays energised during
   Suspend-to-RAM is unknown to me** — the manual does not say and I cannot measure it. A microSD's
   standby is a few hundred µA, so ~1 mW against a 128.6 mW module: small, but it is the reading
   state, which is the one number R2 exists to reduce. A load switch would settle it. **Needs a
   hardware test on the dev kit.**
2. Power-cycling the card means power-cycling Linux. Fine for a boot device, irritating for storage.

Layout: Table 16 asks for the MMC signals length-matched within **12 700 µm** — 12.7 mm, which is
generous and will not constrain placement. §8.

## 5. Control and housekeeping

All of these are on voltage domain **`VDDSHV0`** (jumper `J1`, default 3.3 V) unless noted —
`SPI0_*`, `UART0_*`, `I2C*`, `PORZ_OUT`, `RESET_REQZ`, `RESETSTATZ`, `MMC1_SDCD` are named in
Table 6's `VDDSHV0` row.

| R2 net | `X2` | SOM signal | Purpose |
| --- | --- | --- | --- |
| `FPGA_SCLK` | D40 | `X_SPI0_CLK` | CSR SPI, SoM is master (`mcu.md` §2.1) |
| `FPGA_MOSI` | D41 | `X_SPI0_D0` | |
| `FPGA_MISO` | D42 | `X_SPI0_D1` | |
| `FPGA_CS` | C40 | `X_SPI0_CS0` | to the FPGA |
| `NOR_CS` | C41 | `X_SPI0_CS1` | to the config NOR, for SoM-side bitstream writes |
| `MCU_TXD` | D37 | `X_UART0_RXD` | **named from the MCU's side** — `mcu.md` §10 |
| `MCU_RXD` | D38 | `X_UART0_TXD` | |
| `SOM_RESET#` | C52 | `X_nRESET_IN` | cold reset; 10 kΩ + 100 nF on SOM, so no parts our side |
| `PG_SOM` | C54 | `X_PGOOD` | **new, `power.md` §5.1** — open-drain out; gates `+3V3` |
| `SOM_IRQ#` | **A57** | `X_MCU_MCAN0_TX` = `MCU_GPIO0_13` | MCU → SoM attention |
| `SOM_WAKE#` | **A58** | `X_MCU_MCAN0_RX` = `MCU_GPIO0_14` | MCU → SoM wake from Deep Sleep |
| `SOM_MCU_NRST` | **A59** | `X_MCU_MCAN1_TX` | SoM → MCU reset, through `Q9` on `mcu`. `mcu.md` §5.8 |
| `SOM_MCU_BOOT0` | **A60** | `X_MCU_MCAN1_RX` | SoM → MCU boot select, through `R511` 1 kΩ. `mcu.md` §5.8 |
| `USB_DP` / `USB_DM` | A39 / A38 | `X_USB0_DP` / `X_USB0_DM` | from `J1` on `battery` |

### 5.1 How `SOM_WAKE#` and `SOM_IRQ#` were chosen

**PHYTEC's manual never uses the word "wake".** It is not in the document, so the pin could not be
looked up there; the answer came from TI's AM62x datasheet (`SPRSP58C`) instead.

`som_pinout.json` gives every `X2` pin's AM62x ball. Cross-referencing those against the
datasheet's pin-multiplexing table — which signal each ball presents in mux mode 7 — shows that
**exactly 22 `X2` pins reach an `MCU_GPIO0_*`**, i.e. a GPIO in the **MCU always-on domain**, the
domain that stays powered through DeepSleep. The other ~170 signal pins are MAIN-domain and could
not wake the module whatever firmware did.

Among those 22 the choice is easy: `X_MCU_MCAN0_TX`/`RX` (A57/A58) are **CAN**, which a reader can
never want, and they are adjacent so the two housekeeping lines stay together. `X_MCU_UART0_*` and
`X_WKUP_UART0_*` were rejected as likely debug consoles, and `X_MCU_SPI0_*`/`I2C0_*` because a
future need for them is more plausible than for CAN.

Supporting, though not conclusive: the datasheet's feature list names *"Partial IO support for
**CAN**/GPIO/UART wakeup"*, so these pins are wake-capable in at least one low-power mode.

> ⚠ **Confirm at bring-up.** "Partial IO" is a *different* mode from DeepSleep, and PHYTEC
> demonstrated GPIO wake from Suspend-to-RAM without naming the pin. So the domain is proven and
> the specific pin is not. If `MCU_GPIO0_14` turns out not to be a DeepSleep wake source, moving to
> another of the 22 is a one-net edit — which is precisely why the choice was made from that set
> rather than from a MAIN-domain pin that certainly could not work. `MCU_MCAN1_TX`/`RX` (A59/A60)
> are the obvious next candidates and are on the same unit of the symbol.

**`X_PMIC_EN` (C51) is left unconnected.** It has a 100 kΩ pullup to 5 V on the module, so the
module starts whenever `VIN` does, and `MCU_EN_5V` is already our on/off. It would be a second,
faster kill path — worth a test pad, not a net — and the reason we do not need it is that
`TPS61022` has true output disconnect in shutdown (`power.md` §2.2), so `+5V_SOM` really does
collapse.

**BOOTMODE override pads are worth considering and are not drawn.** `BOOTMODE_10`–`15` are
`VOUT0_DATA18`–`DATA23` (`X2` D5, D6, D7, D8, D10, D11), which 18-bit mode does not use, so
unpopulated 1 kΩ/10 kΩ strap pads there would let bring-up change the *backup* boot mode — to UART
or USB device mode — without going anywhere near `DPI_R6`/`R7`. PHYTEC suggest a DIP switch for
this (§6.3); a DIP switch on `BOOTMODE_8/9` would violate §2's rule, but on 10–15 it is safe.

## 6. Sheet split

| Sheet | Contents |
| --- | --- |
| `dpi_in` | The 22 DPI signals, enumerated from `som_pinout.json` rather than described as a range: **A5 A6 A7 A8 A10 A11 A12 A13 A15 A16** (10), **B4 B5 B6 B7 B9 B10 B11 B12 B14 B15** (10), **D2 D4** (2). The gaps in each run are grounds |
| `som` | Power, ground, microSD, SPI, UART, USB, reset/PG, and every unused pin's no-connect flag |

## 7. Symbol — units by function, not by column

The manual's four columns are a *physical* division (two connectors, two columns each); the
schematic needs a *functional* one, because the DPI group alone spans A, B and D. So the symbol is
one 240-pin `PCM-071` in units:

| Unit | Name | Contents | Pins | Sheet |
| --- | --- | --- | ---: | --- |
| 1 | `POWER` | `VIN` ×3, `VBAT`, `SoC_VDDSHV5_SDIO`, `GND` ×45 | **50** | `som` |
| 2 | `VIDEO` | DPI / `VOUT0`, including D2/D4 | **22** | `dpi_in` |
| 3 | `CTRL` | `SPI0`, `UART0`, `MMC1`, `USB0`, I²C, reset/status, plus the `MCU_*`/`WKUP_*` always-on groups `SOM_WAKE#` will have to come from | **49** | `som` |
| 4 | `NC` | everything R2 does not use | **119** | `som` |

Unit 3 deliberately carries more than R2 wires: the `WKUP_UART0`, `MCU_UART0`, `MCU_SPI0`,
`MCU_I2C0` and `WKUP_I2C0` groups are the always-on domain, and `SOM_WAKE#` (§9 item 1) will have
to land in one of them. Keeping them on the sheet that gets wired means resolving that is an edit,
not a unit reshuffle.

**One symbol and one footprint, not two of each.** The two `BTH-060` connectors have a fixed
relative position set by the module, so drawing them as two independent parts would let a layout
move one and destroy the board with no DRC complaint. A single footprint carrying both patterns
makes that geometry unbreakable. `gen_som_symbol.py` builds the symbol from
`datasheets/som_pinout.json`, so the pin names and numbers come from the manual rather than from
typing. It asserts every one of the 240 numbers appears exactly once, and refuses to run if the
manual uses a signal Type it has no KiCad electrical type for.

**A `pdftotext` artifact worth knowing about, because it is visible in the symbol.** The manual's
superscript footnote markers flatten into the text, so a row's last field can arrive with a digit
glued on: `X_GPMC0_AD8/BOOTMODE_8`**`2`**, `3.3V`**`1`**, `X_EMU0`**`3`**. The parser strips them
only where a rule proves it — the `BOOTMODE` number must equal the `AD` number, so anything past it
is the footnote and a genuine mismatch raises instead of truncating; levels match
`^\d+(\.\d+)?V[123]$`; and `X_EMU0`/`X_VPP_EN` are cited to Table 5's jumper rows `J16`/`J17`,
which name them without a suffix. **Names are cosmetic. The pin number is what the board's
correctness rests on**, and pin numbers carry no footnotes.

## 8. Layout guidelines — collected now, for Stage D

- **MMC1**: length-match within **12 700 µm** (Table 16). Generous; will not constrain placement.
- **USB0**: Table 29 gives the USB layout characteristics — read before routing `J1` to A38/A39.
- **DPI**: 22 signals from `X2` columns A/B/D to FPGA bank 1. `DPI_PCLK` is the only one with a
  frequency constraint (165 MHz in the UCF, ~101 MP/s actual at 1448×1072@60). Keep it over a
  continuous reference plane and away from the EPD source bus.
- **`DPI_R6`/`DPI_R7` carry no components at all** (§2). Worth a note on the sheet so a later
  reviewer does not "fix" the missing termination.
- **All three `VIN` pins and all 45 grounds connected** (§4.6), with the module's 1 A in mind for
  the copper.
- PHYTEC's general advice, §5's preamble: high-speed interfaces placed and routed first, every
  interface over a solid reference plane, clearance ≥ 3 × trace width to limit crosstalk.

## 9. Open

1. ~~**`SOM_WAKE#`'s module pin is unknown**~~ **Chosen 2026-08-15 — A58, `MCU_GPIO0_14`** (§5.1).
   The always-on domain is proven from TI's datasheet; the specific pin still wants a bring-up
   test.
2. ~~**`SOM_IRQ#`'s pin is unchosen**~~ **Chosen — A57, `MCU_GPIO0_13`** (§5.1).
3. **`VBAT`'s source is a review decision** (§3).
4. **Whether `SoC_VDDSHV5_SDIO` stays energised in Suspend-to-RAM** (§4.1) — needs a hardware test.
5. ~~**`PG_SOM` is owed to `mcu.kicad_sch`**~~ **Done — `tools/patch_mcu_pg_som.py` claims
   `PC8`.** ⚠ **Firmware must now *disable* the internal pull-down** — it fights the module's
   100 kΩ pull-up and reads 0.94 V against a 2.31 V threshold, so bring-up would hang. `R512`
   1 MΩ on `mcu` does the biasing instead; `mcu.md` §5.9.
6. **`check_pinout.py` does not exist yet.** `parse_som_pinout.py` is its data source and is done.
7. ~~**The `PCM-071` has never been priced**~~ **Priced 2026-08-18 — €250.00 @ 1–9 pcs**,
   variant `PCM-071-5432DE11I`, PHYTEC order code `C618992`, **MOQ 1**. Lead time not stated.

   This retires the workaround recorded here — buying a `phyBOARD-AM62x` kit (`KPB-07124`, $349)
   *purely because its module unplugs*. The bare module is now cheaper and orderable singly.
   **The owner is buying the Lyra kit anyway, on its own merits** (decided 2026-08-18): it adds a
   working carrier for ~€70 more, and every module-level power and latency figure this design rests
   on (Facts §4.6 — 128.6 mW, ~150 ms) was measured *by PHYTEC on their carrier*, not here. It also
   gives the BSP and the provisioning flow (§10) somewhere to run before R2 exists.

## 10. The two receptacles — how they get bought AND soldered

Found 2026-08-20 while building the footprint, and it is the kind of gap that is only visible from
the assembly side.

`X2` is **one symbol for the module**. The BOM it generates has one line, `PCM-071`. But the parts
that get soldered to `r2:PCM-071_2xBTH-060-01-L-D-A-K` are not the module — they are **two Samtec
`BTH-060-01-L-D-A-K-TR` receptacles**, and the module plugs into them afterwards. A JLCPCB assembly
order built from this schematic's BOM would arrive with **240 empty pads and nowhere to plug the
SoM in**.

| | Part | Source | Qty/board | Placed by |
| --- | --- | --- | ---: | --- |
| the footprint | `BTH-060-01-L-D-A-K-TR` | LCSC **`C3646540`** | **2** | the PCBA house |
| the symbol | `PCM-071` | PHYTEC, direct | 1 | you, afterwards |

> **FIXED 2026-08-20** by `tools/patch_bom_only_items.py`. Three references now sit on free canvas
> on this sheet: **`J26`/`J27`** (the receptacles) and **`MK20`** (the mounting hardware), all on
> `r2:BOM_ITEM`, a pin-less rectangle.
>
> ⚠ **The first version of this fix was half a fix, and the half it got wrong is the one that
> matters.** It made all three `on_board no`, which put the parts on the order and left the board
> unassemblable. §10.0 explains why; the arrangement below is the corrected one.

### 10.0 Getting the connectors *soldered* is a different problem from getting them *bought*

A position file (CPL) has **one row per reference**. `X2` alone therefore produces a single
placement at a single centroid — for a footprint that **two** separate parts occupy, 22.4 mm apart
and 4.8 mm staggered. There is no part that covers all 240 pads. On top of that, JLCPCB rejects a
CPL designator that has no BOM line, and `X2` matches no LCSC part.

So a board ordered that way comes back with **240 bare pads** and nothing to plug the module into.
Purchase-only symbols do not help: a part that is not on the board is not in the CPL either.

**The corrected arrangement splits the two jobs.** The pads stay under `X2`; the placement moves to
two references that exist to be placed:

| Ref | Footprint | On the BOM | In the CPL | Carries nets | Fitted by |
| --- | --- | --- | --- | --- | --- |
| `X2` | `r2:PCM-071_2xBTH-060-01-L-D-A-K`, 246 pads | the module | **no** — `exclude_from_pos_files` | **yes, all of them** | you, by hand |
| `J26`, `J27` | `r2:BTH-060-01-L-D-A-K_AssemblyOnly`, **no pads** | `C3646540` ×2 | **yes**, one row each | no | **the assembler** |
| `MK20` | none, `on_board no` | the M2.5 kit | no | no | you |

The assembler is told to place a `BTH-060-01-L-D-A-K-TR` at each of two centroids; the paste and
copper it lands on come from `X2`, which they never need to know about. **The board arrives with
both receptacles soldered and the module simply plugs in**, which is the point.

Verified: **517 nets before and after with zero membership changes**, ERC unchanged at 32 excluding
`footprint_link_issues`, and a grouped BOM export carries
`"J26,J27" | BTH-060-01-L-D-A-K-TR | C3646540` as one line of quantity 2. Rendered and checked.

#### The offsets are checked, not remembered

Nothing in KiCad ties the three footprints together. Drag `J26` 2 mm at Stage D and DRC still
passes, the BOM is still right, and a 120-pin 0.5 mm connector gets placed 2 mm off its pads. So
the relationship is asserted by **`tools/check_pcb_connectors.py`**, to be run before every fab
order:

```
J26 = X2 + (-11.200, +2.400)
J27 = X2 + (+11.200, -2.400)
```

— PHYTEC's 22.400 mm spacing and 4.800 mm stagger, split symmetrically about the module centre. It
also checks that all three are on the same side and rotation, that `J26`/`J27` have no pads, that
`X2` *is* excluded from the position file and they are *not*, and that `X2` still has 246 pads. It
exits non-zero, so it can gate a release script, and it exits 0 with a note while
`r2.kicad_pcb` does not exist yet.

**This is a stronger guarantee than the single footprint gave.** That arrangement was structurally
unbreakable but also unverifiable — there was nothing to check because nothing could differ. This
one can differ and is checked, which is the better trade once the check exists.

#### ⚠ Two things to confirm with JLCPCB before the first order

Both are cheap to ask and expensive to get wrong.

1. **The no-pad designator.** A reference whose own footprint has no pads is a known technique, not
   an exotic one, but their DFM review may query it. A query costs an email; a rejected order costs
   a week. If they refuse it, the fallback is to restructure the schematic into two 120-pin
   connector symbols with `X2` as a purchase-only module — see §10.1 for what that costs.
2. **CPL rotation.** JLCPCB's pick-and-place does not share KiCad's rotation convention for every
   part, and their own guidance singles connectors out. Verify `J26`/`J27`'s angle against Samtec's
   pin-1 marking before uploading, and record any correction for future orders.

`X2` also carries `MPN`/`Manufacturer` for the module and a `BOM Comments` property explaining that
it is fitted by hand, not by the PCBA house.

### 10.1 Why there is no connector symbol in the first place

Worth stating plainly, because it looks like an omission and is not.
`tools/gen_som_symbol.py` made the call and it still holds:

> *"One symbol and one footprint, not two of each. The two `BTH-060` patterns have a fixed relative
> position set by the module. Drawing them as two independent parts would let a layout move one
> relative to the other and destroy the board with no DRC complaint; a single footprint carrying
> both patterns makes that geometry unbreakable."*

PHYTEC's DXF has since made that cost concrete. The two connectors are not merely 22.400 mm apart —
they are also **staggered 4.800 mm**, which is exactly the kind of relationship a person nudges by
accident and never notices. As one footprint it cannot be got wrong.

There is a second reason, and it is the one that would bite whoever tried the other way. **Samtec
numbers its pads 1–120, alternating between the two rows** (`SAMTEC_BTH-060-X-X-D-A-K.kicad_mod`:
pad `01` at y −3.086, pad `02` at y +3.086, pad `03` at y −3.086 …). The module's pinout is
`A1`–`A60` / `B1`–`B60` / `C1`–`C60` / `D1`–`D60`. So "just use the vendor's symbol and footprint"
is a **240-line renumbering by hand**, on a part where every pin is invisible to ERC — the precise
failure `gen_som_symbol.py` was written to avoid by generating from `som_pinout.json` instead.

So the schematic models **the thing you reason about** (the SoM and its 240 signals) and the
footprint models **the thing you solder** (two connectors at a fixed offset). That split is right,
and §10.0 pays its only real cost — the BOM and CPL rows — without compromising the symbol.

**If JLCPCB ever refuses the no-pad designator, this is the fallback and it is not cheap.**
Restructure into two 120-pin connector symbols, `J26`/`J27`, carrying the nets, with `X2` demoted to
a purchase-only module line. The pad renumbering *can* be generated — both geometries are now known
exactly, so module pin → Samtec pad is a script with assertions rather than 240 lines of typing, and
that weakens the objection above. What it does not weaken is the rest: `som.kicad_sch` and
`dpi_in.kicad_sch` are reviewed and committed, the units-by-function split would have to be redone
(the DPI group spans columns A, B **and** D, so it straddles *both* connectors), and the two
footprints could then drift apart in layout — which `check_pcb_connectors.py` would still have to
police. It is a day of work to buy back something the current arrangement already has.

### 10.2 Samtec's own KiCad footprint — an independent check that passed

The owner downloaded `BTH-060-01-L-D-A-K-TR` from Samtec on 2026-08-20, and it contains a native
`.kicad_mod`. Diffed against the generated footprint's per-connector geometry:

| | Samtec | Generated | |
| --- | --- | --- | --- |
| pad | 0.305 × 1.448 | 0.305 × 1.448 | ✓ |
| row spacing | 6.172 | 6.172 | ✓ |
| pitch / span | **0.500 / 29.500** | 0.500 / 29.500 | ✓ |
| NPTH diameter | 1.016 | 1.016 | ✓ |
| hole off the row centreline | **2.032** | 2.032 | ✓ |
| hole beyond the end pad | 1.991 | 1.986 → **adopted 1.991** | 5 µm |

**Samtec's own KiCad file uses 0.500 pitch and 29.500 span, not the 0.5001 / 29.507 in their own
dimension table** — the same choice this generator had made independently, and the same numbers
PHYTEC's DXF gives. Three sources, one answer.

Two things were taken from it: the 1.991 hole offset, and **`solder_mask_margin 0.102` on every
pad**, which Samtec sets and the generator now does too. That is worth understanding rather than
copying: 0.305 + 2 × 0.102 = 0.509 mm of opening on a 0.500 mm pitch, i.e. **one gang opening per
row with no webs between pads**. That is deliberate at this pitch — a 0.093 mm web is under JLC's
0.1 mm minimum and would be removed by the fab anyway, so stating it here makes the intent explicit
instead of leaving it to the board's global mask margin.

⚠ **Stock is the tight part, and it was not on anyone's list.** LCSC has **60** of `C3646540` and
the board needs two, so that is **30 boards** — the tightest line on the BOM by a wide margin
(compare `U41` at 2 058, `U53` at 1). `C3644612` is the same connector without the `-K` option,
36 more. Check both before ordering; if they are gone, Samtec sells direct with a long lead time.

## 11. The `PCM-071` land pattern, and what settled it

`tools/gen_som_footprint.py`, rebuilt 2026-08-20 on **PHYTEC's own DXF** —
`datasheets/SoM Phycore AM62x/PCM-071_1573-1_3d/PCM-071_1573-1.dxf`, which came with the 3D archive
and is vector, numeric, and named authoritative by PHYTEC's own README (*"Exact specifications can
be found in the corresponding data sheets and DXF data"* — in the same breath as the warning that
the STEP model may be simplified).

The first version derived the placement from `L-1038e.A5` Figure 7 by reading numerals off a raster
image. The DXF agreed with it to **8 µm in x and 61 µm in y** — close enough to be reassuring, far
enough to be worth correcting, since 61 µm is 20 % of a 0.305 mm pad's width. The generator now
asserts its output against the DXF's numbers and the skew is **0.0 µm**.

What the DXF gives directly, origin at the module's lower-left corner
(`BOARD_OUTLINE` is exactly `(0,0)`–`(32.000, 43.000)`):

| | |
| --- | --- |
| four columns of **exactly 60 pads** | x = 1.95, 7.65, 24.35, 30.05 |
| pitch | **0.500 mm exactly**, 59 gaps — not Samtec's inch-derived 0.5001 |
| span | **29.500** — not the 29.507 in Samtec's table |
| left connector pads | y = **9.150 … 38.650** |
| right connector pads | y = **4.350 … 33.850** — 4.800 lower |
| M2.5 mounting holes | (2.800, 2.800), (29.200, 40.200) — exactly Figure 7 |

Those columns are the module's **BSH-060 plug**, so their 5.70 mm row spacing is not ours. Their
*centrelines* are: **4.800 and 27.200** — 22.400 apart, which is Figure 7's number, and exactly
symmetric about the module's 16.000 mm midline. Our receptacle's rows sit ±3.086 either side.

### 11.1 The contradiction that was worth twenty minutes

The DXF has four `MOUNTING_HOLES_LAYER` circles of **1.100 mm** at x 7.452 / 29.852, spaced
**35.126** along the row. None of those is Samtec's `-A` diameter (1.016) or its "A" dimension
(33.482), and the x is 4.692 mm away from where Figure 7 puts the alignment holes.

**They are not our holes.** The `-A` option puts plastic locating pegs on each connector, dropping
into holes in *the board that connector is soldered to*. The plug's pegs land in the module; the
receptacle's pegs land in our board. The two sets never meet, so they have no reason to agree — and
our holes come from Samtec's BTH drawing, referenced to *our* pads, which is what the generator
does.

Had this been "resolved" the other way — by trusting the DXF's hole positions for our footprint —
both connectors would have been 0.62 mm out of place.

### 11.2 What to download, and what not to bother with

**Nothing.** The DXF in the repo is better than anything a library site offers, and the check is
already automated:

- **LCSC has no `PCM-071` and no `phyCORE` anything.** It is a PHYTEC module bought from PHYTEC, not
  an LCSC line item, so no EasyEDA footprint exists for it. LCSC *does* stock the connector
  (`C3646540`, §10) but sells no footprint with it.
- **SnapEDA** (the link in `L-1038e.A5`) would be a genuinely independent check, but it is a
  third-party redraw of the same DXF, so agreement proves less than it looks.
- **The STEP models** are useful for the *enclosure*, not the footprint — `PCM-071_1573-1_Basic.step`
  (8.9 MB) is the one to use for fit checking; PHYTEC's README explicitly warns the full
  `.STEP` may simplify component heights. Neither is worth attaching to the KiCad footprint as a 3D
  model at that size unless you want it in the 3D viewer.
