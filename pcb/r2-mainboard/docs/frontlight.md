# `frontlight` — the panel LED driver — R2 work package 6

Status: **redesigned on paper 2026-08-17. The hold of 2026-08-16 is LIFTED.** The schematic has
**not** been edited yet — §4 is the design to be captured, and `frontlight.kicad_sch` still holds
the provisional `TPS61022` circuit that §3 rejects.

Companion to `power.md`, `epd-port.md` and `panel.md`. The panel is now decided
(`GDEP103TC2-FT11`), which is what made this sheet designable.

---

## 0. Why the hold lifted, and what had actually gone wrong

The hold was placed on 2026-08-16 pending "a frontlight datasheet". **That datasheet was already in
the repo.** `datasheets/e-ink_display/GDEP103TC2-FT11.pdf` has been there throughout, and the copy
the owner added to `parts/Display/` on 2026-08-17 is byte-identical (`md5 5c92be40…`).

The frontlight pinout is not in any numbered section of that document. It is in the **title block of
the mechanical drawing on p.2**, as a nine-row parts table, which is why reading §5 "Input / Output
Interface" — which covers only the 40-pin EPD tail — did not find it. Read at 400 dpi:

| Pin | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | `LED1+` | `LED1−` | NC | NC | `LED2+` | `LED2−` | NC | NC |

The lesson worth keeping: **on a Good Display drawing the interface tables live in the title block,
not in the numbered sections.** The touch tail is still missing for the same reason — it is not in
the title block either, so it genuinely is a vendor question (§10.2).

## 1. What the panel needs

From the mechanical drawing's "Pre-light specification" note and §2 of the datasheet ‡:

| | |
| --- | --- |
| String voltage | **27 V** ‡ |
| Channels | **two** — `LED1` cool, `LED2` warm ‡ |
| Connector | **8-pin FPC**, pinout above ‡ |
| LED count / arrangement | 18 LEDs, 2 × 9 series — **`panel.md` §3, from the vendor product page, not the datasheet** |
| **Current per channel** | **not stated anywhere in the datasheet — the one open number, §10.1** |

**9 LEDs in series is inferred**, from 27 V ÷ 9 ≈ 3.0 V of forward drop, which is ordinary for a
white LED at these currents. It could equally be 8 series at 3.4 V. **The design below is
insensitive to which** — both are under the driver's 10-series limit, and both put V_OUT in the
same 27–29 V band. Nothing here depends on resolving it.

## 2. The premise that was wrong, kept for the record

§2 of the previous revision of this document read: *"There is no LED driver on this board, and there
was none on R1 — the panel's tail regulates the current."*

**That is true of R1 and false here.** R1 drove `J6` into a panel *adapter* board. This panel's
frontlight tail is `LED1±`/`LED2±` — bare anodes and cathodes with nothing regulating them. So the
board needs a real constant-current driver, and a voltage rail of any value would be wrong: LED
brightness would then track forward-voltage spread and temperature, and a few per cent of extra
rail voltage becomes a proportionally larger current error.

`+5V2_FL` and its 4.99 V `TPS61022` (`U53`) are therefore **deleted**, not re-tuned. §7 lists what
that touches.

## 3. Part choice — and the converter that looked obvious and is not

### 3.1 Rejected: a third `LGS6302B5`

The tempting answer was a third instance of the boost already used twice on `epd_power`
(`C5123975`, 11 k in stock, 3.0–60 V, `V_FB` = 1.2 V, SOT23-5). It fails on **duty cycle**.

A boost to a 27 V string sits at 28 V at the switch after the Schottky, so `D = 1 − V_IN/V_OUT`:

| Source | Duty | Margin to `D_MAX` |
| --- | ---: | --- |
| `+VSYS` at 4.2 V | 85.0 % | 5 points |
| `+VSYS` at 3.7 V | 86.8 % | 3 points |
| `+VSYS` at 3.0 V | **89.3 %** | **0.7 points** |

`lgs6302.pdf` gives `D_MAX` = **90 %, typical, with no minimum** ‡. At a flat cell that is not thin
margin, it is unbounded — the frontlight would fade out before the battery did, by a part-to-part
amount. A single `LGS6302` also cannot independently regulate two channels, so cool/warm balance
would need two converters or two linear sinks on top.

### 3.2 Chosen: `LM3630A`

`LM3630ATMX`, DSBGA-12, 1.94 × 1.42 mm. **ACTIVE** at TI (`SNVS974B`). All ‡ from that datasheet:

| | |
| --- | --- |
| Strings | **2 × up to 10 series LEDs** ‡ — we need 2 × 9, one LED of headroom |
| Current per string | **5–28.5 mA, independently controlled** ‡ — this *is* cool/warm balance |
| Input | 2.3–5.5 V ‡ — covers `+VSYS` 3.0–4.4 V directly |
| Output | 12–40 V ‡; ours ≈ 28.5 V |
| Abs max `SW`/`OVP`/`ILED1`/`ILED2` | **45 V** ‡ |
| OVP | programmable **16 / 24 / 32 / 40 V** ‡; the 40 V option trips at 39/41/44 V ‡ |
| Adaptive headroom | sinks regulate at **160–240 mV** ‡ (`V_HR`, at `ILED` = 20 mA) |
| Brightness | 8-bit exponential **or** linear, 256 steps, per string ‡, **plus** a `PWM` pin ‡ |
| Switch current limit | **1 A** ‡, register-selectable via `BOOST_OCP` ‡ |
| `I_Q` | 350 µA running, both banks at 20 mA ‡ |
| Boost frequency | 500 kHz or 1 MHz, programmable ‡ |

Three properties earn it the slot rather than merely fitting:

- **Adaptive headroom is the whole efficiency argument.** The alternative shape — one boost to a
  fixed rail plus two linear sinks — has to carry enough headroom to cover forward-voltage spread,
  call it 2 V, which at 2 × 28.5 mA is **114 mW thrown away**. `V_HR` at 240 mV makes the same term
  **14 mW**. On a reading-state budget of order 1 W that is the difference between noticeable and
  not.
- **It is the purpose-built part for this application**, which also disposes of §3.1's objection:
  its designed use is a Li-ion cell driving up to 40 V of backlight, so the high-duty operation that
  has no specified floor on the `LGS6302` is this part's normal operating point.
- **256 exponential dimming steps.** This is a *reading* light, so the dim end matters. The in-stock
  alternative (§3.3) manages roughly 10:1.

### 3.3 The stock position, stated plainly

| | |
| --- | --- |
| LCSC `C2678552` | **0 in stock** (checked 2026-08-17) |
| DigiKey `296-46302-1-ND` | listed |
| TI lifecycle | **ACTIVE** |

**Owner's decision, 2026-08-17: proceed, order from DigiKey for board 1**, and carry the LCSC gap as
a production-BOM risk rather than a design constraint. This is a deliberate departure from
`battery.md` §1, where 127 units at LCSC was enough to reject the `BQ25896` — the difference is that
that part had a pin-compatible family to move to and this one is being hand-ordered for one board.

**The fallback if the gap persists** is 2 × `TPS61165DBVR` (`C58756`, 4 722 in stock, SOT-23-6,
38 V, 1.2 A). It would use `FL_PWM1`/`FL_PWM2` exactly as already routed and has no 28.5 mA ceiling,
but its PWM mode sets `V_FB` = 200 mV × duty ‡ and `V_FB` regulation degrades from ±6 % at 50 mV to
±15 % at 20 mV ‡ — about 10:1 of usable dimming, against 256 steps. **Not laid out as a DNP option**:
the two topologies need different inductors, different diodes and twice the area, in the most
constrained corner of the board (§9).

## 4. The circuit

### 4.1 Source rail — `+VSYS_FL`, which is where WP2 put it

Considered and rejected: `+5V_DCDC`. Two reasons it lost, both quantified:

- **It loads a rail with no margin to spare.** At full brightness the frontlight is
  2 × 28.5 mA × 28.5 V ≈ 1.62 W, or **≈ 382 mA at 5 V**. `power.md` §8.1's worst realistic case is
  already 1.3 A, and `L10` was sized for 1.5 A — so this would take it to ≈ 1.68 A and trip §8.1's
  own explicit re-run trigger.
- **§3.1's duty argument does not apply to this part** (§3.2), so the reason for leaving the cell
  disappeared with the `LGS6302`.

Cost of staying on the cell, stated because it is real: the worst-case inductor peak is at the
**flat cell**, not at full charge, so the margin below is set by 3.0 V rather than 5.0 V (§4.3).
`+VSYS_FL` and its `U22` ch3 shunt on `power_mon` stay exactly as drawn — **no `power_mon` change**.

### 4.2 Parts

| Ref | Value | Part | Why |
| --- | --- | --- | --- |
| `U53` | — | **`LM3630ATMX`** | §3.2. Replaces the `TPS61022RWUR` at the same reference |
| `L33` | **10 µH** | ≥1.2 A `I_sat`, 3×3 mm class | §4.3. `lm3630a.pdf` Table 22 lists 10–22 µH; the value follows from the current limit |
| `D34` | — | **`1N5819WS`** | 40 V Schottky, **already on the BOM** as `D2`/`D15` on `epd_power`. 40 V against a 32 V OVP setting is 25 % margin |
| `C514` | 4.7 µF | input, at `IN`/`GND` | reuses the existing reference; ‡ Fig. 87 |
| `C515` | 1 µF / 50 V | output, at `D34` cathode | small because the sinks are 57 mA, not amperes |
| `C516` | 100 nF | local HF bypass at `IN` | the pattern every converter on this board uses |
| `J24` | — | **8-pin FPC, 0.5 mm** | **new part — §7.2.** `LED1±`, `LED2±`, four NC |
| `R507` | 100 kΩ | `HWEN` pull-down | keeps the driver off until the MCU asserts `FL_EN`, as all four `MCU_EN_*` rails do |
| `R508` | 10 kΩ | `INTN` pull-up to `+3V3` | `INTN` is open-drain |
| `R509` | **0 Ω to `IN`** | **`SEL` strap — see §5** | sets I²C address 0x38 |

Deleted from the sheet as captured: `R505` (732 k), `R506` (100 k) — the `TPS61022` feedback
divider. `+5V2_FL` disappears as a net.

### 4.3 Why 10 µH and 1 MHz, with the arithmetic

`lm3630a.pdf` eq. 4 and 5 ‡, at both channels' full scale (57 mA total), V_OUT = 28.5 V, η = 0.85:

```
I_pk = (I_LED/η) × (V_OUT/V_IN) + ΔI_L      ΔI_L = V_IN(V_OUT−V_IN) / (2·f·L·V_OUT)
```

| f / L | V_IN = 3.0 V (flat) | 3.7 V | 4.2 V | Margin to the 1 A limit, worst corner |
| --- | ---: | ---: | ---: | --- |
| **1 MHz / 10 µH** | **771 mA** | 678 mA | 634 mA | **30 %** |
| 500 kHz / 10 µH | 905 mA | 838 mA | 813 mA | **10 % — rejected** |
| 500 kHz / 22 µH | 759 mA | 663 mA | 618 mA | 32 %, but a physically larger inductor |

**1 MHz / 10 µH.** 500 kHz at the same inductance leaves 10 % at the flat cell, which is not a
margin; matching 1 MHz's margin at 500 kHz costs a 22 µH part, and area next to `J6` is the scarcest
thing on this board (§9). The `BOOST_OCP` register can raise the limit if bring-up says otherwise.

Note the shape of the worst case: **flat cell *and* both channels at maximum brightness.** If the
panel turns out to want 15 mA per channel rather than 28.5, the peak falls to 470 mA and the margin
to 113 %. §10.1 is therefore a margin question, not a viability question.

### 4.4 Configuration to be set by firmware

| Register field | Setting | Why |
| --- | --- | --- |
| OVP | **32 V** | V_OUT ≈ 28.5 V; the 32 V option is the first one above it. 40 V would let an open string charge the output to within 5 V of the 45 V abs max |
| Boost frequency | **1 MHz** | §4.3 |
| `BOOST_OCP` | default, raise only if measured | §4.3 |
| Full-scale current | **set from the vendor's answer** (§10.1); 20 mA until then | 20 mA is `lm3630a.pdf`'s own characterisation point ‡ and is below any plausible answer |
| Brightness mapping | **exponential** | it is a reading light |

## 5. ⚠ The I²C address, which collides by default

**`SEL` must be tied to `IN`, not to ground.**

‡ `lm3630a.pdf` pin C2: *"Selects I2C-compatible address. Ground selects 7-bit address 36h. VIN
selects address 38h."*
‡ `max17048.pdf` p. 1038: the fuel gauge's address *"is fixed to 0x6C (write)/0x6D (read)"* — i.e.
**7-bit 0x36**.

So the default strap puts the frontlight driver on the same address as `U2`, on
`SCL_AON`/`SDA_AON` — the always-on bus that also carries the charger (0x6B), three `INA3221`s
(0x40–0x43) and, later, touch. Two devices answering one address takes the bus down, and it takes
the fuel gauge and the charger with it.

`SEL` → `IN` gives **0x38**, which is clear of every address on that bus. `R509` is drawn as a 0 Ω
link rather than a hard net so the alternative remains a stuffing option.

This is the one thing on this sheet that would have been found at bring-up rather than at review.

## 6. Sheet interface

| Name | Shape | Other end |
| --- | --- | --- |
| `FL_EN` | input | `mcu` (`PB5`), and `epd`'s `J6.43` — now also `U53.HWEN` |
| `FL_PWM1` | input | `mcu` (`TIM4_CH1`) — now also `U53.PWM` |
| `SCL_AON` | bidirectional | the always-on bus |
| `SDA_AON` | bidirectional | the always-on bus |
| `FL_INT#` | output | `mcu`, a spare GPIO — **new, §10.3** |

`+VSYS_FL` in, `GND`, and `+3V3` for `R508` cross as global power nets. **`+5V2_FL` is gone.**

Three of these are new on this sheet, so the **`frontlight` sheet symbol on `r2.kicad_sch` gains
hierarchical pins** — a root-sheet edit, surgical, no geometry moved.

**`FL_PWM2` is freed** and returns to `mcu.md` §3.2's spare pool. Cool/warm balance is per-string
over I²C with 256 exponential steps, which is strictly better than a second PWM line for this job:
no flicker, and the two channels can be trimmed against each other in firmware rather than in
hardware.

## 7. What this changes elsewhere

### 7.1 Nothing on a frozen sheet

`epd.kicad_sch` is reviewed and frozen, and it carries `+5V2_FL` on `J6.7`/`J6.44` and
`FL_PWM1`/`FL_PWM2` to `J6.41`/`J6.42`. With the frontlight on its own connector those panel-tail
pins simply go unused. **They need no edit** — an unconnected connector pin is not an error, and
`FL_PWM1` keeps a legitimate second destination anyway. `power_mon` is likewise untouched (§4.1).

This is the payoff of the `+VSYS_FL` decision: the change is contained to `frontlight.kicad_sch`
plus three hierarchical pins on the root.

### 7.2 One new connector, and it does not exist yet

The LED tail needs an **8-pin FPC on the mainboard.** There is none today, and the adapter cannot
supply it: `pcb/40p-adapter-ab/adapter.kicad_sch` contains exactly two parts, `J1` (01×40) and `J2`
— a bare passthrough with no frontlight path.

Part not yet chosen. `pcb_common` has `HC-FPC-05-09-6RLTAG` (6-pin, 0.5 mm) for `J22`/`J23`, so the
8-pin sibling in the same family is the obvious candidate and needs an LCSC check.

### 7.3 Documents that now contradict this one

Not edited yet, listed so they are not trusted stale:

| File | What is wrong |
| --- | --- |
| `panel.md` §5, §6, §10 | says `frontlight` is on hold, and its §6 plan buys the 6" module first — **the 6" is EOL** |
| `panel.md` §7 | four documents to request; two are now answered |
| `power.md` §6 | records "an LED boost from `+VSYS` is one conversion, not two" — still the operative decision, but for a different reason than written |
| `NOTES-R2-plan.md` | "Panel choice" section, and the WP6 hold |
| `layout.md` §1 | "the panel model is still deferred" |

## 8. Verification — to be run when the sheet is captured

- Netlist: `+5V2_FL` **absent**; `+VSYS_FL` reaches `U53.IN`; `LED1±`/`LED2±` reach `J24` and
  nothing else; `SEL` on `IN` and not `GND`.
- `FL_EN` = `U20.59` + `J6.43` + `U53.HWEN` — three nodes.
- I²C: `SCL_AON`/`SDA_AON` gain exactly one node each. **Re-check `battery.md` §10.4's rise-time
  budget** — that 2.2 kΩ was sized for ~90 pF over six devices, and this is the seventh.
- ERC: no new `power_pin_not_driven`; the `+5V2_FL` violations disappear with the net.
- `tools/schgen.py`'s `check_label_crossings()` and `check_grid()` — mandatory, per the four silent
  shorts of 2026-08-16.
- Render the page to PNG and read it.

## 9. Layout guidelines — for Stage D

`power.md` §11.2's `TPS61022` section **no longer applies** — different part, different topology,
and this one is asynchronous, so the diode is in the hot loop.

- **It belongs next to `J24`, not next to `U12`.** The output is 28.5 V into a two-wire-per-channel
  tail; the input is a plane net. Keep `V_OUT` short, let `+VSYS_FL` be long.
- **`SW`→`D34`→`C515` is the loop that matters** and it is a 28.5 V, 1 MHz edge. `lm3630a.pdf` pin
  A3 ‡: *"Connect the inductor and diode as close as possible to SW to reduce inductance and
  capacitive coupling to nearby traces."* Diode adjacent to the pin, output capacitor's ground
  returning to `GND` at the part.
- **`OVP` is a sense pin on a 28.5 V node.** Route it as a quiet trace to the output capacitor's
  positive terminal, not tapped off the `SW` side of the diode.
- **This sheet's corner is the crowded one.** `J6` is enclosure-fixed, `io-expansion.md` §7 puts
  `J22`/`J23` there too because the touch and pen tails emerge from the panel, and `J24` joins them.
  The DSBGA is 1.94 × 1.42 mm and the solution size TI quotes is 32 mm² — that smallness is a
  layout asset here, not a vanity number.
- **DSBGA-12 is 0.4 mm pitch.** Already inside this board's assembly envelope — four
  `TPS22914BYFPR` in `WLP-4_0.83x0.83mm_P0.4mm` are on it already — but it wants solder-mask-defined
  pads and no via-in-pad.
- `SCL_AON`/`SDA_AON` reach here from the always-on bus. With `io_expansion`, this is now the second
  long leg; see §8.

## 10. Open

1. **⚠ LED current per channel is unknown.** Not in the datasheet, in any section or title block.
   **The vendor question.** It sets the full-scale current register and `L33`'s saturation rating.
   §4.3 shows the design holds from 15 mA to the driver's 28.5 mA ceiling — so this bounds the
   *margin*, not the *design*. If the answer is above 28.5 mA per channel the part changes to §3.3's
   fallback and this sheet is redrawn; nothing else on the board moves.
2. **The 8-pin FPC part is not chosen** — §7.2.
3. **`FL_INT#` needs an MCU pin.** `mcu.md` §3.2 has two spares left, `PA12` and `PB12`, both kept
   deliberately for capabilities the others lack. `FL_PWM2` is freed by this design and is the
   natural donor — it is already routed to the right corner of the board.
4. **9-series is inferred**, not read from a datasheet (§1). Harmless (§1), but it is not a ‡ fact.
5. **Nothing here has been measured.** Every number is datasheet arithmetic. `power_mon`'s `U22`
   ch3 shunt exists precisely to close this out on first silicon, and `NOTES-STATUS.md` still has
   no frontlight row because R1 never drove `FL_EN`.
