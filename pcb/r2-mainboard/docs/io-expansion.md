# `io_expansion` — touch and pen, provisioned but not fitted — R2 work package 6

Status: **drawn 2026-08-15, not yet reviewed. Everything on this sheet is DNP.**
One decision is owed before fab — §5.

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

**~~This is a guess~~ — resolved 2026-08-19, and the six signals are right.** The
`GDEP103TC2-FT11` listing gives *Touch IC `GT9110H`, Touch Connector 2×14 pin*, which looks
incompatible with `J22`. It is not: `parts/Display/EN-DEJA-TC103.pdf` §4.4.2 says *"the
touchscreen uses an external GT9110 touch board"*, and that board presents `TOUCH_SDA`,
`TOUCH_SCL`, `TOUCH_INT`, `TOUCH_RST`. The 2×14 FFC runs from the panel's ITO sensor to that
board and never reaches the mainboard. **Note the part is the `GT9110H`, not the `GT911` cited
below** — larger-panel variant, same I²C interface. Still to get from the vendor: whether the
touch board ships with the panel, and its output connector's **pin order** against `J22`'s.

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
