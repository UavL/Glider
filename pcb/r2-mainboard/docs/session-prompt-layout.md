# Starting a fresh session for R2 layout

Copy everything between the rules into the first message of a new Claude Code session, run from
`/home/lum/Ereader Projekt/Glider_OG`. It is written to be pasted as-is — it assumes the assistant
has read nothing and knows nothing about this branch.

Keep it up to date: whenever a session ends, the "Where the board stands" list is the part that has
gone stale.

---

I'm laying out R2 in KiCad 10 myself and want you checking my work, not doing it. Branch
`Board-Design`, board is `pcb/r2-mainboard/r2.kicad_pcb`.

**Read these first, in this order, before answering anything:**
1. `CLAUDE.md` — the ground rules. They are not negotiable.
2. `pcb/r2-mainboard/docs/layout.md` — the whole Stage D brief. §4.1 has the net classes and every
   track width with the reason attached; §4.2 explains why clearance is 0.11 mm; §6.3/§6.4 are the
   placement and routing order; §7 is the five things that destroy the board; §9 is troubleshooting.
3. The per-sheet doc for whatever circuit I'm asking about — `docs/<sheet>.md`, §11 of each is its
   layout guidance. Don't answer a layout question about a circuit without reading its §11.
4. **`NOTES-R2-osd62x-plan.md`** if the question touches the SoM corner, `som`, `dpi_in`, `power` or `mcu`
   — the compute module is switching to Octavo's `OSD62x-PM` (owner, 2026-09-11).

**Where the board stands (update this section as it changes):**
- 327 of 327 footprints imported and resolving; 322 of 327 have 3D models (`layout.md` §9.1 lists
  the five that don't and why).
- **The SoM corner is frozen (2026-09-11).** The module is switching to Octavo's `OSD62x-PM`
  (`NOTES-R2-osd62x-plan.md`); `X500`/`J501`/`J502` are still on the board but will be deleted — don't
  route to them.
- Design settings imported from R1 and 9 net classes written —
  `tools/import_r1_settings.py`, `layout.md` §4.1.
- `Edge.Cuts` holds a 185.5 × 95 mm placeholder rectangle, not the real ≈ 90 × 70 mm outline.
- **Routing is under way** (2026-09-10): 1649 segments on `F.Cu`, 279 on `B.Cu`, 77 on `In2.Cu`, 119 on
  `In3.Cu`; 323 vias. DRC after the 2026-09-10 rule and net-class changes: 365 violations — 147 errors,
  218 warnings — including **4 real shorts** (`In3.Cu` tracks across through-vias) and **39 HV-separation**
  hits; 492 unconnected items.
- **Six-layer, 0.8 mm** — owner-confirmed 2026-09-11 (`datasheets/PCB/6-layers PCB_3313.pdf`,
  `layout.md` §4.1.1): `F.Cu` sig / `In1.Cu` GND / `In2.Cu` power / `In3.Cu` sig / `In4.Cu` GND / `B.Cu` sig.
  The four-layer plan of 2026-09-03 is superseded.
- `r2.kicad_dru` and the net classes were rewritten 2026-09-10 (region-tiered DDR3 rules, HV, diff-pair
  gap; derivation in the file's comments). **They get in the way of interactive routing — open, to be
  revisited** (`NOTES-R2-osd62x-plan.md` §7).
- Placement is untouched since import outside the FPGA/DRAM corner, so most of the 33 proximity rules
  still fail. That's expected, not a bug.

**How I want you to work:**
- `python3 tools/check_pcb.py` after every session of mine — it's the machine-checkable half of
  `layout.md` §7. Read what it says before forming an opinion; the proximity failures are the
  placement backlog, in priority order.
- **Never write to `r2.kicad_pcb`, `r2.kicad_pro` or any `.kicad_sch` while KiCad is open.** KiCad
  holds the project in memory and rewrites it on save, so the edit disappears with no error. Check
  `pgrep -x kicad` and the `~*.lck` files, and ask me to close it.
- `pcb/mainboard/` is R1 and is **read-only** — KiCad 8, and opening it in 10 upgrades it
  irreversibly. Read it, copy out of it, never save into it.
- Verify with `~/Apps/kicad-10.0.4/usr/bin/kicad-cli`, not by assuming.
- Separate **verified from source** / **inferred** / **needs a hardware test** every time. You
  cannot flash, measure or observe the hardware, and this is the only dev kit.
- When you need a decision from me, ask with the question tool rather than stopping on a prose
  question.

**What's actually open, highest value first:**
1. Draw the real board outline and mounting holes, then place in `layout.md` §6.3's order —
   `J1000` and the folded-flex connectors first, since the enclosure fixes them.
2. ~~Confirm the `BTH-060` 3D model's rotation in the 3D viewer~~ — moot: the connectors are being
   removed with the `OSD62x-PM` switch.
3. Before ordering: build Caster for the `-2` speed grade (`par/ise_flow.sh`, two `-ftg256-3` →
   `-2`) — the DDR3 bus has 0.05 % margin at `U700`. Re-check `C3646540` stock. Confirm CPL
   rotation with JLCPCB (`som.md` §10.4).

---
