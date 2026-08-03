# Glider R1 power work — current state

Last updated **2026-08-03**. Branch `power-analysis`; still current for anything hands-on with
the existing board.

> **This work concluded: the ceiling is hardware.** See the end of this file — 82 % of retain
> power sits on rails with no enable pin. That conclusion is what started R2.
> **For the board design that follows from it, read `NOTES-R2-plan.md` and
> `NOTES-R2-hardware-facts.md` on branch `Board-Design`.**
>
> **Still open here:** the firmware and gateware from `613e8ee` have never been flashed or
> tested on hardware. The gateware half needs the ISE VM (192.168.56.102, down as of 2026-08-03).

This file is the handoff for R1: current hardware state, what is settled, what is open, what to
do next. **`NOTES-power-analysis.md` is 1400+ lines of chronological working notes and is
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

## Re-measured 2026-08-03 on `4f7829d` + merged gateware (`power_survey.py`)

Firmware and gateware from `613e8ee`/`5385304` are now flashed and verified on hardware:
`ver` reports `4f7829d`, `power status` reports **`caster features: 0x01`**, and retain resume
no longer flashes the panel — confirmed by the hardware owner.

| Rail (AVG mW) | active | retain | retain-manual | off |
| --- | --- | --- | --- | --- |
| MCU + IO | 558.1 | 552.9 | 550.4 | **123.6** |
| FPGA DDR | 101.5 | 98.8 | 96.3 | 2.7 |
| FPGA CORE | 165.6 | 164.5 | 164.9 | 12.0 |
| VIDEO IN | 574.4 | 573.4 | 573.8 | 26.2 |
| EPD HV | 67.0 | **0.0** | **0.0** | 0.0 |
| **TOTAL** | **1466.6** | **1389.6** | **1385.4** | **164.5** |

Against the `2f714ab` baseline below:

- **`off` improved 190 → 164.5 mW (−13%).** This is the `__WFI` idle hook (`freertos.c`) plus the
  shell loop no longer waking the core ~500x/s (`usbapp.c`) and the `usbpd.c` sub-ms spin fix,
  measured where they matter most. The pre-measurement estimate was 40-80 mW for MCU idle alone;
  the real total is ~25 mW.
- **`active` improved 1496 → 1466.6 mW (−29 mW).** ~13 mW of it on MCU + IO, ~11 mW on VIDEO IN
  (parking the PTN3460 when auto-select settles on TMDS — previously "unknown", now quantified).
- **`retain` is unchanged: 1395 → 1389.6 mW, within noise.** Exactly as predicted. Retain now
  works *correctly* (no flash, no ghosting accumulation) but it cannot work *cheaply*, because
  the rails it would need to switch have no enable pins. **The hardware wall is re-confirmed on
  the new stack; R2 remains the only path to e-reader battery life.**
- retain vs retain-manual differ by ~4 mW, i.e. not at all.

### `power scanstop on` — measured 2026-08-03, and the estimate was wrong

Enabled from the shell, entered via **retain-manual** (it is gated on `!damage_wake`, since
stopping the scan freezes the damage counter — `ui.c:1194`), sampled twice, then resumed and
disabled. The board resumed cleanly; suspend/resume counts matched.

| Rail (mW) | retain | retain + scanstop | delta |
| --- | --- | --- | --- |
| FPGA DDR | 98.8 | **22.5** | **−76.3** |
| FPGA CORE | 164.5 | **134.1** | **−30.4** |
| MCU + IO | 552.9 | 537.3 | −15.6 |
| VIDEO IN | 573.4 | 572.6 | −0.8 |
| **TOTAL** | **1389.6** | **1266.5** | **−123.1 (−8.9%)** |

**The 250-400 mW estimate was wrong, and so was the reasoning behind it.** It rested on "~420 of
the 559 mW MCU + IO is FPGA I/O switching" (NOTES §, line ~828) — but MCU + IO moved only
15.6 mW. Almost the whole saving is the framebuffer *read* traffic stopping: DDR fell 77%. Do
not reuse the "420 mW of FPGA I/O" figure; it is not supported by measurement.

123 mW does not change the conclusion. Retain with everything firmware can do is ~1266 mW
against a 164.5 mW `off`, and the gap is still rails with no enable pin.

### ⚠ scanstop still corrupts the panel. Do not enable it.

**The measurement above was taken, but the state it measured is not safe.** Immediately after
the test the panel looked clean and the electrical side was correct — clean resume, matched
suspend/resume counts. **The corruption was latent:** on subsequent page scrolls the hardware
owner saw words scrambling, and recovery took several `power off` → `power resume` cycles plus
scrolling to work the panel back to a good state.

This is the same failure `d53afdb` produced and `05cfa68` reverted it for. The claim in this
file's earlier revision — that the hold bit prevents it because the old failure was writeback
continuing while stopped — **is contradicted by evidence.** Hold works (feature bit `0x01`,
retain resume is flash-free), and scan-stop still corrupts. Whatever the mechanism is, it is not
the one that was assumed.

Consequences:

- **`power scanstop on` must stay off.** It is off by default and RAM-only, so a replug clears
  it; nothing persists. The 123 mW is not available.
- **A clean panel immediately after the transition does not mean the state was safe.** Any future
  test of this must scroll several pages before drawing any conclusion.
- **For R2:** on-demand scan is core to the planned reading state (`NOTES-R2-plan.md` step 3),
  and it is now *less* proven than before this test, not more. Treat it as an open gateware
  problem to be root-caused, not as a mechanism that works. Budget nothing for it until it does.
- Root-causing it is the natural next gateware task: hold freezes `framecap_en`, but stopping
  `CASTER_EN_REFRESH` also stops the panel scan the source/gate drivers need, and the EPD glass
  may be integrating charge with no drive. That is a hypothesis, not a finding.

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

## Session 2026-08-02b: ghosting root-caused, hold/panel-idle/scan-stop implemented

Code is written and builds; **nothing here has been on hardware.** The ISE VM at
192.168.56.102 was down, so the RTL has never been through XST either — treat the first
gateware build as a syntax check.

**Ghosting in Reading mode — root cause (read from the RTL, certain).** In `BASEMODE_AUTO_LUT`
a pixel whose target is pure black or pure white gets *one* unipolar drive of
`fastg_g2w_frames[0]` / `fastg_g2b_frames[15]` = **9 frames** (~120 ms at 75 Hz) and then never
runs the waveform LUT: `pixel_processing.v:348` skips `STAGE_GREY` when
`autolut_binary_src == pixel_prev`, which is always true once the pixel has settled on a rail.
So body text gets no DC-balancing pulse, ever, and unchanged pixels are never re-driven
(`:359`, `:373-376`). The balanced `0->0` / `15->15` rows do exist in
`rtl/spartan6/default_waveform.mem` — they are simply unreachable in auto-LUT.

**`autoclear` was off by default** (`config.c:74` was `AC_OFF`), so there was no periodic
refresh either. Also: **adaptive autoclear is structurally broken on this gateware.**
`CSR_DAMAGE_COUNT` is per-frame and a page turn's transitions all start in one frame, so
`ui_task`'s ~200 ms poll sees roughly 1 frame in 15 and undercounts by that factor. An
event-counting rewrite does *not* fix this (same sampling problem). Fixed interval does.

**Changes made (firmware, works on the currently flashed `2f714ab`):**

- `config.c` — autoclear defaults to `AC_FIXED`/`AC_5MIN`, in both `config_init_settings()` and
  the `config_validate_loaded()` repair path. **A config already saved with `AC_OFF` is in
  range and is left alone**, so on this board it must still be switched on from the OSD menu.
- `ui.c` — the interval timer is armed in adaptive mode too, as a backstop.
- `ui.c` `park_unused_frontend()` — in `INPUT_SEL_AUTO`, power the PTN3460 down once the FPGA
  has settled on TMDS. DP presence is detected via USB-PD (`dp_ready`) and the `DP_ACTIVE` pin,
  never through the bridge, so this does not blind DP detection. Saves in *all* modes.
- `freertos.c` / `FreeRTOSConfig.h` — `vApplicationIdleHook()` executing `__WFI()`. The MCU
  previously never slept at all. Not tickless: the HAL timebase is on a TIM
  (`stm32h7xx_hal_timebase_tim.c`), so it would keep firing at 1 kHz anyway.
- `usbapp.c` — `TERM_INPUT_WAIT` now blocks on the queue instead of mapping to a 2 ms timeout;
  the shell loop was waking the core ~500x/s forever, including while suspended.
- `ui.c` — the retained loop's `is_selected_video_active()` I2C probe is rate-limited to 1 Hz
  (`RETAIN_VIDEO_CHECK_MS`). The 30 ms damage poll stays: the counter is per-frame.
- `usbpd.c` — `pdMS_TO_TICKS(timeout/1000)` truncated sub-ms waits to 0 ticks, a spin at
  priority tskIDLE+4. Clamped to 1 tick.
- `shell` — `caster frames [<b2w> <w2b>]` writes `CSR_CFG_B2WFRAME`/`W2BFRAME` live;
  `power scanstop [on|off]`; `power status` now prints the gateware feature bitmap.

**Changes made (Caster RTL, needs an ISE build):**

- `csr.v` — `CSR_ENABLE` bit 2 decoded into a new `csr_hold` output; `CSR_STATUS` bit 1 now
  carries `panel_active`; new read register **`CSR_FEATURES` (144)** returning a feature
  bitmap. Undecoded reads return 0, so every older bitstream self-reports "no features" — the
  firmware branches on `caster_has_feature(CASTER_FEATURE_HOLD)` instead of guessing, which
  ends the "which half is flashed" class of bug.
- `caster.v` — `framecap_en = !csr_hold` (was hardwired 1); `panel_frame_active` OR-reduced
  from `pixel_comb` and latched at vsync together with `autolut_frame_pending` and
  `autolut_running`; **`vin_ready = s1_active || !global_en`** so the video FIFO keeps draining
  while the scan is stopped — this is what makes clearing `CASTER_EN_REFRESH` survivable.
- `pixel_processing.v` — auto-LUT mono drive from a *binary* source now takes its length from
  `csr_b2wframe`/`csr_w2bframe` instead of the hardcoded tables (identical at the default of 9;
  the point is runtime tunability). `framecap_en` now also gates the change-initiating branches
  in `BASEMODE_FAST_MONO` and `BASEMODE_FAST_GREY`, which it never did — hold only ever worked
  in Reading mode. While held, a settled pixel that differs from the input asserts `pixel_diff`
  without driving or writing back, so **the damage counter becomes a level** ("pixels that no
  longer match the glass") rather than an edge, and a slow poll cannot miss a page turn.

**What that buys, if it works on hardware:**

- Retain resume needs no `caster_redraw()` at all — hence no flash. `ui.c` drops it when the
  feature bit is set and keeps the old redraw path when it is not.
- Hold and damage-wake are no longer mutually exclusive.
- Retain entry is closed-loop on `STATUS_PANEL_ACTIVE` instead of the open-loop 1950 ms sleep.
- Wake threshold is ~1% of the panel in damage-counter *groups* (`retain_damage_threshold()`),
  so a cursor blink no longer bounces retain straight back to active.

**Untested and gated:** `power scanstop on` clears `CASTER_EN_REFRESH` during retain. This is
the only change here that should move the power numbers meaningfully (NOTES §, line ~828: ~420
of the 559 mW "MCU + IO" is FPGA I/O). It is **off by default, RAM-only, and requires the
feature bit plus damage-wake off** — stopping the scan freezes the damage counter, so the two
cannot coexist. A firmware-only version of this was tried before (`d53afdb`) and reverted for
panel inversion (`05cfa68`); that failure was writeback continuing while stopped, which the
hold bit now prevents. Recovery remains `power off` -> `power resume` x2-3.

**Estimated, not measured:** scan-stop 250-400 mW, MCU idle 40-80 mW, PTN3460 unknown.

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
- **`CSR_DAMAGE_COUNT` is per-frame.** Any snapshot-delta logic is silently dead. It also means
  anything sampling it from the ~200 ms `ui_task` loop (adaptive autoclear) misses ~14 frames
  out of 15. Only the held-mode level semantics added this session are poll-rate independent.
- **Check `power status` for `caster features`** before trusting any retain behaviour: `0x00`
  means the gateware predates the hold/panel-idle/tunable-frames bundle and the firmware has
  silently fallen back to the old redraw-on-resume path.
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

## Battery budget (5000 mAh integrated cell + low-power SoM)

Assumptions, which must be quoted alongside any number here: single-cell Li-ion 5000 mAh at
3.7 V = 18.5 Wh; ~92 % usable to cutoff and ~90 % through the boost to the board's 5 V input,
so **15.3 Wh delivered**. `sensor` figures are post-buck, so board input = rail sum / 0.88
(four SY8113C bucks). Reading time = retain time, since the power model keeps the link up.
SoM budget 0.8 W for an RK3566 / i.MX8MM / CM4-class part; Pi 4 (~2.7 W) shown for contrast.

| Glider state | rail sum | board input | Glider alone | + 0.8 W SoM | + 2.7 W Pi 4 |
| --- | --- | --- | --- | --- | --- |
| Active | 1496 mW | 1.70 W | 9.0 h | 6.1 h | 3.5 h |
| **Retain today** | 1412 mW | 1.61 W | 9.5 h | 6.4 h | 3.6 h |
| Retain, this session's work *(est.)* | ~970 mW | ~1.10 W | 13.9 h | **8.1 h** | 4.0 h |
| Retain + ADV7611 down *(est., round 2)* | ~540 mW | ~0.61 W | 25 h | 10.8 h | 4.6 h |
| Off / standby | 190 mW | 0.22 W | 71 h | 57 h *(SoM suspended)* | — |

**The ceiling is hardware, not firmware.** 82 % of retain power sits on rails that cannot be
gated at all: `pcb/mainboard/pcb.kicad_pcb` shows the SY8113C EN pins for `+3V3_DCDC`,
`+1V8_DCDC`, `+1V35_DCDC` and `+1V2_DCDC` tied to `+5V`, and `power.kicad_sch` has no global
labels — no MCU net reaches that sheet. The only firmware-switchable supplies are the EPD HV
chain and the `HPD_EN` load switch. A ~1-day reader is the realistic target for this board
revision; Kobo-class runtime needs `+1V8_VID`/`+3V3_VID` and the FPGA rails made switchable in
silicon.

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
