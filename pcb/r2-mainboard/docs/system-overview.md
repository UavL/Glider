# System overview — what the blocks are, how they connect, and how each one gets programmed

Written 2026-08-18 to answer four owner questions in one place: how a bare board from the fab
becomes a working product, whether the SoM's DDR4 can serve the FPGA, what the SPI NOR flash
actually does, and what the whole system looks like as one picture.

**This is a map, not a new source of truth.** Every number here comes from a per-sheet doc in this
directory or from `../../NOTES-R2-hardware-facts.md`, and those win if they disagree. What is new
is §6, which is a design gap this survey exposed.

---

## 1. The four programmable devices

Everything else on the board is fixed-function. These four hold state that has to be *put there*,
and each takes a different route:

| # | Device | Refdes | Sheet | Holds | Where its image comes from |
| --- | --- | --- | --- | --- | --- |
| 1 | **AM62x SoM** | `X2` | `som` (p. 2) | Linux, on 32 GB eMMC | eMMC primary, **microSD fallback** — module default straps |
| 2 | **FPGA** `XC6SLX16` | `U41` | `fpga_io` (p. 6) | Caster gateware — **volatile**, reloaded every power-up | config NOR `U42` |
| 3 | **Config NOR** `W25Q128JVSIQ` | `U42` | `fpga_config` (p. 11) | the FPGA bitstream, 16 MB | JTAG `J20`, **or the SoM writes it in-system** |
| 4 | **MCU** `STM32G0B1` | `U20` | `mcu` (p. 10) | housekeeping firmware | **SWD via `J20` only** ← the gap, §6.2 |

The SoM is `X2`, not `U`-anything — it is a *connector* reference because the part is a plug-in
module on two `BTH-060` receptacles, and it lives on **page 2**, not page 5 (page 5 is `power`).

## 2. Block map — every link and what it carries

```
                    ┌──────────────────────┐
   USB-C  ──────────┤  BQ25892  charger    ├──── +VSYS ──── the whole board
   J1              │  power path, OTG     │
    │              └──────────┬───────────┘
    │  D+/D−                  │  I²C (always-on bus, 0x6B)
    │                    cell PL706090 ── J2 Pico-Lock / J25 pads
    │                         │
    │                    MAX17048 gauge (0x36)
    │
    └── USB 2.0 ──►┌───────────────────────┐
                   │   X2   AM62x SoM      │
                   │   Linux · eMMC · DDR4 │
                   └───┬─────────┬────┬────┘
        microSD J21 ───┘         │    │
                                 │    └── UART ──► MCU  (console + control)
                    DPI 22 wires │    └── SPI0 ──► FPGA CSR bus  +  NOR_CS
                    18 data      │
                    +PCLK/DE/HS/VS
                                 ▼
                         ┌────────────────┐        ┌──────────────┐
              U42 NOR ──►│  U41  FPGA     │◄──────►│ U52 DDR3L    │
              bitstream  │  Caster EPDC   │ 666MT/s│ 128 MiB      │
                         └───────┬────────┘        └──────────────┘
                                 │ EPD bus (16-bit + timing)
                                 ▼
                         ┌────────────────────────────────┐
                         │  GDEP103TC2-FT11  10.3" panel  │
                         │  J6 EPD  ·  J24 frontlight     │
                         └────────────────────────────────┘
                                 ▲
                    LM3630A U53 ─┘  2 LED strings from +VSYS

   U20 STM32G0 (always on) ──► every MCU_EN_* rail enable, EPD HV sequencing,
                               VCOM/VGH DACs, page buttons, charger/gauge I²C
```

### The links, one row each

| Link | From → To | Width | Carries | Doc |
| --- | --- | --- | --- | --- |
| **DPI** | `X2` → `U41` | 22 | 18-bit RGB666 + `PCLK`/`DE`/`HSYNC`/`VSYNC`, 40–50 Hz | `som.md` §2 |
| **CSR SPI** | `X2` → `U41` | 4 + `NOR_CS` | Caster register/command bus — *the SoM drives it, not the MCU* | `fpga.md` §4.1 |
| **UART** | `X2` ↔ `U20` | 2 | console and control between Linux and housekeeping | `mcu.md` §3.2 |
| **EPD bus** | `U41` → `J6` | 16 + timing | pixel data to the panel | `epd-port.md` |
| **DDR3** | `U41` ↔ `U52` | x16 | EPDC framebuffer + per-pixel waveform state | `fpga.md` §5.1 |
| **Config** | `U42` → `U41` | 4 (x1 today, x4 wired) | the bitstream, on every power-up | §4 below |
| **I²C always-on** | `U20` ↔ charger, gauge, `U53` | 2 | `SCL_AON`/`SDA_AON`, alive whenever the cell is | `mcu.md` §5.3 |
| **MCU control** | `U20` → everything | ~20 | rail enables, `FPGA_PROG#`/`DONE`/`SUSP`, `SOM_WAKE#`/`RESET#`/`IRQ#` | `mcu.md` §3 |
| **USB 2.0** | `J1` → `X2` | 2 | sideloading books; D+/D− go to the SoM, not the charger | `battery.md` §1 |

## 3. The power tree, and who owns each rail

**The rule R2 exists to enforce:** every rail below `+3V3_AON` has a named enable net, a named
owner, and a pull-down that makes *off* the power-up state. R1 hardwired the enables high, which is
why 82 % of its idle draw could not be fixed in firmware.

| Rail | From | Part | Enable net | Owner | Feeds |
| --- | --- | --- | --- | --- | --- |
| `+VSYS` 3.0–4.4 V | cell | `BQ25892` power path | — | charger | everything |
| `+3V3_AON` | `+VSYS` | `TPS7A0233` LDO | **none** (tied on) | — | MCU, I²C pull-ups, buttons, gauge |
| `+5V` | `+VSYS` | `TPS61022` boost | `MCU_EN_5V` | **MCU** | SoM `VIN`, EPD HV chain |
| `+3V3` | `+VSYS` | `TPS63802` buck-boost | `MCU_EN_3V3` | **MCU** | FPGA `VCCO`/`VCCAUX`, `U42`, panel logic |
| `+1V2_FPGA` | `+VSYS` | `TPS62A02` buck | `MCU_EN_FPGA_CORE` | **MCU** | FPGA `VCCINT` |
| `+1V5` | `+VSYS` | `TPS62A02` buck | `MCU_EN_DDR` | **MCU** | DDR3L, FPGA bank 3 |
| `VGH`/`VGL`/`VPOS`/`VNEG`/`VCOM` | `+5V` | `epd_power` chain | `EPD_PWR_EN_MCU` &c. | **MCU** | panel HV |
| frontlight ×2 | **`+VSYS`** | `LM3630A` | `FL_EN` + `FL_PWM1` | **MCU** | bonded LED strings |
| `+3V3_SDIO` | **the module** | `SoC_VDDSHV5_SDIO` | — | **SoM** | microSD only |
| `+3V3_TOUCH`, `+3V3_PEN` | `+3V3` | load switches, **all DNP** | — | MCU | board-2 touch/pen |

Two things worth noticing in that table. The frontlight runs **straight off the cell**, not through
`+5V` — one conversion instead of two, and it is a current source, not a rail (`frontlight.md`).
And the microSD is powered **by the module**, not by our `+3V3`, so it costs nothing when the SoM
is off and it tracks the SoM's own 1.8/3.3 V I/O choice (`som.md` §4.1).

### 3.1 What actually runs on each rail

Taken from the exported netlist rather than from prose, so this is what the schematic says today.

| Rail | Blocks on it |
| --- | --- |
| `+3V3_AON` | housekeeping MCU `U20` · buttons `SW21`/`SW22` with 100 k pull-ups `R42`/`R43` · status LED `D20` · always-on I²C pull-ups and the charger/gauge open-drain status lines (`R3`–`R7`, `R19`) · three `INA3221` rail monitors `U21`/`U22`/`U27` · **the SoM's RTC backup on `X2` pin B2** · `J20` SWD/JTAG header (DNP) |
| `+5V` | SoM `VIN` via `+5V_SOM` · the EPD HV chain via `U6` (`MT9700`) |
| `+3V3` | FPGA I/O banks `U41` · config NOR `U42` · 33.33 MHz oscillator `X2` · panel logic through `J6` · `Q7` (VCOM gate drive) · touch/pen load switches `U1400`/`U1401` (**DNP**) |
| `+1V2_FPGA` | `U41` `VCCINT` — **sole load** |
| `+1V5` | DDR3L `U52` · FPGA bank 3 `VCCO` |
| `+VSYS_FL` | `L33` + `U53` `LM3630A` → two LED strings |
| `+3V3_SDIO` | microSD `J21` — **sourced by `X2` pin B1, not by this board** |
| `+3V3_TOUCH` / `+3V3_PEN` | `J1400` / `J1401` FPCs — both DNP on board 1 |

Three things this made visible that the per-sheet docs do not state together:

1. **`+1V2_FPGA` has exactly one load.** The cleanest rail on the board to gate, and where
   `MCU_EN_FPGA_CORE` buys the most for the least risk.
2. **The 5 V rail splits into six named branches before doing any work** — `+5V_SOM`, `+5V_EPD`,
   `+5V_EG`, `+5V_ES`, `+5V_VGH`, `+5V_VSH` — each with its own shunt or load switch, and the EPD
   chain is gated **twice**: `EPD_PWR_EN` through `U6` for the whole chain, then `EPD_POS_EN`
   through `U7`/`U8` for the source rails alone.
3. **The power button never touches an MCU rail.** `SW20` goes straight to the charger's `QON`
   pin (`/CHG_QON#`), so the board can be woken from a state where nothing but the charger is
   alive. `mcu.md` §2.2 designed this deliberately; it is worth restating because it is the reason
   the always-on rail can be as small as it is.

### 3.2 The EPD high-voltage chain, one level down

`+5V_DCDC` → `U6` `MT9700` load switch (`EPD_PWR_EN`) → `+5V_EPD`, then:

| Output | Generated by | Input branch |
| --- | --- | --- |
| `+VGH` | `U24` `LGS6302B5` boost + `L5` | `+5V_VGH`, switched by `U8` (`EPD_POS_EN`) |
| `-VGL` | `U9` `LGS5145` inverting converter | `+5V_EG` |
| `+VP` (VPOS) | `U23` `LGS6302B5` boost + `L30` | `+5V_VSH`, switched by `U7` (`EPD_POS_EN`) |
| `-VN` (VNEG) | `U26` `LGS5145` inverting converter | `+5V_ES` |
| `-VCOM` | `U31` `LM321` buffer + `Q6` | `+5V_EPD` |

All five land on `J6` and go to the panel. The MCU measures `VGH`/`VGL`/`VP`/`VN`/`VCOM` on its
ADC and trims `VGH` and `VCOM` through its two DAC outputs.

**Who controls what, in one sentence each.** The **MCU** owns every rail enable and the entire EPD
high-voltage sequence — it is the only thing awake in standby. The **SoM** owns the display
pipeline: it generates pixels over DPI and drives Caster's register bus over SPI. The **FPGA** owns
nothing but its own memory and the panel timing. The **charger** owns `+VSYS` and reports over I²C.

## 4. The SPI NOR flash — what it does and how

### 4.1 There are two, and only one of them is ours

- **On the module:** 64 MB QSPI NOR, part of the `PCM-071`. An *alternative* boot source for the
  AM62x. The module's default straps boot eMMC-primary with SD as backup (`som.md` §4), so R2 does
  not use it. It is there, it is spare, and R2 changes no straps.
- **On our board:** `U42`, a `W25Q128JVSIQ`, 16 MB, SOIC-8, on `fpga_config`. **This one matters**,
  and it is new in R2 — R1 has no configuration flash at all.

### 4.2 What it is for

A Spartan-6 is SRAM-based: at power-up it holds no logic whatsoever, and the entire 3,731,264-bit
bitstream has to be loaded before it is an EPDC. R1 does that from the MCU — `fpga.c`'s
`fpga_init()` pushes the bitstream out of SPIFFS over SPI **on every wake**, because `+1V2_FPGA` is
off in standby. R1 measures **360–400 ms** doing it, on every single resume.

`U42` removes the MCU from that path. Mode straps `M[1:0] = 01` select **Master SPI**: when `PROG#`
releases, the FPGA itself drives `CCLK`, issues a read to the NOR, clocks the bitstream in through
`DIN`, and raises `DONE` when the CRC checks. Nothing else is involved. This is what let the
housekeeping MCU be downgraded from an STM32**H750** to a **G0B1** — it no longer needs the flash
capacity or the throughput to serve a bitstream.

### 4.3 The clever part: four pins, three jobs

The same four wires are reused, and the directions only work out because of where Caster's UCF put
the register bus (`fpga.md` §4.1):

| Net | While configuring | While running | With `PROG#` held low |
| --- | --- | --- | --- |
| `CCLK` | FPGA drives | CSR `SCK` ← SoM | **SoM drives** |
| `DIN` | FPGA reads | CSR `MOSI` ← SoM | — |
| `MOSI/CSI_B` | FPGA drives | CSR `MISO` → SoM | **SoM drives** |
| `CSO_B` | FPGA drives | idle high | **SoM drives** via `R411` |

That third column is the one to remember: **hold the FPGA in reset and the SoM can rewrite the
gateware flash over its own SPI port.** Field gateware updates need no JTAG, no programmer and no
open case. It also carries a software rule with it — *the SoM must park those pins as inputs until
`FPGA_DONE`*, or it fights the FPGA for `CCLK` during configuration. `R411` (100 Ω) bounds the
fault current if firmware gets that wrong.

### 4.4 The bitgen settings are part of the deliverable

Self-boot is only worth having if it beats R1's 360–400 ms, and that is set by clock rate and bus
width, not by hardware:

| Mode | Typical | vs R1 |
| --- | ---: | --- |
| x1 @ `ConfigRate 2` — **what bitgen emits today** | 1866 ms | **5× worse** |
| x1 @ `ConfigRate 22` | 170 ms | ~2× better |
| **x4 @ `ConfigRate 22`** | **42 ms** | **~9× better** |

The board already wires x4 (`IO2`/`IO3` to `N12`/`P12`). **Shipping today's bitgen settings would
make resume five times slower than R1 while looking like an upgrade.** `fpga.md` §12 lists the five
bitgen changes; they are gateware work, and they are not optional.

## 5. Can the FPGA use the SoM's 2 GB of DDR4?

**No — and the reason is mechanical before it is architectural: those pins do not leave the
module.** Checked, not assumed: `datasheets/som_pinout.json` is the parsed `X2` pinout, all 240
pins. Searching it for `DDR`, `DQS`, `CKE`, `ODT`, `DQM` and `EMIF` returns **one** hit, and that
one is `X_GPMC0_ADVn_ALE` — the substring "DDR" inside "**ADDR**ess". There is no memory bus on the
connector to attach to.

That is the whole answer, but three other reasons would each be sufficient on their own:

1. **A DDR bus has one controller.** It is a point-to-point fly-by topology owned by the SoC's
   memory controller. There is no arbitration protocol for a second master; it is not a bus in the
   shared sense at all.
2. **The speed does not survive the connector.** DDR4 runs ~1.6 GT/s with tightly matched lengths.
   Taking it off-module through a 0.5 mm board-to-board connector and across our PCB to a second
   device is not a routing problem to be solved carefully — it is outside what the topology allows.
3. **Even if it worked, it would defeat the point.** Caster streams pixels at panel rate through
   `clk_mem`. Sharing DRAM with Linux means arbitration jitter on exactly the path this whole
   design exists to keep deterministic.

**What the FPGA uses instead:** `U52`, `MT41K64M16TW`, 1 Gb x16 DDR3L = **128 MiB**, private,
running 666 MT/s against a part rated for 1066 — margin deliberately left on the table so the
layout is easy (`fpga.md` §5.1, §11.1).

And the question underneath the question has a good answer: **the SoM does not need to share memory
with the FPGA, because it already hands it pixels** — that is what the 22-wire DPI link is. The
DDR3 is not a second copy of the SoM's RAM; it is the EPDC's working store, holding the previous
frame and per-pixel waveform state that e-paper greyscale needs and that the SoM never sees.

## 6. Production — how a bare board becomes a product

### 6.1 What arrives from the fab

JLCPCB or PCBWay ships an assembled board with **`U42` blank, `U20` blank, and no SoM fitted**.
Nothing on it can boot. The SoM plugs in afterwards and arrives from PHYTEC with their BSP demo
image on its eMMC — *whether that is true of every unit is worth confirming with PHYTEC, and it is
not something this design should depend on.*

### 6.2 The one real gap — and it is still cheap to close

Three of the four devices have a clean provisioning path:

| Device | Path from a bare board | Needs the case open? |
| --- | --- | --- |
| SoM | boot from microSD → write eMMC | no |
| Config NOR `U42` | **SoM writes it over SPI** with `PROG#` low (§4.3) | no |
| FPGA | reloads itself from `U42` at every power-up | no |
| **MCU `U20`** | **SWD via `J20` — pads only, header not fitted** | **yes, every unit** |

**As drawn, every board needs a physical SWD probe on an unfitted header to get its firmware.**
That is a manual bench step per unit, and it is also the recovery path — a bad flash means opening
the case. `mcu.md` §5.7 found this and named it correctly: *"free now, impossible after
fabrication."*

The MCU's own ROM bootloader can reprogram flash over **USART on `PA9`/`PA10`** — which *are*
`MCU_TXD`/`MCU_RXD`, with the SoM already on the other end. **The data path exists; the control
path does not.** `BOOT0` is `PA14` with a 10 kΩ pull-*down* (`R40`), and `MCU_NRST` reaches only
`J20`. So the SoM can talk to the bootloader but cannot start it, because it can neither reset the
MCU nor pull `BOOT0` high.

**Two SoM GPIO would close it** — one to `MCU_NRST`, one to `BOOT0` through a series resistor so it
fights neither `R40` nor an attached debugger. The SoM has ~150 unused pins. This is a WP8 decision
and Stage D has not started, so the cost today is two nets and two resistors.

### 6.3 What production would then look like

With those two GPIO, the board provisions itself and no step needs a probe:

1. Board comes off the line; a SoM is plugged in.
2. **Insert a factory microSD** and power on. The module's default straps boot eMMC-primary with SD
   backup, and a blank eMMC falls through to the card — so this needs no strap change and no
   button (`som.md` §4).
3. The card's image writes the production rootfs to eMMC.
4. The same script pulses `BOOT0`+`NRST` and flashes the **MCU** over the existing UART.
5. The same script holds `FPGA_PROG#` low and writes the **gateware** into `U42` over SPI.
6. Reboot from eMMC, self-test, remove the card.

One operator action, one card, no probe, no open case — and every step is the same one used for
field updates later.

### 6.4 So: should the product ship with an SD card?

**Ship the slot, not the rootfs.** `J21` is already on the board (`som.md` §4) and it should stay,
but Linux should live on the eMMC:

- The 32 GB eMMC is already bought and is faster and far more durable than a card — SD cards are
  the single most common failure part in this class of device.
- The boot order you want is already the module's factory default. **R2 changes no straps.**
- The slot then earns its place three times over: it is the **factory provisioning** route above,
  the **unbrickable recovery** route (a bad eMMC image is fixed by inserting a card, not by RMA),
  and a **user feature** for sideloading books.

One caveat, already on the record: `som.md` §4 flags that whether `SoC_VDDSHV5_SDIO` stays
energised in Suspend-to-RAM is **unknown and unmeasurable here**. A card left in for the product's
life is a few hundred µA against a 128.6 mW module — small, but it lands in the reading state,
which is the one number R2 exists to reduce. That is a dev-kit measurement, and the Lyra kit can
now make it.

## 7. What this survey opened

1. **Two SoM GPIO to `MCU_NRST` and `BOOT0`** (§6.2) — the only item here with a fabrication
   deadline. Owner decision, WP8.
2. **Ask PHYTEC what ships on the eMMC**, and whether they will pre-flash a customer image.
3. **The bitgen settings** (§4.4) — gateware work, and today's defaults are a regression.
4. **Does `SoC_VDDSHV5_SDIO` survive Suspend-to-RAM** (§6.4) — a dev-kit measurement.
5. **`+5V2_FL` is an orphaned net.** Its only nodes are `J6.7`, `J6.44` and `C147.1` — no source
   anywhere. It was the *old* panel's frontlight supply, taken out through the EPD connector; the
   chosen panel's frontlight is bonded and driven from `J24`, so the net was deleted when
   `frontlight` was redrawn but survives on `epd.kicad_sch`, which is frozen and was not touched.
   Nothing unsafe — two connector pins and a capacitor on a dead net — but `C147` is a BOM part
   doing nothing, and those two `J6` pins should be confirmed no-connect on the
   `GDEP103TC2-FT11` rather than something the panel expects. Like the `VGH` resistor
   (`epd-port.md` §10), the edit rides with the owner's review pass on that sheet.
