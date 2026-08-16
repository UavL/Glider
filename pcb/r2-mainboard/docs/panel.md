# Panel selection — which E Ink panel Reflow is designed around

Status: **open, actively being sourced as of 2026-08-16. Nothing is ordered.** Companion to
`epd-port.md` (the connector and HV chain), `frontlight.md` (on hold because of this decision) and
`io-expansion.md` (touch, likewise). The gateware side is `fpga.md` §16.

The panel had been deferred alongside touch and pen. The hardware owner began sourcing on
2026-08-16, which turned it from "read it off the tail label later" into the decision that several
frozen sheets now depend on.

---

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

| | `GDE060F3-FT01` | `GDEP103TC2-FT11` | `ED060KC1` family |
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

| Sheet | Impact |
| --- | --- |
| `frontlight` | **ON HOLD.** The 4.99 V rail suits neither candidate, and a bonded frontlight film needs a **constant-current driver this board does not have**. The premise in `frontlight.md` §2 — "the panel's tail regulates the current" — is true of R1's adapter and false for a bonded film. `frontlight.md` §0 |
| `io_expansion` | `J22`'s six signals (`VCC`/`GND`/`SCL`/`SDA`/`INT`/`RST`) are right for **every** candidate; the **pad order** is still open and now needs `FT5436`'s FPC pinout. `io-expansion.md` §5.1 |
| `epd_power` | `GDEP103TC2` wants **`VGH` 27–29 V**; `fw/User/power.c:287` records the R1 chain topping out at **~26.87 V** at DAC = 0, with the comment *"Valid range: 22V - 27V"*. A ~1 V shortfall — the `U23`/`U24` feedback divider would need revisiting, and `epd_power` is a frozen, reviewed 1:1 R1 port. **Not an issue for either 6" candidate.** |
| `epd` | `J6` is 50-pin and covers 8- and 16-bit panels (`epd-port.md` §9.3); every candidate reaches it through an adapter project that already exists. **No change.** |

## 6. The plan, as decided 2026-08-16

1. **Buy `GDE060F3-FT01` (6") first**, if it can be sourced. It is a complete module, so it is the
   one that lets **frontlight and touch be exercised on the PCB** — which is the point, given
   `NOTES-R2-plan.md` constraint 3 makes both DNP on board 1. Its pixel count is exactly
   128-divisible and it sits at roughly a third of every limit.
2. **Then a 10.3" (or similar) for developing the bigger product**, padded to 1872×1400.
3. **Short-final-burst handling comes later**, once a panel is on the bench. A few unused lines are
   acceptable in the meantime.

The 1024×758 module is **212 ppi against the 300 ppi of the `ED060KC1` family**, and that is a real
step down in reading quality. It is the right call anyway for a board whose job is to prove
compute + display + power + light + touch, but it is not the final reading experience, and the
density question reopens when a production panel is chosen.

## 7. Documents to request from the vendor

1. **Frontlight FPC pinout and drive spec** — voltage, current, series/parallel arrangement,
   dimming method. Unblocks `frontlight.kicad_sch`.
2. **Touch FPC pinout** (`FT5436`). Unblocks `io-expansion.md` §5 — the last open Stage C decision.
3. **Full `GDE060F3-FT01` datasheet** — interface width and the 34-pin assignment. The product page
   says "parallel, 22 channels", which is not enough to wire against.
4. **Stock and lead time**, since it currently lists 0 in stock.

Worth asking at the same time: Good Display evidently does custom frontlight + touch bonding — the
`-FT` suffix is exactly that — so **whether they will bond a frontlight and touch layer onto a
1448×1072 panel** is a question with a potentially large payoff. That combination does not appear
to exist off the shelf, and it is what the product actually wants.

## 8. Rejected

**`GDEY075T7-T01`, 7.5" 800×480** — evaluated 2026-08-16, rejected on the spot. It is a screen
**with an integrated controller** (`UC8179`, SPI, on-panel LUT in flash): datasheet p.4 §1 lists
"gate buffer, source buffer, timing control logic, oscillator, DC-DC, SRAM, LUT, VCOM" inside the
module. There is no source/gate bus to drive, so Caster, the DDR3 framebuffer and the EPD HV chain
would all sit unused. Its `T update` is **3 s typ** (p.36 §8) against Caster's per-pixel updates,
and it is 1-bit B/W at 124 DPI. `README.md:179` lists 7.5" under "screens with controller", which
is the tell.

Its one useful contribution is in `io-expansion.md` §5.1: a real 6-pin `GT911` touch FPC pinout,
which is evidence toward the `J22` pad order even though the panel itself is unusable here.

## 9. The tension worth keeping in view

`Project_description.md:27` targets *"a Kobo Sage equivalent"* — 8", 1440×1920 = 2.76 Mpx, which is
**more pixels than the 10.3" candidate**. `Project_description.md:250` already concluded that
Sage-class needs ~177 MP/s at 60 Hz and is over both the input and dithering limits.

At 40 Hz that becomes ~118 MP/s and would fit — so the 75 Hz correction moves Sage-class from
"impossible on this controller" to "arguable". It is not proven, and nothing in this repo has run a
panel that large. **Do not treat it as settled**; it is a reason to keep the question open rather
than a reason to design for it now.

## 10. Open

1. **Nothing is ordered.** `GDE060F3-FT01` shows 0 in stock; the enquiry is out.
2. **The four vendor documents in §7** — two of them block frozen sheets.
3. **`GDE060F3-FT01`'s interface width** is unconfirmed ("22 channels" on the product page).
   8-bit is likely on a 34-pin connector, but it decides the Caster build variant.
4. **`VGH` 27 V** for the 10.3", against a ~26.87 V ceiling (§5). Only bites if that panel is used.
5. **Nothing here has been tested on hardware.** Every rate figure is arithmetic over
   `README.md`'s tables and datasheet numbers; the `clk_epdc` decoupling is read from RTL.
