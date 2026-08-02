# Glider power work — current state (read this first)

Last updated **2026-08-02**. Branch `power-analysis`.

This file is the handoff: current hardware state, what is settled, what is open, what to do
next. **`NOTES-power-analysis.md` is 1400+ lines of chronological working notes and is
partly superseded** — read it only for depth on a specific section, and prefer the later
sections (§8 onward) over the earlier ones. Section pointers are at the bottom.

---

## Ground rules for this work

These come from the hardware owner and are not negotiable:

- **The assistant cannot flash, measure, or observe the hardware.** The user does that.
  Never claim a behaviour was confirmed on hardware. Label predictions as predictions and
  say how to test them.
- **This is the only dev kit.** Nothing may risk bricking it without a documented recovery
  path. (Recovery for gateware is below; the STM32 is DFU-updatable.)
- **Do not modify anything outside this repo.**
- The user reads Linux and Python fluently; their C is roughly Arduino level. Explain
  firmware/RTOS concepts as you go, don't dumb down anything else.
- **Separate clearly, everywhere: verified from the code / inferred / needs a hardware
  test.** If a number is an estimate, say so.

## The product this is for

A battery-powered high-refresh e-ink reader: Modos Paper Dev Kit (6", 1448×1072 @ 75 Hz)
driven by a Raspberry Pi 4 running KOReader under the `cage` kiosk compositor.

**The power model (the user's, and it overrides older analysis in NOTES §1–§7):**

- **Retain = the READING mode.** HDMI link stays up. A page turn must NOT cause a link
  renegotiation or a full-panel refresh — both are ugly and too slow. This is where reading
  time is spent, so this is what must get cheaper.
- **Off = STANDBY.** ~4 s bring-up plus a full refresh. Fine for waking from a pause, not
  for a page turn. **Do not propose duty-cycling `off` per page.**

---

## Current hardware state

| | Version | Flashed |
| --- | --- | --- |
| Gateware | Caster `2f714ab` ("Support internal clock and video timing check") | 2026-08-02 ✅ |
| MCU firmware | **unconfirmed** — run `ver` in the shell (prints build date/time) | ? |

Confirmed live from the boot log: `Legacy bitstream: no input-control interface` is **gone**,
and `Input status 3a, measured 1448 x 1072, total 1528 x 1110` — the new timing monitor
reads the panel correctly. See §12 for what `2f714ab` changed.

**Flashing.** `dev_flash_fpga.sh` passes `--skip-mcu`, so gateware flashes never touch the
MCU and the two sides drift apart silently — this already happened once. Use:

```bash
scripts/dev_flash_mcu.sh                                        # MCU only, board in DFU mode
scripts/dev_flash_fpga.sh  --ise-host 192.168.56.102 --variant 8bit-mono   # gateware only
scripts/dev_flash_all.sh   --ise-host 192.168.56.102 --variant 8bit-mono   # both
```

DFU mode = hold the button nearest the USB port while plugging in. ISE VM at
`192.168.56.102`, `ssh ise@…` / password `xilinx`.

**Gateware recovery (no bricking risk).** There is no FPGA config flash — the bitstream is a
file on SPIFFS streamed over SPI at every pipeline start. A bad build means the FPGA does not
come up and the firmware parks in `fatal()` with the shell alive. Restore with:

```bash
python3 utils/flash_tool/flash.py --skip-mcu --bitstream utils/flash_tool/fpga.bit \
    --no-fonts --no-config
```

(`utils/flash_tool/fpga.bit`, 450366 B, is the checked-in stock bitstream.) The MCU and its
DFU bootloader are untouched by gateware work.

---

## The central measurement (2026-08-02, `sensor`, on `2f714ab`)

| rail | retain | active |
| --- | --- | --- |
| MCU + IO | 559.1 mW | 565.8 mW |
| VIDEO IN | 587.6 mW | 588.1 mW |
| FPGA CORE | 151.2 mW | 168.0 mW |
| FPGA DDR | 97.3 mW | 102.8 mW |
| EPD HV | **0.0 mW** | 71.8 mW |
| **total** | **1395 mW** | **1496 mW** |

Full suspend (`off`) measured 190 mW on the previous bitstream (NOTES §8); not re-measured
since.

**Read this table before proposing anything.** Two conclusions follow, and they redirect the
whole project:

1. **Retain saves 101 mW — 6.7%.** EPD HV is already at zero in retain, so there is nothing
   left for retain itself to switch off. Making retain *lossless* (the §11 gateware plan) buys
   correctness, not power.
2. **MCU+IO plus VIDEO IN is 1147 mW, 82% of retain power, and retain touches neither.**
   All remaining headroom is in those two rails.

Retain matched the old bitstream's 1.40 W exactly — **`2f714ab` changed nothing about power.**

---

## Verified from the code (these hold; don't re-derive them)

**Gateware, read from the RTL in `Caster/` at `2f714ab`:**

- **Per-pixel waveform timers live in the framebuffer state word** (`pixel_framecnt =
  proc_bi[9:4]`, pixel_processing.v:152) and decrement *only* by writing `proc_bo` back to
  VRAM. **Therefore gating framebuffer writeback is not a freeze** — it strands counters
  non-zero and drives those pixels forever (DC-imbalance hazard). An earlier plan to gate
  `bo_valid` was wrong and has been dropped.
- **`framecap_en` already exists** — a `pixel_processing` input hardwired `1'b1` at
  caster.v:342, already gating every change-initiating branch in auto-LUT
  (pixel_processing.v:292, 305, 333, 341, 359). Wiring it to a CSR bit is ~3 lines and gives
  exactly the needed hold semantics. Hold alone is a stable terminal state (`framecnt == 0` +
  target == previous → `NO_DRIVE`, `proc_bo = proc_bi` forever); no two-phase quiesce needed.
- **Nothing currently knows when the panel has settled.** `op_busy`/`op_queue` track only the
  host operation queue; `damage_counter` counts transition *starts*. A panel-idle status bit
  is ~6 lines and is the load-bearing piece of the gateware plan.
- **`CSR_DAMAGE_COUNT` is PER-FRAME, not cumulative** — wired to `damage_counter_last`
  (caster.v:189), zeroed every vsync (caster.v:858). Snapshot-delta logic silently never
  fires. **This broke three successive retain fixes.** Accumulate samples over time instead.
- **`OP_EXT_REDRAW` is already a clear-and-repaint** (`clear_en` → `force_clear`,
  pixel_processing.v:174-178), so a plain `caster_redraw()` fixes a diverged panel.
- **`CSR_ENABLE` bit 2 and `CSR_STATUS` bit 1 are free** on every bitstream — csr.v has only
  ever decoded `spi_req_wdata[1:0]`, and status bit 1 is `2'd0` filler. Safe to drive from
  firmware ahead of the gateware.
- **RTL shortcuts that were checked and ruled out:** no per-pixel "no-drive" mode (unused mode
  codes fall back to FAST_MONO, pixel_processing.v:220-223); `top.v` has no enable/standby
  input (`FPGA_SUSP` is not wired to the design); `CSR_ENABLE` bit 0 (stop scan) is unusable
  because `vin_ready = s1_active` (caster.v:483) — halting the scan stalls input consumption
  and the video FIFO desyncs with no flush.
- **On this gateware, state-update and input-consumption are the same signal.** Firmware can
  detect divergence and correct it, not prevent it.

**Firmware:**

- Retain damage wake triggers on `damage != damage_last` (ui.c:1139) — **any** change, one
  pixel is enough.
- **Damage-wake and hold are mutually exclusive by construction.** Waking on image change
  needs the framebuffer to keep tracking the input, which is exactly what hold suppresses.
  So `caster_set_hold(true)` is asserted only for `POWER_REQ_RETAIN_NOWAKE`.
- Requests to *enter* a suspend state are only consumed while `ui_task` is active; sending one
  while suspended is silently dropped. Always bounce through active first.

---

## Settled this session (2026-08-02, from the boot/shell log)

- **Damage wake works.** `last wake: 0x10` = `POWER_WAKE_DAMAGE` (`1u << 4`), not button.
  Pressing a key on the Pi makes KOReader redraw; the *image changing* resumes the Glider.
  Because the trigger is any single-pixel change, shell `power retain` bounces straight back
  to active under any KOReader activity.
- **The `a7882e8` hold path has never executed.** Shell `power retain` keeps damage wake, so
  hold is never asserted. Testing it needs `flash.py --powerdown retain-manual` (HID param 2,
  what `retain_hook.py` sends).
- **The live-timeout reload fired once on cold boot** and self-corrected — not a loop:
  ```
  [32.015] Input source stable; requesting auto
  [37.036] Input did not go live after switch; reloading pipeline
  [38.512] Input status 3a, measured 1448 x 1072
  ```
  Cost: 6.5 s and a full bitstream reload. `adv7611_init()` ran at t=1.169 while the Pi (which
  takes ~31 s to boot) had no HDMI output; status stayed `0x19` for the whole 5 s window, so
  the mux never left internal. The reload re-initialized the ADV7611 with the source already
  present and it locked in 202 ms.

---

## Open work, ranked

**1. Does the CSR bus now survive video loss? (highest value — can redirect everything)**

*Inference from the RTL, not measured.* `vin.v:186/228` add `BUFGMUX`es that can clock the
EPDC from `clk_internal` = `clk_sys`, the on-board oscillator (top.v:156). NOTES §8–§10 put
the reading-mode floor at ~1.0–1.3 W and blamed VIDEO IN (~588 mW) having to stay powered,
because losing the recovered pixel clock wedged the EPDC *and* the CSR bus — both on
`clk_epdc` (the "CSR-on-video-clock trap", NOTES §9). The BUFGMUX may have killed that.

Given the measurement table above, VIDEO IN is 42% of retain power and the largest single
thing retain could ever switch off. **Test:** board active, drop the HDMI signal, watch syslog
for `FPGA access lost` / `FPGA CSR recovered after N ms dropout`. Riding through cleanly means
the trap is gone.

Caveat that does *not* go away if the test passes: powering the ADV7611 down deasserts HPD,
which makes the Pi renegotiate — and the power model forbids a renegotiation per page turn.
So the follow-on question is whether the frontend can be quiesced without dropping HPD.

**2. Cheap recovery for the cold-boot input switch (well-scoped, ~15 lines of C)**

The reload at ui.c:1324-1340 exists because "the mux may be latched onto a clock that went
away" and the gateware FSM cannot fall back on its own. That is not what happened above:
status `0x19` has `INPUT_STATUS_INTERNAL` set, so the mux was parked on internal, clocked
from `clk_sys`, healthy. The new status register can distinguish the two cases:

- `INPUT_STATUS_INTERNAL` still set → mux alive → re-init the ADV7611 and re-issue the
  request. Cheap.
- INTERNAL clear and not LIVE → mux stuck on a dead clock → full pipeline reload, as today.

Saves ~6 s and a bitstream reload on every cold boot where the Pi is slower than the Glider,
which is always.

**3. Test what `a7882e8` actually changed (never yet exercised)**

- Reading mode (`UM_AUTO_LUT_NO_DITHER`), static page → retain → resume. The mode-aware
  settle (`RETAIN_SETTLE_AUTOLUT_MS` 1950 ms vs `RETAIN_SETTLE_MS` 700 ms) targets a real
  race: the gateware drives for 60 quiet frames + 38 LUT frames ≈ 1.63 s after the last
  change, and neither phase asserts `pixel_diff`, so the damage counter reads 0 throughout.
  Rails were being cut at ~820 ms, before the greyscale phase started. Entering retain in
  Reading mode now takes ~2 s; that is deliberate.
- `flash.py --powerdown retain-manual` → change the page during retain → `--powerup`. This is
  the only path that asserts hold, and hold is a no-op on `2f714ab`, so expect the existing
  behaviour: syslog `Image changed during retain (N px)`, one clearing flash, correct page.
  **If that syslog line is absent the trigger is wrong — capture the log.**

**4. The gateware change (NOTES §11) — ~9 lines of Verilog**

Only worth doing once (1) is answered, since it buys correctness rather than power.

- Panel-idle status bit → `CSR_STATUS` bit 1 (~6 lines). Firmware already reads it as
  `STATUS_PANEL_ACTIVE` via `caster_panel_active()`.
- Decode `spi_req_wdata[2]` in csr.v into a `csr_hold` output, drive `framecap_en` from
  `~csr_hold` at caster.v:342 (~3 lines). Firmware already writes it as `CASTER_EN_HOLD` via
  `caster_set_hold()`.
- **Do not gate framebuffer writeback.** See the verified list above.

**5. Deferred / lower priority**

- MCU+IO is 559 mW and identical in retain and active — 40% of retain power, entirely
  untouched by any suspend path. Nobody has looked at it. PR #17 (tickless idle) is relevant.
- Resume-latency polish: double `ADV7611 initialization done` per resume; SPIFFS-bound
  bitstream read (~360-400 ms measured today, better than the 688 ms in NOTES).
- Pi-side `retain_hook.py` (evdev idle manager) has never been tested live.
- Upstream PRs to Modos: `config_save` fd leak; the CSR-on-`clk_epdc` question.
- Re-measure `off` (190 mW figure predates `2f714ab`).

---

## Gotchas that have bitten more than once

- **Flashing gateware does not flash the MCU.** Check `ver` before trusting a behavioural test.
- **`CSR_DAMAGE_COUNT` is per-frame.** Any snapshot-delta logic is silently dead.
- **`power retain` from the shell keeps damage wake**, so it will not stay in retain and will
  not assert hold. Use `--powerdown retain-manual` for anything hold- or power-related.
- **`ui_task` reboots the MCU** (`NVIC_SystemReset()`) if a sanity `fpga_write_reg8(CSR_ID0)`
  read fails — the only spontaneous repeatable reset path; no watchdog is configured.
- **`ui.c`/`caster.c` cannot be compiled on the dev host** (they need the STM32 HAL headers).
  Host tests do not cover them. Compile errors come back from STM32CubeIDE.
- **This checkout is `Glider_OG` under a path containing a space.** That broke
  `test_release_scripts.sh`; fixed in `abd7db1`, but suspect it if other script tests fail.
- Recovery for a stressed/inverted panel: `power off` → `power resume` ×2–3 (full init
  waveform).

## Test commands

```bash
bash fw/User/tests/build_host_tests.sh        # host-side C unit tests
bash scripts/tests/test_shell_commands.sh
bash scripts/tests/test_fw_config_timing.sh
bash scripts/tests/test_cfggen.sh
bash scripts/tests/test_release_scripts.sh
cd utils/flash_tool && python3 -m unittest discover -s tests -p "test_*.py"
```

All passing as of `abd7db1`.

## Where to look in `NOTES-power-analysis.md`

| § | Contents | Still current? |
| --- | --- | --- |
| 0–7 | Session 1: pre-hardware analysis, PR review, original test plan | **Largely superseded** |
| 8 | First measured power, old bitstream | Historical baseline only |
| 9 | Resume-from-off spurious MCU reboots — root-caused | Yes |
| 10 | R1/R2 results, retain scramble root-cause and fixes | Yes |
| 11 | Gateware plan for lossless retain (revised) | Yes — the plan of record |
| 12 | What `2f714ab` changed; free-bit re-verification | Yes |
| 13 | 2026-08-02 hardware results | Yes |
