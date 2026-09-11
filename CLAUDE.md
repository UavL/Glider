# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Glider is an open-source low-latency Eink monitor. This repo holds the PCB design (KiCad) and the MCU
firmware (`fw/`); the FPGA gateware ("Caster") lives in the `Caster/` git submodule
(https://gitlab.com/zephray/Caster.git). `README.md` has deep background on EPD theory and the Caster/Glider
design; `USAGE.md` has the practical board/flashing/dev workflow — read that first for anything hands-on.

**Ongoing work on branch `Board-Design`: designing R2, a battery e-reader board.** R1's power
work hit a hardware wall — 82 % of the idle draw sits on bucks whose enable pins are hardwired
on, so no firmware change can fix it. Read in this order:
- **`NOTES-R2-plan.md`** — what R2 is and what to do next. Start here; its "Stage C progress"
  table says which sheets are drawn, which are reviewed, and what is waiting on the owner.
- **`NOTES-R2-osd62x-plan.md`** — **the compute module is switching** from PHYTEC's `PCM-071` to Octavo's
  `OSD62x-PM` SiP (owner, 2026-09-11). Read it before touching `som`, `dpi_in`, `power`, `mcu` or the SoM
  corner of the board; docs that still describe the `PCM-071` are the record of the old design.
- **`pcb/r2-mainboard/docs/<sheet>.md`** — one spec per schematic sheet: part choices with LCSC
  codes, values with the arithmetic shown, the sheet's hierarchical interface, review answers and
  the layout guidelines for that circuit. Read the sheet's doc before touching its `.kicad_sch`.
- **`NOTES-R2-hardware-facts.md`** — the evidence base: every verified fact with its source
  (TI TRM/app notes, PHYTEC manuals, LCSC catalogue, this repo).
- **`pcb/r2-mainboard/docs/libraries.md`** — every symbol and footprint made for R2, what it was
  derived from, which `tools/` script emits it, and what was checked. `pcb_common` is never modified.
- **`NOTES-production-costing.md`** — what 1 000 units would cost and what a campaign would need to
  raise. Planning, not a quote; the SoM price is the dominant unknown.
- **`NOTES-STATUS.md`** — R1's state: what is flashed on the board, the measured power budget,
  what is verified vs. inferred vs. untested. Still current for anything hands-on with the
  existing hardware. `NOTES-power-analysis.md` is the 1500-line chronological record behind it
  and is partly superseded; consult it only for depth on a section `NOTES-STATUS.md` points to.

**Reference designators follow the sheet's page number** (owner's scheme, rolled out across
all 13 sheets on 2026-08-31): classifier + page + two-digit part, numbered from `00`. Pages 2–9
give three digits, pages 10–14 give four:

| 2 battery | 3 power | 4 mcu | 5 som | 6 dpi_in | 7 fpga_io | 8 fpga_ddr | 9 fpga_config |
|---|---|---|---|---|---|---|---|
| `U200` | `U300` | `U400` | `J501` | `U600` | `U700` | `C821` | `U902` |

| 10 epd | 11 epd_power | 12 power_mon | 13 frontlight | 14 io_expansion |
|---|---|---|---|---|
| `J1000` | `C1105` | `R1200` | `U1300` | `U1400` |

A part shared by several sheets takes its **lowest** page, so the FPGA is `U700` (pages 7–9) and
the two SoM connectors are `J501`/`J502` (pages 5–6). `tools/renumber_by_page.py` performed the
conversion; `tools/check_pcb.py`, `check_pcb_connectors.py` and `check_ucf.py` assert on the new
names. The `gen_*`/`patch_*`/`port_r1.py` scripts deliberately keep the **old** names — they each
wrote a sheet once and are a historical record, not re-runnable code. **Two classes of string look exactly like a designator and must never be
rewritten**: FPGA ball names (`C1`, `D2`, `N11`, `T1`…) and BTH-060 pin names (`A1`–`D60`).
Substituting them silently rewires the board — see `docs/layout.md` §9.5.

Ground rules for this work, from the hardware owner and not negotiable: **the assistant cannot
flash, measure or observe the hardware** — never claim a behaviour was confirmed on it; **this is
the only dev kit**, so nothing may risk bricking it; **do not modify anything outside this repo**;
and **always separate verified-from-source / inferred / needs-a-hardware-test**.

Repo layout:
- `fw/` — STM32H750 MCU firmware (STM32CubeIDE project), FreeRTOS-based.
- `Caster/` — FPGA gateware submodule (Spartan-6, built with Xilinx ISE 14.7).
- `fw/User/tinyusb/` — TinyUSB submodule (USB stack).
- `pcb/` — KiCad board design (`pcb/pcb_common` submodule for shared library parts).
  `pcb/mainboard/` is R1 (KiCad 8, **read-only**); `pcb/r2-mainboard/` is R2 (KiCad 10), with
  `docs/` specs, `datasheets/`, and `tools/` — the generators and patch scripts that produced the
  sheets. A sheet that has been saved in Eeschema is edited surgically, never regenerated.
- `utils/flash_tool/` — `flash.py` (HID-based flashing/config tool), `cfggen` (display timing config generator),
  `power_survey.py` (compares power draw across suspend states over HID+shell).
- `scripts/` — build/release automation (see Commands below).
- `case/`, `tools/fonts/` — enclosure design, OSD font generation.

Clone with `git clone --recursive`; if submodules are missing, `git submodule update --init --recursive`
(a missing `tusb.h` build error means the `tinyusb` submodule wasn't cloned).

## Commands

### Build MCU firmware
Headless STM32CubeIDE build (no GUI needed):
```bash
scripts/build_mcu.sh <version> <release-dir>
```
Or interactively: open STM32CubeIDE, import `fw/` as an existing project, build the `glider_ec_rtos` project
(Debug config by default). Output: `fw/Debug/glider_ec_rtos.bin`.

Dev loop (rebuild + `dfu-util` flash in one step, board must be in DFU mode — hold the button nearest the
USB port while plugging in):
```bash
scripts/dev_flash_mcu.sh
```

### Build FPGA gateware
Requires a Xilinx ISE 14.7 VM reachable over SSH (see `USAGE.md` for VM setup). Full release (MCU + all
4 Caster variants: `8bit-mono`, `8bit-k3`, `16bit-mono`, `16bit-k3`):
```bash
scripts/release.sh --ise-host <vm-ip> <version>          # real build
scripts/release.sh --dry-run --ise-host <vm-ip> <version> # exercises the script without touching hardware tools
```
One variant only, for iterating on gateware:
```bash
scripts/dev_flash_fpga.sh --ise-host <vm-ip> --variant 8bit-mono
```

### Flash a built firmware
```bash
python3 utils/flash_tool/flash.py                # interactive HID flashing (dfu-util + FPGA/font/config transfer)
sudo dfu-util -a 0 -i 0 -s 0x08000000:leave -D glider_ec_rtos.bin  # manual MCU-only DFU flash
```
`flash.py` needs the `hidapi` PyPI package (`pip install hidapi`) — **not** the unrelated `hid` PyPI package,
which has an incompatible API (`hid.Device` vs the `hid.device` class `flash.py` expects). On Linux, install
udev rules instead of using `sudo` for the Python tools — `sudo` re-resolves `python3`/`site-packages` from
root's environment and can pick up that wrong package. See `USAGE.md` "Flashing Requirements" for the rules,
or `utils/flash_tool/99-glider.rules` (also covers the `tty` subsystem for the CDC-ACM shell console, which
the `USAGE.md` rules don't).

### Tests
Host-side C unit tests (compiles individual firmware modules with plain `gcc -DGLIDER_HOST_TEST`, no
hardware/STM32CubeIDE needed):
```bash
bash fw/User/tests/build_host_tests.sh
```
Shell-script assertions (registration/wiring checks for shell commands, config timing, release scripts):
```bash
bash scripts/tests/test_shell_commands.sh
bash scripts/tests/test_fw_config_timing.sh
bash scripts/tests/test_cfggen.sh
bash scripts/tests/test_release_scripts.sh
```
Python tests for the flash tool:
```bash
cd utils/flash_tool && python3 -m unittest discover -s tests -p "test_*.py"
```
(`test_factory_tool.py` needs `tkinter` for `main.py`, the factory GUI tool — failures there are an
environment gap, not a code issue, if `tkinter` isn't installed.)

## Architecture

### MCU firmware (`fw/User/`)
FreeRTOS tasks coordinate over the housekeeping duties described in README's "Firmware Functions": EPD power
supply sequencing and VCOM measurement, rail voltage/current monitoring, FPGA bitstream push over SPI on
boot (the FPGA has no own flash — `fpga.c`'s `fpga_init()`/`fpga_reset()` load it from the MCU's SPIFFS
filesystem every time), USB-C PD negotiation and DP Alt-Mode lane muxing (`usbpd.c`), video decoder init
(`adv7611.c` for DVI, `ptn3460.c` for DP-to-LVDS), and host communication.

Key modules: `power.c`/`power_state.c` (suspend/resume state machine — see below), `ui.c` (main
`ui_task` loop: input selection, OSD/menu, autoclear, suspend/resume orchestration), `caster.c` (host-side
driver for the FPGA's register/command interface), `usbapp.c` (USB HID command dispatch, see `USBCMD_*` in
both `usbapp.c` and `utils/flash_tool/flash.py` — keep them in sync), `config.c`/`config_timing.c` (display
timing config, persisted via SPIFFS), `shell/` (a linenoise-derived interactive shell, see below).

The device enumerates as a single composite USB device (VID `0x1209`, PID `0xAE86`): a HID interface
("Control", used by `flash.py`/`power_survey.py`) and a CDC-ACM interface ("Debug", the shell console —
typically `/dev/ttyACMx` on Linux). `usbapp.c`'s CDC output (`usbapp_term_out`) writes unconditionally; it
does not gate on host-connected state.

### Power/suspend state machine
`power_state.c` tracks `POWER_STATE_{ACTIVE,SUSPENDING,SUSPENDED,RESUMING}` plus a suspend reason
(`POWER_SUSPEND_{USER,VIDEO_LOSS,USB,RETAIN}`) and wake sources (`POWER_WAKE_{BUTTON,USB_PD,INPUT,USB,DAMAGE}`).
`power.c`'s `power_suspend()` has two paths:
- **Retain** (`POWER_SUSPEND_RETAIN`): only the EPD rails go off; FPGA, DDR3 framebuffer, and video frontends
  stay alive, so resume is just `power_on_epd()` + a full redraw (fast).
- **Full suspend** (any other reason): also suspends the FPGA (`fpga_suspend()`, which erases its
  configuration) and powers down the video frontend chips. Resume calls `fpga_resume()` then
  `start_display_pipeline()` → `restart_fpga()`, which fully reloads the bitstream and blocks until the FPGA's
  CSR bus responds before proceeding — this path is much heavier than retain's.

Host-triggered requests (`power_post_request()`/`power_take_request()`, backed by a critical section, not an
ISR-safe primitive — only called from task context) come from the shell (`power {status,off,retain,resume}`)
or USB HID (`USBCMD_POWERDOWN` param 0/1/2 = retain/off/retain-no-autowake, `USBCMD_POWERUP` = resume).
Requests to enter retain/retain-manual/full-suspend are only consumed by `ui_task` while it's currently
*active* — sending one while already suspended is silently dropped (only `RESUME` and `SUSPEND`-to-deepen are
handled from the suspended branch, via `power_retain_deepen()`). Always bounce through active before
requesting a different suspend state.

`ui_task`'s main loop also has a standing safety net (pre-dating any of the above): if a sanity
`fpga_write_reg8(CSR_ID0, ...)` read ever fails, it calls `NVIC_SystemReset()` — the only spontaneous,
repeatable reset path in the firmware (no watchdog is configured; `HardFault_Handler` just hangs).

### Shell (`fw/User/shell/`)
A linenoise-derived interactive command shell (prompt `"# "`, Enter = `\r`, see `shell_platform.c`'s
`term_translate`) reachable over the CDC-ACM interface. Most maintenance/diagnostic commands (`sensor`,
`mem`, `test`, `i2c_probe`, `recv`/`send`, `fs`, `setvolt`, `damage`) are gated behind the
`GLIDER_DIAGNOSTIC_SHELL` preprocessor symbol in `fw/.cproject` (defined in all three build configs —
Debug/Release/DebugRAM — as of this repo state; check before assuming it's still there upstream).
`sensor` (per-rail current/power breakdown) is what `power_survey.py` depends on.

### FPGA gateware (Caster)
Three clock domains (`clk_vi` input video, `clk_epdc` EPDC core, `clk_mem` DDR3) connected through sync/async
FIFOs; `caster.v` is the EPDC core, `top.v` wires in the surrounding I/O and memory interface modules. Compile
variant (`8bit-mono`/`8bit-k3`/`16bit-mono`/`16bit-k3`) is a build-time choice — `CASTER_COLORMODE` and
`CASTER_OUTPUT_WIDTH` are generated together and must match.
