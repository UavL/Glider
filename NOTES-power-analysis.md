# Glider power / gray-screen analysis

Working branch: `power-analysis` (branched from local `main` @ `550a171`).
This file is committed on that branch.

Legend used throughout:

- **[CODE]** — read directly out of this repo, with file:line. Not hardware-confirmed.
- **[INFER]** — reasoned from the code, but depends on an assumption I could not check.
- **[TEST]** — unknown; needs the hardware experiment named.
- **[EST]** — a number I calculated, not measured. Error bars given.

Nothing in this document has been observed on hardware. I cannot flash, measure, or
observe the board.

---

## 0. Read this first: the premise of the task does not match this tree

The task was written as if against a fresh clone of upstream `Modos-Labs/Glider`. This
working copy is **8 commits ahead of `origin/main`**, and that local work already
implements most of what PR #16 proposes, plus a large amount of suspend/resume machinery
that does not exist upstream at all. `git log --oneline origin/main..main`:

```
550a171 Add CLAUDE.md with build/test commands and architecture overview
ed3853e Add --monitor mode to power_survey.py for live syslog watching
ad59125 Harden power_survey.py's resume-on-exit against a second Ctrl+C
a18df1c Define GLIDER_DIAGNOSTIC_SHELL in all build configs
2f435e4 Add tty subsystem rule to 99-glider.rules for CDC-ACM shell access
d750d71 Add power_survey.py: compare power draw across suspend states
b4314e1 Add retain suspend: EPD rails off with image kept on panel
8d1b467 Fix compilation warnings and errors under GCC 15
```

Consequences that change the answers below:

1. `USBCMD_POWERDOWN` / `USBCMD_POWERUP` are **already wired** here
   ([usbapp.c:161-176](fw/User/usbapp.c#L161-L176)), and wired *better* than PR #16 does
   it. PR #16's headline change is redundant and, as written, worse. See §7.
2. A **retain suspend** mode already exists (EPD rails off, image kept, FPGA/DDR3 alive)
   — this is the single most useful thing for your battery goal and it is already here.
3. A `power` **shell command already exists** ([shell.c:114](fw/User/shell/shell.c#L114))
   exposing `status|off|retain|resume`. You can run the whole rails-off-then-link-off
   experiment today **without building anything** — *if* the board is running this
   firmware.
4. PR #17 **will not apply to this tree**; it conflicts in `usbpd.c` because local commit
   `8d1b467` already made an overlapping change there. Verified:
   `git apply --check` fails at `fw/User/usbpd.c:90`; `--3way` reports a conflict.

**The single most important open question is therefore: what firmware is physically on
the board right now?** Your 1.77 W / 0.42 W numbers are attributed to "stock firmware",
but this tree is not stock. Experiment 0 resolves this and everything else depends on it.

---

## 1. What is now established from the code

### 1.1 `power_suspend()` — what it actually sequences

[power.c:129-164](fw/User/power.c#L129-L164). Two distinct paths.

**Retain path** (`POWER_SUSPEND_RETAIN`), [power.c:134-143](fw/User/power.c#L134-L143) — **[CODE]**:

1. `power_off_epd()` — EPD rails only.
2. LEDs off.
3. Mark suspended. Return.

FPGA stays configured, DDR3 stays powered and refreshed, ADV7611 and PTN3460 stay
powered, USB-PD/DP alt-mode untouched. Resume is `power_on_epd()` + `caster_redraw()`
([ui.c:955-965](fw/User/ui.c#L955-L965)).

**Full path** (any other reason), [power.c:144-163](fw/User/power.c#L144-L163) — **[CODE]**:

1. If reason != `VIDEO_LOSS`: `usbpd_disarm_wake()`, `usbpd_suspend_displayport()`.
2. `power_off_epd()` — **EPD rails go off first, before the FPGA is touched.**
3. `fpga_suspend()` — [fpga.c:176-180](fw/User/fpga.c#L176-L180): `FPGA_SUSP=1`,
   **`FPGA_PROG=0`**. Driving PROG_B low **erases the FPGA configuration.**
4. If reason != `VIDEO_LOSS`: `adv7611_powerdown()`, `ptn3460_powerdown()`, `HPD_EN=0`,
   `DEC_RST=0`, `DP_PDN=0`.
5. LEDs off, mark suspended.

Note the `VIDEO_LOSS` asymmetry: on video loss the **video frontends deliberately stay
powered** (so the board can notice video coming back). That means `POWER_SUSPEND_USER`
should draw *less* than `POWER_SUSPEND_VIDEO_LOSS`. Your measured 0.42 W "no video"
figure is the `VIDEO_LOSS` state, i.e. **not the floor.** — **[INFER]**

**EPD rail-off order**, [power.c:258-267](fw/User/power.c#L258-L267) — **[CODE]**:
VCOM disable → 10 ms → `EPD_POSEN=0` + DAC2 stop → 10 ms → `EPD_PWREN=0` + DAC1 stop.
So positive rails collapse before negative. There is **no wait for an in-flight panel
update to finish** inside `power_off_epd()` — that responsibility sits with the caller,
and only `enter_retain()` actually discharges it (§1.4).

**DDR3 framebuffer**: contents are lost on the full path, because step 3 erases the FPGA
configuration and the DDR3 controller lives in the FPGA fabric — no controller, no
refresh. Retain keeps it. — **[INFER]**, high confidence.

### 1.2 Every `POWER_SUSPEND_*` reason

[power_state.h:23-28](fw/User/power_state.h#L23-L28).

| Reason | Raised by | EPD rails | FPGA config | Video frontends | USB-PD wake |
|---|---|---|---|---|---|
| `NONE` | initial state | — | — | — | — |
| `USER` | shell `power off`, `USBCMD_POWERDOWN` param 1, `ACT_POFF` button | off | erased | powered down | disarmed |
| `VIDEO_LOSS` | `recover_from_live_loss()` ([ui.c:762](fw/User/ui.c#L762)) | off | erased | **left on** | **left armed** |
| `USB` | USB bus suspend ([ui.c:992](fw/User/ui.c#L992)) | off | erased | powered down | disarmed |
| `RETAIN` | `USBCMD_POWERDOWN` param 0/2, shell `power retain` | off | **kept** | **kept** | **kept** |

### 1.3 Every `POWER_WAKE_*` source

[power_state.h:14-19](fw/User/power_state.h#L14-L19). Which are polled depends on which
suspend branch `ui_task` is sitting in.

| Source | Polled in deep suspend ([ui.c:775-804](fw/User/ui.c#L775-L804)) | Polled in retain ([ui.c:855-895](fw/User/ui.c#L855-L895)) |
|---|---|---|
| `BUTTON` | yes, 200 ms queue wait | yes, 30 ms queue wait |
| `USB_PD` | yes, armed 1 s after entering suspend | no |
| `INPUT` (video came back) | yes, **only if reason == `VIDEO_LOSS`** | n/a |
| `USB` (host `POWERUP` / bus resume) | yes | yes |
| `DAMAGE` (framebuffer changed) | no | yes, **only if entered via param 0**, not param 2 |

**Gotcha worth knowing** (already documented in CLAUDE.md, confirmed in code): a request
to *enter* retain or full suspend is only consumed while `ui_task` is in its active
branch ([ui.c:998-1012](fw/User/ui.c#L998-L1012)). Sending `retain` while already
suspended is silently dropped. Only `RESUME`, and `SUSPEND`-to-deepen, are handled from
the suspended branch. Always bounce through active.

### 1.4 The correct shutdown pattern already exists — in exactly one place

`enter_retain()` [ui.c:815-853](fw/User/ui.c#L815-L853) is the only path that cuts EPD
rails *safely*. It:

1. Disables the OSD.
2. Polls `caster_get_damage_counter()` until the image has been quiet for
   `RETAIN_QUIET_MS` = 120 ms (giving up after 2 s).
3. `caster_wait_idle(1000)` — waits for the FPGA's op queue to drain
   ([caster.c:129-143](fw/User/caster.c#L129-L143)).
4. Sleeps `RETAIN_SETTLE_MS` = 700 ms so in-flight per-pixel waveforms finish **on
   glass**.
5. Only then `power_suspend(POWER_SUSPEND_RETAIN)`.

Hold this next to §2. The video-loss path does none of steps 1–4.

### 1.5 FPGA bitstream lifecycle

- **No config flash.** `fpga_init()` ([fpga.c:156-174](fw/User/fpga.c#L156-L174)) resets
  the FPGA and streams the bitstream from the MCU's SPIFFS every time. Confirmed —
  **[CODE]**.
- `fpga_suspend()` erases config (PROG_B low); `fpga_resume()`
  ([fpga.c:182-186](fw/User/fpga.c#L182-L186)) only releases PROG_B and waits 2 ms — it
  does **not** reload. The reload happens in `restart_fpga()`
  ([ui.c:653-664](fw/User/ui.c#L653-L664)).
- **Reload time [EST]:** `fpga.bit` is 450,366 B = 3.60 Mbit. SPI runs at 24 MHz during
  bitstream load ([fpga_spi_policy.c:3-5](fw/User/fpga_spi_policy.c#L3-L5)), then drops to
  1 MHz for registers. Pure shift time = 3.60e6 / 24e6 = **150 ms**. SPIFFS reads are
  double-buffered against the SPI DMA in 4 KB blocks
  ([fpga.c:76-96](fw/User/fpga.c#L76-L96)), so flash read time largely overlaps; call it
  **150–250 ms**. Add `fpga_reset()` 12 ms, `fpga_wait_done()` quantized to 100 ms
  ([fpga.c:127-138](fw/User/fpga.c#L127-L138)), and `restart_fpga()`'s CSR poll which
  sleeps 100 ms *before its first check* ([ui.c:657](fw/User/ui.c#L657)) — so **~0.35–0.5 s
  for FPGA bring-up**, with ~200 ms of that being pure polling quantization that could be
  tightened.
  **You do not have to trust this estimate**: the firmware already logs the real number
  as `Bitstream loading took %d ms` ([fpga.c:123](fw/User/fpga.c#L123)) and `FPGA is up
  after %d ms` — just read `syslog`.
- **After a full suspend/resume, a full refresh is mandatory**, because DDR3 lost the
  framebuffer *and* the FPGA lost its previous-frame state used for waveform selection. It
  is triggered automatically inside `start_display_pipeline()` →
  `apply_input_selection()`; the host does not need to ask. — **[INFER]**
- After a **retain** suspend/resume, DDR3 was never lost, and resume issues
  `caster_redraw(0,0,hact,vact)` ([ui.c:960](fw/User/ui.c#L960)) — a full-screen redraw
  from intact data. Image should return intact, not ghosted. — **[INFER]**

### 1.6 The CDC shell — full command inventory

Table at [shell.c:107-129](fw/User/shell/shell.c#L107-L129). Prompt is `# `, Enter is
`\r`. Device is the CDC-ACM "Debug" interface, typically `/dev/ttyACMx`.

Always present:

| Command | Purpose |
|---|---|
| `help` | list commands |
| `ver` | firmware version + git hash — **this is Experiment 0** |
| `syslog` | dump the firmware log ring |
| `setcfg` | get/set any config field, incl. `input_sel` and `bitstream` |
| `setres` | set display resolution/timing |
| **`power`** | **`status` \| `off` \| `retain` \| `resume`** — [shell_cmds.c:805-839](fw/User/shell/shell_cmds.c#L805-L839) |
| `exit` | leave shell |

Gated behind `GLIDER_DIAGNOSTIC_SHELL` (defined in all three build configs in this tree,
per commit `a18df1c`, so present in a local build; **may be absent from an upstream
release build**):

`mem`, `test`, `i2c_probe`, `recv`, `send`, `fs`, `setvolt`, `sensor`, `damage`.

`sensor` prints the per-rail voltage/current/power breakdown
([shell_cmds.c:1046-1078](fw/User/shell/shell_cmds.c#L1046-L1078)) — that is what lets you
attribute board power to the FPGA (1V2/1V35), the video frontends (1V8VID/3V3VID) and the
EPD (5VES/5VEG) **without a USB meter**, and it is what `power_survey.py` drives.

**Answer to "does a working EPD-power/suspend command already exist independent of the
HID stubs": yes — `power retain`, `power off`, `power resume`.** They post requests via
`power_post_request()` ([shell_cmds.c:814-820](fw/User/shell/shell_cmds.c#L814-L820)),
consumed by `ui_task`. Conditional on Experiment 0.

There is also a **no-host** trigger: the default button binding for **long-press BTN1** is
`ACT_POFF` ([config.c default_actions index 3](fw/User/config.c#L277-L284) ↔
[ui.c:427-432](fw/User/ui.c#L427-L432)). Note `ACT_POFF` **deliberately blanks the panel
first** — `caster_redraw_blank()` then a full redraw then `power_off()`
([ui.c:562-569](fw/User/ui.c#L562-L569)). So the button is *not* the retention path; it is
designed to leave a clean white screen.

### 1.7 Which input path is active on your hardware

- Selection is `config.input_sel`, values `INPUT_SEL_AUTO=0`, `TMDS=1`, `DP=2`
  ([config.h:36-38](fw/User/config.h#L36-L38)).
- **Default is `INPUT_SEL_AUTO`** ([config.c:262](fw/User/config.c#L262)), and it is
  re-clamped to AUTO if out of range ([config.c:291-292](fw/User/config.c#L291-L292)).
- Persisted in the SPIFFS config blob via `config_save()`; also settable from the OSD
  menu, from `USBCMD_SETINPUT`, and from the shell (`setcfg input_sel`)
  ([shell_cmds.c:945](fw/User/shell/shell_cmds.c#L945)).
- Dispatch is `apply_input_selection()`
  ([ui.c:622-651](fw/User/ui.c#L622-L651)).

**This is the important part, and it cuts against the assumption in the task.** On the
`INPUT_SEL_AUTO` branch the firmware calls `resume_video_frontends()`
([ui.c:679-684](fw/User/ui.c#L679-L684)), which initialises **both** frontends:

```c
adv7611_early_init();  adv7611_init();  ptn3460_init();  usbpd_resume_displayport();
```

So: **even on a pure-HDMI setup, if `input_sel` is AUTO (the default), `ptn3460_init()`
still runs.** PR #16's PTN3460 half is therefore *not* automatically irrelevant to you —
contrary to the framing in the task. It is only irrelevant if you have explicitly pinned
`input_sel` to TMDS, in which case [ui.c:629](fw/User/ui.c#L629) calls
`ptn3460_powerdown()` instead.

Concrete checks you can run — **[TEST]**, see Experiment 1:

1. `setcfg input_sel` — prints the stored value. 0 = Auto, 1 = TMDS, 2 = DP.
2. `syslog` — look for `Requesting auto input` vs `Requesting TMDS input` vs `Requesting
   DP input` ([ui.c:626/633/646](fw/User/ui.c#L626)), and for `PTN3460 up after %d ms`
   ([ptn3460.c:79](fw/User/ptn3460.c#L79)). If that PTN3460 line appears, the DP chip is
   being initialised regardless of what you feed the board.
3. `syslog` also logs `Input status %02x, measured %u x %u`
   ([ui.c:749](fw/User/ui.c#L749)). Decode against
   [caster.h:124-131](fw/User/caster.h#L124-L131): bit1 = TMDS, bit2 = DP, bit5 = LIVE.
   `INPUT_STATUS_TMDS` set + `LIVE` set ⇒ you are on the ADV7611 path.
4. `sensor` — with HDMI live, compare the 1V8VID/3V3VID draw before and after
   `setcfg input_sel 1` + reboot. If pinning TMDS drops those rails measurably, the
   PTN3460 was being powered needlessly.

**Status: unresolved from code alone** — it depends on your saved config. Item 3 resolves
it definitively in one command.

---

## 2. The gray screen: the code path that explains it

**Confidence: high that this is the mechanism. `recover_from_live_loss()`
([ui.c:762-773](fw/User/ui.c#L762-L773)) is an active clear, not a passive rail collapse —
and it may be *both*.**

When live video is lost, `ui_task` detects it at
[ui.c:1055-1060](fw/User/ui.c#L1055-L1060) (or via `INPUT_STATUS_LOST` at
[ui.c:1073-1086](fw/User/ui.c#L1073-L1086)) and calls:

```
recover_from_live_loss()
 └─ reload_to_internal_source()                         [ui.c:753-760]
     ├─ power_off_epd()                 ← rails off, image frozen as-is
     └─ start_display_pipeline()                        [ui.c:666-677]
         ├─ restart_fpga()              ← ***FPGA RECONFIGURED — DDR3 FRAMEBUFFER LOST***
         ├─ power_on_epd()              ← rails back ON
         ├─ caster_init()               ← CSR_ENABLE=1, refresh enabled  [caster.c:79]
         └─ apply_input_selection()
 ├─ draw_signal_popup("Sleeping")       ← OSD on
 ├─ caster_redraw(0,0,hact,vact)        ← ***FULL-SCREEN REDRAW OF THE LOST FRAMEBUFFER***
 ├─ sleep_ms(600)                       ← only 600 ms
 └─ power_suspend(POWER_SUSPEND_VIDEO_LOSS)  ← power_off_epd() immediately  [power.c:148]
```

There are **two independent gray-making mechanisms here, and they predict different
visual signatures**:

**Mechanism A — active clear (abrupt).** The FPGA is reconfigured, so DDR3 no longer holds
your page. The firmware then *deliberately powers the rails back on and drives a
full-screen redraw* of whatever the freshly-reloaded framebuffer contains. That is an
active drive of every pixel to garbage/uniform content. Predicted signature: **abrupt**,
one visible full-panel flash, ending gray/mottled.

**Mechanism B — rails cut mid-waveform (fade/streaky).** The 600 ms wait at
[ui.c:771](fw/User/ui.c#L771) is not synchronised to anything. Unlike `enter_retain()`,
this path calls **no `caster_wait_idle()`** and **no damage-quiet poll**. If the redraw
takes longer than 600 ms, `power_suspend()` cuts the rails mid-waveform and pixels freeze
in intermediate states. Predicted signature: **uneven, streaky, mid-gray, possibly with
visible banding**, and *mode-dependent*.

**The mode-dependence is the key falsifiable prediction — [INFER]/[EST]:**
`get_update_frames()` returns a hardcoded 16 ([caster.c:40-45](fw/User/caster.c#L40-L45),
comment: *"actually, just always return 0.5s"*), but `caster_init()` programs
`CSR_LUT_FRAME = 38` ([caster.c:74](fw/User/caster.c#L74)). LUT-based modes
(`UM_AUTO_LUT_NO_DITHER`, the "Reading" preset) run the full 38-frame waveform; the fast
mono modes run ~16. At a plausible EPD frame rate of 50–65 Hz, 16 frames ≈ 250–320 ms
(fits inside 600 ms) but 38 frames ≈ 580–760 ms (**does not**).

⇒ **Prediction: the gray screen is worse in "Reading" mode than in "Browsing" mode.** If
Experiment 4 confirms that, Mechanism B is live and the fix is a `caster_wait_idle()` call.
If the damage is identical in both modes, Mechanism B is not the driver and Mechanism A
alone explains it — the fix is then "don't reload the FPGA and don't redraw on video
loss," i.e. route video loss into the retain path instead.

**Contrast with the retain path, which is already correct.** `enter_retain()` does *not*
reload the FPGA, does *not* redraw, waits for damage-quiet, waits for
`caster_wait_idle()`, and waits 700 ms of settle before cutting rails. **This strongly
suggests the fix for your bug is to make video-loss behave like retain** — and that
`recover_from_live_loss()` simply pre-dates the retain work (commit `b4314e1`) and never
got the same treatment.

---

## 3. Decision (Task 2), and why

### PR #16 → **(b), partially: cherry-pick the PTN3460 hunks only. Reject the usbapp.c hunk.**

Applied on this branch as commit `da63bb8`, +2 lines, `fw/User/ptn3460.c` only.

**Why reject the `usbapp.c` hunk** — this is the substantive call. PR #16 does:

```c
case USBCMD_POWERDOWN:  power_suspend(POWER_SUSPEND_USER);       break;
case USBCMD_POWERUP:    power_request_resume(POWER_WAKE_USB);    break;
```

directly inside `tud_hid_set_report_cb()`. That runs in the **TinyUSB task context**, and
`power_suspend()` does blocking I2C, GPIO sequencing, `sleep_ms()` and `fpga_suspend()`.
Meanwhile `ui_task` is in its own loop hitting `fpga_write_reg8(CSR_ID0, ...)` every
iteration and **calls `NVIC_SystemReset()` if that read ever fails**
([ui.c:1061-1065](fw/User/ui.c#L1061-L1065)). Erasing the FPGA configuration from another
task while `ui_task` polls the CSR bus is a textbook way to trip that reset. Given that
`ui_task` reset is the only spontaneous reset path in this firmware, this is a genuine
"why does my board randomly reboot" generator.

This tree's existing implementation
([usbapp.c:161-176](fw/User/usbapp.c#L161-L176)) is strictly better: it posts a request via
`power_post_request()` and lets `ui_task` — the task that owns the FPGA — do the work, and
it supports three modes (retain / full / retain-no-autowake) instead of one. Taking PR #16
here would be a regression.

**Why take the PTN3460 hunks.** They are independent of the power work and both are real:

- `ptn3460_init()` logged `PTN3460 boot timeout` after 500 ticks and then **kept looping
  forever** ([ptn3460.c:72-80](fw/User/ptn3460.c#L72-L80)). Since `ptn3460_init()` is
  called from `ui_task` via `apply_input_selection()` — **including on the AUTO path you
  are probably on** — a PTN3460 that never raises DP_HPD hangs `ui_task` before the
  display ever comes up. Adding `break;` bounds it.
- 50 ms settle after `DP_PDN=1` before the first I2C access is ordinary good practice.

Against the criteria: it does **not** fix your gray screen, it does **not** save power, and
it is **not** needed for Stage 1. It is 2 lines of pure insurance against a hang class,
carried at essentially zero cost and zero upstream-drift risk (if Modos merges PR #16, this
becomes a no-op merge). **Do not flash on its account alone** — fold it into whatever build
you flash next for a real reason.

### PR #17 → **(c), skip. Not now.**

Five reasons, in descending order of decisiveness:

1. **The prize is tiny and you have already measured that it is tiny.** The clock tree is
   HSE 24 MHz, PLLM=24, PLLN=192, PLLP=4 ⇒ **SYSCLK = 48 MHz**, at
   `PWR_REGULATOR_VOLTAGE_SCALE3` with `FLASH_LATENCY_1`
   ([main.c:221-259](fw/Core/Src/main.c#L221-L259)). This is *not* a 480 MHz H750 — it is
   an H750 loafing at a tenth of its rated clock in the lowest voltage scale. **[EST]:**
   STM32H750 Run at 48 MHz / VOS3 draws roughly 25–40 mA; on the 3V3 rail that is
   **~80–130 mW**. WFI (Sleep mode) gates the CPU clock but leaves PLL and peripherals
   running, saving perhaps 30–40% ⇒ **~25–50 mW recoverable, at 100% duty**. Against your
   1770 mW active that is **1.4–2.8%**; against the 420 mW idle state, **6–12%**. Error
   bars are wide (±50%) because I do not have the datasheet's exact VOS3/48 MHz row in
   front of me, but the order of magnitude is not in doubt. Your own measurement already
   says 76% of the board is the video path — the MCU is not where your battery goes.
2. **The change cannot achieve even that, because of a task this PR does not touch.**
   `key_scan_task` runs `vTaskDelay(pdMS_TO_TICKS(10))`
   ([ui.c:1234](fw/User/ui.c#L1234)). Tickless idle only suppresses ticks while *every*
   task is blocked, so the sleep window is capped at **10 ms** no matter what
   `configUSE_TICKLESS_IDLE` does. `power_monitor_task` at 100 ms
   ([power.c:435](fw/User/power.c#L435)) and `ui_task` at 200 ms
   ([ui.c:1109](fw/User/ui.c#L1109)) are irrelevant next to that. Enabling tickless idle
   without first fixing the 10 ms key scan buys you a fraction of the 25–50 mW. **The
   cheap win PR #17 is reaching for is "make `key_scan_task` interrupt-driven or slower",
   and PR #17 does not do that.**
3. **It does not apply to this tree.** Verified: `git apply --check` fails at
   `fw/User/usbpd.c:90`; `--3way` applies the other three files cleanly but conflicts in
   `usbpd.c`. Local commit `8d1b467` already changed `fusb302_tcpc_alert(0)` →
   `tcpc_alert(0)` on the same lines PR #17 rewrites. Carrying it means hand-resolving a
   conflict in USB-PD code every time either side moves.
4. **It edits vendored Chrome EC code.** The second commit's "idle timeout" — the thing the
   task asked me to identify — is
   [usb_pd_protocol.c:3084](fw/User/usbpd/usb_pd_protocol.c#L3084): in
   `PD_STATE_SNK_READY`, `timeout = 200*MSEC_US` becomes `2000*MSEC_US`. That is the PD
   state machine's re-poll interval once contract negotiation is complete; it feeds
   `xSemaphoreTake(isr_sem, pdMS_TO_TICKS(timeout/1000))` in the task loop. A 10× longer
   poll means up to 2 s of latency reacting to anything the FUSB302 does not raise a hard
   interrupt for — and **DP alt-mode / HPD handling rides on this loop**. On a board whose
   whole job is a display link, that is a real if unquantified risk, and it is exactly the
   kind of change a maintainer will want to tune differently.
5. **It is Stage 3 work.** Your blocking problem is the gray screen (§2), which is a
   correctness bug in `recover_from_live_loss()`. PR #17 addresses neither the gray screen
   nor the 76% that is the video path.

**The one genuinely good idea in PR #17** is unrelated to tickless idle: upstream's
`do { tcpc_alert(0); ... } while (gpio_get(TCPC_INT) == 0)`
([usbpd.c:99-113](fw/User/usbpd.c#L99-L113)) has no iteration bound, so a stuck-low TCPC
interrupt pins the CPU at 100%. PR #17 bounds it at 5 iterations. **Whether that loop
actually spins on your board is measurable** — Experiment 8. If it does, that is worth
fixing on its own merits, as a 5-line local change, independent of tickless idle and
independent of the PD timeout change.

### Summary

| | Decision | Applied? |
|---|---|---|
| PR #16 `usbapp.c` | **Reject** — this tree's version is better and avoids a cross-task race | no |
| PR #16 `ptn3460.c` | **Take** — 2-line hang fix, zero risk | ✅ `da63bb8` |
| PR #17 tickless idle | **Skip** — capped at 10 ms by `key_scan_task`, ~1–3% of budget | no |
| PR #17 `usbpd.c` loop bound | **Defer** — good idea, but measure Experiment 8 first | no |
| PR #17 PD 200→2000 ms | **Reject** — risks DP/HPD latency, edits vendored code | no |

### Build status

**Not compile-verified.** No `arm-none-eabi-gcc`, no `dfu-util`, no STM32CubeIDE in this
environment (checked). The change is 2 lines in one file with no new symbols, so the risk
is low, but it is unverified and I am not claiming otherwise.

The host-side C unit tests **do** run here and pass (`bash fw/User/tests/build_host_tests.sh`,
exit 0) — they do not cover `ptn3460.c`.

To build for real you need STM32CubeIDE (headless is fine):
`scripts/build_mcu.sh <version> <release-dir>`, or `scripts/dev_flash_mcu.sh` for the
rebuild+flash dev loop. Install `dfu-util` and the udev rules from
`utils/flash_tool/99-glider.rules` first.

### Recovery path (verified in the repo, not on hardware)

- The STM32H750 is DFU-updatable. **DFU entry: hold the button nearest the USB port while
  plugging in USB** (USAGE.md:63, :195, :236).
- Manual flash: `dfu-util -a 0 -i 0 -s 0x08000000:leave -D glider_ec_rtos.bin` (USAGE.md:214).
- **Back up the stock image before flashing anything.** Note the repo ships a prebuilt
  `utils/flash_tool/glider_ec_rtos.bin` and `utils/flash_tool/fpga.bit`, which is a
  fallback, but it is not necessarily the image currently on *your* board. Read yours out
  first:
  `dfu-util -a 0 -i 0 -s 0x08000000:0x20000 -U glider-stock-backup.bin`
  **[TEST]** — I have not verified the upload length or that upload is unlocked on this
  part; confirm before relying on it.
- DFU lives in STM32 system ROM, so a bad application image cannot brick the board — the
  button-hold entry path does not depend on your firmware running.

---

## 4. What is still unknown, and which experiment resolves it

| # | Unknown | Resolved by |
|---|---|---|
| U1 | **What firmware is on the board?** Stock upstream, or this tree? Everything depends on it. | Exp 0 |
| U2 | Is `input_sel` AUTO or TMDS? Is the PTN3460 being powered/initialised needlessly? | Exp 1 |
| U3 | Is the gray abrupt (Mechanism A) or streaky/mid-transition (Mechanism B)? | Exp 4 |
| U4 | Is the damage mode-dependent (⇒ Mechanism B confirmed, 600 ms too short)? | Exp 5 |
| U5 | Does commanding rails off *before* dropping the link preserve the image? | Exp 6 |
| U6 | Real power of retain vs full suspend vs video-loss. Does retain save enough to matter? | Exp 3, 7 |
| U7 | Resume latency, retain vs full. Page-turn viable? | Exp 6, 7 |
| U8 | Actual FPGA reload time (firmware logs it). | Exp 7 |
| U9 | Does the USB-PD loop actually spin at 100% CPU? | Exp 8 |
| U10 | Does coil whine change per state? | recorded throughout |
| U11 | Does `GLIDER_DIAGNOSTIC_SHELL` exist in the running build (is `sensor` available)? | Exp 0 |

---

## 5. Test plan

Ordered cheapest/safest first. **Experiments 0–8 require no flashing.** Stop and re-read
if any result contradicts a prediction — that is the point.

Setup: USB-C power meter inline, board at 5.14 V. Shell on `/dev/ttyACMx`
(`screen /dev/ttyACM0 115200`, or `picocom`). Enter is `\r`; prompt is `# `.
Install `utils/flash_tool/99-glider.rules` so you do not need `sudo`.

Record whine subjectively (none / faint / louder / different pitch) at **every** step.

---

### Exp 0 — Identify the running firmware ⚠️ **DO THIS FIRST**

**Steps:** connect shell. Run `ver`, then `help`, then `power status`.

**Measure:** nothing. **Observe:** version string + git hash; whether `power` is listed;
whether `sensor` is listed.

**Predicted:** if the board runs this tree, `ver` reports a hash at/after `b4314e1`, and
both `power` and `sensor` appear.

**If `power` is absent** → the board is on upstream stock. Everything from Exp 3 onward
needs a flash first, and the decision in §3 should be revisited: you would then want to
build and flash *this tree* (which already has retain suspend) rather than either PR.
**This single result changes the whole plan.**

**If `sensor` is absent** but `power` is present → `GLIDER_DIAGNOSTIC_SHELL` is off in the
running build; you lose per-rail attribution and must rely on the USB meter alone.

→ Decision tree: gates everything.

---

### Exp 1 — Establish the input path (U2)

**Steps:** `setcfg input_sel`. Then `syslog`, and search for `Requesting `, `PTN3460 up
after`, and `Input status`.

**Observe:** the `Input status %02x` value. Decode: bit1(0x02)=TMDS, bit2(0x04)=DP,
bit3(0x08)=STABLE, bit4(0x10)=SUPPORTED, bit5(0x20)=LIVE.

**Predicted:** `input_sel` = 0 (Auto); `Requesting auto input`; `PTN3460 up after N ms`
**present** (because AUTO initialises both frontends); `Input status` with 0x02|0x20 set
⇒ ADV7611/TMDS carrying the picture.

**If `PTN3460 up` is present** → the DP chip is powered and initialised even though you
feed HDMI. PR #16's PTN3460 hunks *are* relevant to you, and Exp 2 may be free power.
**If `input_sel` is already 1** → PTN3460 is powered down; skip Exp 2.

---

### Exp 2 — Free power: pin the input to TMDS (U2, U6)

**Steps:** record baseline W with video live. `setcfg input_sel 1`, then power-cycle.
Confirm picture still works. Record W. Run `sensor`, note 1V8VID / 3V3VID.

**Predicted [EST]:** **30–120 mW saved** — the PTN3460 stops being initialised and held
up. Small, but it is free, persistent, and costs nothing but a config write.

**If no change** → the PTN3460 was already idle/powered down; harmless, revert with
`setcfg input_sel 0` if you ever want DP.

---

### Exp 3 — Baseline power state table (U6)

Fill this in. Predictions are **[EST]**, ±30% unless noted.

| State | How to reach it | Predicted W @ 5.14 V | Measured W | Whine | Panel |
|---|---|---|---|---|---|
| Active, KOReader | normal | 1.77 (**measured, given**) | | | image |
| Active, CLI | normal | 1.77 (**measured, given**) | | | image |
| No video (`VIDEO_LOSS`) | unplug HDMI | 0.42 (**measured, given**) | | faint (given) | **gray — the bug** |
| **Retain** | `power retain` | **1.15 – 1.50** | | | **image kept** |
| **Full suspend** (`USER`) | `power off` | **0.22 – 0.35** | | | blanked white |
| Resumed from retain | `power resume` | ≈ 1.77 | | | image back |
| Resumed from full | `power resume` | ≈ 1.77 | | | full refresh then image |

**The two predictions that matter, and why:**

- **Retain will disappoint you.** It only cuts the EPD rails; FPGA, DDR3 and both video
  frontends stay fully alive ([power.c:134-143](fw/User/power.c#L134-L143)). Since your own
  measurement says the video path is 76% of the board, retain should land **near active,
  not near idle**. Retain is a *latency* optimisation, not a *power* one.
- **`power off` will beat the 0.42 W "no video" state.** `VIDEO_LOSS` deliberately leaves
  the frontends powered ([power.c:150-156](fw/User/power.c#L150-L156)) so it can see video
  return; `USER` powers them down. **Predicted: `power off` < 0.42 W.**

**If retain measures near 0.42 W** → my model of where the power goes is wrong, the FPGA/DDR3
is not the load I think it is, and retain becomes your primary battery strategy. Great news;
tell me.
**If `power off` is not below 0.42 W** → the frontend powerdown is not effective, and the
1V8VID/3V3VID rails in `sensor` will show it.

---

### Exp 4 — Characterise the gray: abrupt vs fade (U3) ⭐ **the decisive one**

**Steps:** display a high-contrast page (text). Have the panel in view and, ideally, a
phone recording video at 60 fps — the distinction happens in under a second and you will
not catch it reliably by eye. Then yank the HDMI cable. Immediately afterwards, run
`syslog`.

**Observe, in the recording:**

- Does the panel do **one visible full-panel flash/sweep** and settle to uniform gray?
- Or does the image **decay unevenly**, streaky/banded, with parts of the old image
  lingering?
- How long from cable-out to final state?
- Does the "Sleeping" OSD box appear?

**In `syslog`, expect this sequence** ([ui.c:756-772](fw/User/ui.c#L756-L772)):
`Live video lost; reloading FPGA into internal source` → `Loading bitstream 'fpga.bit'` →
`Bitstream loading took N ms` → `FPGA is up after N ms` → `Waiting for FPGA CSR access` →
`FPGA up` → VN/VGL/VP/VGH/VCOM voltages → `Suspending system` → `System suspended`.

**Predicted:** you see all of the above, and a **full-panel flash ~0.5–1.0 s after cable-out,
settling to gray** (Mechanism A dominant), possibly with streaks (Mechanism B on top).

**Discrimination:**
- **One clean flash → uniform gray** ⇒ **Mechanism A only.** Fix: stop reloading the FPGA
  and stop redrawing on video loss; route video loss into the retain path.
- **Uneven / streaky / partial** ⇒ **Mechanism B present.** Fix: add `caster_wait_idle()`
  before the rails come down.
- **Slow passive fade with no flash and no `Loading bitstream` in syslog** ⇒ neither; my
  analysis is wrong and this is an analog/rail problem. Send me the syslog.
- **No syslog entries at all** ⇒ the board is not running this firmware; go back to Exp 0.

---

### Exp 5 — Is the damage mode-dependent? (U4)

**Steps:** repeat Exp 4 twice: once with update mode = **"Browsing"** (`UM_FAST_MONO_BAYER`,
~16 frames) and once with **"Reading"** (`UM_AUTO_LUT_NO_DITHER`, 38-frame LUT). Set via
the OSD menu or the button bindings. Same page, same yank, record both.

**Predicted:** **"Reading" is visibly worse** — because a 38-frame waveform (**[EST]**
580–760 ms) does not fit inside the hardcoded `sleep_ms(600)` at
[ui.c:771](fw/User/ui.c#L771), whereas 16 frames (~250–320 ms) does.

**Discrimination:**
- **Reading worse than Browsing** ⇒ **Mechanism B confirmed**, and the 600 ms constant is
  the proximate cause. Cheap, surgical fix.
- **Identical in both modes** ⇒ Mechanism B ruled out; Mechanism A alone. The fix is
  structural (don't reload/redraw), not a constant.

---

### Exp 6 — Rails off *before* the link drops (U5, U7) ⭐ **the one that might just solve it**

**Steps:** with a page displayed and HDMI live:
1. `power retain`  → wait 3 s → **observe and photograph the panel.**
2. **Now** unplug HDMI. Observe again.
3. Replug HDMI. Observe. Then `power resume`. Time it with a stopwatch.

**Predicted:**
1. After `power retain`: **image stays on the panel, fully intact.** This is the whole
   point of the retain path, and `enter_retain()` does the settle correctly
   ([ui.c:815-853](fw/User/ui.c#L815-L853)).
2. After unplugging: `wait_for_retain_wake()` notices video loss and calls
   `power_retain_deepen(POWER_SUSPEND_VIDEO_LOSS)`
   ([ui.c:876-880](fw/User/ui.c#L876-L880)). Crucially, **`power_retain_deepen()` does NOT
   redraw and does NOT reload the FPGA** ([power.c:169-187](fw/User/power.c#L169-L187)) —
   it only suspends the FPGA and (for non-VIDEO_LOSS reasons) the frontends. **Predicted:
   the image survives.** Power should fall toward the `VIDEO_LOSS` figure.
3. `power resume` from a deepened retain goes through the **full** resume path
   (`last_suspend_reason` is now `VIDEO_LOSS`, not `RETAIN`), so bitstream reload + full
   refresh. **[EST] 1.5–3 s.**

**This is the big one.** If step 2 preserves the image, then **your workaround exists today
with zero firmware changes**: have the Pi send `power retain` (shell) or
`USBCMD_POWERDOWN` param 0 (HID, via `flash.py`) *before* it blanks the link, instead of
just dropping the link. That sidesteps `recover_from_live_loss()` entirely.

**If the image is destroyed in step 1** → `enter_retain()`'s settle is insufficient too,
and the problem is more fundamental than `recover_from_live_loss()`. Report the syslog.
**If it survives step 1 but dies in step 2** → deepening is also destructive; worth a
separate look, and it would surprise me.

---

### Exp 7 — Resume latency and the FPGA reload number (U7, U8)

**Steps:** stopwatch each, three times, take the median:
- (a) `power retain` → `power resume` (fast path: `power_on_epd()` + redraw).
- (b) `power off` → `power resume` (full path: bitstream reload + pipeline restart).
Then `syslog` and read the **actual** `Bitstream loading took N ms` and `FPGA is up after
N ms` lines.

**Predicted [EST]:**
- (a) **0.6–1.2 s** — rail bring-up (polled at 10 ms, [power.c:189-190](fw/User/power.c#L189-L190))
  plus one full redraw. **Marginal for a page turn; fine after a reading pause.**
- (b) **1.5–3.0 s** — ~0.35–0.5 s FPGA (§1.5) + rails + `caster_init()` + full refresh.
  **Not page-turn viable.**
- `Bitstream loading took` ≈ **150–250 ms**.

**If (a) is under ~400 ms** → retain is page-turn viable and becomes the centre of your
power strategy despite its poor power figure.
**If `Bitstream loading took` is ≫ 400 ms** → SPIFFS read is the bottleneck, not the 24 MHz
SPI, and there is headroom in `fpga_spi_policy.c` / the SPIFFS config.

---

### Exp 8 — Does the USB-PD loop actually spin? (U9)

**Steps:** at idle with video live, run `sensor` and note the **3V3** rail current
(the MCU's rail). Then compare against the 3V3 draw in `power off` state.

**Predicted [EST]:** MCU at 48 MHz/VOS3 ⇒ **25–40 mA on 3V3**. A pinned-at-100% CPU would
sit at the top of or above that range; a mostly-idle CPU nearer the bottom.

**If 3V3 is ≥ 40 mA and does not drop in suspend** → the `do/while (gpio_get(TCPC_INT)==0)`
loop ([usbpd.c:99-113](fw/User/usbpd.c#L99-L113)) is likely spinning, and PR #17's
loop-bound hunk is worth taking **on its own**, separately from tickless idle.
**If 3V3 is ~25 mA** → nothing is spinning; PR #17 has no case at all and the skip decision
in §3 is confirmed.

Caveat: this is indirect. A proper answer needs FreeRTOS runtime stats
(`configGENERATE_RUN_TIME_STATS`), which this build does not enable.

---

## 6. Continue here — next step per outcome

Hand this file back with the tables filled in and the syslog dumps, and pick up from here.

**If Exp 0 says the board is on upstream stock** → nothing else in this plan is valid as
written. Next step: back up the stock image via DFU, build this tree
(`scripts/build_mcu.sh`), flash it, redo Exp 0–3. This tree's retain suspend is a large
head start over stock and over both PRs.

**If Exp 6 step 2 preserves the image** → **stop firmware work.** Solve it host-side: make
the Pi issue `power retain` (or HID `USBCMD_POWERDOWN` param 0 through `flash.py`) before
it blanks, and `power resume`/`USBCMD_POWERUP` on wake. Wire that into a
`cage`/KOReader idle hook. Zero flash risk, Stage 1 complete. Then revisit power with
Exp 3's numbers — likely by preferring `power off` over retain for long idles.

**If Exp 5 shows Reading worse than Browsing (Mechanism B)** → the fix is surgical: in
`recover_from_live_loss()` ([ui.c:762-773](fw/User/ui.c#L762-L773)), replace the bare
`sleep_ms(600)` with `caster_wait_idle(...)` + a settle, mirroring `enter_retain()`
([ui.c:844-848](fw/User/ui.c#L844-L848)). ~4 lines. This is also a clean, well-motivated
upstream PR.

**If Exp 5 shows no mode dependence (Mechanism A only)** → the fix is structural: on video
loss, do **not** call `reload_to_internal_source()`. Either enter the retain path directly,
or reorder so the FPGA is suspended without the intervening `power_on_epd()` +
`caster_redraw()`. Bigger change, needs care around the `INPUT_STATUS_LOST` branch at
[ui.c:1073-1086](fw/User/ui.c#L1073-L1086) which shares the same helper. Ask me and I will
draft it against the measured behaviour.

**If Exp 3 shows retain ≈ active** (as predicted) → retain is for page-turn latency only.
Battery strategy becomes tiered: retain for short idles (< ~1 min), `power off` for long
ones, accepting Exp 7(b) wake latency.

**If Exp 8 shows a spinning PD loop** → cherry-pick *only* the loop-bound hunk from PR #17's
`usbpd.c` (not the tickless-idle commit, not the 200→2000 ms change), hand-resolving the
conflict against local `8d1b467`.

**If you later want the MCU idle win anyway** → do it in this order: (1) make
`key_scan_task` interrupt-driven or drop it to 50 ms
([ui.c:1234](fw/User/ui.c#L1234)); (2) *then* enable tickless idle. Step 1 is the
prerequisite PR #17 omits, and without it step 2 is nearly a no-op.

---

## 7. Open questions for Modos / the PR author

Paste-ready.

**On the gray screen (highest value):**

> On video-signal loss, `recover_from_live_loss()` in `fw/User/ui.c` calls
> `reload_to_internal_source()`, which does `power_off_epd()` and then
> `start_display_pipeline()` — reconfiguring the FPGA (losing the DDR3 framebuffer),
> powering the EPD rails back **on**, and issuing a full-screen `caster_redraw()` — before
> `power_suspend(POWER_SUSPEND_VIDEO_LOSS)` cuts the rails again 600 ms later. On my 6"
> dev kit this leaves the panel gray with no image retained. Is the FPGA reload on video
> loss intentional? It looks like the goal is to park on the internal source, but the
> side effect is destroying the retained image. Would you accept a patch that routes video
> loss through the retain path (rails off, image kept, no FPGA reload) instead?

> Related: the `sleep_ms(600)` before `power_suspend()` in `recover_from_live_loss()` is
> not synchronised to the panel. `enter_retain()` does this properly — damage-quiet poll,
> `caster_wait_idle()`, then a 700 ms settle. Should `recover_from_live_loss()` use the
> same sequence? With a 38-frame LUT waveform (`CSR_LUT_FRAME = 38` in `caster_init()`),
> 600 ms looks too short and the rails would be cut mid-waveform.

**On `caster.c`:**

> `get_update_frames()` in `fw/User/caster.c` is hardcoded to 16 with the comment
> "actually, just always return 0.5s", but `caster_init()` programs `CSR_LUT_FRAME = 38`.
> For LUT-based modes like `UM_AUTO_LUT_NO_DITHER`, does the hardware use `CSR_OP_LENGTH`
> or `CSR_LUT_FRAME` to decide how long the update runs? I am trying to work out the true
> worst-case time for a full redraw so I know how long to wait before cutting EPD power.

**On PR #16, to @genneth:**

> In this PR, `USBCMD_POWERDOWN` calls `power_suspend()` directly from
> `tud_hid_set_report_cb()`, i.e. the TinyUSB task. `power_suspend()` does blocking I2C and
> `fpga_suspend()` (which drives PROG_B low and erases the FPGA config), while `ui_task` is
> concurrently polling `fpga_write_reg8(CSR_ID0, ...)` and calls `NVIC_SystemReset()` if
> that read fails. Have you seen spurious resets when issuing POWERDOWN over HID? Would you
> consider deferring the work to `ui_task` via a posted request instead?

**On PR #17, to @genneth:**

> Two questions. (1) `key_scan_task` in `ui.c` runs `vTaskDelay(pdMS_TO_TICKS(10))`, which
> caps any tickless-idle sleep at 10 ms — did you measure an actual power delta from
> `configUSE_TICKLESS_IDLE` with that task still running, and if so, how much? (2) The
> `PD_STATE_SNK_READY` timeout goes 200 ms → 2000 ms in `usb_pd_protocol.c`. Since DP
> alt-mode HPD handling rides on that same loop, did you check the effect on HPD /
> alt-mode reaction time?

**On the clock configuration (side observation, may be a latent bug):**

> In `SystemClock_Config()`, `PLLM = 24` with `HSE_VALUE = 24000000` gives a 1 MHz PLL
> input, but `PLLRGE` is set to `RCC_PLL1VCIRANGE_3` (8–16 MHz). Is that deliberate? Also,
> SYSCLK works out to 48 MHz at `VOLTAGE_SCALE3` — is that the intended operating point for
> the H750 on this board, or a leftover from bring-up?

---

*Generated from static analysis of the `power-analysis` branch. No hardware was observed.*

---

# Session 2 (2026-07-29) — hardware results are in; everything above is superseded where it conflicts

The board is now **confirmed running this tree's firmware** (the earlier "retain grays the
panel" report came from a stale flash and is void). Measured results:

## 8. Measured power (via `sensor`), and what died with it

| State | MCU+IO | FPGA DDR+CORE | VIDEO IN | EPD HV | ~Total |
|---|---|---|---|---|---|
| Active, static image | 572 mW | ~253 mW | ~585 mW | ~62 mW avg | **~1.46 W** |
| Retain | 566 mW | ~254 mW | ~580 mW | 0 | **~1.40 W** |
| Full off (`power off`) | 147 mW | ~15 mW | 28 mW | 0 | **~0.19 W** |

- **Gray screen: gone.** Image survives retain and full off, both directions. §2's
  mechanisms were never tested against this firmware and are moot for now.
- **Retain is dead as a power state** (−4%; EPD HV idles at ~62 mW). It survives as a
  fast-resume convenience state only. §3's Exp-3 prediction ("retain will disappoint")
  confirmed, more brutally than predicted.
- **Full off is the strategy**: −87%. Duty-cycling active↔off at 60 s/page ≈ 0.29 W board
  average. The Pi (1.5–2.4 W) is now the dominant battery problem — outside this repo.
- ~420 mW of "MCU+IO" is FPGA I/O (it vanishes when the FPGA is erased); true MCU ≈
  145 mW = **77% of the suspend floor** → MCU idle work (PR #17's regime, done properly:
  `key_scan_task` first) is back on the roadmap for the floor, though behind the item below.

## 9. The real bug: resume-from-off spuriously reboots the MCU

`power off` → `power resume` took ~4 s; `syslog` afterwards **starts at [0.000] "System
starting"** — a full reboot, with the pre-suspend log wiped. Once: 6 s + a transient dim
diffuse blob (plausibly a double reset).

Audit of reset paths **[CODE]**: no watchdog; `fatal()` (error.c:56), `HardFault`, and
`configASSERT` (FreeRTOSConfig.h:157) all hang, never reset; `USBCMD_RESET`
(usbapp.c:159) unused. The **only** reachable reset is the FPGA sanity check
[ui.c:1061-1065](fw/User/ui.c#L1061-L1065): one failed `CSR_ID0` read →
`NVIC_SystemReset()`. Its guard (`live_was_selected`) is explicitly false right after
resume ([ui.c:977](fw/User/ui.c#L977)).

Gateware **[CODE]**: `clk_epdc` — the clock the whole caster core *and the CSR/SPI
interface* run on — is `v_pclk`, the vin mux output clock
([Caster/rtl/spartan6/top.v:177](Caster/rtl/spartan6/top.v#L177)), i.e. the
video-recovered pixel clock once a source is selected (internal-clock fallback when
none). During the Pi's HDMI re-training after resume, that clock is switching/unstable —
exactly what the comment at ui.c:1052 warns about — so a CSR read can glitch → instant
reset. Timeline fits: resume ~2 s (bitstream alone measured **688 ms**, SPIFFS-bound, not
the 150–250 ms SPI estimate in §1.5) + reset + reboot 1.75 s + HDMI relock ≈ 4 s.

**[INFER]** — mechanism is code-complete but needs the discriminating test:

- **R1**: `power off` → unplug HDMI → `power resume`, ×5. Predict: **no reboot**, resume
  ~2 s, `syslog` timestamps continue and show `Waking system: 0x..`.
- **R2**: same with HDMI connected, ×5. Predict: intermittent reboot (`syslog` restarts
  at [0.000]).
- **R3** (only if R1 also reboots): brownout suspect — VBUS read 4.76 V in suspend;
  retry on a strong supply without the inline meter.

**Why this outranks everything**: the same unguarded window opens on *any* input glitch
while not-yet-live — Pi modesets, DPMS blank/unblank. The host-side blanking strategy
(§6) would trip this reset landmine constantly. Fix candidates, pending R1/R2: (fw,
small) tolerate CSR failures during the lock transition, or gate the check on ADV7611
lock status over I2C instead of CSR; (gateware, correct) run the CSR on `clk_sys` —
question for Modos/zephray. Also worth doing after: chase the 688 ms SPIFFS bitstream
read, and the ~200 ms of 100 ms-quantized polls in `restart_fpga()`.

## 10. R1/R2 results — hypothesis CONFIRMED; Fix A applied

Hardware results (2026-07-29, later same day):

- **R1, HDMI unplugged**: resume completes cleanly — syslog timestamps continue
  (`Waking system: 0x08`), **no reboot, 1.2 s** board-side (bitstream 564 ms).
- **R2, HDMI connected**: **rebooted every time** (syslog restarts at `[0.000]`).
- **Pinned TMDS (`input_sel 1`) + off/resume**: repeating **reset loop** — EPD rails
  cycling audibly (periodic whine), transient gray blob from fragmentary aborted drives,
  ~15 s until it escapes by winning the race, sometimes stuck (`ui_task` parked, shell
  alive, rails energized under a partially-driven panel — do not leave it in this state;
  DC stress). Mechanism: `apply_input_selection()` switches `clk_epdc` to the untrained
  TMDS clock unconditionally; each reboot re-inits the ADV7611, restarting the very
  handshake it is racing. Brownout ruled out (deterministic, `input_sel`-dependent,
  VBUS 5.07 V, shell-alive stuck states).

**Fix A** committed as `39d5b71` (fw/User/ui.c): while the frontend reports a source but
the FPGA has not confirmed live video, probe `CSR_ID0` first and skip the FPGA-touching
part of the `ui_task` iteration when unresponsive; suppress the `INPUT_STATUS_LOST`
reload in that window; 10 s grace deadline restores the reset net for a genuinely hung
FPGA. Not target-compiled here (no ARM toolchain); host tests pass.

**Post-flash test plan** (build `scripts/build_mcu.sh` or `scripts/dev_flash_mcu.sh`;
DFU recovery documented in §3):

1. `power off` → `power resume` with HDMI connected, ×5. Predict: **no reboot** —
   `syslog` shows `Waking system`, continuing timestamps; image restored after
   board-resume (~1.2 s) + Pi HDMI re-handshake (~1–3 s [EST]). Total 2–4 s.
2. Same with `input_sel 1`. Predict: no reset loop; graceful wait until link trains.
   (Revert afterwards regardless. Note the real shell syntax, wrong in older
   sections of this file: `setcfg get input_sel` / `setcfg set input_sel 0` /
   `setcfg save` — only `save` writes flash and only `save` triggered the fd leak.
   Leak regression test: `setcfg save` ×3, then `power off` → `power resume`.)
3. HDMI unplug/replug while active — regression check on the normal video-loss path.
4. If any reboot still occurs: capture `syslog`, note whether it restarts at 0.000.

### 10.1 First post-flash result (Fix A as of `39d5b71`): two new findings

- **Intermittent DDR3 calibration failure on resume** — `FPGA started with status 90`
  (MIG_ERROR + OP_BUSY, no SYS_READY). Pre-existing: the earlier "stuck blob" sensor
  signature (FPGA DDR ~20 mW, CORE ~120 mW) is the same state. Fix A then correctly
  held 10 s and reset a genuinely sick FPGA. Now handled proactively: `wait_fpga_ready()`
  retries the configuration once (`2e545f5`).
- **Fix A defect found and fixed**: the `INPUT_STATUS_LOST` suppression was gated on
  "acquiring" which never expires if the source needs the LOST reload to re-acquire —
  permanently blocking video bring-up (plausible cause of the observed
  "PC recognizes the display but it never shows" state). Repaired in `2e545f5`:
  suppression now bound to the same 10 s grace as the CSR tolerance.
- **White rectangle in the OSD corner** (~3×1 cm, sharp edges, where mode popups
  appear): almost certainly the OSD overlay stuck enabled — an OSD-disable write lost
  on the dead register bus during the sick-FPGA episode — masking updates beneath it.
  Sharp rectangle ⇒ digital, not panel damage. Predicted to clear after a cold power
  cycle (boot forces `CSR_OSD_EN=0` in `caster_init`) + one full refresh. If it
  survives that, reassess.

### 10.2 Post-flash round 2: the resume failure was a SPIFFS fd leak (now fixed)

Observed: `power resume` → `Unable to open bitstream 'fpga.bit': -10007` → `ui_task`
hung forever in `restart_fpga()`'s unbounded CSR wait (`power status` stuck at
`state: resuming`, all further power requests ignored).

Root cause chain **[CODE, confirmed by syslog]**:

1. `config_save()` (config.c:333) opened `config.bin` and **never closed it** — one
   leaked SPIFFS file descriptor per settings change (9 call sites: every OSD-menu
   change, `setcfg`, `USBCMD_SETINPUT`).
2. The fd table (`fs_fds[32*4]`, spiflash.c:494) holds only ~2–3 descriptors.
   `-10007` = `SPIFFS_ERR_OUT_OF_FILE_DESCS`. Two `setcfg` calls that session were
   enough.
3. With no bitstream, the FPGA never answers CSR → unbounded wait → permanent hang.

Fixes: `5d80bee` (close the file — **upstream bug**, present verbatim in
`Modos-Labs/Glider` `origin/main`; stock firmware's video-loss recovery dies the same
way after ~3 settings changes) and `986c9e1` (failed load → `fatal()` parks with shell
alive; successful load with no CSR response → bounded 5 s wait then reboot).

**White rectangle explained** (~3×1 cm, sharp edges, OSD corner): OSD popups render as
a blank white box when the OSD fonts fail to load (`osd_clear(0xff)` + text draw with
NULL font = box, no text). Mode popups auto-hide via `osd_timeout` → **transient** box
(workstation observation ✓); the no-signal/"Sleeping" popup has **no timeout** →
**permanent** box while video is not live (Pi observation ✓). Why the fonts stopped
loading is still open — run **`fs ls`** and check `fonts/font_quicksand_16.bin` etc.;
if missing/zero-size, re-upload with `utils/flash_tool/flash.py`. Not panel damage.

Also explained, no action: the "different startup" was the workstation's PD/data-capable
USB-C port (`CC status 5 0`, USB MUX CONNECT, PD hard-reset dance) vs the previous dumb
supply; and `syslog` printing nothing means *no new lines* — the shell command consumes
the ring as it prints (tail pointer advances).

**Upstream report, paste-ready:**

> `config_save()` in `fw/User/config.c` opens `config.bin` with
> `SPIFFS_open(... O_CREAT|O_TRUNC|O_WRONLY ...)`, writes, and returns without
> `SPIFFS_close()`. The fd pool passed to `SPIFFS_mount` (`fs_fds[32*4]` in
> `spiflash.c`) only fits a couple of descriptors, so after ~3 settings changes any
> further `SPIFFS_open` fails with `SPIFFS_ERR_OUT_OF_FILE_DESCS` (-10007). From then
> on the bitstream reload in the video-signal-loss path fails
> (`Unable to open bitstream 'fpga.bit': -10007`) and the FPGA is left unconfigured
> with `restart_fpga()` polling CSR forever — display dead until power cycle. One-line
> fix: close the file after the write.

### 10.3 The real root of every reboot loop: the input-mux clock trap (fixed in `a67f8b0`)

Round-3 logs (fonts confirmed loading ✓; MIG status-90 seen at **cold boot** too, retry
recovered it in 0.76 s ✓) still showed resume-with-HDMI reboot-looping ~10× despite the
CSR debounce — with the panel getting darker each cycle. Full trace, end to end **[CODE]**:

1. `apply_input_selection()` wrote `CSR_INPUT_CTRL` (auto/tmds/dp) immediately at
   pipeline start, while the ADV7611 link was still training.
2. Gateware `vin_source_ctrl` switches the mux when `live_valid` asserts — but that is
   just the timing monitor's "supported" flag ([top.v:605-609]), which asserts
   transiently during training.
3. The switch moves `clk_epdc` onto the live pixel clock, **and `vin_source_ctrl` is
   itself clocked by `clk_epdc`** ([top.v:619]) — when the freshly-selected clock dies
   mid-training, the FSM that could fall back to internal freezes with it. Mux, FSM and
   CSR are dead until PROG_B reload.
4. The pipeline health check then read garbage through the dead bus → spurious
   "memory interface unhealthy" → retry → reset. Each reboot re-inits the ADV7611,
   restarting the handshake it is racing → loop until timing luck.
5. Boots were safe only by accident: `CSR_INPUT_CTRL` defaults to internal
   ([csr.v:194]) and the source is usually silent when the request lands.

**Fix (`a67f8b0`)**: `apply_input_selection()` parks the mux on internal; the ui loop
issues the real request only after the frontend (ADV7611 lock over I2C / DP GPIO —
independent of the FPGA clock) reports the source present for 500 ms continuously.
All prior guards stay as safety nets, and the MIG health check is now trustworthy
(always runs on the internal clock).

**Panel darkening**: cumulative DC imbalance from repeatedly aborted drive cycles —
not permanent damage. Recovery: boot cleanly, then run several full refreshes (switch
update modes back and forth, let autoclear fire). It should fade back over a few cycles.

**Upstream question for zephray (gateware), paste-ready:**

> In `vin_source_ctrl.v` the FSM that controls the internal→live source switch is
> clocked by `clk_epdc` (top.v), which is the very clock the switch redirects. If the
> selected live pixel clock subsequently dies (e.g. HDMI link re-training after the
> "supported" flag transiently asserted), the FSM freezes on the dead clock and can
> never fall back to internal — the CSR interface (same clock) stays dead until the
> FPGA is reconfigured. I can reproduce this by requesting the live input while the
> ADV7611 is mid-training. Would you consider clocking `vin_source_ctrl` (and ideally
> the CSR slave) from `clk_sys` so the mux can always retreat to a live clock?

### 10.4 Round 5: gate keyed on the wrong signal; policy switched to reload-not-reboot (`2988131`)

Round-5 results: MIG retry works (status 90 → retry → 21, boots stable), but the
`a67f8b0` gate fired on a bare TMDS carrier ("Input source stable" with no video
flowing — the ADV7611 lock bit asserts during handshake), still latching the mux onto
a dying clock: frozen panel + dead buttons (debounce blocks the loop), ~7 reboots on
resume, and a switched-but-never-LIVE stuck state with no recovery. Cable pull while
live confirmed to always kill CSR (gateware FSM frozen; only reload recovers).

Fixes in `2988131`:
- Gate = **verified video**: TMDS PLL + vertical filter + DE-regen locked AND
  ADV7611-measured resolution == configured mode (HDMI map 0x04/0x07-0x0a), 500 ms
  continuous.
- **5 s post-switch LIVE deadline** → reload pipeline, re-arm gate.
- **CSR loss → reload the FPGA, not the MCU** (debounce 2 s, acquisition grace 3 s):
  keeps shell+syslog alive, and — critically — a new `reinit_frontends=false` path
  means reloads (and resume) no longer re-init the ADV7611, so the source's HDMI
  handshake is not restarted by our own recovery. MCU reset remains only as last
  resort in `restart_fpga`. Resume loses its double ADV7611 init as a bonus.

Expected behavior now: cable pull / source reboot ⇒ up to ~2 s CSR debounce + ~2 s
reload, **no MCU reboots, syslog continuous**; switch only ever issued with real
video flowing.

### 10.5 Round 6: the bitstream is the wrong generation (`156cabb`)

The 6-s flash loop ("Input source stable" → 5 s → "Input did not go live; reloading")
exposed the foundation problem: **the provisioned `fpga.bit` predates the
INPUT_CTRL/`vin_source_ctrl` gateware** (Caster submodule `2f714ab`, 2026-07-05).
Proof: current gateware reads `CSR_INPUT_STATUS ≥ 0x19` when parked internal
(INTERNAL bit + constant STABLE/SUPPORTED); the board reads `0x00` always, LIVE
never asserts, measured timing always 0. On the legacy bitstream, input selection
is autonomous in hardware and all input requests are no-ops. This also finally
explains the **permanent white box**: the input-status-blind firmware drew the
"No Signal" popup over perfectly working video.

`156cabb` detects the 0x00 signature after pipeline start, disables the
live-timeout reload and the signal OSD on legacy bitstreams, and logs
`Legacy bitstream: no input-control interface`. Result: current firmware works on
the old bitstream again (minus the new protections, which physically need the new
gateware).

**The real fix is building the current gateware** — Xilinx ISE 14.7 VM +
`scripts/dev_flash_fpga.sh --ise-host <vm-ip> --variant 8bit-mono` (see USAGE.md
for VM setup). Until then: no MCU reboots occur (reload policy verified working —
resume completed with continuous syslog), but LIVE-based features stay dormant.

### 10.6 Reading-mode reframe: retain is the reading state (`d53afdb`, `9da093d`)

**Power model corrected by the user (this overrides §8's framing):**
- **Retain = reading mode.** HDMI stays up; page flips must not trigger a link
  renegotiation or a full-panel refresh. This is where reading time is spent.
- **Off = standby.** The 4 s bring-up and full refresh are fine for waking the
  reader from a pause; not for a page turn.

**Bug fixed: scrambled text after a page turn during retain** (photo evidence: old
and new page superimposed). Root cause, code-verified: retain left `CSR_ENABLE=1`,
so the EPDC kept processing live video with the EPD rails off — driving each new
frame into an unpowered panel while updating its *internal glass-state model* to
match. On wake, waveforms were selected against a state the glass never actually
reached ⇒ ghosted/superimposed output. `d53afdb`: `enter_retain()` now stops the
scan (`caster_set_enable(false)`, +50 ms for the in-flight frame) before cutting
rails; retain resume re-enables it. Stopped, the scan FSM parks at a frame boundary
with the framebuffer frozen and glass-consistent; on re-enable the first frame
diffs live video against that framebuffer and applies whatever changed as a clean
partial update — which *also* removes the resume flash (the thresholded redraw is
gone).

**Wake model in retain** (the EPDC scan is stopped, so the damage counter is frozen
and autonomous wake-on-page-change no longer fires):
- Board button (short press) — already in `wait_for_retain_wake`. **This is the
  "end retain with a button" ask; it already works.**
- Host command (shell `power resume`, HID `USBCMD_POWERUP`).
- USB resume.
- Frontend-side video-loss deepen (unaffected — MCU checks the frontend, not CSR).

**Host-side reading loop: `utils/flash_tool/retain_hook.py`** (`9da093d`) supplies
the wake trigger the firmware can no longer generate itself. On the Pi it watches
input via evdev and sends `POWERUP` on activity (before the reader renders),
`POWERDOWN retain-manual` after `--idle`, and full `off` after `--deep-idle`.
Run under systemd later, e.g. a unit with
`ExecStart=/usr/bin/python3 /path/utils/flash_tool/retain_hook.py --idle 60
--deep-idle 600`, `After=multi-user.target`, in the `input` group with the glider
udev rule. Validate first with `--dry-run` / `--list`.

**Honest reading-mode power ceiling.** While HDMI is alive, `VIDEO IN ≈ 0.59 W` and
the FPGA core/DDR ≈ 0.25 W are *unavoidable* — they are the cost of keeping the link
and framebuffer up, which reading mode requires. So retain's realistic floor is
~1.0–1.3 W even after MCU idle work, versus off at ~0.19 W. **The battery strategy
is therefore tiered, not "make retain tiny":** retain for active reading and short
gaps, drop to off for pauses beyond ~1 min (the deep-idle escalation does this
automatically). Getting retain itself lower needs gateware (below); the biggest
single lever remains not being in reading mode when you don't need to be.

**Panel cleanup after the scramble** (no firmware): `power off` → `power resume`
runs the FPGA reload + full OP_INIT waveform, which deep-cleans the glass.

**Gateware wishlist (for when the ISE VM exists), in rough value order:**
1. **Watch mode** — capture + damage counting with panel drive disabled, so retain
   can autonomously wake on a page change without the host hook and without driving
   the unpowered panel. This is the clean fix for the wake model above.
2. CSR (and `vin_source_ctrl`) on `clk_sys` — removes the whole class of
   video-clock register deadlocks (§10.3).
3. Gate `epd_sdclk`/driver-OE when idle (a few mW; removes retain electrical
   stress). DDR3 self-refresh when idle (part of the ~95 mW DDR budget).

### 10.7 EPDC-stop retain made it WORSE — reverted (`05cfa68`); retain internals blocked on gateware

`d53afdb` (stop the EPDC during retain) was flashed and **regressed**: retain→resume
still scrambled, and after a manual refresh the panel went **inverted (black bg,
white text) with progressive whitening on each page turn**. Reverted in `05cfa68`;
tree is back to `4d24169` behavior (threshold skip-redraw, no ENABLE toggle).

Root-cause status (honest): **not fully determined, and not determinable from the
repo.** What I established:
- On the board's actual gateware (`Caster@48c3e7d`, the commit the provisioned
  `fpga.bit` predates 2f714ab / reads Input status 0x00), `CSR_ENABLE=0` *does*
  cleanly park the scan FSM (`SCAN_IDLE` while `!global_en`). So the register write
  was correct — the EPDC-stop theory was not a wiring mistake.
- Since stopping the scan did **not** fix the scramble, the scramble's cause is
  **not** "the EPDC consumes page-changes during retain." My earlier theory was
  wrong.
- The inversion correlated with the ENABLE toggle (driver OE stays asserted and
  `epd_sdclk` free-runs even in SCAN_IDLE on this gateware, so a 0→1 transition
  around a rail cut can apply an unbalanced pulse) — but this is unproven, and
  accumulated panel DC-imbalance from the whole session's abnormal cycles is a
  confound.

**Architectural conclusion (3 retain-resume changes, each surfaced a new failure —
`268cfba`, `4d24169`, `d53afdb`):** stop debugging EPD glass-state behavior on the
legacy bitstream. I am reasoning about RTL I cannot build or simulate, on a panel
whose physical state is confounded by session history. **Seamless retain reading
mode is blocked on the gateware rebuild** (where the RTL is known and the input path
works). Until then:
- Retain reading mode = accept the current `4d24169` behavior (clean no-flash resume
  when the framebuffer was static; scramble only if content changed *during* retain
  — which the host-hook flow avoids, since page turns happen in active mode).
- Or use `off` for anything non-instant.

**Two diagnostics still wanted from hardware** (to close the root cause if we return
to it): (D1) does retain→resume scramble even with **no** page change during retain?
(D2) does `power off`→`power resume` reliably clear the inversion (tests glass-state
recoverability vs. physical imbalance)?

**Recovery for the current stressed panel** (no code): `power off` → `power resume`
runs the FPGA reload + init waveform; repeat 2–3× if the inversion/ghost persists.
If it survives that, it is physical DC-imbalance — leave it displaying a full-black
then full-white a few times to rebalance.

**Remaining roadmap after Fix A**, in order: (1) resume latency polish — the double
`ADV7611 initialization done` per resume (`resume_video_frontends()` at ui.c:970 then
again via `apply_input_selection()` AUTO branch) restarts the HDMI handshake twice,
worth ~0.5–1 s; the 688 ms SPIFFS-bound bitstream read; the 100 ms-quantized polls.
(2) Host-side idle hook: Pi issues `power off` (or HID POWERDOWN param 1) after idle,
`power resume` on activity — now safe once Fix A is verified. (3) Suspend-floor MCU
draw (145 mW of the 190 mW floor): `key_scan_task` 10 ms poll first, then tickless
idle (PR #17's regime, done right). (4) Upstream questions: CSR-on-`clk_sys` gateware
change; report the pinned-TMDS reset loop to Modos.
