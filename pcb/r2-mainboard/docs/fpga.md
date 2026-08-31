# `fpga_io`, `fpga_config`, `fpga_ddr` — the FPGA — R2 work package 5

Status: **drawn, verified against the gateware, reviewed 2026-08-15 — §15.** One change came out of
the review: `J3` is deleted. Companion to `battery.md`, `power.md`, `mcu.md` and `epd-port.md`.
Last updated 2026-08-30 (§7 restates what UG393 does and does not sanction about the 22 µF bulk;
§11.5 records the `power_mon` shunts in the path; §4.2.1 withdraws the QE-bit step and names the
file the bitgen settings live in).

**The binding constraint on these three sheets is not R1's schematic — it is Caster's
`constraint.ucf`.** The pinout is fixed by the gateware, and fixed harder than that by the silicon:
the 48 DDR pins are bonded to the MCB3 hard macro, the configuration pins are dedicated, `VCCO` is
per bank, and clock inputs must land on `GCLK` balls. ISE 14.7 is the only toolchain that supports
Spartan-6, so none of it can be renegotiated for layout convenience.

A single swapped ball is fatal and **invisible to ERC** — the schematic stays perfectly legal, it
just no longer matches the gateware. So the acceptance criterion for this work package is not "does
it look right", it is `tools/check_ucf.py`, which compares the exported netlist against the UCF ball
by ball. It currently accounts for all 113 constrained balls with **0 failures** (§10).

---

## 1. The part

**`XC6SLX16-2FTG256C`** — LCSC `C39313`, **speed grade −2**. Device and package verified three
ways: `caster.xise` (`Device xc6slx16` / `Package ftg256`), `par/ise_flow.sh`
(`-p xc6slx16-ftg256-3`), and R1's own sheets, whose `Description` reads `XC6SLX16-FTG256`.
`NOTES-R2-plan.md` and `NOTES-R2-hardware-facts.md` both said `XC6SLX9`, and the facts file carried
a priced BOM line for the wrong part; both are corrected.

### 1.1 The speed grade — settled 2026-08-20, and it is a sourcing answer, not a preference

Earlier revisions of this section said `-3`, and the schematic carried `C39313`, which is a `-2`.
That contradiction was open as decision **D-6**. It closes with three findings, in the order that
matters:

**1. There is no `-3` in FTG256 to buy.** LCSC's whole `XC6SLX16` line, queried 2026-08-20:

| Code | Part | Package | Grade | Stock | Unit |
| --- | --- | --- | --- | ---: | ---: |
| **`C39313`** | `XC6SLX16-2FTG256C` | **FTG256** | **−2** | **2 058** | **$7.79** |
| `C415800` | `XC6SLX16-2FTG256I` | FTG256 | −2, industrial | 431 | $12.68 |
| `C169797` | `XC6SLX16-2CSG324C` | CSG324 | −2 | 1 057 | $9.07 |
| `C1521718` | `XC6SLX16-3CSG324I` | CSG324 | −3 | 69 | $11.12 |

The only `-3` on the catalogue is **CSG324**, a different package with a different ball map — not a
substitution, a redesign. So `-2` is not a choice between two available parts; it is the part.
`C415800` is the same silicon in the industrial temperature range and is the natural second source.

**2. Nobody ever chose `-3`.** In `caster.xise` the device and package properties are marked
`valueState="non-default"` — deliberately set — while every speed-grade property
(`Speed Grade`, `Change Device Speed To`, `Device Speed Grade/Select ABS Minimum`) is
`valueState="**default**"`, i.e. still holding ISE's built-in value, never edited. The `-3` in
`par/ise_flow.sh` is that default carried into the command line. **It is a default, not a
requirement**, which is why it never appeared in any Caster documentation.

**3. But `-2` runs the DDR3 at exactly its rated ceiling, and that is worth knowing before the
order goes out.** `ds162.pdf` Table 25, "Interface Performances", Memory Interfaces implemented
using the MCB, standard `VCCINT`:

| Interface | −3 | −2 | −1L |
| --- | ---: | ---: | ---: |
| DDR3 | 800 Mb/s | **667 Mb/s** | not supported |
| DDR2 | 667 | 625 | 400 |
| DDR | 400 | 400 | 350 |

Caster's MIG is generated with `C3_MEMCLK_PERIOD = 3000` ps (`mig_wrapper.v:76`, and the same value
inside `s6_ddr3.v`), so the memory clock is 333.33 MHz and the data rate is **666.67 Mb/s**.

> Against `-2`'s 667 Mb/s ceiling that is **0.33 Mb/s of margin — 0.05 %.** In spec, and only just.
> On `-3` the same design would have 20 % of headroom.

This is not a reason to change the decision, because there is no `-3` to change to. It is a reason
to do the one check that is free and has to happen before fabrication rather than after:

**Build Caster for `-2` and read the timing report.** `par/ise_flow.sh` hardcodes
`-p xc6slx16-ftg256-3` on the `ngdbuild` and `map` lines; changing those two to `-ftg256-2` retargets
the flow, and the ISE VM already exists (`USAGE.md`). What to look for: the MCB is a hard macro and
will not "fail timing" the way fabric does, so the report to trust is the `TIMESPEC TS_CLK33`
constraint and the 165 MHz `DPI_PCLK` path — a `-2` part is roughly 10–15 % slower in the fabric,
and `DPI_PCLK` is the constraint with the least room. **If that check has not been run, the board is
being ordered on an assumption.**

Two fallbacks exist if it does not close, and neither is a respin: drop `DPI_PCLK` (the panel needs
far less than 165 MHz — §16), or lower `C3_MEMCLK_PERIOD` and give up some framebuffer bandwidth.

**Not verified:** that ISE's default speed grade for `xc6slx16` is `-3` rather than the file having
been edited and re-saved. `valueState="default"` is ISE's own marker for "untouched", which is the
evidence used here; it has not been checked against a fresh ISE project.

It is not a drop-in substitution in either direction: an LX9 would trip the MIG's
`C3_SMALL_DEVICE` path (`s6_ddr3.v:234`, currently `"FALSE"` with the comment "set to TRUE for all
packages of xc6slx9 device"), and the two devices need different decoupling (§7).

The symbol is `pcb_common:XC6SLX-FTG256`, split into **six units**, which is what made a diffable
port possible. KiCad 10 also ships `XC6SLX9-FTG256`; do not use it.

| Unit | Contents | Pins | Sheet |
| --- | --- | ---: | --- |
| 1 | Bank 0 I/O | 45 | `fpga_io` |
| 2 | Bank 1 I/O | 60 | `fpga_io` |
| 3 | Bank 2 I/O | 42 | `fpga_config` |
| 4 | Bank 3 I/O (MCB3) | 59 | `fpga_ddr` |
| 5 | Dedicated config pins | 8 | `fpga_config` |
| 6 | 26 GND, 8 VCCAUX, 8 VCCINT | 42 | `fpga_ddr` |

Unit 6 is on `fpga_ddr` and not, as in R1, on the power sheet — R2's `power.kicad_sch` is reviewed,
committed, and has no FPGA on it. `fpga_ddr` was ported onto A3 to make room. Left where R1 had it,
ERC reported `missing_unit` forever and eight `VCCINT` balls would have reached the board
unconnected.

## 2. What the gateware requires

| Bank | VCCO | Contents | Balls |
| --- | --- | --- | ---: |
| 0 | 3.3 V | `EPD_SD[15:0]` | 16 |
| 1 | 3.3 V | EPD control ×7, `LED`, DPI ×22 | 30 |
| 2 | 3.3 V | `CLK_IN`, CSR SPI ×4, config, FPD-Link ×14 (being removed) | 19 |
| 3 | **1.5 V** | DDR3 ×48 on fixed MCB3 balls | 48 |

`check_ucf.py` reads those rails out of the schematic's own `VCCO_n` balls rather than a table, and
reports a bank split across two nets as a defect — a hand-maintained table going stale is exactly
the failure the script exists to catch.

- **`CONFIG VCCAUX=3.3`** (`constraint.ucf:1`) — mandatory.
- **DDR3 must be on bank 3 / MCB3, on exactly the UCF's balls.** Hard macro, not a preference.
  UG388 p.63 also notes the bank-1 MCB has the most multi-function conflicts and to prefer another
  bank — Caster uses MCB3, which is the right one.
- **`DDR_RZQ` (M4) and `DDR_ZIO` (M5)** are both required because `s6_ddr3.v` sets
  `C3_CALIB_SOFT_IP = "TRUE"`. §5.3.
- **No `INTERNAL_VREF`** anywhere in the UCF → bank 3 needs an external VREF divider. UG393 p.63
  confirms the VREF balls are consumed by any MCB interface except LPDDR, so `A3`/`M3` are not
  available as user I/O.
- **One 33.33 MHz LVCMOS33 oscillator into `M9`**, and nothing else. The MIG independently requires
  30 ns (`C3_INCLK_PERIOD`), and `TIMESPEC TS_CLK33 = PERIOD 30 ns`, so the frequency is not free.
- `DPI_PCLK` → `J13`, constrained to 165 MHz, must be GCLK-capable.
- JTAG must stay reachable: `top.v:830-839` instantiates ChipScope ICON/ILA unconditionally.

### 2.1 Three signal groups the board wires that the gateware does not implement

Each of these is a board net with no source anywhere in Caster. None is an error; each is a thing
that will never work until somebody writes RTL for it, and all three were found by `check_ucf.py`
rather than by reading.

| Board signal | Balls | Why it is dead |
| --- | --- | --- |
| `EPDC_D8`–`D11` (8 nets) | A7 C7 A8 B8 A9 C9 E7 E8 | `EPD_SD` is **16 bits in every build variant** (`caster.v:946-1002`; the 8-bit branch zero-fills the upper half, `top.v:827` is unconditional), and the UCF maps those 16 to panel pairs D0–D7 only. |
| `EPDC_CLKP`/`CLKN` | C8 D8 | There is no `EPD_CLK` port in `top.v` and no `EPD_CLK` line in the UCF. The gateware's only panel clock is `EPD_SDCLK`, which the board calls `EPDC_SE_CLK`. |
| `EPD_THROT` | M16 | "throt" appears nowhere in Caster. Declared on `mcu.kicad_sch` since WP3; contradicts a plan item that assumed it was live. |

**This settled `J3`.** The 16-pin panel connector carried 6 grounds and 10 signals, and *all ten*
were in the first two rows above — not "mostly unused", entirely unimplemented. `epd-port.md` §7
reached the same conclusion from three other directions; this was the fourth and the strongest.
**The owner deleted it on 2026-08-15** (§15.2), so the first two rows are now history rather than a
live finding, and the ten balls carry no-connect flags. `check_ucf.py`'s "reserved but not driven"
list is down from 11 balls to 1. `EPD_THROT` is that one — the only one of the three groups that was
never on `J3`, and it stays wired at `U41.M16` because `mcu.kicad_sch` declares it.

## 3. `fpga_io` — banks 0 and 1

A straight port. 69 net groups identical to R1, four parts (`U700` units 1–2, `R700` 10 kΩ, `D700`
status LED). Three deliberate deletions:

- **The 12-signal FMC bus to the MCU.** R1 wires `FMC_D[7:0]`, `FMC_A16`, `FMC_NE1`, `FMC_NOE`,
  `FMC_NWE` from the H750 to the FPGA, and **no `.ucf` in Caster assigns any of it** — the gateware
  has never used it. R2 has no MCU-side parallel bus at all, so the labels go and the freed bank-1
  balls get no-connect flags.
- **The 10 signals to `J3`** — `EPDC_D8`–`D11` and `EPDC_CLKP`/`CLKN`, deleted with the connector on
  2026-08-15 (§15.2). Balls `C7 A7 B8 A8 C9 A9 E7 E8 D8 C8`, all bank 0, now carry no-connect flags.
- R1 leaves 24 balls unused but flags only 12. The other 12 got flags, so ERC stays honest and
  claiming a pin later is a matter of deleting one.

That leaves **46 no-connect-flagged spare balls** on `fpga_io` — 24 in bank 0, 22 in bank 1, all at
3.3 V `VCCO`, counted from the netlist rather than by hand. 24 of them were spare in R1 too; the
other 22 are what the FMC and `J3` deletions freed. That is the largest block of free I/O on the
board and the place to look first if R2 ever needs another FPGA-side signal.

`EPD_THROT` is terminated here (`U41.M16`), which is where R1 puts it, even though §2.1 says nothing
drives it. Better a documented dead net than a hierarchical label that ends nowhere.

`FPGA_CLK33` arrives here at `K11`, the UCF's commented-out alternative location for `CLK_IN`. Both
`K11` and `M9` are wired, so moving the constraint is an edit to one line of the UCF rather than a
respin.

## 4. `fpga_config` — bank 2, configuration, and the CSR SPI

The only genuinely new circuit in this work package. Everything else is a port.

### 4.1 Self-boot from a config NOR

R1 has no configuration flash: `fpga.c`'s `fpga_init()` pushes the bitstream from the MCU's SPIFFS
over SPI on every pipeline start, and `+1V2_FPGA` is off in standby, so that happens on **every
wake**. R1 measures **360–400 ms** doing it. Self-boot is what allows the H750 → G0 downgrade, and
its real payoff is resume latency.

`U42` is a `W25Q128JVSIQ` in SOIC-8. Mode straps `M[1:0] = 01` (Master SPI, UG380 Table 2-1), tied
directly to GND and `VCCO_2` — UG380 is explicit that mode pins go straight to a rail, not through
resistors. `M1` is ball `N11`, which is why ERC reports one `pin_to_pin`: a bidirectional I/O ball
hard-tied to a rail that has a `PWR_FLAG` on it. That is the correct design and an accepted warning.

**The configuration pins are shared three ways**, and the directions only work out because of where
the UCF put the CSR SPI. This table is the reason the sheet is safe, and it was written before the
sheet was drawn:

| Net | Ball | Configuring (master SPI) | Running | NOR write (`PROG#` low) |
| --- | --- | --- | --- | --- |
| NOR `CLK` | R11 `CCLK` | FPGA drives | CSR `SCK` in ← SoM | SoM drives |
| NOR `DO`/IO1 | P10 `DIN` | FPGA reads | CSR `MOSI` in ← SoM | — |
| NOR `DI`/IO0 | T10 `MOSI/CSI_B` | FPGA drives | CSR `MISO` out → SoM | SoM must drive |
| NOR `CS#` | T3 `CSO_B` | FPGA drives | idle high | SoM drives via `R905` |

Two hazards, both handled on paper before copper:

1. **Contention on `CCLK` during configuration.** The FPGA drives it; the SoM's SPI controller would
   too if enabled. **The SoM must park those pins as inputs until `FPGA_DONE`** — a software rule,
   with `R905` (100 Ω) as the hardware backstop that bounds the fault current.
2. **`NOR DI` has two drivers** (FPGA `T10` and the SoM's MOSI), arbitrated only by `PROG#`. The
   SoM's MOSI lands on an FPGA *output* ball, which is safe only while the FPGA is held in reset.

`R904` (10 kΩ pull-up on `CSO_B`) was added on general grounds and turns out to be **required**:
UG380 note 9 under the Master SPI figure says "If HSWAPEN is left unconnected or tied High, a
pull-up resistor is required for CSO_B", and `HSWAPEN` (`C203`) is unconnected here (§5.4).

### 4.2 Quad-SPI provision — owner's decision, 2026-08-13

Self-boot only pays if it is *faster* than R1's 360–400 ms, and how much faster is set by the
configuration clock rate and the SPI bus width.

| | source |
| --- | --- |
| bitstream 3,731,264 bits | UG380 Table 5-5, XC6SLX16 |
| max master CCLK 40 MHz | DS162 `FMCCK`, −3 speed grade |
| master CCLK tolerance ±50 % | DS162 `FMCCKTOL` |

| Mode | typical | worst case | vs R1 |
| --- | ---: | ---: | --- |
| x1 @ `ConfigRate 2` — **today's bitgen** | 1866 ms | 3732 ms | **5× worse** |
| x1 @ `ConfigRate 22` | 170 ms | 339 ms | ~2× better |
| x4 @ `ConfigRate 22` | 42 ms | 85 ms | ~9× better |

Bus width was the only one of the two with a board cost, and it was nearly free now and a respin
later, so it is provided. UG380 Figure 2-13's x4 connection was already wired except its top two
rows: `MISO[2]` (`N12`) → flash `WP#/IO2`, `MISO[3]` (`P12`) → `HOLD#/IO3`. Both balls were spare
and no-connect flagged; no `.ucf` names them because they are dedicated configuration pins.

Flash pins 3 and 7 were tied hard to `+3V3`, which is right for x1 and wrong for x4 — Figure 2-13
note 4 asks for pull-ups to `VCCO_2` instead, so the tie became `R906`/`R907`, 10 kΩ. **Nothing
about the board's behaviour changes today**: in x1 the pull-ups hold `WP#`/`HOLD#` high exactly as
the hard tie did.

### 4.2.1 Where the settings live, and the QE step that does not apply — 2026-08-30

**The file is `Caster/rtl/spartan6/par/ise_bitgen.txt`**, consumed verbatim by `ise_flow.sh:34`:

```
bitgen -intstyle ise -f ise_bitgen.txt top.ncd
```

It currently reads `-g ConfigRate:2` and `-g SPI_buswidth:1` — the slowest pair available, and the
row that makes self-boot *worse* than R1 in §4.2's table. Caster is a submodule, so changing it is a
commit inside `Caster/` plus a pointer bump here, then a rebuild of all four variants on the ISE VM.

**UG380 Figure 2-13 note 3 does not apply to `W25Q128JVSIQ`.** The note says "The SPI device needs to
be programmed with a specific register setting, which is done in iMPACT software, to enable x4
output" — that setting is the flash's Quad Enable bit, and §8.2.9 of
`datasheets/FPGA/256_W25Q128JV.pdf` confirms QE "must be set to 1 before the device will accept the
Fast Read Quad Output Instruction." But the ordering
code decodes `W25Q128JV` · `S` 8-pin SOIC 208-mil · `I` industrial · **`Q` = "Green Package … with
QE = 1 (fixed) in Status register-2"**, and note 5 of the same table adds "/HOLD function is disabled
to support Standard, Dual and Quad I/O **without user setting**." The `M` suffix is the one that
ships `QE = 0 (programmable)` and would need the iMPACT step.

So **x4 is a one-line bitgen change**, not a bitgen change plus a flash-provisioning step. `Q` over
`M` is also the only correct choice for a self-booting FPGA: with `M` no host exists to set QE before
the FPGA tries to boot.

Three consequences worth recording:

- **x4 still boots x1 first.** UG380 p.47: "The FPGA still initially boots in x1 mode and then
  switches to x2 or x4 mode." Auto-detection loads a header in x1, then `IPROG` reconfigures and the
  bulk transfer runs as **Fast-Read Quad Output (`6Bh`)** with eight dummy clocks after the 24-bit
  address. §4.2's 42 ms is the bulk figure; the x1 header pass is on top.
- **The SoM cannot write the flash in quad.** `NOR_IO2`/`NOR_IO3` reach only `U700` and `R906`/`R907`
  — they are not on `J502`. The SoM sees `FPGA_SCLK`/`MOSI`/`MISO`/`NOR_CS#` only, so SoM-side
  bitstream writes are **x1, always**. That is a deliberate limit, not an oversight: it costs update
  time, never boot time.
- **There is no hardware write protect.** With QE=1 fixed, `/WP` is permanently `IO2` and `/HOLD`
  permanently `IO3`. Protecting the bitstream against a runaway SoM has to use the `BP[2:0]`
  block-protect bits in Status Register-1, in software. The pins are not available either way.

### 4.3 Clock and debug

`X900` is a 33.33 MHz oscillator, `R903` a 33 Ω series termination, reaching `M9` and `K11`.
`FPGA_CLK33` is exported from this sheet as an **output** — a direction error inherited from R1
(`input` on both sheets) that only became visible once the root was wired, because two `input`s
meeting is the one interface shape combination on this board that is never legitimate.

`J400` is one pads-only 2×6 1.27 mm footprint carrying **both** MCU SWD and FPGA JTAG, drawn on
`mcu.kicad_sch` because that sheet already exports the four JTAG nets. See `mcu.md` §10.

`FPGA_INIT` reaches the MCU at `PC10`. With the FPGA self-booting, a corrupt image shows up only as
`DONE` never asserting, which is indistinguishable from "the NOR never answered"; `INIT_B` low
separates the two. R1 did not need this because the MCU fed the bitstream and knew what it had sent.

## 5. `fpga_ddr` — bank 3, the DRAM, and the core rails

A port, with one added capacitor. All 49 local DDR nets are node-for-node identical to R1 after four
reference renames (`U1`→`U700`, `U12`→`U800`, `R400`→`R806`, `R404`→`R807`).

### 5.1 The memory, and how much of it there is

`U800` is `MT41K64M16TW` — **1 Gb**, x16, DDR3L. The MIG is configured for `MT41J64M16` (`mig.prj`),
the 1.5 V sibling of the same density, with `C3_MEM_ADDR_WIDTH = 13`, `C3_MEM_NUM_COL_BITS = 10`,
3 bank bits and 16 DQ. 8 banks × 8192 rows × 1024 columns × 16 bits = 1 Gb = **128 MiB, fully
addressable**. `C3_MEMCLK_PERIOD = 3000` ps → 333 MHz → **666 MT/s**, against a part rated for at
least 1066 MT/s: a lot of margin, and it is what relaxes the layout (§11).

The WP5 work-package plan claimed R1 fits a 4 Gb `MT41K256M16HA` and wastes three quarters of it.
That was wrong, and it came from reading the *symbol* name rather than the Value field. The symbol
is drawn to the 4 Gb ballout; the part fitted is the 1 Gb one, and
`NOTES-R2-hardware-facts.md` had it right all along (`MT41K64M16TW-107`, LCSC `C2060943`).

That mismatch has one visible consequence. **`DRAM_ADDR13`/`DRAM_ADDR14` reach `U800` balls `T3`/`T7`,
which the 1 Gb part does not bond** (Micron 1Gb_DDR3L Rev L Figure 7 p.18 shows `T3`, `T7` and `M7`
as NC), and which `top.v:22` never drives (`output wire [12:0] DDR_A`). Both nets are inert at both
ends. They stay routed: `T3`/`T7` are the density-expansion balls, so leaving them in makes a 2 Gb
or 4 Gb part a gateware-only change instead of a respin, and with bitgen's `-g UnusedPin:PullDown`
the two unconstrained FPGA balls sit at a weak low into an unbonded ball, drawing nothing.

### 5.2 1.35 V → 1.5 V

R1 runs this bank at 1.35 V. R2 runs it at **1.5 V**, and `power.kicad_sch`'s divider changed with
it (`R313` 124 k → 150 k, giving `0.600 × (1 + 150/100) = 1.500 V`). Three independent reasons:

- Every bank-3 net in the UCF is `SSTL15_II` or `DIFF_SSTL15_II`, and **`DDR_RESET_N` is
  `LVCMOS15`** — which has no 1.35 V form at all.
- DS162 Table 7 gives `SSTL15` a VCCO range of **1.425 / 1.5 / 1.575 V**. 1.35 V is outside it.
- `SSTL135` appears **zero** times in DS162 or UG381, so relabelling the UCF was not an option.

**The corollary, which is what settles the question when it is asked again: R1 is the one running
out of spec.** It uses *this same* `constraint.ucf` — 12 `SSTL15_II`, 6 `DIFF_SSTL15_II`, 1
`LVCMOS15`, no `SSTL135` — at `+1V35_DCDC`, i.e. **5.3 % below DS162's 1.425 V minimum**, with VREF
at 0.675 V against a 0.69 V minimum. It works on Zephray's board. That is evidence, not a
specification, and R2 is a battery device that will see a wider temperature range than a desk
monitor. So "DDR3L runs at 1.35 V" is true and is not the binding constraint: the DRAM is explicitly
"backward compatible to VDD = VDDQ = 1.5 V ±0.075 V", while the FPGA's bank-3 `VCCO` has no 1.35 V
form at all. **Reaffirmed by the hardware owner 2026-08-30** after re-examining it, on top of the
2026-08-15 review (§15.1).

Two things that were true when the decision was made and are more true now: the power case for
1.35 V evaporated on 2026-08-14 (`power.md` §9 — `IDD6` is 10.5 mW at 1.5 V against 10.8–16.2 mW at
1.35 V, and the SoM's 128.6 mW suspend dwarfs both), and §11.1's 0.05 % MCB timing margin means an
under-volted bank is spending the one budget this bus does not have. If it ever needs revisiting,
the change is a single resistor — `R313` 150 k → 124 k — and nothing in layout moves.

The DRAM is happy either way: the datasheet's own words are "Backward compatible to VDD = VDDQ =
1.5 V ±0.075 V". Cost is about 1.9 mW of extra standby draw, computed in `power.md` §9.

**That caveat is now resolved, in the favourable direction.** `mt41k64m16.pdf` specifies only the
1.35 V case and says "Refer to the DDR3 (1.5V) SDRAM data sheet specifications when running in
1.5V compatible mode". That datasheet arrived 2026-08-14 as `datasheets/MT41J.pdf`, and gives
**`IDD6` = 7 mA for every speed grade** (TC ≤ 85 °C, ASR and SRT disabled) → **10.5 mW at 1.5 V**,
against the DDR3L part's own 8 mA / 12 mA at 1.35 V (10.8 / 16.2 mW). So the 1.5 V decision costs
nothing measurable in self-refresh and may save. ⚠ `MT41J64M16` and `MT41K64M16` are different
orderable parts, so this is the closest published proxy — same density, same organisation, the
voltage we run at — **not** a spec for the fitted device. `docs/power.md` §9 carries the BOM
question that follows (the MIG is configured for the `MT41J`; is it stocked?).

`+DRAM_VREF` is `R804`/`R805`, 1 kΩ each, so it tracks at exactly half the rail: 0.750 V.

### 5.3 The three things UG388 requires, all of which R1 already did

`tools/check_ucf.py` checks the first two by shape rather than by net name, because neither has a
name to compare against.

- **`DDR_RZQ` (M4) needs one resistor to GND**, valued at twice the target impedance. The UCF asks
  for `OUT_TERM = UNTUNED_50` / `IN_TERM = UNTUNED_SPLIT_50`, so 100 Ω. R1 fits `R806` 100 Ω 1 %.
- **`DDR_ZIO` (M5) must be left open.** It is the MCB's internal calibration probe, not a spare pin.
  R1 flags it no-connect and the checker asserts it.
- **`DRAM_CSB` is tied low and reaches no FPGA ball.** UG388 p.43: "The active-Low Chip Select (CS#)
  pin of the target memory device should be connected to ground on the board. Because the MCB only
  supports connections to a single memory component, it does not provide a signal to control the CS#
  input." There is no `DDR_CS_N` in the UCF and no such port in `top.v`. R1 goes through `R801`
  5.1 kΩ rather than a hard short, which is functionally the same into a CMOS input and leaves a
  rework point.

UG388 p.43 also asks for **4.7 kΩ** pull-downs on `RESET` and `CKE` so both are low during memory
initialisation. R1 fits **5.1 kΩ** on each (`R803`, `R807`). The difference is immaterial — the
requirement is "weak pull-down", not a value — and it is left as R1 has it rather than changed for
the sake of matching a number.

`R802` 240 Ω on `ZQ` is the DRAM's own calibration reference and comes from the Micron datasheet,
not from Xilinx. Do not confuse it with `RZQ`.

### 5.4 `HSWAPEN`, and why the VREF divider is safe

UG388 p.43 carries a caution that lands directly on this board: if `HSWAPEN` is low during
configuration, internal pull-ups to `VCCO` are enabled on every I/O **including the VREF balls**, so
a resistor-divider VREF can be pulled up during configuration and the MCB can calibrate against a
wrong reference.

R2's VREF *is* a resistor divider. `HSWAPEN` (`C203`) is **unconnected**, inherited from R1, which is
the safe state — the pin has an internal pull-up, so floating reads High and the internal pull-ups
stay off. The hazard does not apply. It is recorded here because "unconnected" looks like an
oversight and is in fact the correct answer, and because anyone who later ties `C203` low to save a
few microamps would break DDR calibration in a way that would take days to find.

### 5.5 The FPGA core rails

Unit 6 and its 12 decoupling capacitors, relocated from R1's power sheet at +300. `VCCINT` is
`+1V2_FPGA`, `VCCAUX` is `+3V3`. One capacitor is added — see §7.

## 6. Sheet interfaces

| Sheet | Sheet pins | Notes |
| --- | ---: | --- |
| `fpga_io` | 47 | 23 `EPDC_*` (to `epd`), 22 `DPI_*` (to `dpi_in`, WP7), `EPD_THROT`, `FPGA_CLK33`. Was 57/33 before the `J3` deletion (§15.2) |
| `fpga_config` | 14 | CSR SPI ×4 + `NOR_CS` (to `som`, WP8), MCU control ×7, `FPGA_CLK33` out |
| `fpga_ddr` | **0** | Every net on the sheet is local; the rails arrive as power symbols |

`fpga_ddr` having no interface at all is worth stating plainly: the DDR bus runs from unit 4 to the
DRAM and stops, so there is nothing for the root to connect.

## 7. Decoupling, against UG393 Table 2-1

Table 2-1 (p.14), row `FT(G)256 LX16`, gives required PCB decoupling as (100 µF, 4.7 µF, 0.47 µF)
triples per rail:

| Rail | Required | R1 fits | Verdict |
| --- | --- | --- | --- |
| VCCINT | 0 / **5** / 1 | 2×22 µF, **4**×4.7 µF, 1×470 nF | **one 4.7 µF short** |
| VCCAUX | 1 / 1 / 2 | 2×22 µF, 1×4.7 µF, 2×470 nF | 4.7/0.47 met; 44 µF where 100 µF is listed |
| VCCO bank 3 | 1 / 1 / 2 | 5×22 µF (110 µF), 1×4.7 µF, 8×470 nF, 7×100 nF | **meets or exceeds all three** |
| VCCO banks 0/1/2 | 3 / 3 / 4 total | 6×22 µF (132 µF), 3×4.7 µF, 5×470 nF | 4.7/0.47 met; 132 µF where 300 µF is listed |

**One change made: `C833`, a fifth 4.7 µF on `VCCINT`.** It is a 0402 and it costs nothing; the
alternative is to argue from a PDS impedance simulation nobody here has run.

**Nothing else changed**, deliberately — but be precise about what licenses the 22 µF, because it is
weaker than it first reads.

**UG393 has no 22 µF part.** Table 2-2 (p.16) offers exactly three classes — 100 µF/1210,
4.7 µF/0805, 0.47 µF/0402-or-0204 — under four substitution rules: values may be *larger*, body size
may be *smaller*, ESR must stay in 10–60 mΩ, voltage rating may be higher. Rule 2 is what legalises
our 4.7 µF parts, which are 0402 `CL05A475MQ5NRNC` against a listed 0805. **Rule 1 does not do the
same job for the bulk**: 22 µF is *smaller* than 100 µF, and the Capacitor Consolidation Rules
(p.17) run the other direction — many small into one large, never one large into several small. So
no clause in UG393 makes 5×22 µF a sanctioned stand-in for 1×100 µF.

Table 2-1 note 3 is the nearest thing to support, and it is directional rather than dispositive: the
guidelines "do not include some of the 100 µF capacitors of previous versions and the total
capacitance requirement can include an increase in the quantity of **4.7 µF** capacitors. Both
versions of these guideline are valid." That sanctions trading bulk against *4.7 µF* parts. It never
names 22 µF. R1's arrangement is in the spirit of it, not licensed by it.

**What the 22 µF actually is: this design's house bulk part, inherited.** `CL10A226MQ8NRNC`, 0603
X5R 6.3 V, LCSC `C59461` — 15 instances, plus 16 more of the 10 V 0805 variant. R2 contains **no
capacitor larger than 22 µF anywhere on the board**; there is no 100 µF and no 1210 footprint. The
choice predates all R2 work (`pcb/mainboard/` goes back to `r0p4` in this repo's history).

Three things do support it, in descending order of strength: R1's board runs DDR3 at full rate;
board-level bulk covers part of the shortfall (`+3V3` carries about 200 µF distributed, and each
buck has a 22 µF/10 V 0805 at its own output — `C308`/`C310`/`C312`, with the caveat in §11.5); and
note 3's direction of travel is toward less bulk, not more. Making this rigorous means simulating the
PDS impedance from 100 kHz to 500 MHz, which is what UG393 actually asks for and is out of scope
here; it is a Stage-D item (§11.5), not a defect.

## 8. The root sheet

Until this work package the root had **zero** wires, labels or junctions: every child sheet had its
hierarchical interface, `set_sheet_pins` had been putting matching pins on the root's sheet symbols,
and nothing ever joined one sheet's pin to another's. `epd`'s `EPDC_D0P` and `fpga_io`'s `EPDC_D0P`
were two separate one-node nets. The board would have gone to layout with no panel bus at all.

`tools/wire_root.py` stubs each sheet pin and attaches a local label. Labels rather than wires:
well over a hundred pins across 13 boxes in four columns cannot be joined with wires legibly, and a
local label on the root *is* a root-sheet net, so same-named pins are the same net. `global_label`
would work and is worse — it would push every name into every sheet's namespace.

- **167 sheet pins, 99 distinct names, 65 joined across sheets.** (187/109/75 before the `J3`
  deletion took ten names off `epd` and `fpga_io`, §15.2.)
- **34 still one-sided**, each checked against a table of expected-dangling names with reasons:
  22 `DPI_*` (WP7 `dpi_in`), 5 CSR-SPI/NOR (WP8 `som`), 5 MCU↔SoM (WP8), 2 USB (WP8). Anything
  dangling and *not* in that table is reported as a finding, because a hierarchy this size hides a
  one-sided interface very well.

## 9. Open

1. **Two edits owed to Caster's `constraint.ucf` / `top.v`** — see §12. Neither blocks layout.
   The open question inside item 2 (does deleting the LVDS ports cost us the R1 test vehicle?) is
   **closed 2026-08-15**: no, R1's microHDMI path is untouched. §15.5.
2. **`+1V5` and `+DRAM_VREF` report `power_pin_not_driven`.** `+DRAM_VREF` genuinely has no driver —
   it is a divider — and a `PWR_FLAG` was tried and reverted, because the FPGA's VREF balls are
   bidirectional I/O and the flag trades one benign warning for two `pin_to_pin` ones. `+1V5`'s flag
   belongs on `power.kicad_sch` where `U15` makes the rail; that sheet is reviewed, so it is listed
   here rather than edited in silently. R1 reports the identical violation on `+1V35`.
3. ~~**`IDD6` at 1.5 V is unverified** (§5.2). Needs the 1 Gb DDR3 (not DDR3L) datasheet.~~
   **Closed 2026-08-14** — `datasheets/MT41J.pdf`, `IDD6` = 7 mA → 10.5 mW at 1.5 V. §5.2.
4. **The LX16 has never been priced.** `NOTES-R2-hardware-facts.md`'s BOM row is marked "re-query"
   after the LX9 correction. The DRAM (`MT41K64M16TW-107`, `C2060943`, $4.49) and the NOR
   (`W25Q128JVSIQ`, `C97521`, $1.22, the only JLC Basic part in the list) are both already priced
   there; the FPGA is the one gap.
5. **10 duplicate `#PWR` references** across `battery` and the ported sheets make every netlist
   export print "schematic has annotation errors". Power symbols carry their net in the Value field
   so nothing is electrically wrong, but a standing warning trains you to ignore warnings. Cheap to
   fix; touches `battery.kicad_sch`.
6. **`ExtMasterCclk_en` is an unexplored option.** UG380 p.54: `USERCCLK` (ball `T8` — freed by the
   LVDS deletion) can supply the configuration clock instead of the internal oscillator, which
   would remove the ±50 % `FMCCKTOL` spread from the boot-time figures in §4.2. It needs one more
   trace from `X900` and it is not needed to make the NOR worthwhile; noted so the option is not lost.

## 10. Verification — what was actually run

- **`tools/check_ucf.py`** — the one that matters. Parses every `LOC` and `IOSTANDARD` from
  `constraint.ucf`, resolves each ball against `pcb_common:XC6SLX-FTG256`, and asserts the schematic
  connects that ball to the net the gateware expects, at a bank voltage the IOSTANDARD can use.
  Result: **113 constrained balls, all accounted for** — 97 name-matched, 2 checked structurally
  (`RZQ`, `ZIO`), 14 asserted open (the LVDS group). **0 failures, 0 pending, 0 unexplained.**
  The script prints `MATCHED 99`, which is the 97 plus the 2 structural; 99 + 14 = 113.
  It also reports both interesting asymmetries: balls the gateware constrains but the board leaves
  open, and balls the board wires that no `.ucf` assigns — the latter is what found §2.1. Since the
  `J3` deletion (§15.2) that second list is down from 11 balls to 1, `EPD_THROT`.
- **Netlist node-diff against R1**, per sheet. `fpga_io` 69 groups identical; `fpga_ddr` 49 local
  groups identical; `+1V35`→`+1V5` moved with all 47 nodes intact.
- **`kicad-cli sch erc --severity-all --format json`**: 295 → 105 project-wide after wiring the
  root. `/fpga_ddr/` is 4, one fewer than R1's 5 for the same sheet, and all four are inherited.
  Every remaining `isolated_pin_label` and `label_dangling` is one of the 34 pending interfaces
  counted at both ends. `footprint_link_issues` ignored throughout (owner's library tables).
- **PDF export, rendered to PNG and read** at 100–260 dpi, for the root and all three sheets. This
  caught four collisions the netlist could not: the note block running through `fpga_ddr`'s title
  block, a title-block comment overflowing its box, a rail caption landing on the row above's bus,
  and two junction dots left behind by a deleted wire. `patch_fpga_ddr.py` now asserts its note
  block ends above the title block rather than trusting the arithmetic.
- **`git status pcb/mainboard/` clean** after every run — R1 is read-only and was only ever read.

One class of bug found here that neither ERC nor a render would have caught: adding 57 sheet pins
grew `fpga_io`'s root box until it overlapped `epd_power`'s, and seven FPGA balls silently shorted
to `VCOM_MEA_EN`, `SHDN` and friends. **ERC was silent.** The pin-map comparison found it;
`tools/layout_root.py` now asserts boxes do not overlap.

## 11. Layout guidelines — collected now, to be applied at Stage D

Written while the datasheets are open, in the shape of `mcu.md` §11. Nothing here is placement; it
is the constraints placement has to satisfy.

### 11.1 The DDR3 interface, and why it is easier than it looks

666 MT/s against a part rated for 1066+ is a lot of margin, and it is the single most useful fact
for this layout: unit interval is 1.5 ns, so a 100 ps mismatch is under 7 % of a UI. Length matching
still matters, but the tolerances are relaxed compared with a 1600 MT/s interface.

⚠ **That margin is against the DRAM, and only against the DRAM.** At the FPGA end the `-2` part's
MCB is rated for 667 Mb/s against the 666.67 Mb/s this design runs (§1.1) — 0.05 %. So the layout
does *not* get to spend the DRAM's headroom: treat this bus as a bus with no margin at the
controller, match it properly, and keep it over one continuous plane. The relaxed numbers below are
what the *geometry* tolerates, not slack to give away.

- **Match within a byte lane**, tightly: `DQ[7:0]` + `LDM` + `LDQS`/`LDQS#` as one group,
  `DQ[15:8]` + `UDM` + `UDQS`/`UDQS#` as the other. The two lanes need not match each other —
  the MCB deskews per lane (`Phase 2: DQS Centering`, UG388 ch. 4).
- **Address/command/control** is one group matched to the clock pair. UG388 p.42 wants memory
  terminations, if used, placed **after** the memory in fly-by fashion, and trace-length matching to
  **exclude** the stub from the memory ball to any terminating resistor.
- **`DRAM_ADDR13` and `DRAM_ADDR14` are not part of that group and must be excluded from it.**
  They are the density-expansion nets of §5.1: the FPGA drives neither and the fitted 1 Gb part does
  not bond `T3`/`T7`, so they are inert at both ends. They look exactly like address lines to a
  net-class-based length-match rule, which would drag the real group's tolerance around for two
  dead traces. Route them short and direct, give them their own net class, and leave them out of
  the matched set (owner's decision to keep them, §15.3).
- **`DRAM_CKP`/`CKN`** carry `R800`, 100 Ω differential termination, at the DRAM end. Route as a
  proper differential pair with the two halves matched to each other before anything else.
- Keep the whole bus over one continuous reference plane. A split under the DDR bus is the classic
  way to lose the margin the low data rate just handed you.

### 11.2 `RZQ`, `ZIO` and `ZQ` — three different things, one of which must not be routed

- `R806` (100 Ω, `RZQ`, ball `M4`) close to the FPGA, short trace, direct via to ground.
- **Ball `M5` (`ZIO`) gets no copper beyond its pad.** It is an internal calibration probe. A
  helpful autorouter connecting it to anything breaks calibration.
- `R802` (240 Ω, `ZQ`) close to the DRAM's `L8` ball, its own via to ground. This is the DRAM's
  reference, not the FPGA's.

### 11.3 Bank 3 VREF

`+DRAM_VREF` is a quiet, high-impedance node at 0.750 V feeding four balls (`U41.A3`, `U41.M3`,
`U52.H1`, `U52.M8`). Treat it like the `VREF+` island on `mcu.md` §11.2:

- `R804`/`R805` near the FPGA, `C820` (100 nF) at the divider node, `C819` (100 nF) bridging to
  `+1V5` so VREF tracks the rail's noise rather than fighting it.
- Route it as a short, fat, quiet trace to all four balls. Do not pour a plane on it and do not run
  it beside anything switching.
- The 4×470 nF plus 100 nF on this node give an RC of roughly 500 Ω × 2 µF = 1 ms against a VCCO
  ramp DS162 Table 6 allows to be as fast as 0.20 ms. VREF therefore **lags** the rail on power-up,
  which is the safe direction — JEDEC requires VREFDQ ≤ VDDQ at all times, and lagging low satisfies
  that. Worth knowing before someone "fixes" it by removing capacitance.

### 11.4 The 33.33 MHz oscillator and the config NOR

- `X900` with `C918` at its supply pin; `R903` (33 Ω) at the **oscillator** end, not the FPGA end,
  which is where a series termination has to be to do anything.
- The NOR at ConfigRate 22 and x4 is a ~33 MHz worst-case bus over six signals. Keep `U42` close to
  the FPGA's bank-2 balls and keep the six roughly equal; this is not a matched bus but it is no
  longer slow, either.
- `R905` (100 Ω) in the SoM's `NOR_CS` path is a fault-current limiter, so it belongs near the
  contention point, not near the SoM.

### 11.5 Decoupling placement, and the one open PDS question

- §7's counts are a bill of materials, not a layout. UG393 ch. 2's rule is that the network's
  impedance must be at or below the recommended one from 100 kHz to 500 MHz, which is a placement
  property: the 470 nF parts belong hard against their balls with their own vias, the 4.7 µF behind
  them, the 22 µF anywhere reasonable on the rail.
- Bulk substituted *downward* (§7) means placement carries more of the load than it would with the
  100 µF UG393 assumes: there is less low-frequency charge stored, so the path to it matters more.
  The 470 nF in particular cannot be consolidated or relocated — UG393 p.17 is explicit that a
  high-frequency capacitor's usefulness "depends on the number of PCB vias accessed."
- **The `power_mon` shunts are in the path, and that weakens one of §7's three supports.** UG393's
  "PCB Bulk Capacitors" paragraph (p.16) allows the regulator's own output capacitors to count
  toward the Table 2-1 bulk "provided there is no inductor, ferrite bead, choke, or other filter
  between the FPGA and the bulk capacitors." There is something: `R1205` (20 mΩ, 0805) sits between
  `+1V2_DCDC` and `+1V2_FPGA`, `R1204` between `+1V5_DCDC` and `+1V5`, `R1206` between `+3V3_DCDC` and
  `+3V3`. **(inferred, not from UG393)** A shunt is a resistor rather than a bead, and 20 mΩ is
  *inside* the 10–60 mΩ ESR band Xilinx specifies for the capacitors themselves, so it does not
  isolate the way a filter element would — but `C308`/`C310`/`C312` are not straightforwardly parallel
  with the FPGA's own bulk either, and the layout should keep the buck → shunt → FPGA path short and
  wide. Do not treat the buck output capacitors as free bulk without saying this out loud.
- The one genuinely open question is whether the 22 µF-in-quantity substitution for the listed
  100 µF holds up on this stack-up. R1's board is the evidence that it does; a PDS simulation is the
  proof, and neither has been done for R2's geometry. UG393 names the price itself — the ESR ranges
  "can be over-ridden. However, this requires analysis of the resulting power distribution system
  impedance to ensure that no resonant impedance spikes result" (p.16). Flagging it here so it is a
  decision at Stage D rather than a discovery at bring-up.

### 11.6 Power-up

DS162 Table 6 note 2: "Spartan-6 devices do not have a required power-on sequence." Ramp times must
land in **0.20–50.0 ms** (Table 6), which is a constraint on `power.kicad_sch`'s soft-start, not on
this sheet. R1 brings all rails up together and works.

## 12. Owed to Caster

Neither of these blocks the schematic, and both are why the fork exists.

1. **Assign `CSO_B` in the UCF and drive it high in `top.v`.** After configuration `CSO_B` becomes a
   user pin; with no constraint and `-g UnusedPin:PullDown` it would sit low, holding the NOR
   selected while the CSR SPI is using the same clock and data lines.
2. **Delete the 14 LVDS constraint lines and their top-level ports.** R2 has no FPD-Link source, so
   seven differential input buffers with `DIFF_TERM` enabled would sit at an indeterminate common
   mode where they can self-oscillate and draw current — in the reading state, which is the one
   number R2 exists to reduce. ~~**Open question:** removing the ports makes the bitstream
   R2-specific and breaks DisplayPort input on R1, which is the only test vehicle. This probably
   wants the `write_build_config.sh` variant mechanism rather than an unconditional deletion.~~
   **Closed 2026-08-15 — delete unconditionally, no build variant** (§15.5). R1 has two video
   inputs on two different Caster source ports, and only the USB-C DisplayPort one goes through
   these pins; the microHDMI/`ADV7611` path drives the same `DPI_*` nets R2's SoM will drive, so R1
   stays a complete test vehicle for everything R2 does. R2 needs its own UCF regardless — the
   config pins and the `N12`/`P12` `PULLUP`s differ from R1, and ISE's UCF has no preprocessor.

And three bitgen changes that the config NOR needs to be worth having (§4.2; the file they live
in is named in §4.2.1) — **all three applied by the owner 2026-08-31** in
`Caster/rtl/spartan6/par/ise_bitgen.txt`: `ConfigRate 2 → 22`, `Binary no → yes`,
`SPI_buswidth 1 → 4`. Self-boot goes from 1866 ms to ~42 ms typical. Not yet rebuilt or measured:

3. **`-g ConfigRate: 2 → 22`.** At 2 MHz self-boot takes 1.9 s, five times worse than R1.
4. **`-g Binary: no → yes`**, so there is a flash image to program.
5. **`-g spi_buswidth: 1 → 4`**, when x4 is wanted. ~~plus the flash's QE bit (UG380 Fig 2-13
   note 3)~~ — **there is no QE step for the part we fitted; see §4.2.1.** Also give `N12`/`P12` an
   explicit `PULLUP` constraint so `-g UnusedPin:PullDown` does not fight `R906`/`R907` after
   configuration.

And one that is wanted eventually but is explicitly **not** for the first board:

6. **Handle a short final DDR3 burst in `memif.v`**, which would retire the 128-pixel resolution
   rule (§16). `mig_cmd_bl` is already a per-command 6-bit port, hardwired at `memif.v:252` to
   `BURST_LENGTH - 1`, and the Xilinx MIG supports a variable burst length — so the mechanism
   exists and is unused. **Deferred by the hardware owner, 2026-08-16**: padding the resolution
   costs a handful of unused lines, and this is Verilog in the DDR3 path, which is not where the
   first board's risk should go. Revisit once there is a panel on the bench.

`r0p7` is already merged into the branch this was verified against (`704c4dd Merge branch 'r0p7'`);
its one unmerged commit, `93d76f2 WIP changes for K3`, changes no `LOC` line, so none of the above
is affected by it.

## 13. Conventions

Same as the other sheets. Spare pins carry no-connect flags. Ported references keep their R1 number
unless they collide, in which case U/L take +40 and C/R/D take +300; parts genuinely new in R2 take
the next number in the 5xx block (`C919`, `C833`). `pcb/mainboard/` is **read-only** and is only
ever read. A sheet that has been saved in Eeschema is patched surgically, never regenerated —
`port_r1.py` refuses to re-port a sheet in its `FROZEN` set without `--force`.

## 14. What changed from R1, and why

| | R1 | R2 | Why |
| --- | --- | --- | --- |
| Bitstream source | MCU SPIFFS, pushed over SPI every wake | `U42` config NOR, self-boot | 360–400 ms on every resume; also what allows the H750 → G0 downgrade |
| Config mode | Slave Serial, `M[1:0]=11` | Master SPI, `M[1:0]=01` | follows from self-boot |
| CSR SPI master | MCU | SoM | `mcu.md` §2.1 |
| Bank 3 VCCO | 1.35 V | **1.5 V** | `LVCMOS15` and `SSTL15` have no 1.35 V form (§5.2) |
| NOR IO2/IO3 | — | wired to `N12`/`P12` | keeps x4 boot a software change (§4.2) |
| FPGA unit 6 | on `power.kicad_sch` | on `fpga_ddr` | R2's power sheet has no FPGA |
| VCCINT decoupling | 4×4.7 µF | 5×4.7 µF (`C833`) | UG393 Table 2-1 asks for five |
| FMC bus to MCU | 12 signals | deleted | no `.ucf` ever assigned it |
| FPD-Link input | 14 signals | deleted | no PTN3460 in R2 |
| Debug header | `J5` 2×6, fitted | `J400` 2×6, pads only | `mcu.md` §10 |
| `INIT_B` | unconnected, no pull-up | `R908` 4.7 kΩ + MCU `PC10` | tells a CRC error from a silent NOR |
| `J3` 16-pin panel connector | fitted, 10 signals | **deleted** | no gateware for any of the ten (§2.1); owner's decision §15.2 |

## 15. Review 1 (2026-08-15) — the analysis note, answered

The note is `../manual-analysis/Analysis_fpga.md`, answering the five decisions put up in §9 and in
the review message. Four are accepted as drawn; one is a change, and it is made.

The owner's framing matters for how this review was set up: *"analysing the fpga sheets is out of my
scope and the datasheets don't have the same neat pinout and example layout that I could check your
design against."* That is right, and it is why `check_ucf.py` exists — the ball-level correctness is
machine-checked against Caster's own `constraint.ucf`, and what was put up for review was the four
or five judgement calls the script cannot make.

### 15.1 Bank 3 at 1.5 V — accepted

> "1.5V is fine."

Closed. No change. This was the item flagged hardest because it reached into `power`, `power_mon`
and `fpga_config`, three sheets already approved at 1.35 V. The cost stands at about 1.9 mW of extra
standby draw (`power.md` §9), against `LVCMOS15` having no 1.35 V form at all (§5.2).

### 15.2 `J3` — deleted

> "Yes, delete J3 connector. What was the reason it existed on the original Caster Design?"

**Done** — `tools/patch_drop_j3.py`, commit `28b6e0f`. What went: `J3`, its ten signal nets
(`EPDC_D8`–`D11`, `EPDC_CLKP`/`CLKN`), its six grounds and the mounting pin, the matching
hierarchical labels on both `epd` and `fpga_io`, and the ten root sheet pins. The ten freed FPGA
balls — `C7 A7 B8 A8 C9 A9 E7 E8 D8 C8`, all bank 0 — carry no-connect flags. The netlist before and
after has 351 nets either way, with exactly those ten gone, exactly seven nodes off `GND`, and every
other net unchanged.

**Why it existed.** Not a Caster thing — a *Glider* thing, and Glider is a general-purpose EPD
monitor rather than a reader. `README.md`, "Screen Adapters":

> "The motherboard uses a **50 pin + 16 pin** connector. A single 50 pin connector is enough for
> 8/16-bit screens, the 16 pin connector additionally adds support for **LVDS screens and 32-bit /
> 64-bit screens**."

and, under "LVDS":

> "Some higher resolution panels (such as **25.3″** ones, and **11.8″ Gallery 3** panel) uses LVDS
> signaling instead of LVCMOS."

The screen list bears that out with no exceptions: every `MiniLVDS` row is 8″ 1920×1440 or larger
(`AC080KH1/2`, `AC118TC1`, the 25.3″ and 28″ families), and every 6″ 1448×1072 panel — the whole
`ED060*`/`EC060*` family, which is what a reader uses — is `TTL`, 34 pins, adapter `34P-A`. So `J3`
is the big-panel and colour-Gallery option. `J1000` alone is the reader's connector, and it still has
five spare pins.

**A fifth confirmation, found while writing this up.** None of the ten adapter boards in this
repo — `34p-adapter-a/b`, `35p-adapter-a`, `39p-adapter-b/c`, `40p-adapter-ab`,
`50p-adapter-b/c`, `mega_adapter`, `u133_adapter` — contains a 16-pin FPC part. Every one mates
with the 50-pin `J1000` alone. The connector was unused by the whole adapter ecosystem that
shipped with R1. (Careful with the name: `35p-adapter-a` has a reference designator `J3` of its
own, and it is that board's 35-pin *panel* connector, nothing to do with this one.)

**Does this foreclose a bigger / colour tablet later? No — and `J3` was never the obstacle.**
Asked by the owner 2026-08-15. README's panel table splits **126 TTL / 11 MiniLVDS**, and the
MiniLVDS set is short enough to list in full: 8.0″ `AC080KH1/KH2` and 11.8″ `AC118TC1`, all three
**Gallery 3**, plus the 25.3″/28″ signage panels. So of tablet-sized panels, the *only* things
behind `J3` are 8″ and 11.8″ Gallery 3. Everything else that is bigger, colour, or both is on `J1000`:

| Size | Panel | Technology | Panel pins |
| --- | --- | --- | ---: |
| 7.8″ 1872×1404 | `EC078KH6`/`KH7` | Kaleido 3 | 40 |
| 10.3″ 1872×1404 | `EC103TH2` | Kaleido 3 | — |
| 10.3″ 2480×1860 | `EC103KH2` | Kaleido 3 | — |
| 13.3″ 1600×1200 | `EC133UJ1` | Kaleido 3 Outdoor | 39 |
| 13.3″ 1600×1200 | `AC133UT1` | Gallery / Gallery 4000 | 39 |
| 13.3″ 1600×1200 | `EL133UR1`/`US1` | Spectra 3000 | 39 |

The split falls there for a physical reason, not an arbitrary one. Kaleido is a **colour filter
array**, and README says the consequence outright: *"the low-level driving is the same with the
greyscale panels"* — which is why Caster carries `8bit-k3` and `16bit-k3` as build variants of the
same design. Gallery 3 and Spectra 6 are **multi-pigment**, *"much more difficult to drive, and
quite slow"*, and `CASTER_COLORMODE` has only `MONO`, `K3` and `RGBW` — there is no ACeP or Gallery
mode anywhere in Caster. So an 8″ Gallery 3 needs three things: the connector, MiniLVDS RTL that
does not exist, and an ACeP waveform pipeline that does not exist. The connector is by far the
cheapest of the three, and adding a 16-pin FPC to a future board is a schematic edit.

**The binding constraint on a bigger panel is pixel rate, not pins.** README's own limits are
133 MP/s processing with dithering enabled (280 MP/s without), `DPI_PCLK` constrained to 165 MHz in
the UCF, and 300 MP/s from DDR3-667 x16. Against demand at 60 Hz:

| Panel | MP/s @60 Hz | Verdict on this architecture |
| --- | ---: | --- |
| 13.3″ 1600×1200 | 125 | **fits everything**, dithering on |
| 10.3″ 1872×1404 | 169 | over the 165 MHz DPI constraint *and* over dithered processing |
| 8.0″ 1920×1440 | 177 | same — before MiniLVDS is even considered |
| 13.3″ 2200×1650 | 232 | dithering off only |

So the natural bigger-tablet target for this architecture is **13.3″ 1600×1200 colour at 60 Hz** —
125 MP/s, comfortably inside every limit, on `J1000`, with Caster's existing `k3` variant and a
`EC133UJ1` / `AC133UT1` / `EL133UR1` panel. That needs nothing from `J3`. (One number still to
check when WP7 lands: whether the AM62x DSS can source the required `VOUT` pixel clock. It bounds
this table from the SoM side and is not yet verified.)

Nothing is lost at the silicon level either: the ten balls are **no-connect flagged, not removed**.
They exist on the package, and a future layout can wire them.

**The residual risk, stated plainly.** This is irreversible after fab, and the panel model is still
deferred (`NOTES-R2-plan.md`: "read it off the tail/back label"). If that panel turns out to be an
8″-or-larger Gallery 3 / Spectra part, it is MiniLVDS and it needs `J3`. For any 6″ Carta panel it
cannot. The second, stronger argument does not depend on the panel at all: **no `LOC` line in
Caster assigns any of the ten signals**, so even with `J3` fitted and a MiniLVDS panel attached,
nothing in the gateware could drive it — that is an RTL project, not a connector.

**One knock-on worth knowing before someone adds a feature.** These ten balls take `fpga_io`'s
no-connect count to **46** — 24 in bank 0, 22 in bank 1, all 3.3 V `VCCO`. 24 were spare in R1 as
well; the other 22 are what this deletion and the FMC one freed. §3.

### 15.3 `DRAM_ADDR13`/`ADDR14` — kept, as drawn

> "If this causes no problems, then yeah sure keep the traces, why not?"

Kept. It is worth being precise about "no problems", because there is one and it is small:

- **Electrically, nothing.** Both ends are inert. `top.v:22` declares `DDR_A` as `[12:0]`, so the
  FPGA balls `F6`/`F5` are unconstrained and `-g UnusedPin:PullDown` sits them at a weak low; the
  fitted 1 Gb `MT41K64M16` does not bond `T3`/`T7` (Micron Figure 7, p.18), so the far end is a
  package ball with no die attached. No current, no load on the address bus.
- **In layout, two stubs.** They sit in the middle of the DDR3 fan-out and will be mistaken for
  real address lines by anyone length-matching by net-class. Added to §11.1 as an explicit
  exclusion so that does not happen.

What it buys: a 2 Gb or 4 Gb part becomes a `mig.prj` change instead of a respin, which matters
because the DRAM is the one part on this board with a live shortage attached to it.

### 15.4 `C833`, the fifth 4.7 µF on `VCCINT` — accepted

> "That is a good change you noticed. Its good to keep as the datasheet says."

Kept. It is the only BOM change on these three sheets: one 0402, `UG393` Table 2-1 row
`FT(G)256 LX16`, which asks for five and which R1 met with four. Worth restating what was *not*
changed on the same evidence — the bulk (100 µF) column, where R1 is short on three rails and
deliberately so, because Table 2-1 note 3 explicitly blesses trading bulk for more 4.7 µF parts
(§7). Making that rigorous needs a PDS impedance simulation, which is a Stage-D item, not a defect.

### 15.5 The FPD-Link deletion and DisplayPort — the decision dissolves

> "I dont see what decision I have to take here? We dont need DisplayPort, but if you think we need
> it for debug or prototype purposes we can discuss for sure."

**Fair — and on checking, there is no decision left to take.** I had framed it as a trade against
losing the only test vehicle, and that framing was wrong, because R1 has *two* video inputs and only
one of them goes through the FPD-Link pins.

`README.md`, "Hardware":

> "Type-C DisplayPort Alt-Mode video input with onboard **PTN3460 DP-LVDS bridge** *or*
> DVI (via microHDMI connector) video input with onboard **ADV7611 decoder**"

Those land on different FPGA banks and different Caster source ports. `vin.v` selects between three
sources — `SRC_INTERNAL`, `SRC_DPI` and `SRC_FPDLINK`:

| R1 input | bridge | FPGA pins | Caster source |
| --- | --- | --- | --- |
| USB-C DP Alt-Mode | `PTN3460` | 14 LVDS balls, bank 2 | `SRC_FPDLINK` |
| microHDMI DVI | `ADV7611` | `DPI_PCLK`, `DPI_DE/HS/VS`, `DPI_PIXEL[17:0]`, bank 1 | `SRC_DPI` |

And R1's `tmds_in.kicad_sch` drives net names `DPI_B2`…`DPI_R7`, `DPI_PCLK`, `DPI_DE/HS/VS` into
`fpga_io` — **the same twenty-two nets R2's SoM will drive**. So deleting the FPD-Link ports costs
R1 its USB-C DisplayPort input and nothing else; the microHDMI path, which is the path R2 uses,
keeps working. R1 stays a complete test vehicle for every video feature R2 has.

So: **delete unconditionally, no `write_build_config.sh` board variant needed.** §12 item 2 is
updated. Two smaller points that go with it:

- The deletion is not optional cosmetics. Seven differential input buffers with `DIFF_TERM = "TRUE"`
  on nets that no longer have a driver sit at an indeterminate common mode; with the constraint gone
  the balls become unconstrained and `-g UnusedPin:PullDown` gives them a defined weak low instead.
  `check_ucf.py` already asserts all fourteen are unconnected on the R2 schematic, so a
  half-finished deletion fails the check rather than passing quietly.
- The bitstream becomes R2-specific either way. R2's config pins, the NOR quad pins and the
  `PULLUP`s on `N12`/`P12` all differ from R1, and ISE's UCF has no preprocessor, so R2 needs its
  own constraint file regardless of what happens to the LVDS lines. That was the real cost I had
  mispriced as belonging to this one item.
- If a DisplayPort-capable bitstream for R1 is ever wanted again, it is `git checkout` of the
  pre-deletion revision, not a rebuild of the mechanism.

---

## 16. The 128-pixel resolution rule — where it comes from

`README.md:1139` states the constraint without explaining it:

> Current version of the Caster has additional requirements of the resoltion: X resolution
> multiply by Y resolution must be a multiple of 128.

Traced to source 2026-08-16, because it looked like it might veto a panel choice. **It does not.
It is DDR3 burst alignment, and nothing to do with e-paper, the waveform or the panel.**

Two files close the arithmetic.

**`Caster/rtl/spartan6/memif.v:64-66`** — the framebuffer moves in fixed-size bursts:

```verilog
localparam BYTE_PER_WORD = 16; // 128 bit bus
localparam BURST_LENGTH  = 16; // Should be at least 2
localparam BYTE_PER_CMD  = BYTE_PER_WORD * BURST_LENGTH;   // = 256 bytes
```

**`fw/User/caster.c:84`** — how much memory one frame takes:

```c
uint32_t frame_bytes = config.tcon_hact * 4 * config.tcon_vact * 2;
```

and `fw/User/config_timing.c:135` gives `tcon_hact = x_res / 4` — four pixels per source clock on
the 8-bit bus. Substituting: **`frame_bytes = x_res × y_res × 2`**, i.e. Caster keeps **2 bytes of
waveform state per pixel**.

> **256 bytes per DDR3 command ÷ 2 bytes per pixel = 128 pixels per command.**

`memif`'s own header comment says it "reads the VRAM via the read port **linearly through the whole
framebuffer**" — there is no partial-burst path at the end, so the pixel count must be a whole
number of commands.

**Cross-check:** 1448×1072 → `tcon_hact` = 362, matching `utils/flash_tool/cfggen/config.c:54`;
`frame_bytes` = 3 104 512 = **2.96 MiB**, which is the "3.0 MB waveform state" in
`NOTES-R2-plan.md`'s architecture diagram. The model is right.

### What it costs in practice

Pad the resolution down and lose the remainder — `README.md:1141` already does this for a 13.3"
panel (2200×1650 → **2200×1648**, "leaving the last 2 lines unused").

| Panel | X × Y | ÷ 128 | Action |
| --- | ---: | ---: | --- |
| `ED060KC1` family, 6" | 1448 × 1072 = 1 552 256 | 12 127 ✓ | none needed |
| `GDE060F3`, 6" | 1024 × 758 = 776 192 | 6 064 ✓ | none needed |
| `GDEP103TC2`, 10.3" | 1872 × 1404 = 2 628 288 | 20 533.5 ✗ | use **1872 × 1400** = 20 475 ✓ |

The 10.3" case costs **4 lines out of 1404** — 0.28 % of the height, 0.45 mm at the 112 µm pitch.
1872 = 2⁴ × 117 and 1404 = 2² × 351, so the product carries 2⁶ and is one factor of two short;
dropping Y to the nearest multiple of 8 supplies it. Trimming X instead would cost 16 columns, so
trimming Y is the better of the two.

**Accepted by the hardware owner, 2026-08-16**: pad, don't fix. The proper fix is §12 item 6.

### The related question this answered: input rate ≠ panel rate

While tracing the above: `Caster/rtl/spartan6/sysclock.v:53` sets `CLKIN_PERIOD (30.0)`, so
`clk_epdc` derives from a fixed **33.33 MHz** oscillator and not from the video clock. The panel
scans at a rate set by that clock and the panel timing, **independent of the input frame rate** —
which is what makes `framecap_en` (hold) possible at all: the framebuffer freezes while the glass
keeps being scanned.

Consequence for panel choice: **the input link rate and the panel's greyscale frame rate are
separate budgets.** A 40 Hz DPI link does not mean 40 Hz waveforms. `Project_description.md:246`'s
"grayscale rendering wants 85 Hz" is about the panel side, which comes from `clk_epdc`.

Noteworthy: `GDEP103TC2-FT11`'s datasheet §6 Mode 3 specifies **SDCK 33.33 MHz, 8 pixels/SDCK,
FR 84.99 Hz** — Caster's `clk_epdc` exactly, with no gateware clock change.

**Inferred from RTL, not measured.** Confirm at bring-up.
