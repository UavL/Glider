# Session handoff — regenerated 2026-08-17 (evening)

**This file is a dated snapshot, not a source of truth.** If it contradicts `NOTES-R2-plan.md`,
`NOTES-R2-hardware-facts.md` or any `pcb/r2-mainboard/docs/*.md`, **those win** — they are
maintained, this is not. Delete or regenerate it once it stops matching.

This replaces the morning's version, which was written before the panel was chosen and was wrong
about four things by the end of the day.

---

## 1. Orientation

**Reflow** (codename; `Blatt` is a *candidate* company name, not decided) is an open low-latency
e-ink reader built on the Modos **Caster + Glider** stack. Branch `Board-Design` is designing
**R2**, a battery e-reader mainboard, because R1 cannot be fixed in firmware — 82 % of its idle draw
sits on bucks whose enable pins are hardwired on.

Read in this order: **`CLAUDE.md`** → **`NOTES-R2-plan.md`** → **`pcb/r2-mainboard/docs/<sheet>.md`**
(read a sheet's doc before touching its `.kicad_sch`) → **`NOTES-R2-hardware-facts.md`**.
`NOTES-STATUS.md` is R1's measured state and is still current for anything hands-on.

## 2. What changed on 2026-08-17, which is most of what matters

**The panel was chosen, and it cascaded.**

1. **`GDEP103TC2-FT11`, 10.3", 1872×1404** — `panel.md` §0. The 6" `GDE060F3-FT01` front-runner
   turned out to be **EOL**, which collapsed the two-panel plan into one panel.
2. **The frontlight datasheet had been in the repo all along.** The pinout is in the **title block
   of the mechanical drawing on p.2**, not in the numbered I/O section. The sheet had been on hold
   since 2026-08-16 waiting for a document already on disk. Lesson in `frontlight.md` §0.
3. **`frontlight` was redrawn from scratch and captured.** A bonded film's tail is `LED1±`/`LED2±` —
   bare anodes and cathodes — so it needs constant **current**, not a rail. `U53` is an `LM3630A`
   driving two independently dimmed strings; `+5V2_FL`, the `TPS61022` and its divider are gone; a
   new 8-pin FPC `J24` carries the tail.
4. **`epd_power`'s `VGH` needs one resistor changed** — `R225` 22 kΩ → 20.5 kΩ, derived and
   tolerance-checked in `epd-port.md` §10. **Not applied**: that sheet is frozen and reviewed, so
   the edit should ride with the owner's review pass.
5. **The cell is chosen** — `PL706090`, and it closed two open items in `battery.md` while raising
   two new ones (§9.1).
6. **`layout.md` §1 went from three blocking decisions to one.**

## 3. Where the work stands

**Stage C — capture — is COMPLETE.** All 14 sheets drawn, root wired.

| | |
| --- | --- |
| Root nets | 108 names, **107 joined, 1 one-sided** (`FL_INT#`, declared in `wire_root.py`'s `DANGLING_OK`) |
| `tools/check_ucf.py` | **0 failures** |
| ERC | 338 total, **305 `footprint_link_issues`** (the owner's broken global tables — ignore); 33 excluding those, one of which is `FL_INT#`'s dangling label |
| Unresolved footprints | **1** — the `PCM-071`'s, an owner download |

**Stage D — layout — has NOT started.** `r2.kicad_pcb` does not exist.

**Review status:** WP1–WP5 reviewed. **WP6 (`frontlight`, `io_expansion`), WP7 (`dpi_in`),
WP8 (`som`) are drawn but NOT reviewed.** `frontlight` is the newest and least examined.

## 4. Blocked — and on whom

| # | Blocked on | Unblocks |
| --- | --- | --- |
| 1 | **Where the SoM sits, and on which side** — `layout.md` §1.2 | **Stage D placement. The only blocker.** |
| 2 | **Frontlight LED current per channel**, and whether 28.5 mA is per-channel or combined | the full-scale register and `L33`'s margin — *not* the design, `frontlight.md` §10.1 |
| 3 | **`GT9110H` touch tail pinout** | `io-expansion.md` §5 — the last open Stage C decision |
| 4 | **Cell NTC type** (R25, β) | `battery.md` §10.2's `R9`/`R10` |
| ~~5~~ | ~~**Cell connector**~~ | **DECIDED 2026-08-18** (`7b73727`): `J2` → Molex Pico-Lock `504050-0391` (3.5 A, 2.00 mm mated), plus `J25`, three solder pads on the same nets. The pack still has to be re-terminated |
| 6 | ~~**`PCM-071` price/MOQ**~~ **priced 2026-08-18: €250 @1–9, MOQ 1** — lead time still unstated. **Its footprint** (`X2`, `footprints:PCM-071_2xBTH-060-01-L-D-A-K`) is still the one unresolved footprint | ordering |
| 7 | **KiCad global library tables** (Preferences → Configure Paths) | the 305 `footprint_link_issues` |
| 8 | **Order `LM3630A` from DigiKey** (`296-46302-1-ND`) — LCSC `C2678552` is at 0 | building board 1 |

## 5. Next steps

**A. Owner:** ~~send the vendor questions~~ **sent 2026-08-18**; decide the SoM position and review
WP6–WP8. ~~decide the cell connector~~ **decided.** Also outstanding: forward PHYTEC's *technical*
reply — their pricing mail refers to a colleague's answer that has not reached this repo, and it is
the one carrying questions 2–4 (`NOTES-R2-plan.md`, "Follow-up enquiry").

**B. Assistant, unblocked today:**
1. `NOTES-R2-hardware-facts.md` has none of this session's evidence — the `LGS6302` `D_MAX`, the
   `MAX17048` address collision, the `LM3630A` numbers, the panel and cell dimensions.
2. `fpga.md` needs the panel's consequences recorded: Caster builds **16-bit**, resolution
   **1872×1400**, 40 Hz link.
3. `fpga.md` §9.5 — 10 duplicate `#PWR` references make every netlist export warn.
4. The `Specter` → `Reflow` rename: 13 title blocks plus the generators that emit the string.

**C. When the panel arrives:** `power_set_vgh()`'s constants are **computed, replacing empirical
ones**, and must be re-measured (`epd-port.md` §10.5).

## 6. Ground rules — from the hardware owner, not negotiable

- **The assistant cannot flash, measure or observe the hardware.** Never claim a behaviour was
  confirmed on it.
- **This is the only dev kit.** Nothing may risk bricking it.
- **Do not modify anything outside this repo.**
- **Always separate verified-from-source / inferred / needs-a-hardware-test.**
- **`pcb/mainboard/` (R1, KiCad 8) is read-only.** Opening it in KiCad 10 upgrades it irreversibly.
- **A sheet that has been saved in Eeschema is patched surgically, never regenerated.** Check before
  assuming: `frontlight.kicad_sch` was safe to regenerate today only because its line multiset
  matched a fresh generator run exactly, proving it had never been opened.
- **Ignore `footprint_link_issues`.**
- **Verify with `~/Apps/kicad-10.0.4/usr/bin/kicad-cli`, and render the page to a PNG and actually
  look at it before calling it done.**
- **Do not stop with a prose question — use `AskUserQuestion`.**

## 7. Mistakes worth not repeating

- **Four silent shorts** were created on 2026-08-16 by wires passing through label anchors, each
  invisible to ERC. `tools/schgen.py` now runs `check_label_crossings()` and `check_grid()` inside
  `render()`, so a sheet cannot be written without them. **Never bypass them.** The `frontlight`
  symbol's pin order was chosen specifically so no pull-down has to cross a signal.
- **Rendering is not optional.** `frontlight` was electrically correct and visually wrong for three
  rounds: overlapping value text, and `D34`'s reference printing **mirrored** because KiCad inverts
  a 180°-placed symbol's text. None of it shows in a netlist.
- **Check the repo before asking a vendor.** The frontlight pinout was on disk for a day while the
  sheet sat on hold.
- **Twice a panel was declared unviable and the call had to be reversed** — once by treating 75 Hz
  as a requirement when it was an upper bound, once by calling the 128-pixel rule a blocker when
  `README.md:1141` already documented the workaround. **Identify which limit actually binds, and
  check whether a constraint is a spec or an assumption, before concluding.**
- **Verify a "failure" before reporting it.** Two netlist checks "failed" today purely because the
  assertion had a resistor's pins backwards and used a pre-root-wiring net name.
- The repo's `README.md` is **upstream Modos documentation, 1421 lines**, cited constantly by line
  number. If `git status` shows it modified, check before assuming that was intentional.
