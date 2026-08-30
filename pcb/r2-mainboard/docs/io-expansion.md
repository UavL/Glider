# `io_expansion` — touch, pen and the USB host port — R2 work package 6

Status: **drawn 2026-08-15, not yet reviewed. The touch and pen provision is DNP; the USB1 host
port added 2026-08-30 is fitted.** One decision is owed before fab — §5.

`NOTES-R2-plan.md` constraint 3: *"First board is compute + display + power only. Touch and pen
get unpopulated FPC connectors so they can be added without a respin."* This sheet is that
provision.

---

## 1. What "without a respin" actually requires

Three separate things, and they are not equally certain:

| | Certain? | Why |
| --- | --- | --- |
| **The MCU pins exist and are routed** | **yes** | a pin is a pin; §3 claims seven of the nine spares |
| **The gated rails exist** | **yes** | `+3V3_TOUCH` / `+3V3_PEN` off `+3V3` through a load switch, §4 |
| **The FPC pad order matches the part** | **no** | the parts are not chosen, so the pin order is a bet — §5 |

The first two are the ones that would otherwise force a whole-board respin, and they are solid.
The third is local to two connectors and is stated plainly rather than glossed.

## 2. Everything here is DNP, including the load switches

The connectors, the load switches, their capacitors and the pull-ups are all **do-not-populate**.
That is coherent rather than lazy: with no connector fitted there is no load, so a fitted load
switch would be two parts powering nothing.

A useful side-effect: `epd-port.md` §7 flags that **`TPS22914BYFPR` stock is thin** — 1 487 units
at LCSC for a part already used twice. These two instances are DNP, so **they consume none of it**
for R2's build, and the second-source problem stays a two-part problem.

Populating touch or pen later means populating that group *together*: switch, its capacitors, the
connector, and any pull-ups.

## 3. MCU pins claimed

`mcu.md` §3.2's spare list had nine after `PG_SOM` took `PC8`. This sheet claims seven:

| Net | MCU pin | Function | Why this pin |
| --- | --- | --- | --- |
| `PEN_TXD` | `PC4` | **`USART3_TX`** (AF0) | a real hardware UART, not bit-banged |
| `PEN_RXD` | `PC5` | **`USART3_RX`** (AF0) | the matching half, adjacent |
| `PEN_INT#` | `PC6` | GPIO / EXTI | next to the UART it belongs to |
| `MCU_EN_PEN` | `PC9` | GPIO | plain output |
| `TOUCH_INT#` | `PC3` | GPIO / EXTI | plain input |
| `TOUCH_RST#` | `PD9` | GPIO | plain output |
| `MCU_EN_TOUCH` | `PA11` | GPIO | plain output |

`USART3` on `PC4`/`PC5` is verified in `stm32g0b1.pdf`'s alternate-function table — both are
`USART3_TX`/`USART3_RX` at AF0, and both were free. That is the one allocation here that is not
interchangeable; the other five are ordinary GPIO and can be swapped for layout convenience.

**Touch needs no new I²C pins.** It sits on the existing always-on bus, `SCL_AON`/`SDA_AON`
(`PB8`/`PB9`), which already carries the charger, the gauge and the three `INA3221`s. A touch
controller is one more address on it.

**Two spares remain**: `PA12` (USB-DP capable) and `PB12` (ADC-capable). Keeping those two
specifically was deliberate — they are the two with a capability the others lack.

## 4. The rails

| | |
| --- | --- |
| `+3V3` → `+3V3_TOUCH` | `U54` `TPS22914BYFPR`, enable `MCU_EN_TOUCH` |
| `+3V3` → `+3V3_PEN` | `U55` `TPS22914BYFPR`, enable `MCU_EN_PEN` |

Same part, symbol and footprint as `U7`/`U8` on `epd_power` (`Power_Management:AP22914CN4`,
`Package_BGA:WLP-4_0.83x0.83mm_P0.4mm`) — no new line item, and active-high `EN` keeps the
`MCU_EN_*` convention every other switched rail on this board uses.

Both rails come off **`+3V3`**, not `+3V3_AON`: touch and pen are only useful when the reader is
awake, and hanging them on the always-on domain would put their leakage in the standby budget for
no gain. The cost is that a touch wake would need `+3V3` up first, which `mcu.md` §5 already
sequences.

Each switch gets a 1 µF output capacitor, DNP with the rest.

## 5. ⚠ The one thing that needs a decision before fab

**The FPC pin order is provisional.** Both connectors are `HC-FPC-05-09-6RLTAG` (6-pin, 0.5 mm,
already in `pcb_common`), wired in the order that is most common for these two interfaces:

| Pin | `J22` touch | `J23` pen |
| --- | --- | --- |
| 1 | `+3V3_TOUCH` | `+3V3_PEN` |
| 2 | `GND` | `GND` |
| 3 | `SCL_AON` | `PEN_TXD` |
| 4 | `SDA_AON` | `PEN_RXD` |
| 5 | `TOUCH_INT#` | `PEN_INT#` |
| 6 | `TOUCH_RST#` | `GND` |

**~~This is a guess~~ — investigated 2026-08-19. `J22`'s six signals are still the right choice,
but there is an adapter to design and it is not optional.**

The `GDEP103TC2-FT11` listing gives *Touch IC `GT9110H`, Touch Connector 2×14 pin*. That 2×14 is
**not** a host interface — it is the panel's raw ITO sensor tail, and it runs to an **external
GT9110 touch board** that comes with the module, physically bonded near the panel's flex
(`parts/Display/Bildschirmfoto_20260819_162728.png` shows the arrangement).

The important qualifier, from `parts/Display/EN-DEJA-TC103.pdf` §4.4.2, and it was missed on the
first read:

> "since the touchscreen uses an external GT9110 touch board, the board has a reserved **USB**
> communication interface. If using the IIC interface, **wiring modifications are required**. The
> board already provides IIC test points for connection. **The adapter board between the two can be
> designed independently and is not provided separately by our company.**"

So the GT9110 board's *native* output is **USB**, and the `TOUCH_SDA`/`SCL`/`INT`/`RST` pins listed
in §4.4.2 are the **ESP32 dev board's** I²C interface, not the touch board's default. Reaching I²C
means a small adapter that Good Display explicitly does not sell.

### Which interface R2 should take

| | I²C into `J22` (as drawn) | USB into the free `USB1` |
| --- | --- | --- |
| Board cost | 6-pin FPC, already there | one more connector, plus routing a USB pair |
| Driver | mainline `goodix` | generic USB HID multitouch — near-zero effort |
| Adapter | **yes, self-designed** | probably none |
| **Standby power** | **controller gated off `+3V3_TOUCH`; wake on `INT`** | **USB PHY must stay powered to see a touch** |

**Stay with I²C.** On a battery e-reader the last row decides it: `+3V3_TOUCH` can be switched off
entirely and the panel woken by a single interrupt line, where USB would hold a PHY up in standby.
The adapter is a small flex or a 2-connector interposer, and it has to be designed either way
because the vendor does not sell one.

**What is still needed from the vendor:** the GT9110 touch board's own connector pinout and pitch,
and its I²C test-point mapping. `J22`'s order is 1 `GND`, 2 `VCC`, 3 `RESET`, 4 `INT`, 5 `SDA`,
6 `SCL` — the adapter absorbs any difference, so this does not block the mainboard, but it does
block the adapter.

**Note the part is the `GT9110H`, not the `GT911` cited below** — larger-panel variant, same I²C
protocol, same mainline driver.

The original note, kept because the reasoning still applies to any other panel: A capacitive touch controller's FPC
and an EMR digitizer's FPC both have part-specific pinouts, and neither part is chosen — the panel
model itself is still deferred. If the eventual part disagrees, the pads are wrong and *that*
group would need a respin, which is exactly what the provision was meant to avoid.

### 5.1 Evidence gathered 2026-08-16 — the signal set is right, the order is still open

Two real touch modules were examined while evaluating panels, and **both need exactly the six
signals `J22` carries** — `VCC`, `GND`, `SCL`, `SDA`, `INT`, `RST`. Nothing needs a seventh pin.
That is the half of §5 that was actually load-bearing, and it holds.

| Module | Touch IC | Connector | Pin order |
| --- | --- | --- | --- |
| `GDEY075T7-T01`, 7.5" | `GT911` | 6-pin FPC | 1 `GND`, 2 `VCC`, 3 `RESET`, 4 `INT`, 5 `SDA`, 6 `SCL` |
| **`GDEP103TC2-FT11`, 10.3" ← the chosen panel** | **`GT9110H`** | not stated | **unknown — request from vendor** |
| ~~`GDE060F3-FT01`, 6"~~ | ~~`FT5436`~~ | — | **void: the panel is EOL** (`panel.md` §0) |

### 5.2 Revised 2026-08-17, when the panel was chosen

Two things changed and they pull in opposite directions.

**The signal set is now confirmed, not merely likely.** `GDEP103TC2-FT11.pdf`'s specification table
(in the mechanical drawing's title block, p.2) gives: *IC type `GT9110H`*, *optional interfaces
`IIC`*, *structure `3.3V`*, and — *"does the motherboard SDA/SCL come with a pull-up resistor:
**YES**"*. So the module presents plain I²C at 3.3 V and **carries its own bus pull-ups**. `J22`'s
six signals are right.

**One consequence for this sheet:** our pull-ups on the touch side would be in parallel with the
module's. They are already DNP with everything else here, so nothing needs changing today — but
whoever populates touch must **leave them unfitted** rather than assume they are needed.

**The pin order is still open**, and `panel.md` §3's "2×14" for this module is the *sensor-to-IC*
connection, not the host interface — it is not evidence about `J22`. The specific document to ask
Good Display for is the **`GT9110H` touch tail pinout and connector type**. Note `GT9110H` is Goodix,
so the `GT911` datasheet in `datasheets/e-ink_display/` is a *sibling* part: useful for the register
interface, not authoritative for this module's tail.

Three ways to close it, in order of preference:

1. **Choose the touch controller and digitizer**, and re-wire this sheet to their actual pinouts.
   It is a ten-minute edit once the parts exist.
2. **Accept the risk** on the grounds that these are deferred features anyway and R3 will revisit.
3. **Replace the FPCs with 2.54 mm DNP headers**, which can be jumpered to anything during
   bring-up at the cost of board area — defensible on a first prototype, and a real option on a
   board whose stated purpose is "compute + display + power only".

I have drawn (1)'s shape with (2)'s risk. **It is the owner's call**, and it is the last open
decision in Stage C.

## 6. Sheet interface

| Name | Shape |
| --- | --- |
| `SCL_AON`, `SDA_AON` | bidirectional |
| `MCU_EN_TOUCH`, `MCU_EN_PEN`, `TOUCH_RST#` | input |
| `TOUCH_INT#`, `PEN_INT#` | output |
| `PEN_TXD` | input |
| `PEN_RXD` | output |

Shapes are from this sheet's point of view: the interrupts leave it, the enables and resets arrive.

## 7. Layout guidelines — for Stage D

- **Both connectors are enclosure-fixed**, like `J6`. Their position comes from where the touch
  layer's and digitizer's tails emerge, which comes from the panel — so they are placed with `J6`,
  not around it.
- The rails are DNP, so **the load switches sit next to their connectors**, not next to `power`.
  Populating one later should not mean routing a rail across the board.
- `SCL_AON`/`SDA_AON` reach here from the always-on bus. That bus already spans `battery`, `mcu`
  and `power_mon`; this is its longest leg, so it is the one to check for capacitance if the
  I²C rise time is ever marginal.
- Nothing on this sheet is fast. `USART3` at digitizer rates and I²C at 400 kHz have no routing
  constraints worth writing down.

## 8. Open

1. **The FPC pin order** — §5. Still the last open decision in Stage C, and now a pure vendor
   question rather than a design one.
2. ~~**No touch controller is chosen**~~ — **CLOSED**: the panel is chosen, so touch is `GT9110H`,
   I²C at 3.3 V, with pull-ups on the module (§5.2). **The digitizer is still unchosen**, and `J23`
   stays provisional with it.
3. **Our touch-side pull-ups must stay unfitted** when touch is populated — the module has its own
   (§5.2).
4. **`TOUCH_RST#` may not be needed** by the eventual part; if not, `PD9` returns to the spare
   pool.
5. **Whether touch is populated on board 1 at all** is reopened by the panel: the chosen module has
   touch bonded on, so `NOTES-R2-plan.md` constraint 3 is worth revisiting. Owner's call.


## 7. The USB1 host port — added 2026-08-30

Owner's decision. Closes `NOTES-R2-review-round-2.md` **D-3**, which had it as *"the cheap half of a
port … it cannot be retrofitted"* — the four `USB1` pins were already on `J26` and cost nothing until
the board was fabbed.

**Host only, not dual-role.** The USB-C port `J1` is a permanent sink: `R1`/`R2` are fixed 5.1 kΩ Rd
on `CC1`/`CC2`, so it can never source. Making *that* port dual-role would need a CC controller, the
`X_USB0_DRVVBUS` ball wired, and `C2` on `PMID` taken from 8.2 µF to 40 µF (`battery.md` §6). A
second, source-only port needs none of that, and it does not touch the charge path.

### 7.1 The circuit

| Ref | Part | LCSC | Why |
| --- | --- | --- | --- |
| `J28` | `TYPE-C-31-M-12` | `C165948` | the same receptacle as `J1` — no new BOM line |
| `U56` | **`TPS2553DBVR`** SOT-23-6 | `C55266` | adjustable current limit, `EN` **active high** |
| `U57` | `USBLC6-2SC6` | `C7519` | same ESD part and same wiring as `U3` on `battery` |
| `R520`, `R521` | 56 kΩ | — | Rp on `CC1`/`CC2`: a source advertising *Default USB Power* |
| `R522` | 49.9 kΩ 1 % | — | `ILIM` |
| `R523` | 100 kΩ | — | pull-up on the open-drain `FAULT` |
| `C519` | 100 nF | — | at `IN`; the datasheet's pin table asks for ≥0.1 µF "as close as possible" |
| `C520`, `C521` | 22 µF, 100 nF | — | on the switched output |

**Why a current-limited switch and not a plain load switch.** `+5V_DCDC` is shared with the SoM. A
stick that shorts VBUS, or one with a large inrush, would otherwise brown the module out — a hard
reset of the whole device. `tps2553.pdf` §7.5 gives `tIOS` = **2 µs** response to a short, which is
what makes that impossible. The board's existing `TPS22965`/`TPS22914` load switches have no current
limit and would not do.

**`R522` = 49.9 kΩ.** Straight off the datasheet's `IOS` row, not a formula:
**475 / 520 / 565 mA** over −40 °C ≤ TJ ≤ 125 °C. That is the USB 2.0 host budget, and it is what
the 56 kΩ Rp advertises, so the electrical limit and the Type-C advertisement agree.

**Rp goes to `+5V_DCDC`, not to the switched output.** A source should advertise before VBUS
appears. With nothing plugged in, `CC` is open and the pull-ups pass no current, so this costs
nothing in standby — and `+5V_DCDC` is off with `MCU_EN_5V` anyway, so the port is dead when the
reader is asleep.

**The rail is `+5V_DCDC`, deliberately.** There is no net called `+5V` on this board: the boost
output is `+5V_DCDC` and it splits into `+5V_SOM`, `+5V_EPD` and the rest *after* the `power_mon`
shunts. Hanging the port on `+5V_SOM` would corrupt `U22` ch1's reading of the module. The cost is
that USB current is not separately measured; `USB1_FAULT#` is the signal that something is wrong.

### 7.2 Control and fault

| Net | From | To |
| --- | --- | --- |
| `USB1_DRVVBUS` | SoM `J26.B42` (`X_USB1_DRVVBUS`) | `U56.EN` — the SoM's own VBUS gate, active high |
| `USB1_VBUS` | `U56.OUT` | `J28` VBUS, `U57`, and SoM `J26.B41` so the controller senses its own output |
| `USB1_DM` / `USB1_DP` | SoM `J26.B39`/`B40` | `U57` then `J28`'s two D− and two D+ contacts |
| `USB1_FAULT#` | `U56.FAULT`, open drain + `R523` | MCU `PB7` (`U20.61`) |

`PB7` is the pin freed when `FL_PWM2` was retired the same day (`mcu.md` §16.1). It went straight
back out again, which is the best possible outcome for a spare.

### 7.3 ⚠ What this costs the `+5V` budget

`power.md` §8.1 sized `L10` against a worst realistic case of **1.3 A** — the SoM's 1.0 A design
bound plus an EPD refresh — with 1.5 A the design point and 2.0 A the line where "margin is gone".
The port's limit is 565 mA at its worst corner, so **worst case becomes 1.865 A**. That is inside
2.0 A but it is the whole remaining margin, and it is why the limit is 49.9 kΩ and not something
looser. Recorded in `power.md` §8.1.

Two things make it less alarming than the arithmetic looks: the SoM's 1.0 A is a *design bound*
against 651 mA measured under a heavy load Glider does not run and 324 mA idle; and firmware owns
`USB1_DRVVBUS`, so it can refuse to enable the port during an EPD refresh if bring-up ever shows it
matters.

### 7.4 Open

- **The schematic block is dense.** The passives are on a 7.62 mm pitch and KiCad's auto-placed
  reference and value text overlaps in places. Nothing is electrically ambiguous — the netlist was
  verified net by net — but *Tools → Autoplace Fields* on this sheet would be worth a minute.
- **No CC sensing.** The AM62x's `USB1` group is `DM`/`DP`/`VBUS`/`DRVVBUS` only; there is no CC
  input. Attach detection is therefore the ordinary USB 2.0 one — the device's D+ pull-up, seen once
  VBUS is on — so firmware should just enable `USB1_DRVVBUS` while the system is awake. Type-C's own
  attach logic is not available and is not needed for a fixed-role source.
