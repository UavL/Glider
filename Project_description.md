# Project: Open Low-Latency E-Ink Reader (working name: Specter)

> This file is the standing brief — who I am, what I want, and the requirements. It has not been
> superseded. For where the work actually stands, see `NOTES-R2-plan.md` (the board being
> designed) and `NOTES-STATUS.md` (the existing dev-kit board). The Pi 4 named below is the
> current dev machine and is being replaced by a soldered-down AM62x module, exactly as the
> power measurements in this file concluded it must be.
 
## Who I am
 
Lum, based in Germany (German native, English fine — I may switch between them).
 
**Background:** Comfortable with Linux and Python. Very little C (Arduino level). Hobbyist
experience with Arduplane/RC (LiPos, BMS, connectors, flashing firmware, parameter tuning),
soldering, and 3D printing. In school we milled very simple PCBs on a CNC and hand-soldered
them — but **no real electronics design experience**. Learning KiCad.
 
Assume I can follow technical instructions, but explain new concepts (FPGA gateware, DRM/KMS,
Yocto, high-speed layout) rather than assuming familiarity. Don't dumb down Linux or Python.
 
## What I'm building
 
A DIY e-ink reader/notetaker that does **not** have the sluggish refresh of normal e-readers,
built on the open-source Modos Labs stack. Target: essentially a **Kobo Sage equivalent plus a
high-refresh-rate display**, with comparable battery life. Long-term goal is a genuinely
product-grade device, possibly crowdfunded; near-term goal is a working prototype.
 
**Requirements:**
- Kobo Sage–class form factor and reading experience
- **High refresh rate is the non-negotiable core feature** (see below)
- Battery powered, target ~15–20 h active reading (this *is* Sage level — see battery section)
- Touch required
- Frontlight required
- Physical page-turn buttons in the enclosure, like commercial e-readers
- Pen/EMR input: **explicitly deferred to a later iteration**
- No WiFi in the near term (simpler, lower power; books sideloaded)
## The technology base
 
**Modos Labs** (Caster + Glider), mirrors at github.com/Modos-Labs and gitlab.com/zephray:
- **Caster** — FPGA gateware implementing an e-paper controller that treats every pixel as its
  own update region instead of doing sequential whole-screen updates. This is what enables the
  low latency and 75 Hz. **This is the entire reason the project exists.**
- **Glider** — reference hardware: Spartan-6 LX16 FPGA, DDR3-800 framebuffer, STM32H750 MCU,
  ±15 V EPD supply, video decoder chip, KiCad sources, waveform tooling, C API.
- **Glider Mega Adapter** — many panel connector types, incl. the `ED078KCx` family.
- Community: Modos Discord (`discord.gg/rtT7euSHQS`).
Glider is designed as an **external monitor controller**, not a tablet. Everything
tablet-specific (battery, power management, touch, buttons, enclosure, standalone OS) does not
exist in the project and is mine to build.
 
### Standing rule: do not propose integrated-EPDC SoCs
 
Commercial e-readers use SoCs with a built-in EPDC (i.MX6SLL/i.MX7, Allwinner). Those are
exactly what *limits* refresh rate — Caster exists to escape them. I explored this branch
already and rejected it deliberately. **Do not re-offer "just use an i.MX with EPDC, it's
easier / better battery" as a suggestion.** If a tradeoff genuinely requires revisiting it,
say so once, with the specific reason, and move on.
 
## Current status (as of late July 2026)
 
### Hardware on hand
- **Modos Paper Dev Kit (6")** — arrived and working. Panel reports EDID name "Paper Monitor",
  native mode **1448×1072 @ 75 Hz**, pixel clock **127.32 MHz** (htot 1528 × vtot 1111 × 75).
- Raspberry Pi 4 — current dev machine, hostname `raspberrypi-koreader`, user `koreader`
- Raspberry Pi 400 (disassembled), Waveshare 7" DPI LCD HAT (dead end, see below)
### What works: KOReader on the Modos panel
 
The display path is solved. Key finding that took a while to isolate:
 
**KOReader's bundled SDL3 has no kmsdrm backend.** `strings` on
`~/koreader/lib/koreader/libs/libSDL3.so.0` shows only `wayland`, `x11`, `offscreen`, `dummy`.
Setting `SDL_VIDEODRIVER=kmsdrm` is therefore silently ignored and SDL falls back to a dummy
device — KOReader runs fine, logs no error, reports a fixed 600×800 framebuffer, and displays
nothing. Bare-kmsdrm is impossible without building SDL3 myself.
 
**Working solution — `cage` kiosk compositor:**
```
SDL_VIDEODRIVER=wayland cage -- ./bin/koreader
```
`cage` takes DRM master and does the modeset; no desktop, no login, single fullscreen app.
This *is* an appliance setup — "direct" does not have to mean bare kmsdrm.
 
**systemd unit** (`/etc/systemd/system/koreader.service`) — the `PAMName`/`TTYPath` pair is
what makes it startable over SSH, because logind then builds a real seat0 session:
```ini
[Unit]
Description=KOReader Kiosk
After=systemd-user-sessions.service getty@tty1.service
Conflicts=getty@tty1.service
 
[Service]
User=koreader
WorkingDirectory=/home/koreader/koreader
PAMName=login
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
StandardInput=tty-fail
StandardOutput=journal
StandardError=journal
UtmpIdentifier=tty1
UtmpMode=user
Environment=SDL_VIDEODRIVER=wayland
ExecStart=/usr/bin/cage -- /home/koreader/koreader/bin/koreader
Restart=always
 
[Install]
WantedBy=multi-user.target
```
Control via `systemctl start|stop|enable koreader`. Do not also leave a `cage` line in
`~/.bash_profile` — two things fighting over tty1.
 
**Rotation:** cage 0.2.0 ignores `WLR_OUTPUT_TRANSFORM`, so output rotation is not available.
Rotation is currently done **inside KOReader** (menu → display → rotation, locked), which
persists in `settings.reader.lua` (keys `rotation_mode` / `fmanager_rotation_mode`; values
0=portrait, 1=landscape CW, 2=180°, 3=landscape CCW). Note KOReader rewrites that file on
clean exit — stop the service before editing it by hand.
 
Console/CLI rotation is separate and was solved with **`fbcon=rotate:3`** in
`/boot/firmware/cmdline.txt` (single line). `video=...,rotate=90` alone did nothing. Console
rotation does **not** affect cage/KOReader — different layers.
 
**Known consequence:** because rotation happens in the app and not in the compositor, the
mouse pointer runs in the un-rotated landscape coordinate system. Harmless now; when touch is
added, either rotate in the compositor (needs a newer cage / different kiosk compositor) or
apply a libinput coordinate transformation matrix.
 
**Plugins:** third-party plugins go in `~/koreader/plugins/<name>.koplugin/` with `_meta.lua`
and `main.lua` at the top level. GitHub zips extract as `<name>-main/` and must be renamed.
SimpleUI (doctorhetfield-cmd) is the intended launcher/home screen; it is community code,
partly AI-generated per its own README — test before shipping.
 
**Debugging note:** redirect with `2>&1` to capture SDL's stderr; `./koreader.sh` writes
`crash.log` automatically but doesn't let me pass env vars as easily.
 
### Power measurements (measured, USB-C meter, at 5.14 V)
 
| Device | State | Power |
|---|---|---|
| Modos board | booting (brief, varies) | ~1.4 W |
| Modos board | idle, KOReader displayed | 1.77 W |
| Modos board | idle, CLI displayed | 1.77 W |
| Modos board | **no HDMI signal** | **0.42 W** |
| Pi 4 | idle, CLI | 2.4 W |
| Pi 4 | idle, KOReader under cage | 1.7–2.06 W |
| Pi 4 | no HDMI signal | 1.5–2.0 W |
 
**Interpretation:** ~76 % of the Modos board's draw is the active video path (decoder, FPGA
compare logic, DDR3) — content is irrelevant, only the 75 Hz stream matters. This validates
the core power strategy: **blank the link when the image is static**, not "lower the refresh
rate". The Pi 4 draws heavily in every state and cannot sleep — it must be replaced.
Total system today: ~3.5–3.8 W → roughly 2.5 h on 3000 mAh. Faint coil whine audible on the
Modos board in the 0.42 W state (light-load burst mode; a regulator-selection criterion later).
 
### Open problem: image is not retained when the link drops
 
When HDMI is disconnected, the panel goes **gray and loses the image**. E-ink holds an image
with zero power, so something is actively driving it into that state — either the
gateware/firmware clears or keeps driving on sync loss, or the EPD rails collapse mid-drive
and leave pixels in intermediate states. (Modos has known signal-loss/sleep handling issues;
the Flow needs a "port dance" after PC sleep, acknowledged as a firmware bug.)
 
**Planned fix — define an ordering instead of just cutting the signal:** power down the EPD
rails via the MCU *first*, then drop video. The STM32 already switches and monitors EPD power
(incl. VCOM) and exposes a USB serial shell plus a HID interface for modes and forced
refreshes. Next test: open the board shell over USB, inventory the commands, try
rails-off → video-off, verify image retention, measure that state, and check wake-up (does it
need a full refresh?). Diagnostic detail still to determine: did the screen go gray
**abruptly** (active clear/drive) or **fade slowly** (rails collapsing)?
If the firmware clears on sync loss, `fw/` is open C — fixable without touching Verilog.
 
## Established roadmap
 
Ordered so each stage is usable on its own and each builds the skills for the next.
 
**Stage 1 — Integration prototype (current stage).** Dev kit + lower-power SBC + battery +
touch overlay + GPIO buttons in a 3D-printed case. No PCB design required. Deliverable: a
working, if chunky, device — and the demo unit for any future campaign.
- Note: the parallel-RGB/decoder-bypass trick is **not possible on the dev kit** — the decoder
  is hardwired. Stage 1 does link management over HDMI via DPMS (~0.5–1 s wake, acceptable
  after reading pauses, not per page turn).
- SBC candidate: **Pi Zero 2 W** (~0.6–0.8 W idle vs ~2.7 W; same OS, existing setup migrates
  on the SD card; caveat 512 MB RAM — test KOReader early). Alternative: Radxa Zero 3W /
  RK3566 class (more RAM, similar power, new OS bring-up). Needs mini-HDMI adapter.
- Battery: 1S LiPo 3000–5000 mAh + charger/boost module. Must have **power-path/pass-through**,
  ≥2.5–3 A headroom, and **must not auto-shut-off at low load** (the classic powerbank-module
  trap, since idle draw will be low).
- Touch: capacitive overlay with a mainline-driver controller (GT911 / FT5x06 family), I²C +
  interrupt on GPIO.
- Buttons: plain switches on GPIO via the `gpio-keys` device-tree overlay → arrive as key
  events KOReader already understands.
- Case: start from the **`case/` directory in the Glider repo** for panel and board geometry.
- Also in scope: read-only rootfs / overlayfs (mandatory — an appliance that gets switched off
  will eventually corrupt a writable SD card), clean power button → `poweroff`, boot-time
  tuning, idle detection + DPMS blanking + wake logic.
**Stage 2 — First own PCB: power and control board.** Charger (BQ24074 class), fuel gauge
(MAX17048 class), buttons, frontlight LED driver (constant current, PWM dimming, optionally
warm/cool), power-on/off controller. Two layers, no high-speed signals, all well-documented
parts with reference schematics. Fabricate at JLCPCB/PCBWay (assembly optional). This is the
right *first* real KiCad project — and the device needs it anyway.
 
**Stage 3 — Carrier board: SoM + integrated Glider circuit.** One board carrying a bought-in
SoM (low-power applications processor with a display output) plus the Glider circuitry (FPGA,
DDR3, EPD supply, MCU) — **without** the ADV7611 decoder, feeding the FPGA directly. Realistic
with an experienced freelance hardware designer (rough order 10–30 k€, estimate not a quote)
while I do the software; solo this is a 1–2 year project with 2–3 respins, and not advisable
as a first board.
 
**Stage 4 — Full custom SoC-down board.** BGA SoC, LPDDR, HDI stackup, custom BSP. This is
what Modos does as a company. Not realistic solo; only after Stage 3 ships in small volume.
 
### Crowdfunding shape (if pursued)
 
Build Stage 1 myself → use it as the campaign demo → fund Stages 2/3 with 1–2 freelancers
(hardware, possibly FPGA) while I own system integration and software. A campaign is a
delivery obligation, not learning money: battery device means CE/FCC, battery transport
certification, tooling, panel supply at volume. Rough order for a sellable small series:
100–250 k€+ (estimate). For calibration: Modos raised ~$110 k and delivered a dev kit with no
battery and no consumer enclosure.
 
## Hard technical constraints (from the repos — verified, keep in mind)
 
- **License split:** Caster (gateware) is CERN-OHL-P **permissive** → usable in a closed
  product. Glider (hardware design) is CERN-OHL-S **strongly reciprocal** → a board derived
  from it must be published. Fine for an open-hardware product, but a conscious choice.
- **Toolchain:** Caster builds with **Xilinx ISE 14.7** (legacy, best in the vendor VM).
  Spartan-6 is EOL. → **Stay on the Spartan-6 LX16 and copy the design**; migrating to a modern
  FPGA family is a real gateware port and is out of scope.
- **FPGA has no config flash** — the MCU loads the bitstream over SPI at every power-on. So the
  FPGA can be fully powered down when idle and reloaded in well under a second. Cost: the DDR3
  pixel state is lost → wake needs one full refresh (a "flash"). Acceptable after a pause.
- **Board is 4-layer KiCad 8**, Spartan-6 in CSG324 BGA (assembly service required). The hard
  DDR3 routing already exists and is copyable.
- **Firmware** is FreeRTOS, STM32CubeIDE, DFU-updatable, open C. Power management can largely
  be built in MCU C + host scripts — **no Verilog needed** for the "sleep when static" feature.
- **Panel resolution must be set manually** through the board shell; the board cannot detect it.
- **X resolution × Y resolution must be a multiple of 128**, or lines go unused.
  - 1448×1072 = 1,552,256 ✓ (exactly divisible)
  - 1872×1404 = 2,628,288 ✗ (**not** a multiple of 128) — **verify with Modos how ED078KC
    panels are handled here** before committing to that panel.
- **Grayscale rendering wants 85 Hz** input; 60 Hz only works with effort in some cases.
- **Input paths and limits:** DVI via ADV7611 ≤165 MP/s · DVI directly into the FPGA
  deserializers ≤105 MP/s · DisplayPort via PTN3460 ≤224 MP/s · MIPI/LVDS ≤230 MP/s.
  **Processing** limit: 133 MP/s with error-diffusion dithering, 200 MP/s without.
- **Consequence for panel size — the current 6" panel is close to a limit already:**
  1448×1072 @ 75 Hz = **127.3 MP/s**, i.e. just under the 133 MP/s dithering ceiling.
  Sage-class 1920×1440 needs ~177 MP/s @60 Hz (over ADV7611 *and* over the dithering limit)
  and ~255 MP/s @85 Hz (over every input option). 1872×1404 @85 Hz ≈ 243 MP/s, also over.
  **8" at 300 ppi is at or beyond what this Caster/Spartan-6 generation can do.** 6"–7" is
  comfortable. The Modos Flow already replaced Caster with a next-gen controller supporting
  larger and higher-res panels; whether that becomes open is unknown.
- **KOReader's own e-ink features do not reach the panel over HDMI.** Refresh behaviour,
  ghosting and grayscale are controlled by **Caster modes** (Reading/Typing/Watching/Browsing
  presets, or the C API / HID interface), not by KOReader settings. The hybrid mode already
  switches per pixel between fast binary and grayscale re-render when the image settles —
  which is ideal for reading, so mostly this means "pick the right preset".
- Waveforms: E-Ink ships `.wbf`; the repo provides an Interchangeable Waveform Format plus
  converters and documents extraction from device flash dumps. Kit panels are covered; a custom
  panel is sourcing work but not a blocker.
## Battery reality check
 
The Kobo Sage has only **1200 mAh** and real-world ~15–20 h of reading — *not* the multi-week
life of classic e-readers. So "Sage-level battery" means **15–20 h active**, which is
achievable. Projection with a 3000 mAh (~11.1 Wh) cell, ~85 % converter efficiency, ~90 %
static reading time — orders of magnitude, not promises:
 
| Configuration | Avg. power | Runtime |
|---|---|---|
| Today: Pi 4 + Modos always active | ~3.7 W | ~2.5 h |
| Pi Zero 2 W, Modos always active | ~2.5 W | ~4 h |
| + link blanking when static (the measured 0.42 W state) | ~1.3 W | ~7–8 h |
| + rails/FPGA off when idle, SBC tuned | ~0.8 W | ~11–12 h |
 
Last row with a 4000–5000 mAh cell → 15–19 h, i.e. the target. Deep standby
(suspend-to-RAM, rails and FPGA off) should reach tens of mW → days to weeks.
 
## Pen / EMR (deferred, for reference)
 
Real handwriting on e-ink needs an **EMR digitizer layer behind the panel**, not a capacitive
stylus. Hard to source as a component, requires center-alignment to the panel's active area,
magnetic shielding, and no metal near the digitizer. Separately: **KOReader is not a
note-taking app** — it does highlights/annotations, not free handwriting. Pen support would
mean a second application (Xournal++ or custom) plus switching logic. Treat as its own project
after Stage 1–2.
 
## Dead ends — do not re-litigate
 
- **`SDL_DRM_DEVICE`** is not a real SDL variable. SDL selects by index
  (`SDL_KMSDRM_DEVICE_INDEX`), and none of it matters here anyway (next point).
- **kmsdrm with KOReader's bundled SDL3** — the backend is not compiled in. Confirmed by
  `strings`. Only a self-built SDL3 would change this; not worth it, cage works.
- **`WLR_OUTPUT_TRANSFORM` with cage 0.2.0** — ignored. Revisit only with a newer
  cage/wlroots, and then mainly for touch-coordinate consistency.
- **`video=...,rotate=90` in cmdline.txt** — did nothing on vc4; `fbcon=rotate:N` is the
  working parameter, and it only affects the text console.
- **Waveshare 7" DPI LCD on the Pi 400** — never produced an image despite everything checking
  out in software (overlays loaded, connector `connected`, correct mode, `fb0` correct size,
  raw writes invisible). Concluded to be a physical/data-path issue. Disposable stand-in,
  superseded by the Modos kit. Not worth further time.
- **Parallel-RGB bypass of the decoder on the dev kit** — not possible, decoder is hardwired.
  It is a Stage 3 option only, and even then the realistic decoder-less paths are direct DVI
  (≤105 MP/s) or MIPI/LVDS, not a native parallel-RGB input (which the gateware doesn't list).
## Open decisions
 
1. **Panel size for the product** — 6"–7" with full 75 Hz and headroom, or push for 8" Sage
   format and accept reduced refresh / DP input / a next-gen controller? Biggest open
   architectural question.
2. **SBC for Stage 1** — Pi Zero 2 W (easy migration, 512 MB) vs RK3566 class (more RAM, new
   bring-up).
3. **Rotation strategy once touch exists** — keep app-level rotation and transform touch
   coordinates, or move to a compositor that honours output transform.
4. Panel sourcing: does a bare panel with **integrated touch and frontlight** exist for the
   chosen size, or do overlay/light-guide layers have to be laminated by hand?
## Immediate next actions
 
1. **Board shell over USB** — inventory MCU commands; test rails-off-then-video-off; verify
   image retention; measure that state; test wake and whether a full refresh is required.
   Ask on the Modos Discord about signal-loss behaviour in parallel.
2. Continue Stage 1 procurement and the first 3D-printed case (seed geometry from Glider
   `case/`).
3. Read-only rootfs / overlayfs before the device gets switched off casually.
4. Minor but real: the Pi has no RTC and no network, so its clock drifts (KOReader logs showed
   late June while the actual date was late July). **The product will need an RTC** — note it
   for the Stage 2 power board.
## How I want you to help
 
**Do:**
- Write and debug Python, Lua, shell, systemd units, Linux config
- Write C and teach it as we go — I want to grow past Arduino-level C toward kernel-adjacent
  and MCU firmware work
- Explain Verilog/Caster internals so I understand the gateware (I don't intend to author it)
- Read datasheets and translate them; review schematics; select parts; do power/thermal/battery
  math
- Give debugging strategy: tell me what to measure and interpret results with me
- Flag when I'm about to sink time into something that won't transfer to the final product
- Push back on my plans when they're wrong, but don't talk me out of things I've explicitly
  chosen for good reasons (above all the low-latency FPGA path)
- Ask the one question that actually gates the next step, rather than listing options
**Can't:**
- Flash, measure, or touch hardware; run FPGA synthesis; see my board
- Guarantee hardware works first try — hardware debugging is a dialogue
**Style:**
- Be direct and honest about uncertainty. If a number is an estimate, say so.
- Prefer verifying current versions/URLs/prices by searching over recalling them.
- When I ask to see something work, take that seriously; "trust me, it works invisibly" is not
  a satisfying answer for a display project.
- Concrete next actions beat long option lists.
- If you gave me advice that later turns out wrong, say so explicitly and retract it.
## Caveats on figures in this document
 
Measured values (the power table) are real, from a USB-C meter at 5.14 V. Everything else —
runtime projections, freelancer and campaign cost ranges, timeline estimates, thickness — is
back-of-envelope and should be validated, not treated as established fact. Pixel-rate figures
for panels other than the 6" kit include estimated blanking and should be recomputed with the
Modos timing calculator before any decision rests on them.
