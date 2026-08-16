# `frontlight` — the panel LED rail — R2 work package 6

Status: **drawn 2026-08-15. ⚠ ON HOLD 2026-08-16 by the hardware owner — the sheet as drawn is
wrong for either candidate panel, and no edit happens until a frontlight datasheet arrives.**
Companion to `power.md` and `epd-port.md`. Read §0 before anything below it.

---

## 0. ⚠ On hold — the premise in §2 was wrong

Everything from §1 down was written on the assumption in §2 that **"there is no LED driver on this
board, and there was none on R1 — the panel's tail regulates the current."** That is true of R1,
which drove `J6` into a panel *adapter* board. **It is not true of a bonded frontlight film**,
whose FPC is LED anodes and cathodes with nothing regulating them. If R2 uses a module with a
bonded frontlight, **this board needs a real constant-current driver**, which is not what is drawn.

The two candidate panels are also nowhere near each other:

| Candidate | Frontlight | vs. the 4.99 V rail drawn here |
| --- | --- | --- |
| `GDE060F3-FT01`, 6" | **2.8–3.6 V**, separate FPC | too high, and unregulated |
| `GDEP103TC2-FT11`, 10.3" | **27 V**, 18 LEDs, dual-channel 9-series, cool + warm, 8-pin | far too low |

A `TPS61022` cannot reach 27 V (5.5 V max) and is the wrong topology for 3.3 V from a 3.0–4.4 V
cell. **`U53` and its whole network are provisional.**

**Decision, 2026-08-16:** hold the sheet. Do not redesign on a guess — request the frontlight FPC
pinout and drive spec (voltage, current, series/parallel arrangement, dimming method) from the
panel vendor, then design to it. Three options were put to the owner: a wide-range 2-channel
constant-current driver covering 3–30 V, a low-voltage design for the 6" module only, or hold.
**Hold was chosen.**

What is *not* in doubt and does not need to change: `+VSYS_FL` and its `U22` ch3 shunt, `FL_EN`
reaching both this sheet and `J6.43`, and the fact that `+5V2_FL` needs *a* source (§1).

---

One converter, and it closes a hole in the design rather than adding a feature.

---

## 1. What was wrong before this sheet existed

The netlist said it plainly:

```
+5V2_FL    C147.1  J6.44  J6.7          <- three loads, no source
+VSYS_FL   R72.1   U22.1                <- a shunt into an ammeter, going nowhere
```

**`+5V2_FL` had no source at all.** R1 fed it from `+5V_DCDC` through shunt `R72`
(`R1 +5V_DCDC: … R72.2 …`, `R1 +5V2_FL: C147.1 J6.44 J6.7 R72.1 U22.1`), so the panel saw about
**4.99 V**. WP2 moved the frontlight to the cell — `power_mon`'s `U22` ch3 became
`+VSYS` → `+VSYS_FL` — and the plan noted that "the frontlight boost moves to
`frontlight.kicad_sch`". Until now that sheet was empty, so the rail was orphaned at one end and
the shunt dead-ended at the other. This sheet joins them.

## 2. The architecture, which is R1's and is not obvious

**There is no LED driver on this board, and there was none on R1.** The mainboard supplies a
voltage rail and three logic signals; whatever regulates the LED current lives on the panel's tail
or its adapter:

| Net | `J6` | Direction | Drawn on |
| --- | --- | --- | --- |
| `+5V2_FL` | 7, 44 | rail out | `epd` (loads), **this sheet** (source) |
| `FL_EN` | 43 | MCU out | `mcu` → `epd`, **and now this sheet** |
| `FL_PWM1` | 41 | MCU out, `TIM4_CH1` | `mcu` → `epd` |
| `FL_PWM2` | 42 | MCU out, `TIM4_CH2` | `mcu` → `epd` |

So this sheet's whole job is: **boost `+VSYS_FL` (3.0–4.4 V) to the LED anode rail, and switch it
off when the frontlight is off.** Dimming stays where R1 put it — panel-side, via the two PWM
lines — and is not this board's problem.

## 3. Why the rail is 4.99 V and not 5.2 V

The net is called `+5V2_FL` and **that name was already wrong in R1**, where it came off a 5.0 V
rail through a 20 mΩ shunt. `epd-port.md` §7 flagged it and left "confirm or rename" to WP6.

**Confirmed as ~5.0 V, name kept.** Two reasons:

- The panel-side circuit is unknown — the panel model is still deferred — so matching the value R1
  actually delivered is the conservative choice. If the panel regulates current, extra headroom is
  wasted power; if it uses a series resistor, 4 % more voltage is 4 % more LED current and a
  brightness/lifetime change nobody asked for.
- Renaming would touch `epd.kicad_sch`, which is reviewed and frozen, for a cosmetic gain.

The name describes the LED anode rail, not its voltage. If a chosen panel wants a different string
voltage, it is **two resistors** (§4), not a respin.

## 4. The circuit

`U53` is a second `TPS61022RWUR`, identical in topology to `U12` on `power.kicad_sch`.

| Ref | Value | Part | Why |
| --- | --- | --- | --- |
| `U53` | — | `TPS61022RWUR` (`C915088`) | already in the BOM; **true output disconnect in shutdown** (`power.md` §2.2), which is exactly what a frontlight rail needs |
| `L33` | 1 µH | `DFE322512F-1R0M` (`C3224227`) | same inductor as `L10`; `tps61022.pdf` Fig. 8-1 |
| `R505` | 732 kΩ | | feedback top — **the same value as `R21`** |
| `R506` | 100 kΩ | | feedback bottom, = `R22`. 0.600 × (1 + 7.32) = **4.992 V** |
| `R507` | 100 kΩ | | `EN` pull-down, the pattern all four `MCU_EN_*` rails use |
| `C514` | 22 µF/10 V | | input, per `tps61022.pdf` §8.2.2.5 |
| `C515` | 22 µF/10 V | | output — see below |
| `C516` | 100 nF | | local HF bypass at `VIN` |

**Reusing `U12`'s exact divider values is the point, not a coincidence**: 732 k and 100 k are
already on the BOM, so this converter adds *no new passive line items* beyond the capacitors, and
one `DFE322512F` covers `L10`, `L12`, `L13` and now `L33`.

**One output capacitor, not two.** `power.md` §3.3 fits `C26`+`C27` on `U12` because §8.2.2.3 asks
for 10–50 µF *effective* at that converter's current. This one drives an EPD frontlight — tens of
milliamps, not amperes — so a single 22 µF derating to ~12 µF at 5 V sits in the band. Add the
second if measurement says otherwise.

**No feedforward capacitor.** `U12` has `C28` as a DNP option; §8.2.2.4's 2 kHz zero is only wanted
above 40 µF effective, which this rail is nowhere near.

**The boost is oversized and that is deliberate.** A 3 A part for a ~100 mA load is silly on paper,
but the alternative is a new IC, a new footprint, a new inductor and an LCSC stock check, to save a
few hundred µA of operating quiescent on a rail that is off whenever the light is off. `TPS61022`
draws 27 µA from `VOUT` and 0.9 µA from `VIN` while running ‡, against LEDs pulling tens of mA —
under 1 %. In shutdown it is 0.25 µA typ ‡, which is what matters for the reading state.

## 5. Sheet interface

| Name | Shape | Other end |
| --- | --- | --- |
| `FL_EN` | input | `mcu` (`PB5`), and `epd`'s `J6.43` |

Everything else crosses as a global power net: `+VSYS_FL` in, `+5V2_FL` out, `GND`.

**`FL_EN` now has three nodes**, and that is intended: one signal means "frontlight on", and it
both starts the boost and tells the panel side. There is no case where one should be true and the
other false, so giving the boost its own enable would have added a net and a firmware ordering
question for nothing.

## 6. Verification

- Netlist: `+5V2_FL` now has a source (`U53.VOUT`), and `+VSYS_FL` reaches `U53.VIN` instead of
  dead-ending at `U22`. Both were checked before and after.
- `FL_EN` = `U20.59` + `J6.43` + `U53.EN` — three nodes across three sheets.
- ERC: no new violations; the sheet adds no `power_pin_not_driven` because `+5V2_FL` is now driven.
- Rendered and read.

## 7. Layout guidelines — for Stage D

`power.md` §11.2 is the `TPS61022` section and **applies verbatim** — this is the same part in the
same topology. The additions specific to this instance:

- **It belongs near `J6`, not near `U12`.** The rail's only load is the panel connector, so keeping
  `+5V2_FL` short beats keeping `+VSYS_FL` short — the input side is a plane net and the output is
  not.
- Same rule as every other converter: **input capacitor loop first** (`C514` across `U53`'s `VIN`
  and `GND`), then the inductor, then everything else.
- `L33`'s `SW` node stays small. It is the only high-dv/dt node this sheet has, and it sits next to
  the panel connector's analogue-ish HV rails (`epd-port.md` §11.2), so it is worth being tidy
  about even at this current.
- The feedback node (`R505`/`R506` junction) is high-impedance: keep it off the `SW` node and short
  to pin `FB`.

## 8. Open

1. **The LED string's voltage and current are unknown**, because the panel is. §3 sets the rail to
   R1's proven ~4.99 V; a different panel changes `R505` and possibly the output capacitor.
2. **`+5V2_FL`'s name remains historically wrong** (§3). Kept deliberately; if `epd.kicad_sch` is
   ever unfrozen for another reason, rename both ends then.
3. **Nothing has measured the frontlight**, on R1 or anywhere — `NOTES-STATUS.md`'s table has no
   frontlight row because R1 never drove `FL_EN`. The `U22` ch3 shunt is there to fix that on first
   silicon.
