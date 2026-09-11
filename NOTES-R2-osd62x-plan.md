# R2 — switching to the Octavo `OSD62x-PM`: what we have, what is needed, and in what order

Branch `Board-Design`. Written **2026-09-11**, the day the owner confirmed the switch. **Keep §0
current** — it is the part that goes stale.

**Decision (owner, 2026-09-11):** R2's compute module changes from PHYTEC's connectorised `PCM-071`
(chosen 2026-08-13) to Octavo Systems' **`OSD62x-PM`** system-in-package, orderable as
**`OSD6254-1G-IPM`** — AM6254 + 1 GB DDR4 in a 9 × 14 × 1.3 mm, 500-ball, **0.5 mm-pitch** BGA that
is soldered to the board. The full `OSD62x` (21 × 21 mm, 1.0 mm pitch, PMIC inside) was not
chosen: it is beta/sample only and has no datasheet, so there is nothing to design against.

Background and the vendor evidence: **`HANDOFF-octavo-osd62x.md`**, written 2026-09-10 by a web
session with no local access. Its status header lists what it got wrong about this repo. Its vendor
facts are that session's reading and have **not** been re-read here yet — task E1 fixes that.

| Tag | Meaning |
| --- | --- |
| **[B]** | read from this repo or from `r2.kicad_pcb` on 2026-09-10/11 |
| **[O]** | the owner's statement |
| **[W]** | a vendor fact as reported by the web handoff — not yet re-read from the source locally |
| **[I]** | inferred — check before relying on it |
| **[H]** | needs a hardware test; nobody can confirm it without a board |

---

## 0. Where it stands

| | |
| --- | --- |
| Decision | **switch confirmed** [O], 2026-09-11 |
| Board | **six layers, 0.8 mm** [O][B] — `layout.md` §4.1.1. Routing under way on the DDR3 bus |
| SoM corner | **frozen, and effectively unrouted** — 1 of the 99 connected `J501`/`J502` pads has a track [B] |
| SiP stock | **100+ across DigiKey and Mouser**, more from Octavo direct if the product matures [O]. **Not on LCSC** [B, jlcsearch 2026-09-10] |
| Vendor documents in the repo | in `datasheets/SiC OSD62x-PM/` (2026-09-11): the `-PM` datasheet (Rev. 2.0), the BRK's Eagle files, **`SPRSP58C`** (saved as `am623.pdf` — it is the AM62x datasheet, covering AM625/AM623/AM620), and three app notes saved as web pages (power, power budgeting, schematic checklist). `TPS65219`: only the `-Q1` and `…05` datasheets so far (§3.1). **Still missing:** the layout guide, pin mapping, thermal and boot-chain notes |
| PMIC | **`TPS6521903`** — owner, 2026-09-11, after Phase 1 showed the BRK uses it and `…01` expects a 5 V input (§9) |
| Phase 1 | **done 2026-09-11** — results in **§9** and `NOTES-R2-hardware-facts.md` §3.3. E7 is answered from the fabs' published tables; a quote is still needed |
| Decisions | D1–D5 and D7–D10 **decided by the owner 2026-09-11** (§9.2) · D6 (fab) open · D11 proposed |
| Next | a fab quote for the between-ball vias (`docs/sic.md` §12) → Phase 4 capture from **`docs/sic.md`** (owner). **The eMMC symbol is generated** (`tools/gen_emmc_symbol.py`, 2026-09-12) and its footprint is KiCad's stock `LFBGA-153_11.5x13mm_Layout14x14_P0.5mm` |

---

## 1. Why — four reasons, in order of weight

1. **Cost is the business case.** `NOTES-production-costing.md` §4.2 calls the SoM "the whole game".
   €250 + $12.98 of `BTH-060` receptacles becomes **$22.50** [W] + a `TPS65219` PMIC at **$3.12–4.14**
   [B, LCSC] + a load switch, crystal and boot storage. That lands at or below the costing table's
   **€60 row — a goal of ≈ €400 k instead of €548 k** [I], without waiting on PHYTEC's memory surcharge.
2. **Supplier.** The owner had problems with PHYTEC [O]. The `-PM` is a catalogue part with a public
   price and visible stock, and everything needed to design it in — datasheet, seven app notes, an
   open-hardware reference board, the DDR4 configuration on GitHub — is public [W].
3. **The prototype tests the product.** On the `PCM-071`, R2's reading-state power would have been
   PHYTEC's module, to be thrown away later. On the `-PM` it is the product's own number.
4. **It fits this board.** Six layers give the SiP a power layer (`In2.Cu`) for its core and DDR
   rails. The handoff's main objection (§4.2 there) assumed a four-layer board with two ground
   planes and no room for power [B].

---

## 2. What we have

### 2.1 Unaffected — carries over as it is

- **Sheets** `battery`, `epd`, `epd_power`, `power_mon`, `fpga_io`, `fpga_ddr`, `fpga_config`,
  `frontlight`, `io_expansion` (except a note on the `+5V` budget) — per the handoff's §8, to be
  confirmed at capture.
- **Caster gateware** and `tools/check_ucf.py`, which must still report 0 failures after the swap.
- **The DDR3 routing done so far**, the stack-up, and every net class and rule outside the SoM corner.

### 2.2 Carries over, with changes

| Item | Today [B] | After the switch |
| --- | --- | --- |
| DPI link | 22 nets: RGB666 on `VOUT0_DATA[17:0]`, `BOOTMODE_8/9` shared with `DATA16/17` (facts §2) | same SoC, so the same signals on new balls [W]. The **boot straps become ours** (§3.1) |
| `SOM_WAKE#` / `SOM_IRQ#` | `MCU_GPIO0_14` / `_13` (`som.md` §5.1) | same SoC signals, new balls. Wake from Deep Sleep still [H] |
| MCU link | `U400` pin 10 `MCU_EN_5V`, 11 `MCU_EN_3V3`, 36 `SOM_WAKE#`, 37/42 `MCU_TXD`/`RXD`, 47 `SOM_RESET#`, 48 `PG_SOM` (`PC8`), 58 `SOM_IRQ#`; `Q400`/`R406`/`R407` drive `SOM_MCU_NRST`/`BOOT0` (`mcu.md` §5.8) | `SOM_RESET#` probably becomes a wire-AND onto the SoC's fail-safe `MCU_PORz` [I]. **`PG_SOM` has no direct equivalent** — the `TPS65219` has `nRSTOUT` and `nINT`, no power-good pin [W]. `MCU_EN_5V` no longer powers the SoC |
| microSD | `J500`, `R500`–`R504` 47 kΩ, `C510`–`C513`; the card is powered from the module's `SoC_VDDSHV5_SDIO` (`som.md` §4) | the circuit stays; its supply becomes ours (D5) |
| SPI to the FPGA + `NOR_CS` | 5 nets | unchanged [I] |
| USB | **USB0** (`USBD±`) **and USB1** (`USB1_D±`, `USB1_DRVVBUS`, `USB1_VBUS`) — both PHYs in use | keep both USB rail groups; each `VBUS` input needs a divider to 0–3.465 V [W] |
| Power | `U301` `TPS61022` → `+5V_DCDC` feeds the SoM's `VIN`; `U302` `TPS63802` → `+3V3_DCDC`, 2 A; `U303`/`U304` `TPS62A02` | `+5V_DCDC` loses its largest load (the SoM's 1.0 A bound, `power.md` §8.1); a PMIC joins the tree (D1) |
| Provisioning | `system-overview.md` §6 — the module arrives with a demo image | the board ships blank; the flow still works with an eMMC or the SD slot [I] |

**48 signal nets pass through `J501`/`J502` today** [B]: 22 DPI, 5 SPI/NOR, 2 UART, 7 SD, 6 USB,
6 control. The handoff estimated ~45.

### 2.3 The board

- **Stack-up** (`layout.md` §4.1.1): `F.Cu` signals / `In1.Cu` GND / `In2.Cu` power pours /
  `In3.Cu` signals / `In4.Cu` GND / `B.Cu` signals; 3313 prepreg, 0.0925 mm under each outer layer;
  **ENIG**, which the SiP's 0.20 mm lands need [B][W].
- **SoM corner**: `J501` at x 240.0–246.1, `J502` at x 262.4–268.5, y ≈ 56–94 mm, on `F.Cu`, with
  `X500`'s outline between them. `In2.Cu`'s `VSYS` pours run along the corner's top edge [B].
- **Rules**: `r2.kicad_dru` (region-tiered, 2026-09-10), via floor 0.45/0.3 mm, clearance floor
  0.11 mm. The SiP wants **0.25/0.15 mm vias and ~0.10 mm trace/space locally** [W] — see E8 and §7.

### 2.4 Documents and parts in hand

- `datasheets/Power/`: `tps22965.pdf` (the 3.3 V IO switch), `tps63802.pdf`, `tps62a01.pdf` [B].
- `datasheets/SoM Phycore AM62x/`: PHYTEC's documents — now the record of the old design.
- **In `datasheets/SiC OSD62x-PM/` since 2026-09-11:** the `-PM` datasheet (Rev. 2.0), the 2024 overview,
  the BRK's Eagle design files, and `osd62x_pm_pinout.json` (`tools/parse_osd62x_pinout.py`).
  **Still not in the repo:** `SPRSP58`, Octavo's app notes, the `TPS65219` datasheet and NVM manuals,
  anything on an eMMC.

### 2.5 What we give up

- **PHYTEC's measurements** — 128.6 mW Suspend-to-RAM, ~150 ms wake (facts §4.6). They no longer
  apply, and nothing replaces them until R2 is measured [H]. Octavo's reference board draws ~0.25 W
  in Deep Sleep, but was not designed for low power [W].
- A working BSP and a module that boots out of the box.
- The module's own eMMC, QSPI NOR, PMIC, sequencing and boot-strap pull-ups — all now our design.
- A socketed part: a dead board no longer hands its SoM on. At $22.50 that matters little.

---

## 3. What is needed

### 3.1 Parts to add — page 5, so `U5xx` / `R5xx` / `C5xx` / `Y5xx` per `CLAUDE.md`

| Part | Role | Candidate | Status |
| --- | --- | --- | --- |
| SiP | AM6254 + DDR4 | `OSD6254-1G-IPM`, 1 GB [W]; a 2 GB part number is a question for Octavo | 100+ in stock [O] |
| PMIC | every SoC rail, the sequence, `MCU_PORz` | `TPS65219`, NVM variant per D3 | LCSC 2026-09-10 [B]: `…03` **6 pcs** $4.14 · `…01` **2853 pcs** $3.12 · `…04` 31 pcs $4.82 |
| 3.3 V IO switch | PMIC `GPO2` → the switched 3.3 V for the SoC's `VDDSHV*` **and** FPGA `VCCO` bank 1 | `TPS22965` — datasheet in the repo | |
| 25 MHz reference | required | a crystal; the BRK's oscillator costs ~4.5 mA always-on [W] | |
| Boot storage | Linux root filesystem | eMMC in a routable package, or SD-only — D4 | not checked |
| SD card supply | power-cycle the card below 0.3 V (S6) | `TPS22918` as Octavo does, or pin `VDDSHV5` at 3.3 V — D5 | |
| Boot straps | select the boot source; must overpower the Spartan-6 `HSWAPEN` pull-ups on `DPI_R6`/`R7` | resistors, values from the AM62x TRM | |
| `VBUS` dividers ×2 | USB0/USB1 `VBUS` sensing, 0–3.465 V [W] | resistors | |
| I²C0 pull-ups | the PMIC bus, to the **switched** 3.3 V [W] | resistors | |
| Ferrites / filters | analog rails, per Octavo's schematic checklist | | |
| — | `VPP` must be 0 V in normal use: leave it unconnected (S9) [W] | not fitted | |

**Removed:** `J501`, `J502`, `X500`. `R500`–`R504` and `C510`–`C513` to be re-examined at capture.

### 3.2 Owner decisions

| # | Decision | Options | Recommendation |
| --- | --- | --- | --- |
| D1 | Power tree | **A** PMIC after a 3.3 V buck-boost (TI/Octavo's reference) · **B** PMIC bucks straight from `+VSYS` 3.0–4.4 V | **B** [I] — one conversion instead of two, and under A the SiP's ~1.9 A worst case [W] lands on `U302`, which is 2 A and already carries the FPGA and panel logic. Needs E4 |
| D2 | Core voltage | 0.75 V (A53 ≤ 1.25 GHz, TI's validated `…03` sequence) · 0.85 V (1.4 GHz) | **0.75 V** [I] — an e-reader has no use for 1.4 GHz |
| D3 | PMIC NVM variant | `…01` / `…03` / `…04` / `…07`, or blank `…05` | after E4; stock favours `…01` if it fits |
| D4 | Boot storage | eMMC · SD-only | SD-only for R2's first bring-up [I]; eMMC for the product |
| D5 | UHS-I on the SD card | keep it (needs the card switch) · pin `VDDSHV5` at 3.3 V | pin at 3.3 V, no UHS-I [I] — it also sidesteps the S6 residual-voltage trap |
| D6 | Fab | PCBWay · JLCPCB | ask PCBWay first — the four-layer stack-up PDFs were theirs (`layout.md` §4.1.2) and the six-layer one uses the same template. Needs E7 |
| D7 | Quantities | SiPs for the prototypes plus assembly spares; one `OSD62-PM-BRK` | owner |
| D8 | Memory | 1 GB (orderable) · 2 GB | 1 GB [I] |
| D9 | How the `som` page is replaced | the owner redraws it in Eeschema · the assistant writes a new sheet | **owner's call.** The sheet has been saved in Eeschema, so `CLAUDE.md`'s "patch surgically, never regenerate" governs edits to it; replacing it wholesale is a different act and needs an explicit decision |

### 3.3 Evidence tasks — before any sheet is touched

- **E1** Put the vendor documents in `pcb/r2-mainboard/datasheets/SiC OSD62x-PM/`: `SPRSP58`, the
  `-PM` datasheet v2.0, the power app note, power design & budgeting, layout guide, schematic
  checklist, pin mapping, boot chain & debug; the `TPS65219` datasheet and NVM manuals (`SLVUCJ2A`
  and siblings); the BRK design files; `octavosystems/osd62-pm-ddr`. The list is the handoff's §11. **Mostly done 2026-09-11:** the datasheet, the
  BRK files, `SPRSP58C` (as `am623.pdf`) and three app notes (as web pages) are in. Missing: the layout
  guide, pin mapping, thermal and boot-chain notes, the base `TPS65219` datasheet and the NVM TRMs.
- **E2** From `SPRSP58`: the power-up/power-down sequencing figures and supply-assignment tables,
  with page numbers. Cross-check the handoff's rules S1–S13.
- **E3** From the pin map: the ball of **every** net R2 wires — the 48 of §2.2 plus PMIC, clock,
  boot-strap and supply balls — and each ball's row counted from the package edge. **The answer that
  matters: are all the signals in rows 1–3?** If yes, the hard "trace between two vias" case in the
  handoff's §4.1 never arises. **Answered 2026-09-11: no.** Nine sit in ring 4
  — `VOUT0_DATA1`, `VOUT0_DATA3`, `VOUT0_DE`, `VOUT0_HSYNC`, `SPI0_CS0`, `SPI0_D0`, `USB1_DRVVBUS`,
  `MCU_PORZ`, `PMIC_LPM_EN0`; none is deeper. `docs/osd62x-symbol-guide.md` §6.
- **E4** From the NVM manuals: core voltage, the `VSYS` each variant assumes, UV/OV thresholds, the
  sequence and the standby enables. Can the bucks run from 3.0–4.4 V? Pick D3.
- **E5** Rail budget under D1-B: `U302`'s new load (SiP IO + FPGA + panel logic) against 2 A, and the
  PMIC's input current from `+VSYS`.
- **E6** Ramps and discharge: every SoC rail ≤ 18 mV/µs during power-up [W, S2]; Spartan-6 supplies
  within 0.20–50 ms (`ds162` Table 6) [B]; every rail below 0.3 V before the next power-up [W, S6];
  the `TPS22965` `CT` value that satisfies both.
- **E7** Fab capability in writing: six layers, 0.25/0.15 mm vias, 0.09–0.10 mm trace/space, 0.20 mm
  BGA lands, ENIG, X-ray inspection of a 0.5 mm BGA. Settles D6.
- **E8** KiCad probe on a scratch copy — cheap: can a custom rule permit a via or clearance *below*
  the board-setup minimums? If not, the floors drop to the SiP's numbers and rules raise them
  everywhere else. **Do it with §7 in mind: rules bind the interactive router.**
- **E9** The BRK design files: what format, is there a KiCad symbol/footprint to check ours against,
  and does the BRK bring out `VOUT0` so the DPI output can be tested on it? **Answered 2026-09-11:** the
  design files are Eagle (`OSD62-PM-BRK-3.zip`); their library agrees with the datasheet on all 500
  balls and uses 0.25 mm round lands. **All 20 `VOUT0` pins reach the BRK's 100-mil headers `JP2`/`JP3`**,
  so the DPI output can be tested there. Octavo's symbol libraries are Eagle and Altium only, behind
  a sign-up form — no KiCad.
- **E10** Questions for Octavo — the handoff's §10.1, trimmed to what still matters: a 2 GB part
  number; what changed from datasheet 1.0 to 2.0; the NVM they recommend for a 1S Li-ion `VSYS`;
  whether their BSP needs an EEPROM; a Deep Sleep figure on a low-power design; whether rows 3–4
  escape at 0.25/0.15 mm vias.

---

## 4. The work, in phases

Each phase ends at a check the owner can see. **No `.kicad_*` file is edited while KiCad is open.**

**Phase 0 — freeze and procure (now).**
Don't route the SoM corner. Order an `OSD62-PM-BRK` and the SiPs (D7). Do E1.
*Exit:* parts ordered; the documents are in the repo.

**Phase 1 — evidence.** E2–E10. No sheet edits.
*Exit:* D1–D9 can each be answered from a cited source. Verified results go into
`NOTES-R2-hardware-facts.md` with their tags; a [W] becomes verified only once re-read from source.

**Phase 2 — spec.** Write the new `docs/som.md` (move the `PCM-071` version to
`docs/som-pcm071.md` as the record). Rewrite `power.md` §1, §5.1, §8.1 and `mcu.md` §5.8–§5.9;
update `system-overview.md`.
*Exit:* the owner's review.

**Phase 3 — library.** Generate the SiP's symbol and footprint from Octavo's pin map and package
drawing with a `tools/` script, the way `gen_som_footprint.py` built the connectors from PHYTEC's
DXF. Check both against the BRK files (E9). The PMIC is a VQFN-32 5 × 5 mm (`RHB`). Record each in
`libraries.md`. **How to build the symbol: `docs/osd62x-symbol-guide.md`**, generated from
`datasheets/SiC OSD62x-PM/osd62x_pm_pinout.json`. **Symbol built 2026-09-11** (`Reflow:OSD6254-1G-IPM`, `tools/gen_osd62x_symbol.py`); footprint from
SamacSys, pads verified (`libraries.md` §6). Still open in Phase 3: the footprint's outline against the
p. 31 drawing, its 3D model path, and the PMIC footprint.
*Exit:* every ball in the symbol maps to the pin-map table, no ball is claimed twice, and the 48
functional nets land on the balls E3 listed.

**Phase 4 — capture.** Replace the `som` page as D9 decides; edit `power`, `mcu` and `dpi_in`. Run
ERC. Diff the netlist against the pre-swap one: the only changes should be the SoC side of the 48
nets and the new parts. `check_ucf.py` must still report 0 failures. Retire the `J501`/`J502`
assertions in `check_pcb_connectors.py` in favour of a SiP placement check.
*Exit:* ERC clean apart from the known library-table noise; the netlist diff explained line by line.

**Phase 5 — layout.** Delete `J501`/`J502`/`X500`. Place the SiP in the same corner — the USB pair
is still the reason — and the PMIC beside the SiP's core and DDR balls. Pour the `VDD_CORE` /
`VDDS_DDR` island on `In2.Cu`. Add fine-pitch rules scoped to the SiP's courtyard (E8, §7). Escape
rows 1–2 on `F.Cu` and rows 3–4 to `In3.Cu` or `B.Cu`. Update `layout.md` §1.1: the SiP is 1.3 mm,
not a 5.0 mm stack, so the 7.0 mm cell becomes what sets the device's depth [I].
*Exit:* `tools/check_pcb.py` and DRC clean in the SoM corner.

**Phase 6 — software on the BRK, in parallel from Phase 0.** TI SDK or Octavo's image; the DDR
configuration from `osd62-pm-ddr`; DPI output at the panel's timing if E9 says the BRK exposes it;
Deep Sleep entry and exit; wake on `MCU_GPIO0_14`; re-check PHYTEC's "stop the M4F before suspend"
quirk on TI's SDK [H]; build U-Boot SPL / `tiboot3` with R2's straps.

**Phase 7 — bring-up on R2** [H]. The PMIC sequence on a scope against E2; the `MCU_PORz` /
boot-strap latch with FPGA `VCCO` on the shared switched 3.3 V; Deep Sleep power **at the battery**
(the `PCM-071`'s 128.6 mW was measured at the boost's 5 V output, not at the cell); resume-to-valid-DPI
latency; the DPI link at 40–50 Hz.

---

## 5. Risks

| Risk | Mitigation |
| --- | --- |
| **Two unknowns at the first power-on** — the SoC's power and the FPGA | bring the SiP domain up and verify it with the FPGA unconfigured; test points on every PMIC rail, `nRSTOUT` and `MCU_PORz`; the MCU can hold `MCU_PORz`; software proven on the BRK first |
| 0.5 mm, 500-ball assembly | the fab's DFM review and X-ray; spare SiPs |
| Single source | Octavo direct at volume. The same SoC exists bare — `AM6254ATCGGAALW`, 137 pcs on LCSC 2026-09-10 [B] — as the fall-back |
| Reading-state power unknown | measure on the BRK early; no `-PM` figure goes into the facts file until measured |
| PMIC NVM stock | choose D3 with stock in view (E4) |
| Memory prices | the SiP's price includes its DDR4 [W]; re-check before a volume order |

---

## 6. Repo impact

| File / tool | Impact |
| --- | --- |
| `som.kicad_sch`, `dpi_in.kicad_sch`, `docs/som.md` | replaced (Phase 2/4) |
| `tools/parse_som_pinout.py`, `gen_som.py`, `gen_som_symbol.py`, `gen_som_footprint.py`, `place_som.py`, `patch_som_mcu_recovery.py`, `patch_mcu_pg_som.py`, `patch_pg_som_pulldown.py` | PHYTEC-specific; history, like the other one-shot generators |
| `datasheets/SoM Phycore AM62x/` | the record of the old design |
| `tools/check_pcb_connectors.py` | retire or replace (Phase 4) |
| `power.kicad_sch`, `docs/power.md` §1, §5.1, §8.1 | rail tree, sequence, `+5V` budget |
| `mcu.kicad_sch`, `docs/mcu.md` §5.8–§5.9 | `PG_SOM` / `SOM_RESET#` semantics; `A59`/`A60` disappear with the connectors |
| `r2.kicad_dru`, `docs/layout.md` §1.1, §3.2, §4 | fine-pitch rules; thickness; SoM corner |
| `docs/libraries.md` | the `BTH-060` and `PCM-071_Module` rows retire; SiP and PMIC rows added |
| `NOTES-production-costing.md` §1–§4 | recompute |
| `NOTES-R2-hardware-facts.md` §3 | new section for the `-PM`, from re-read sources |
| Unaffected | §2.1 |

---

## 7. Open on the board, independent of the switch

1. **The custom DRC rules get in the way of interactive routing** [O], 2026-09-11 — to be revisited.
   Not yet diagnosed. Two likely causes, both [I]:
   - **The router probably enforces every clearance the DRC engine resolves, whatever the rule's
     `(severity)`.** Severity changes how DRC *reports* a violation; the push-and-shove router asks
     for the clearance itself. If so, the 0.38 mm (3×W) and 0.5 mm (clock/strobe) rules demoted to
     warnings on 2026-09-10 are still hard walls while routing — which defeats the reason they were
     demoted.
   - Conditions that test `intersectsCourtyard()` on both items are evaluated for every item pair and
     can make the router slow.

   The likely fix, once diagnosed: keep in `r2.kicad_dru` only the rules that must bind while
   routing (the `U700`/`U800` escape tiers, HV separation, the diff-pair gap) and move the 3×W and
   20-mil checks into a script under `tools/` that reads the board — advisory by construction.
   The SiP's fine-pitch rules (Phase 5) should be designed knowing this.
2. **Four real shorts** from the 2026-09-10 DRC — `In3.Cu` tracks crossing through-vias of other nets —
   and **39 HV-separation violations** (`+VGH` within 0.4 mm of the `+3V3` pour on `In2.Cu`).
3. KiCad's Physical Stackup differs from the six-layer PDF in two small places (`layout.md` §4.1.1).
4. The `EPD_PWR` net class still has no pattern.

---

## 8. Documents changed on 2026-09-11 for this decision

Status notes, not rewrites — the rewrites happen in the phases above:
`CLAUDE.md` (pointer to this file), `NOTES-R2-plan.md` (header, Architecture, the DSC section),
`NOTES-R2-hardware-facts.md` §3, `NOTES-production-costing.md` §1, `HANDOFF-octavo-osd62x.md`
(status header), `docs/som.md`, `docs/power.md`, `docs/mcu.md` §5.8, `docs/system-overview.md`,
`docs/session-prompt-layout.md` ("Where the board stands"), and `docs/layout.md` — status line,
§1.1, **a new §4.1.1 for the six-layer stack-up** (the four-layer one is kept as §4.1.1a), §4.1.2, §4.3.

---

## 9. Phase 1 results — 2026-09-11

Evidence in `NOTES-R2-hardware-facts.md` §3.3 (verified, with page numbers). This section is what it
means for the decisions. Phase 2's spec is **`docs/sic.md`**.

### 9.1 The evidence tasks

| Task | Result |
| --- | --- |
| E1 documents | **Done.** In the repo: Octavo datasheet, BRK design files, seven app notes (web pages), `SPRSP58C` (as `am623.pdf`), TPS65219 datasheet `SLVSGA0D`, both NVM manuals, TI's AM62x+TPS65219 note, TPS22965/TPS22918. The AM62x TRM (`SPRUIV7`, 132 MB) was read but is **not** committed |
| E2 sequencing | **Done.** `SPRSP58C` Table 6-5/Fig. 6-5; the `…03` NVM satisfies it slot by slot (facts §3.3) |
| E3 ball rings | **Done** (`osd62x-symbol-guide.md` §6): nine R2 signals in ring 4, none deeper |
| E4 NVM | **Done → D3 = `TPS6521903`.** `…01` is built for a **5 V** input (its BUCK2 makes the 3.3 V IO rail and it needs an external 1.8 V buck); `…03` is built for 3.3 V and is what Octavo's BRK uses |
| E5 budget | **Done**, one gap. PMIC input worst case ≈ **4.6 W** (Octavo's rail maxima) → ~1.5 A from a 3.0 V cell; nominal ≈ 1.3 W. The new switched 3.3 V rail adds ≤ ~0.3 A of SoC IO plus the SD card to `U302`. **Gap: R2 has no `+3V3_DCDC` budget at all** — needs the FPGA's own estimate before `U302`'s 2 A can be called enough |
| E6 ramps | **Done.** `TPS22965` with CT = 1000 pF rises in ~2–2.5 ms: under 18 mV/µs, inside Spartan-6's 0.2–50 ms and inside the PMIC's 10 ms slot 0. PMIC active discharge is on by default, the PMIC refuses to start until every rail is below the short-circuit threshold, and the `TPS22965` has 225–300 Ω quick output discharge |
| E7 fab | **Answered from the published tables** (facts §3.3). **No PCBWay through-via fits between the SiP's balls:** their 4 mil minimum via ring makes a 0.2 mm hole 0.40 mm across and a 0.15 mm hole 0.353 mm, against 0.329 mm of room at 3.5 mil. **JLCPCB's published 0.15/0.25 mm via fits.** PCBWay may accept a thinner ring on request — the question is in `docs/sic.md` §12 |
| E8 KiCad | **Done: yes.** A courtyard-scoped custom rule can permit 0.25/0.15 mm vias below the 0.45/0.3 board floor — verified with `kicad-cli`. Mind §7: rules bind the router |
| E9 BRK | **Done.** Eagle files; library = datasheet on all 500 balls; all 20 `VOUT0` pins reach its headers |
| E10 Octavo | **Reduced** to: a 2 GB part number; what changed from datasheet 1.0 to 2.0; whether their BSP needs an EEPROM; a Deep Sleep figure on a low-power design; and **whether `…03` may run from a 3.0–4.4 V `VSYS` with LDO1 fed from BUCK2** (§9.2 D1) — the one question worth putting to TI (E2E) too |

### 9.2 Decisions

| # | Decision | Status |
| --- | --- | --- |
| **D1** | Power tree | **Decided (owner, 2026-09-11): the PMIC runs straight from `+VSYS` through an MCU-switched `TPS22965`.** All its inputs are ≤ VSYS as the datasheet demands, except LDO1: `PVIN_LDO1` may not exceed VSYS and bypass mode needs ≤ 3.4 V, which no 3.3 V source satisfies on a 3.0–4.4 V cell. So **`PVIN_LDO1` is fed from BUCK2 (1.8 V)** and LDO1 is left unloaded; `VDDSHV5` comes from the switched 3.3 V. The alternative — a second 3.3 V buck-boost feeding the PMIC like the BRK — costs a converter and a conversion stage. *(inferred; confirm with TI)* |
| D2 | Core voltage | **Decided: 0.75 V** (owner, 2026-09-11) — fixed by the NVM (both `…01` and `…03`). A53 ≤ 1.25 GHz; no DVS on AM62x |
| D3 | PMIC | **Decided: `TPS6521903`** (owner, 2026-09-11). LCSC had 6 on 2026-09-10 — check DigiKey/Mouser |
| D4 | Boot storage | **Decided: SD-only boot** (MMC1), as the BRK boots (owner, 2026-09-11) — **plus an eMMC footprint on MMC0, fitted on one or two prototypes** (`docs/sic.md` §6.1) |
| D5 | UHS-I | **Follows from D1: no.** UHS-I is the SD card's fast mode (≈ 50–100 MB/s instead of ≈ 25 MB/s). For it the card switches its signals to 1.8 V, which needs a switchable `VDDSHV5` and a card power switch. `VDDSHV5` stays at 3.3 V — fast enough to boot and to load books — so the residual-voltage trap never arises |
| D6 | Fab | **Open — needs a quote.** Owner: 0.15 mm holes cost more than 0.2 mm; 4/4 mil is standard. From the published tables (E7): **no PCBWay through-via fits between the balls; JLCPCB's 0.15/0.25 mm does.** The lands stay 0.20 mm — 0.17 mm is below both fabs' BGA-land minimum. The owner quotes both with `docs/sic.md` §12's question. X-ray: have the fab assemble the SiP and X-ray it [I] |
| D7 | Quantities | **5 boards per respin; ~1 000 after a crowdfunding** (owner). Per respin, order two spare SiPs and PMICs for rework [I]. A thousand is beyond DigiKey + Mouser's 100+; that run comes from Octavo direct |
| D8 | Memory | **Decided: 1 GB** (owner) — renegotiable later |
| D9 | Who draws the page | **Decided: the owner** captures Phases 4 and 5 (2026-09-11) |
| **D10** | *new* — the FPGA must not drive the SoC while the SoC is off | Caster's MISO is always driven, and the FPGA's configuration reads the NOR over the same line. **Decided (owner, 2026-09-11): firmware *and* the Caster fix.** The MCU holds `FPGA_PROG#` low until the SoC reports `RESETSTATz` high and pulls it low again before any SoC power-down — existing hardware, firmware only — and `SPI_MISO` is tri-stated in Caster's `top.v` while the active-low chip select is high. The Verilog is written out in `docs/sic.md` §9 and **not applied**: `Caster/` is a submodule, and it needs an ISE build and a dev-kit test. Alternative, not taken: move FPGA `VCCO_1`/`VCCO_2` and the NOR onto the SoC's switched 3.3 V |
| **D11** | *new* — backup boot | **Proposed, kept: USB DFU on USB0** (R2's USB-C port) instead of the BRK's UART. What it is for: when the boot device — SD card or eMMC — is missing, blank or corrupt, the ROM waits for a PC on USB to send it a bootloader. That recovers a board without opening it, and it is how a blank eMMC gets its first image (`docs/sic.md` §6, §6.1) |
