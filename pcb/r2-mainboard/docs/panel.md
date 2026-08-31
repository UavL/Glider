# Panel selection — which E Ink panel Reflow is designed around

Status: **DECIDED 2026-08-17 — `GDEP103TC2-FT11`, 10.3", 1872×1404.** Nothing is ordered.
Companion to `epd-port.md` (the connector and HV chain, and §10 for the `VGH` change this panel
forces), `frontlight.md` (redesigned to this panel, hold lifted) and `io-expansion.md` (touch).
The gateware side is `fpga.md` §16.

The panel had been deferred alongside touch and pen. The hardware owner began sourcing on
2026-08-16, which turned it from "read it off the tail label later" into the decision several
frozen sheets depended on. It closed on 2026-08-17.

---

## 0. The decision, and what closed with it

**`GDEP103TC2-FT11` it is.** Two things settled it on 2026-08-17:

1. **`GDE060F3-FT01` is end-of-life.** The 6" module was §6's first purchase and the whole reason
   for buying it — that it is the only *complete* module with bonded frontlight and touch — is moot
   if it cannot be bought. It had already been showing 0 in stock at $54.
2. **The 10.3" datasheet answers more than it looked like it did.** It was in
   `datasheets/e-ink_display/` throughout; the frontlight pinout is in the **title block of the
   mechanical drawing on p.2**, not in §5 "Input / Output Interface". `frontlight.md` §0.

There is now **one** panel, not a prototype panel and a product panel, so several "which candidate"
branches below are dead weight and are marked as such rather than deleted — the reasoning is still
the record of how the decision was reached.

What the decision closed:

| | Was blocked on | Now |
| --- | --- | --- |
| `frontlight.kicad_sch` | frontlight FPC pinout + drive spec | **designed** — `frontlight.md`. `LM3630A`, 2 × 9 series, from `+VSYS_FL` |
| `epd_power`'s `VGH` | whether the 10.3" would be used | **designed** — `epd-port.md` §10. `R1117` 22 k → 20.5 k, one resistor |
| Board outline | the panel's dimensions | module is **174.4 × 216.7 × 1.93 mm**, 110 g ‡ |
| Resolution / Caster variant | the panel | 1872×1400 padded (§4), and **16-bit** — the panel is `D0`–`D1106` ‡ |
| Cell size and position | the cell choice | `PL706090`, **60 × 90 × 7.0 mm** — `battery.md` §9 |

`layout.md` §1's three blocking decisions are therefore down to **one**: where the SoM sits.

**Still open, and now genuinely vendor-blocked rather than choice-blocked:** the frontlight's LED
current per channel (`frontlight.md` §10.1) and the touch tail pinout (`io-expansion.md` §5). §7.

## 1. The rule for reading every number below

**There are two independent rate budgets, and conflating them is what made the first pass of this
analysis wrong.**

| | What it is | Set by | Limits |
| --- | --- | --- | --- |
| **Input link rate** | SoM DPI → FPGA | the video timing the SoM emits | **165 MP/s** AM62x DPI (TRM Table 12-361) · **133 MP/s** Caster with error-diffusion dithering, 200 without · **360 MP/s** DDR3L-800 ×16 memory (`README.md:1096`) |
| **Panel scan rate** | FPGA → glass | **`clk_epdc`, a fixed 33.33 MHz oscillator** (`sysclock.v:53`) and the panel timing | the panel's own spec |

They are separate clock domains joined through the DDR3 framebuffer. `framecap_en` (hold) is the
proof in practice: the framebuffer freezes while the glass keeps being scanned.

**Consequence: a 40 Hz input link does not mean 40 Hz greyscale waveforms.**
`Project_description.md:246`'s "grayscale rendering wants 85 Hz" is about the *panel* side, which
comes from `clk_epdc` and not from the link. Derivation in `fpga.md` §16.
**Inferred from RTL, not measured — confirm at bring-up.**

## 2. What changed on 2026-08-16, and why it matters

`NOTES-R2-plan.md` constraint 2 used to read *"Design the video link for 75 Hz; operate at 50 Hz"*.
The owner corrected it: **75 Hz was never a requirement.** It had been read off the repo as a
maximum and then treated as a spec. The actual requirement is a fluid reader — *"maybe even 40 Hz
is acceptable"*.

That single number was **the binding constraint on panel size, and it was the only one.** Every
conclusion below that looks generous compared to earlier notes is downstream of this correction.

## 3. Candidates

**Historical as of 2026-08-17** — the middle column won (§0). `GDE060F3-FT01` is **EOL**.

| | ~~`GDE060F3-FT01`~~ **EOL** | **`GDEP103TC2-FT11` ← chosen** | `ED060KC1` family |
| --- | --- | --- | --- |
| Size / resolution | 6", 1024×758 | 10.3", 1872×1404 | 6", 1448×1072 |
| Density | 212 ppi | 227 ppi | **300 ppi** |
| Interface | parallel TTL, 34-pin | parallel TTL **16-bit**, 40-pin (`196033-40041`) | TTL, 34P-A |
| Greyscale | 16 | 16 | 16 |
| Frontlight | bonded, **2.8–3.6 V** | bonded, **27 V**, 18 LED, dual-channel 9-series, cool+warm, 8-pin | none |
| Touch | bonded, **`FT5436`** | bonded, **`GT9110H`**, 2×14 | none |
| X×Y ÷ 128 | 776 192 → 6 064 ✓ | 2 628 288 → 20 533.5 ✗ | 1 552 256 → 12 127 ✓ |
| Link @ 40 Hz | 34 MP/s | **113 MP/s** | 68 MP/s |
| Link @ 50 Hz | 43 MP/s | 141 MP/s | 85 MP/s |
| Link @ 75 Hz | 65 MP/s | 211 MP/s ✗ | 127 MP/s |
| In-repo adapter | `pcb/34p-adapter-a` | `pcb/40p-adapter-ab` | `pcb/34p-adapter-a` |
| Sourcing | **$54, 0 in stock** — enquiry sent | listed | Waveshare sells the raw panel; salvage is the other route |

Link figures are `README.md:1109-1117`'s CVT-RBv2 table rescaled linearly by frame rate.

### 3.1 The 10.3" against the limits

| Input rate | MP/s | DPI ≤165 | Dither ≤133 | Memory ≤360 |
| --- | ---: | :---: | :---: | :---: |
| 75 Hz | 211 | ✗ | ✗ | ✓ |
| 60 Hz | 169 | ✗ | ✗ | ✓ |
| 50 Hz | 141 | ✓ | ✗ | ✓ |
| **40 Hz** | **113** | **✓** | **✓** | **✓** |

**At 40 Hz it clears every limit, dithering included.** It failed only against the retired 75 Hz
number.

Better still, its datasheet §6 Mode 3 specifies **SDCK 33.33 MHz, 8 pixels/SDCK, FR 84.99 Hz** —
`clk_epdc` exactly, with 234 clocks × 8 px = 1872 ✓. **The panel side needs no gateware clock
change at all**, and the glass still gets 85 Hz greyscale waveforms while the link idles at 40.

### 3.2 Not yet sourced, and the ones actually worth asking for

Found 2026-08-16 by tracing the model code on an E Ink shopkits listing back through
`README.md`'s panel table. **`VD1400` is an E Ink panel-model family, and it contains TTL members**
— the shopkits product happens to be an integrated-controller sibling (§8), but these two are not:

| | `ED070KC4` | `ES080KC2` |
| --- | --- | --- |
| E Ink model | **`VD1400-GOC`** | **`VD1400-HOB`** |
| Size / resolution | 7", 1680×1264 | 8", 1920×1440 |
| Density | **300 ppi** † | **300 ppi** † |
| Platform | Carta 1200 | Carta 1200 |
| Interface | **TTL** | **TTL** |
| X×Y ÷ 128 | 2 123 520 → **16 590 ✓** | 2 764 800 → **21 600 ✓** |
| Link @ 40 Hz | **92 MP/s ✓** | **119 MP/s ✓** |
| Link @ 50 Hz | **115 MP/s ✓** | 149 MP/s ✗ (dither), ✓ without |
| Link @ 60 Hz | 138 MP/s ✗ | 179 MP/s ✗ |
| README row | `1333` | `1355` |

† derived from the diagonal, not read off a datasheet. Rates are active pixels × rate × ~1.08
blanking, cross-checked against `README.md:1109-1117`.

**`ED070KC4` looks like the best fit this project has found.** 300 ppi at 7", exactly
128-divisible, comfortably inside every limit at 40–50 Hz, on a current platform — and
`Project_description.md:251` independently says *"6"–7" is comfortable"*. It is bigger than the
`ED060KC1` family at the same density.

**`ES080KC2` is the Sage-class panel from §9**, and at 40 Hz it clears every limit including
dithering. That is the size the product brief actually asks for.

Neither has been priced, and **neither is known to be available in single quantities or with a
bonded frontlight and touch layer** — which is exactly what to ask about. Connector type is also
blank in `README.md`'s table for both; `ED078KC1` in the same size class is 40P-A.

## 4. The 128-pixel rule, in practice

Caster requires X × Y to be a multiple of 128. It is DDR3 burst alignment — 256 bytes per command
÷ 2 bytes of waveform state per pixel — and has nothing to do with e-paper. Full derivation in
`fpga.md` §16.

`README.md:1141` already establishes the workaround: pad down and leave the remainder unused
(2200×1650 → 2200×1648 on a 13.3"). For the 10.3":

> **1872 × 1400 = 2 620 800 ÷ 128 = 20 475 ✓ — 4 unused lines out of 1404.**

0.28 % of the height, **0.45 mm** at the 112 µm pitch. 1872 = 2⁴ × 117 and 1404 = 2² × 351, so the
product carries 2⁶ and is one factor of two short; dropping Y to the nearest multiple of 8 supplies
it. Trimming X instead would cost 16 columns, so Y is the better of the two.

**Accepted by the owner, 2026-08-16: pad, don't fix.** The proper fix — short-final-burst handling
in `memif.v` — is `fpga.md` §12 item 6, deferred until a panel is on the bench.

## 5. What each candidate costs elsewhere on the board

Rewritten 2026-08-17 for the chosen panel. Every row below is now a real consequence, not a
comparison.

| Sheet | Impact |
| --- | --- |
| `frontlight` | **Redesigned, hold lifted.** A bonded film's tail is bare `LED1±`/`LED2±`, so the board needs a constant-current driver — `LM3630A` from `+VSYS_FL`, 2 channels, 256 exponential dimming steps. `+5V2_FL` and `U1300`'s `TPS61022` are deleted. **Costs one new 8-pin FPC connector**, which the board does not have and the adapter cannot supply. `frontlight.md` |
| `epd_power` | **`VGH` must reach 27–29 V** ‡ and the R1 chain tops out at ~26.87 V (`fw/User/power.c:286`). Fixed by **`R1117` 22 kΩ → 20.5 kΩ**, one resistor on a frozen sheet; the DAC's gain is untouched, so firmware needs one constant changed. Full derivation and the tolerance corners in `epd-port.md` §10 |
| `io_expansion` | `J1400`'s six signals are still right — the datasheet ‡ confirms the module presents **I²C at 3.3 V with SDA/SCL pull-ups already on the module**, so our pull-ups should become DNP. The **pad order** now needs `GT9110H`'s tail pinout, not `FT5436`'s. `io-expansion.md` §5.1 |
| `epd` | ~~`J1000` is 50-pin and covers 16-bit via `pcb/40p-adapter-ab` … **No change to this frozen sheet.**~~ **Superseded 2026-08-30.** The owner's folded-flex decision (`layout.md` §1.2) removed the adapter, so `J1000` is now a **40-pin `XF2M-4015-1A`** wired straight to the panel tail. `+5V2_FL` (with `C147`) and the three `FL_*` pins are deleted rather than left unused. `epd-port.md` §9.5 |
| `power_mon` | **No change.** Keeping the frontlight on `+VSYS_FL` leaves the `U1201` ch3 shunt exactly where WP2 put it. `frontlight.md` §4.1 |
| `mcu` | **`FL_PWM2` is freed** and returns to the spare pool; cool/warm balance goes over I²C. ~~`FL_INT#` wants one pin in exchange.~~ **Done 2026-08-30** — `PB7` retired, and `FL_INT#` was itself withdrawn on 2026-08-23. `mcu.md` §16.1 |
| Firmware / gateware | Resolution **1872×1400** (§4), Caster **16-bit** — the tail is `D0`–`D1106` ‡ — and `power_set_vgh()`'s constants need re-measuring |

## 6. The plan — superseded 2026-08-17

**The two-panel plan is dead.** It read: buy `GDE060F3-FT01` (6") first as the complete
frontlight-and-touch module, then a 10.3" for the bigger product. **The 6" is EOL** (§0), so there is
one panel and it is the 10.3".

What survives from that reasoning, and matters more now:

1. **The 10.3" is also the frontlight-and-touch testbed**, because it is a complete `-FT` module too
   — 27 V bonded frontlight, bonded `GT9110H` touch. So `NOTES-R2-plan.md` constraint 3's "touch and
   pen get unpopulated FPC connectors" is worth revisiting: the frontlight is now a **populated**
   circuit on board 1 (`frontlight.md`), and touch could be as well.
2. **Short-final-burst handling in `memif.v` still comes later** (`fpga.md` §12 item 6). Padding to
   1872×1400 costs 4 lines of 1404 — 0.45 mm at the 112 µm pitch (§4).
3. **227 ppi, and the density question does not reopen.** At 10.3" the 1872×1404 panel is 227 ppi
   against the `ED060KC1` family's 300. That is a real step down per-pixel, but §9's tension resolves
   the other way now: this is the largest panel this controller generation can drive at all, and it
   is 2.63 Mpx against the 6"'s 0.78.

## 7. Documents to request from the vendor — revised 2026-08-17

Four items were listed on 2026-08-16. **Two are answered, one is void, and one remains** — plus one
new question from the battery.

| | Item | Status |
| --- | --- | --- |
| 1 | Frontlight FPC pinout | **ANSWERED** — in the mechanical drawing's title block. `frontlight.md` §0 |
| 2 | Frontlight **drive spec** | **STILL OPEN — the LED current per channel.** Voltage (27 V), arrangement (2 channels, cool + warm) and dimming (ours to choose) are all answered; current is stated nowhere. `frontlight.md` §10.1 |
| 3 | Touch tail pinout | **STILL OPEN**, and it is `GT9110H`, not `FT5436`. The signal set is confirmed as I²C 3.3 V with on-module pull-ups ‡; only the connector and pad order are missing. `io-expansion.md` §5 |
| 4 | Full `GDE060F3-FT01` datasheet, stock, lead time | **VOID** — EOL (§0) |

**The one frontlight question, phrased so it cannot be answered vaguely:** *"For `GDEP103TC2-FT11`,
what is the rated and maximum forward current per frontlight channel (`LED1+`/`LED1−` and
`LED2+`/`LED2−`), and how many LEDs are in series per channel?"* The design holds anywhere from
15 mA to 28.5 mA per channel, so this bounds the margin rather than the design — but above 28.5 mA
the driver changes (`frontlight.md` §3.3).

**New, for the battery supplier** (`battery.md` §9): the `PL706090`'s NTC type — R at 25 °C and its
β, or an R–T table. Two resistor values depend on it, and `battery.md` §10.2's ratio is fixed by the
charger, not by the thermistor, so any answer resolves it in one step.

**Still worth asking Good Display, and the payoff is larger now than it was:** they evidently do
custom frontlight + touch bonding — the `-FT` suffix is exactly that. **Whether they will bond a
frontlight and touch layer onto a 300 ppi panel** (`ED060KC1`-class, or the `ED070KC4` in §3.2) is
the question that would give this project a reading-quality panel rather than a 227 ppi one. It is
not a board-design blocker; it is a product question for R3.

## 8. Rejected

**`GDEY075T7-T01`, 7.5" 800×480** — evaluated 2026-08-16, rejected on the spot. It is a screen
**with an integrated controller** (`UC8179`, SPI, on-panel LUT in flash): datasheet p.4 §1 lists
"gate buffer, source buffer, timing control logic, oscillator, DC-DC, SRAM, LUT, VCOM" inside the
module. There is no source/gate bus to drive, so Caster, the DDR3 framebuffer and the EPD HV chain
would all sit unused. Its `T update` is **3 s typ** (p.36 §8) against Caster's per-pixel updates,
and it is 1-bit B/W at 124 DPI. `README.md:179` lists 7.5" under "screens with controller", which
is the tell.

Its one useful contribution is in `io-expansion.md` §5.1: a real 6-pin `GT911` touch FPC pinout,
which is evidence toward the `J1400` pad order even though the panel itself is unusable here.

**E Ink shopkits `VD1400-GOE`, 7" 960×640** — evaluated 2026-08-16, rejected. The listing says
*"All-in-one IC include Drive、TCON、PMIC and Temp Sensor"*: **the timing controller is inside the
panel**, which is the job Caster exists to do. 960×640 at 7" is also ~165 ppi, and the module needs
a THOR driving board ($150) and a Loki accessory ($200) on top of its own $149. Useful only for
having led to §3.2 — it is a sibling of `VD1400-GOC`/`ED070KC4`, which *is* TTL.

**SeeKink `B082A03`, 8.2" 1440×1920** — evaluated 2026-08-16, rejected. **SPI**, *"Built-in
T-con"*, and a **15–18 s full refresh**. The glass itself is desirable — 292 ppi at 8.2" is very
close to what the product wants — but the interface makes it unusable here. Its controller-less
equivalent is `ES080KC2` in §3.2. Worth asking SeeKink whether they sell the bare panel.

### 8.1 How to screen a listing without reading the datasheet

Both rejections above, and `GDEY075T7-T01`, were decidable from the product page alone. The tells:

| **Reject** — integrated controller | **Keep looking** — controller-less |
| --- | --- |
| "SPI" or "I²C" interface | "parallel", "TTL" |
| "built-in T-con", "integrated controller", "all-in-one IC" | needs external `VGH`/`VGL`/`VPOS`/`VNEG`/`VCOM` |
| refresh quoted **in seconds** | refresh not quoted at all — it depends on *our* controller |
| "on-chip display RAM", "waveform stored in flash" | 34 / 39 / 40 / 50-pin FPC |
| "needs only a few capacitors, inductors and MOSFETs" | signals named `XCL`/`XLE`/`XOE`/`XSTL`, `CKV`/`SPV`/`MODE` |

`README.md:179` is the quick sanity check on size alone: 1.02"–5.83", 7.5" and 12.48" are
overwhelmingly integrated-controller parts; 4.3", 6.0", 7.8", 8.0", 9.7", 10.3", 13.3" and up are
overwhelmingly not.

**The question to put to a supplier is therefore not "does it have touch and frontlight" but
"do you sell the controller-less parallel/TTL panel, and will you bond a frontlight and touch layer
onto it".** The second half is the hard part — §7.

## 9. The tension worth keeping in view

`Project_description.md:27` targets *"a Kobo Sage equivalent"* — 8", 1440×1920 = 2.76 Mpx, which is
**more pixels than the 10.3" candidate**. `Project_description.md:250` already concluded that
Sage-class needs ~177 MP/s at 60 Hz and is over both the input and dithering limits.

At 40 Hz that becomes ~118 MP/s and would fit — so the 75 Hz correction moves Sage-class from
"impossible on this controller" to "arguable". It is not proven, and nothing in this repo has run a
panel that large. **Do not treat it as settled**; it is a reason to keep the question open rather
than a reason to design for it now.

## 10. Open — revised 2026-08-17

1. **Nothing is ordered.** The panel is chosen, not bought.
2. **The frontlight LED current** — §7 item 2, `frontlight.md` §10.1. Bounds the margin, not the
   design.
3. **The touch tail pinout** — §7 item 3, `io-expansion.md` §5. Still the last open Stage C decision.
4. ~~**`GDE060F3-FT01`'s interface width**~~ — void, EOL.
5. ~~**`VGH` 27 V against a ~26.87 V ceiling**~~ — **CLOSED**, `epd-port.md` §10. One resistor.
6. **Two panel numbers are inferred, not read:** that the frontlight is 2 × 9 series (from 27 V ÷ 9,
   `frontlight.md` §1) and the 227 ppi figure (from the diagonal). Neither is load-bearing.
7. **Nothing here has been tested on hardware.** Every rate figure is arithmetic over
   `README.md`'s tables and datasheet numbers; the `clk_epdc` decoupling is read from RTL; and the
   two designs this decision unblocked (`frontlight.md`, `epd-port.md` §10) are datasheet arithmetic
   whose firmware constants must be re-measured on the bench.
