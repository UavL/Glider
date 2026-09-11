# What 1 000 units would cost, and what a campaign would have to raise

Written 2026-08-31 at the owner's request, after Good Display quoted a custom touch panel at
**US$750 tooling / MOQ 1 000 per lot** (`pcb/r2-mainboard/docs/io-expansion.md` §5.2). That MOQ is
the first hard number attached to a production run, so this is the first attempt at costing one.

**This is a planning document, not a quote.** Every line is marked for confidence. Two of them are
guesses that move the answer by six figures, and they are named in §5 so they can be replaced with
real numbers rather than argued about.

---

## 1. The two facts that dominate everything

> **2026-09-11 — the SoM line changes.** The owner confirmed the switch to Octavo's `OSD62x-PM`
> (`NOTES-R2-osd62x-plan.md`). The module becomes `OSD6254-1G-IPM` at **$22.50 list** (web handoff, not
> re-verified) plus a `TPS65219` PMIC (**$3.12–4.14** on LCSC, 2026-09-10), a load switch, a crystal and
> boot storage (unpriced); the two `BTH-060` receptacles (**$12.98**) disappear. That lands at or below
> §4.2's **€60 row — a goal of ≈ €400 k** — *inferred, not recomputed*. The board also went to six layers,
> which the PCBA line in §3 does not reflect. §3–§4 have not been redone.

**The SoM costs more than the display.** `som.md` §9: PHYTEC quoted `PCM-071` at **€250.00 @ 1–9 pcs**
(2026-08-18, order code `C618992`). The display is €140 at single quantity.

⚠ **And most of that €250 may be a market condition, not a price.** `NOTES-R2-hardware-facts.md`
records the sibling quote: `PCL-071-001-R` at €281 @1–9, where **"the price includes ~€190 of
memory-shortage surcharge."** If the same holds for the `PCM-071`, the underlying module is nearer
€60 and €190 is transient. **Nobody has asked PHYTEC for a 1 000-piece price.** Until someone does,
every total below carries a ±€290 000 uncertainty on the goal.

## 2. Component prices actually checked

LCSC, 2026-08-31, at the quantities LCSC shows — i.e. these are **ceilings**, not volume pricing.

| Part | Ref | Each |
| --- | --- | ---: |
| `BTH-060-01-L-D-A-K-TR` | `J501`, `J502` | **$6.49 × 2 = $12.98** |
| `MT41K64M16TW` DDR3L | `U800` | $7.95 |
| `XC6SLX16-2FTG256C` | `U700` | $7.79 |
| `STM32G0B1RET6` | `U400` | $6.24 |
| `BQ25892RTWR` | `U1` | $3.06 |
| `W25Q128JVSIQ` | `U42` | $2.45 |
| `TYPE-C-31-M-12` | `J1`, `J1402` | $0.19 × 2 |

The board carries **331 placements**: 141 C, 114 R, 28 U, 12 D, 12 J, 10 L, 6 Q, 3 SW, 2 X, plus a
fuse, a ferrite and the crystal.

Worth noticing: **the two SoM receptacles cost more than the FPGA.** That is a direct consequence of
choosing the connectorised `PCM-071` over the solder-down `PCL-071`, which was the right call for a
prototype (`NOTES-R2-hardware-facts.md`) and is worth revisiting at volume — see §5.

## 3. Per-unit COGS at 1 000 units

| Item | €/unit | Confidence | Basis |
| --- | ---: | --- | --- |
| Display `GDEP103TC2-FT11` | 110 | med | €140 single; e-paper discounts modestly |
| **SoM `PCM-071`** | **90 – 160** | ⚠ **low** | §1 |
| Mainboard PCBA — PCB + 331 parts + assembly incl. BGA | 60 | med | §2 extrapolated with reel pricing |
| Case, injection-moulded, tooling amortised over 1 k | 18 | low-med | ~€12 k tool + ~€6 material |
| Custom touch panel, after tooling | 15 | med | Good Display, 10.3" PCAP |
| Battery `PL706090` | 9 | med | €14 single |
| Cover lens, flex, fasteners, magnets | 8 | low | not designed yet |
| Packaging | 4 | med | |
| **Total** | **314 – 384** | | central **€340** |

## 4. The goal

```
COGS             1 000 × €340                    = €340 000
NRE              §4.1                            =  €29 700
Fulfilment       1 000 × €18 shipping            =  €18 000
Spares/failures  4 % of units                    =  €13 600
                                                   ─────────
                                                   €401 300
contingency 25 % — hardware, first production run = €100 300
                                                   ─────────
                                                   €501 600
÷ (1 − 8.5 %) platform + payment processing        ─────────
GOAL                                             ≈ €548 000
```

**≈ €550 000, or €550 per unit delivered.**

### 4.1 One-off costs

| | € | Confidence |
| --- | ---: | --- |
| Touch panel tooling — Good Display's US$750 | 700 | **known** |
| Case injection tooling | 12 000 | low — depends on geometry nobody has drawn |
| PCB stencil, assembly setup, first article | 1 500 | med |
| CE / EMC testing — EN 55032 / 55035. **No radio, so no RED** | 5 000 | med |
| FCC Part 15B, if selling into the US | 3 500 | med |
| Certification admin, DoC, labelling | 1 000 | med |
| Board respins and sample rounds before production | 6 000 | low |
| **Total** | **29 700** | |

### 4.2 Sensitivity — the SoM is the whole game

| SoM @1 k | COGS/unit | Goal |
| ---: | ---: | ---: |
| €250 — no volume discount at all | €430 | **€690 k** |
| €160 | €340 | **€548 k** |
| €90 | €270 | **€432 k** |
| €60 — surcharge fully gone | €240 | **€400 k** |

One quote request moves this by **€290 000**. It is the highest-value hour of work available.

## 5. ⚠ The unit economics, stated plainly

At the central estimate, landed cost is **~€360/unit** before margin, marketing, returns, warranty or
anybody's time. Market comparables for a 10.3" e-reader: reMarkable 2 ≈ €400, Boox Note Air4 C ≈
€500, Boox Tab Ultra ≈ €600.

**So at €340 COGS the margin at a competitive price is thin to negative.** That is not an argument
against the project; it is an argument for attacking the two big lines *before* committing to a
campaign, because both are addressable:

1. **Get a 1 000-piece SoM quote, and ask what the memory surcharge is today.** Re-price `PCL-071`
   (solder-down) at the same time: it removes the **$12.98 of `BTH-060` receptacles** as well, so the
   combined saving could exceed €80/unit. The trade is that a soldered module must be consigned to
   the fab — a real complication at 1 000 units, and much less of one than at 1.
2. **Ask Good Display for 1 000-piece display pricing.** The €140 is a distributor single price and he
   has already opened the door on volume terms for the touch panel.
3. **Longer term: a bare AM62x plus our own DDR** replaces a €90–250 module with perhaps €35 of
   silicon. That is a serious engineering programme and explicitly *not* an R2 change — but it is the
   standard path once volume is real, and it is what makes these numbers work at scale.

## 6. What this document is missing

- **No case design exists**, so both the tooling figure and the per-unit plastic are guesses.
- **1 000 units is an awkward volume** — low for injection moulding, low for reel pricing, high for
  anything hand-finished. Some of these lines behave very differently at 500 or 5 000.
- **No margin, marketing, support or warranty reserve** is included. A campaign that raises exactly
  the goal above delivers 1 000 units and earns nothing.
- **VAT, duties and import handling** are not modelled and differ per destination.
- **The frontlight is bonded into the panel**, so it is inside the display line, not separate.
