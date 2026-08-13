#!/usr/bin/env python3
"""Port R1 sheets into the R2 project — work package 4.

`epd`, `epd_power` and `power_mon` are carried over from `pcb/mainboard/`
rather than redrawn, because the acceptance criterion for this work package is
"is it the same as R1". Copying keeps every part, value, coordinate and wire
identical, so a reviewer can diff the two directly; redrawing would change the
geometry and make that check impossible.

**R1 is read-only.** This script only ever reads `pcb/mainboard/*.kicad_sch`.

Five mechanical transforms are applied, and nothing else:

1. **Designator collisions.** Only references that clash with a designator R2
   has already issued are renamed, by a fixed offset (+200 for R/C, +20 for
   U/L) so the R1 number stays legible inside the new one. 92 of the 117 parts
   keep their exact R1 designator.
2. **Global labels become hierarchical labels.** R1 wires its sheets together
   with global labels; R2 uses hierarchical labels and sheet pins (WP1-WP3).
   The two are different nets in KiCad, so a mixed project would silently fail
   to connect. A few names are also renamed to R2's convention.
3. **Library links.** Three transistor symbols moved library in KiCad 10, and
   `SY8120`/`MT9700` are not in `pcb_common` at all — in R1 they survive only
   as definitions embedded in the sheet. Both are repointed at symbols this
   project owns.
4. **Rail names on `power_mon`.** The video-decoder rails are gone in R2, so
   three shunt channels are repurposed. The topology does not change at all --
   only which rail passes through each shunt. See `docs/epd-port.md` §3.
5. **Project identity.** Sheet instance paths, project name and title block.

The embedded `lib_symbols` definitions for stock symbols are also refreshed
from the installed KiCad 10 libraries -- the same thing Eeschema's "Update
Symbols from Library" does -- because five of them were revised between v8 and
v10 and otherwise ERC reports 54 `lib_symbol_mismatch` warnings. The refresh
refuses to run on any symbol whose pin geometry changed, so it can never move a
pin out from under a wire.
"""
import pathlib
import re
import subprocess
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import _extract_symbol_block, sheet_uuids  # noqa: E402

PROJ = HERE.parent
R1 = PROJ.parent / "mainboard"

# --- 1. designator collisions -------------------------------------------
# R2 has already issued U1-3/10-15/20, C1-8/20-34/40-50, R1-19/20-36/40-45,
# L1/10-13, D20, J1-2/20. Everything below collides with one of those; every
# other R1 designator on these three sheets is free and is kept as-is.
RENAMES = {
    "epd": {},
    "epd_power": {
        **{f"C{n}": f"C{n + 200}" for n in (32, 33, 41, 42, 44, 45, 46, 49)},
        **{f"R{n}": f"R{n + 200}" for n in (13, 17, 18, 19, 24, 25, 26, 27,
                                            28, 29, 30, 34)},
        "L10": "L30", "L12": "L32",
        "U11": "U31",
    },
    "power_mon": {"R7": "R207", "R8": "R208"},
    # WP5. The FPGA sheets add U/+40 and C,R,D/+300 -- R1's U1 (the FPGA) and
    # U12 (the DRAM) collide with battery's U1 and power's U12, and R11/R35-R37/
    # R40/R44/C26/C207 collide with blocks already issued. Offsets keep the R1
    # number legible inside the new one, as epd-port.md §1 does with +200.
    "fpga_io": {"U1": "U41", "R11": "R311", "D8": "D308"},
    "fpga_config": {
        "U1": "U41",
        **{f"R{n}": f"R{n + 300}" for n in (35, 36, 37, 109)},
        **{f"C{n}": f"C{n + 300}" for n in (16, 26, 92, 93, 148, 149, 150, 156,
                                            157, 182, 183, 184, 185, 186, 187,
                                            188, 189, 190, 207)},
        # X1 keeps its number: nothing else on the board uses X.
    },
    # fpga_ddr collides in only four places, so 27 of its 31 parts keep their R1
    # designator and the sheet diffs against R1 almost cleanly. `U1` must become
    # `U41` -- it is the *same* FPGA, unit 4, so the reference has to match the
    # one fpga_io/fpga_config already use or KiCad splits it into two parts.
    "fpga_ddr": {
        "U1": "U41",
        "U12": "U52",
        "R40": "R340",
        "R44": "R344",
        # Two power symbols only; R2 issued #PWR039/#PWR042 on other sheets.
        # These are two of the five that RAILS then moves to +1V5, so they are
        # renamed first and RAILS is keyed on the new names.
        "#PWR039": "#PWR0439",
        "#PWR042": "#PWR0442",
    },
}

# --- 1b. paper size ------------------------------------------------------
# R1 draws all three FPGA sheets on A4 and fpga_ddr fills it (content reaches
# x=276.9, y=191.8 of 297x210). R2 has to fit unit 6 of the FPGA symbol on here
# as well -- 42 power/ground pins that R1 keeps on its own power.kicad_sch,
# which in R2 is reviewed and has no FPGA on it at all. A3 is what the R2 stub
# was already generated as, and enlarging the page moves no symbol: KiCad
# measures from the top-left corner, so the extra 123 x 87 mm appears to the
# right of and below existing content.
PAPER = {"fpga_ddr": "A3"}

# --- 3. library links ----------------------------------------------------
LIB_REMAP = {
    "Device:Q_NMOS_GSD": "Transistor_FET:Q_NMOS_GSD",
    "Device:Q_PMOS_GSD": "Transistor_FET:Q_PMOS_GSD",
    "Device:Q_NPN_BEC": "Transistor_BJT:Q_NPN_BEC",
    "symbols:SY8120": "r2:SY8120",
    "symbols:MT9700": "r2:MT9700",
}

# --- 2. sheet interface --------------------------------------------------
# name in R1 -> (name in R2, hierarchical shape as seen from this sheet)
EPDC = {f"EPDC_{s}": (f"EPDC_{s}", "input") for s in (
    "CLKN", "CLKP", "GDCLK", "GDOE", "GDSP", "SDCE0", "SDLE", "SDOE", "SE_CLK",
    *[f"D{i}{p}" for i in range(12) for p in ("N", "P")])}
HIER = {
    "epd": {
        **EPDC,
        "FL_EN": ("FL_EN", "input"),
        "FL_PWM1": ("FL_PWM1", "input"),
        "FL_PWM2": ("FL_PWM2", "input"),
    },
    "epd_power": {
        "EPD_PWR_EN": ("EPD_PWR_EN", "input"),
        "EPD_POS_EN": ("EPD_POS_EN", "input"),
        "VCOM_EN": ("VCOM_EN", "input"),
        "VCOM_MEA_EN": ("VCOM_MEA_EN", "input"),
        "VCOM_DAC": ("VCOM_DAC", "input"),
        "VGH_DAC": ("VGH_DAC", "input"),
        "VCOM_MEA": ("VCOM_MEA", "output"),
    },
    # fpga_io is the other end of `epd`'s 33 EPDC labels, so every shape is the
    # complement of the one above: the FPGA drives the panel bus and receives
    # DPI. R1 already had these shapes right, but they are restated rather than
    # inherited so a wrong one cannot survive the port silently.
    "fpga_io": {
        **{f"EPDC_{s}": (f"EPDC_{s}", "output") for s in (
            "CLKN", "CLKP", "GDCLK", "GDOE", "GDSP", "SDCE0", "SDLE", "SDOE",
            "SE_CLK", *[f"D{i}{p}" for i in range(12) for p in ("N", "P")])},
        # 18-bit RGB666: bits 2..7 of each channel, which is what the DSS
        # presents and what the UCF's B2..B7/G2..G7/R2..R7 comments name.
        **{f"DPI_{c}{b}": (f"DPI_{c}{b}", "input")
           for c in ("R", "G", "B") for b in range(2, 8)},
        **{n: (n, "input") for n in ("DPI_PCLK", "DPI_DE", "DPI_HS", "DPI_VS")},
        # MCU -> FPGA throttle. Declared on mcu.kicad_sch since WP3 but
        # terminated nowhere until now; in R1 it lands on U1.M16.
        "EPD_THROT": ("EPD_THROT", "input"),
        # R1's bare "GCLK" says nothing about what it is. The net is X1's
        # 33.33 MHz through R409, and it reaches K11 here and M9 on
        # fpga_config -- the UCF keeps M9 active and K11 commented as the
        # alternative, so the board can move the constraint without a respin.
        "GCLK": ("FPGA_CLK33", "input"),
    },
    # Bank 2 plus the dedicated config pins. Directions are from the FPGA's
    # side: the SoM is the CSR master in R2 (docs/mcu.md §2.1), so SCLK/MOSI/CS
    # come in and MISO goes out. INIT_B is open-drain and both driven and
    # sensed, hence bidirectional.
    "fpga_config": {
        "FPGA_SCLK": ("FPGA_SCLK", "input"),
        "FPGA_MOSI": ("FPGA_MOSI", "input"),
        "FPGA_MISO": ("FPGA_MISO", "output"),
        "FPGA_CS": ("FPGA_CS", "input"),
        # FPGA_INIT is deliberately absent: on R1 it is a *local* label whose net
        # has exactly one member, U1.R3. R1 leaves INIT_B unconnected with no
        # pull-up at all. It stays local through the port so the sheet matches;
        # giving it a pull-up and a route to the MCU is a separate change, and it
        # matters more in R2 than R1 because with self-boot INIT_B low is how you
        # tell a CRC error from "still configuring" when DONE never arrives.
        "FPGA_PROG": ("FPGA_PROG#", "input"),
        "FPGA_DONE": ("FPGA_DONE", "output"),
        "FPGA_SUSP": ("FPGA_SUSP", "input"),
        "FPGA_TCK": ("FPGA_TCK", "input"),
        "FPGA_TDI": ("FPGA_TDI", "input"),
        "FPGA_TMS": ("FPGA_TMS", "input"),
        "FPGA_TDO": ("FPGA_TDO", "output"),
        # `output`, not `input` as fpga_io sees it: X1 and its series resistor
        # R409 are on *this* sheet, so the 33.33 MHz clock is generated here and
        # exported. The sheet consumes it too (ball M9), which is why R1 has two
        # labels of the same name -- but the direction a sheet pin advertises is
        # the direction the net leaves the sheet.
        "GCLK": ("FPGA_CLK33", "output"),
    },
    # fpga_ddr has no interface at all. Every net on R1's sheet is a *local*
    # label -- the DDR bus runs from unit 4 of the FPGA to the DRAM and stops
    # there, and the rails arrive as power symbols, which are global by name.
    # So this sheet gets zero sheet pins, which is also what the root already
    # has for it.
    "fpga_ddr": {},
    "power_mon": {
        # R1 called the housekeeping bus I2C1_*; R2 calls it *_AON because it
        # is the one bus that stays alive with every switched rail down.
        "I2C1_SCL": ("SCL_AON", "bidirectional"),
        "I2C1_SDA": ("SDA_AON", "bidirectional"),
        # U21's CRITICAL pin is an open-drain output on this net, so the sheet
        # both listens and drives -- see docs/epd-port.md §4.
        "EPD_PWR_EN": ("EPD_PWR_EN", "bidirectional"),
        "VBUS_MEA": ("VBUS_MEA", "output"),
        "VP_MEA": ("VP_MEA", "output"),
        "VN_MEA": ("VN_MEA", "output"),
        "VGH_MEA": ("VGH_MEA", "output"),
        "VGL_MEA": ("VGL_MEA", "output"),
    },
}

# --- 4. rail names, keyed by the power symbol's own #PWR reference --------
# Keyed by reference rather than by value because several instances share a
# value and only some of them move. docs/epd-port.md §3 has the channel table.
RAILS = {
    # R1 spreads the FPGA's decoupling across sheets, so five of the DDR bank's
    # VCCO capacitors are drawn on fpga_config rather than fpga_ddr. That rail is
    # 1.5 V in R2 (tools/patch_ddr_15v.py), so the symbol has to move with it --
    # caught by the netlist diff, which showed a stale `+1V35` net appearing with
    # 5 nodes. fpga_ddr carries the same name and will need the same treatment.
    "fpga_config": {"#PWR0259": "+1V5"},
    # The DDR bank itself. Five symbols carry the rail into VCCO_3, the VREF
    # divider and 16 decoupling caps; all five move together or the sheet ends
    # up with two rails that look the same and are not connected.
    "fpga_ddr": {r: "+1V5" for r in ("#PWR0439", "#PWR0442", "#PWR0137",
                                     "#PWR0139", "#PWR0144")},
    "power_mon": {
        "#PWR0182": "+5V_DCDC",        # was +1V8_DCDC  -- U22 ch1 in
        "#PWR0243": "+5V_SOM",         # was +1V8_VID   -- U22 ch1 out
        "#PWR0213": "+3V3_AON_DCDC",   # was +3V3_DCDC  -- U22 ch2 in
        "#PWR0250": "+3V3_AON",        # was +3V3_VID   -- U22 ch2 out
        "#PWR0245": "+VSYS",           # was +5V_DCDC   -- U22 ch3 in
        "#PWR0271": "+VSYS_FL",        # was +5V2_FL    -- U22 ch3 out
        "#PWR0229": "+3V3_AON",        # U21 VS/VPU
        "#PWR0179": "+3V3_AON",        # U22 VS/VPU
        "#PWR0181": "+3V3_AON",        # U27 VS/VPU
        "#PWR0196": "+3V3_AON",        # U22 A0 address strap
    },
}

# --- 5. signals to delete outright ---------------------------------------
# R1 wires a 12-signal parallel bus between the H750's FMC and the FPGA, but
# *no* .ucf in Caster assigns any of it -- the gateware has never used it. R2
# has no MCU-side parallel bus at all, so the labels and their stubs go and the
# freed bank-1 pins get no-connect flags, which is this project's convention for
# a spare pin (docs/mcu.md §3.2).
DROP = {
    "fpga_io": frozenset(("FMC_A16", "FMC_NE1", "FMC_NOE", "FMC_NWE",
                          *[f"FMC_D{i}" for i in range(8)])),
    # The FPD-Link/LVDS video input. R2 deletes the PTN3460 that drove it, so
    # these 14 balls have no source. They are dropped here *and* deconstrained
    # in Caster's constraint.ucf (owner's decision, 2026-08-12): left as
    # constrained-but-floating LVDS_33 inputs with DIFF_TERM enabled, seven
    # differential buffers would sit at an indeterminate common mode where they
    # can self-oscillate and draw current -- in the reading state, which is the
    # one number R2 exists to reduce. Removing the constraint removes the buffer.
    "fpga_config": frozenset(
        [f"LVDS_{h}_{l}{p}" for h in ("EVEN", "ODD") for l in "ABC" for p in "PN"]
        + ["LVDS_ODD_CKP", "LVDS_ODD_CKN"]),
}

# --- 6. spare pins R1 leaves bare ----------------------------------------
# R1's fpga_io has 24 unused balls but flags only 12 of them, so the other 12
# come across as `pin_not_connected`. docs/mcu.md §3.2's convention is that
# every spare carries a no-connect flag: ERC stays honest, and claiming the pin
# later is a matter of deleting the flag. Coordinates and pin names read off the
# ERC report after the first port run.
NO_CONNECT = {
    "fpga_io": (
        (114.30, 45.72),   # E13  IO_L1P_A25_1
        (114.30, 48.26),   # E12  IO_L1N_A24_VREF_1
        (114.30, 55.88),   # F12  IO_L30P_A21_M1RESET_1
        (114.30, 58.42),   # G11  IO_L30N_A20_M1A11_1
        (114.30, 66.04),   # F13  IO_L32P_A17_M1A8_1
        (114.30, 68.58),   # F14  IO_L32N_A16_M1A9_1
        (114.30, 99.06),   # H11  IO_L38N_A4_M1CLKN_1
        (114.30, 106.68),  # J11  IO_L40P_GCLK11_M1A5_1
        (114.30, 152.40),  # R15  IO_L49P_M1DQ10_1
        (114.30, 160.02),  # T15  IO_L50N_M1UDQSN_1
        (213.36, 119.38),  # F9   IO_L40P_0
        (213.36, 121.92),  # D9   IO_L40N_0
    ),
}

TITLE = "Glider-R2 / Specter mainboard"
NOTE = {
    "epd": "epd — panel connectors, ported from R1 pin-for-pin. See docs/epd-port.md.",
    "epd_power": "epd_power — EPD HV chain, ported unchanged from R1. See docs/epd-port.md.",
    "power_mon": "power_mon — 3x INA3221, ported from R1; three channels repurposed.",
    "fpga_io": "fpga_io — XC6SLX16 banks 0/1: EPD panel bus, DPI in. See docs/fpga.md.",
    "fpga_config": "fpga_config — XC6SLX16 bank 2, config and CSR SPI, 33.33 MHz clock. See docs/fpga.md.",
    # Keep these under ~84 characters: past that the title block's comment field
    # runs off its own box. fpga_config's 85-char line already sits exactly on
    # the right border.
    "fpga_ddr": "fpga_ddr — XC6SLX16 bank 3 (MCB3), 1 Gb DDR3L, core rails. See docs/fpga.md.",
}


def _block_end(text: str, start: int) -> int:
    """Index just past the balanced ')' that closes the block at `start`."""
    depth, j, in_str = 0, start, False
    while j < len(text):
        c = text[j]
        if c == '"' and text[j - 1] != "\\":
            in_str = not in_str
        elif not in_str:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return j + 1
        j += 1
    raise ValueError("unbalanced")


def each_block(text: str, token: str):
    """Yield (start, end) for every top-level `(token ...)` block."""
    for m in re.finditer(r"\n\t\(" + re.escape(token) + r"[\s\n]", text):
        s = text.index("(", m.start())
        yield s, _block_end(text, s)


def rewrite_rails(text: str, mapping: dict) -> str:
    if not mapping:
        return text
    out, hits = text, {}
    for s, e in reversed(list(each_block(out, "symbol"))):
        blk = out[s:e]
        m = re.search(r'\(property "Reference" "(#PWR[^"]*)"', blk)
        if not m or m.group(1) not in mapping:
            continue
        new = mapping[m.group(1)]
        blk2 = re.sub(r'(\(property "Value" ")[^"]*(")', rf"\g<1>{new}\g<2>",
                      blk, count=1)
        hits[m.group(1)] = new
        out = out[:s] + blk2 + out[e:]
    missing = set(mapping) - set(hits)
    if missing:
        raise KeyError(f"rail renames never matched: {sorted(missing)}")
    return out


def rewrite_labels(text: str, mapping: dict) -> str:
    """global_label -> hierarchical_label, renaming and reshaping."""
    out, seen = text, set()
    for s, e in reversed(list(each_block(out, "global_label"))):
        blk = out[s:e]
        name = re.match(r'\(global_label "([^"]+)"', blk).group(1)
        if name not in mapping:
            raise KeyError(f"no hierarchical mapping for global label {name!r}")
        new, shape = mapping[name]
        seen.add(name)
        blk = blk.replace(f'(global_label "{name}"',
                          f'(hierarchical_label "{new}"', 1)
        blk = re.sub(r"\(shape \w+\)", f"({'shape'} {shape})", blk, count=1)
        # Intersheetrefs is a global-label-only property; a hierarchical label
        # that carries it will not load.
        for ps, pe in reversed(list(_props(blk, "Intersheetrefs"))):
            blk = blk[:ps].rstrip("\n\t") + "\n" + blk[pe:].lstrip("\n")
        out = out[:s] + blk + out[e:]
    unused = set(mapping) - seen
    if unused:
        raise KeyError(f"mapping has names the sheet never used: {sorted(unused)}")
    return out


def _wires(text: str):
    """Yield (start, end, x1, y1, x2, y2) for every two-point wire block."""
    for s, e in each_block(text, "wire"):
        m = re.search(r"\(pts\s*\n\s*\(xy ([-\d.]+) ([-\d.]+)\) "
                      r"\(xy ([-\d.]+) ([-\d.]+)\)", text[s:e])
        if m:
            yield (s, e, *(float(v) for v in m.groups()))


def drop_labels(text: str, names) -> str:
    """Delete each named global label and its stub wire; no-connect the pin.

    On `fpga_io` every dropped label sits at one end of exactly one 5.08 mm wire
    whose far end is the FPGA pin.  The label and that wire go, and a
    `no_connect` takes the pin's place so the pin stays accounted for in ERC
    instead of becoming a silent `pin_not_connected`.

    If a label turns out to be served by anything other than exactly one wire,
    this raises rather than guessing which segment to remove -- the whole point
    of a port is that no edit is left to inference.
    """
    if not names:
        return text

    def near(a, b):
        return abs(a - b) < 0.01

    spans, opens, seen = [], [], set()
    wires = list(_wires(text))
    for s, e in each_block(text, "global_label"):
        blk = text[s:e]
        name = re.match(r'\(global_label "([^"]+)"', blk).group(1)
        if name not in names:
            continue
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+) (\d+)\)", blk)
        lx, ly = float(at.group(1)), float(at.group(2))
        hits = [w for w in wires
                if (near(w[2], lx) and near(w[3], ly))
                or (near(w[4], lx) and near(w[5], ly))]
        if len(hits) != 1:
            raise AssertionError(
                f"{name} at ({lx},{ly}) is served by {len(hits)} wires, not 1")
        w = hits[0]
        far = (w[4], w[5]) if near(w[2], lx) and near(w[3], ly) else (w[2], w[3])
        spans += [(s, e), (w[0], w[1])]
        opens.append(far)
        seen.add(name)

    missing = set(names) - seen
    if missing:
        raise KeyError(f"labels marked for deletion never appeared: {sorted(missing)}")

    for s, e in sorted(spans, key=lambda p: -p[0]):
        text = text[:s] + text[e:]

    return add_no_connects(text, opens)


def add_no_connects(text: str, points) -> str:
    """Append a `no_connect` flag at each (x, y)."""
    if not points:
        return text
    assert text.endswith(")\n")
    add = "".join(
        f'\t(no_connect\n\t\t(at {x} {y})\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n'
        for x, y in points)
    return text[:-2] + add + ")\n"


def _props(blk: str, name: str):
    for m in re.finditer(r'\n\t*\(property "' + re.escape(name) + r'"[\s\n]', blk):
        s = m.start() + len(m.group(0)) - len(m.group(0).lstrip("\n"))
        s = blk.index("(property", m.start())
        yield s, _block_end(blk, s)


KI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/share/kicad/symbols"
KICAD_CLI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/bin/kicad-cli"


def _pin_geometry(block: str):
    return sorted(re.findall(
        r'\(pin \w+ \w+\s*\n\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)'
        r'[\s\S]*?\(number "([^"]+)"', block))


def refresh_lib_symbols(text: str) -> tuple[str, int]:
    """Replace embedded stock-symbol definitions with the installed ones.

    Skips any symbol whose pins moved between KiCad 8 and 10, which would
    silently disconnect wires, and any derived symbol, whose geometry lives in
    a parent and so has nothing local to compare.
    """
    lib_start = text.index("(lib_symbols")
    lib_end = _block_end(text, lib_start)
    body, n = text[lib_start:lib_end], 0

    spans = []
    for m in re.finditer(r'\n\t\t\(symbol "([^":]+):([^"]+)"[\s\n]', body):
        s0 = body.index("(", m.start())
        spans.append((s0, _block_end(body, s0), m.group(1), m.group(2)))

    for s0, e0, lib, name in reversed(spans):
        src = KI / f"{lib}.kicad_symdir" / f"{name}.kicad_sym"
        if not src.exists():                      # r2: and anything we own
            continue
        new = _extract_symbol_block(src.read_text(), name)
        if new is None or "(extends " in new:
            continue
        old = body[s0:e0]
        if _pin_geometry(old) != _pin_geometry(new):
            print(f"  SKIP {lib}:{name} -- pins moved between KiCad 8 and 10; "
                  "keeping R1's definition so the wires stay attached")
            continue
        # a .kicad_sym indents its symbol body one tab; inside lib_symbols it
        # sits two tabs deep, and the lib_id carries the library prefix.
        new = new.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
        lines = new.splitlines()
        new = lines[0] + "".join("\n\t" + ln if ln else "\n" for ln in lines[1:])
        if new != old:
            body = body[:s0] + new + body[e0:]
            n += 1
    return text[:lib_start] + body + text[lib_end:], n


def port(sheet: str, root_uuid: str, sheet_uuid: str) -> str:
    text = (R1 / f"{sheet}.kicad_sch").read_text()

    for old, new in RENAMES[sheet].items():
        for pat, rep in ((f'(property "Reference" "{old}"',
                          f'(property "Reference" "{new}"'),
                         (f'(reference "{old}")', f'(reference "{new}")')):
            if pat not in text:
                raise KeyError(f"{sheet}: {old} not found ({pat})")
            text = text.replace(pat, rep)

    for old, new in LIB_REMAP.items():
        text = text.replace(f'(lib_id "{old}")', f'(lib_id "{new}")')
        # Only the top-level lib_symbols entry is prefixed; its unit
        # sub-symbols ("GND_0_1") are not, and must be left alone.
        text = text.replace(f'(symbol "{old}"', f'(symbol "{new}"')

    text = rewrite_rails(text, RAILS.get(sheet, {}))
    # drop before rewriting: rewrite_labels refuses to leave any global label
    # unmapped, so anything being deleted has to be gone by the time it runs.
    text = drop_labels(text, DROP.get(sheet, frozenset()))
    text = add_no_connects(text, NO_CONNECT.get(sheet, ()))
    text = rewrite_labels(text, HIER[sheet])

    # project identity: every symbol's instance path moves under r2's root
    text = re.sub(r'\(project "pcb"', '(project "r2"', text)
    text = re.sub(r'\(path "/[0-9a-f-]{36}/[0-9a-f-]{36}"',
                  f'(path "/{root_uuid}/{sheet_uuid}"', text)

    if sheet in PAPER:
        text, n = re.subn(r'\(paper "[^"]*"\)', f'(paper "{PAPER[sheet]}")',
                          text, count=1)
        assert n == 1, f"{sheet}: no (paper ...) to resize"

    text = re.sub(r'\(title "[^"]*"\)', f'(title "{TITLE}")', text, count=1)
    text = re.sub(r'\(rev "[^"]*"\)', '(rev "A")', text, count=1)
    text = re.sub(r'\(date "[^"]*"\)', '(date "2026-08-07")', text, count=1)
    # keep the Modos copyright line: this is their design, carried over
    text = re.sub(r'(\(company "[^"]*"\))',
                  r'\1\n\t\t(comment 1 "' + NOTE[sheet] + '")'
                  r'\n\t\t(comment 2 "Ported from R1 pcb/mainboard/ by '
                  r'tools/port_r1.py. R1 is read-only.")',
                  text, count=1)
    return text


# Sheets that have been ported and committed, and then edited by hand or by a
# patch script. Re-porting one would silently discard everything since --
# power_mon carries the 1.5 V rail rename from tools/patch_ddr_15v.py, and
# fpga_config carries the whole config NOR from tools/patch_fpga_config_nor.py.
FROZEN = frozenset(("epd", "epd_power", "power_mon", "fpga_io", "fpga_config"))


def main():
    names = sys.argv[1:]
    if not names:
        sys.exit(f"usage: port_r1.py <sheet>...   (portable: "
                 f"{', '.join(sorted(set(HIER) ))})")
    for name in names:
        if name in FROZEN and "--force" not in sys.argv:
            sys.exit(f"refusing to re-port {name!r}: it is reviewed and "
                     f"committed, and re-porting would discard later edits. "
                     f"Pass --force only if that is genuinely what you want.")
    names = [n for n in names if not n.startswith("--")]

    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    for name in names:
        out = PROJ / f"{name}.kicad_sch"
        out.write_text(port(name, root_uuid, sheets[name]))
        # The symbol refresh injects KiCad 10 syntax, so the file has to be in
        # the KiCad 10 format first -- upgrade, then refresh.
        subprocess.run([str(KICAD_CLI), "sch", "upgrade", str(out)],
                       check=True, capture_output=True)
        text, n = refresh_lib_symbols(out.read_text())
        out.write_text(text)
        print(f"wrote {out}  (refreshed {n} stock symbol definitions)")

    from sheet_pins import set_sheet_pins
    for name in names:
        pins = sorted({v for v in HIER[name].values()})
        set_sheet_pins(PROJ / "r2.kicad_sch", name, pins)


if __name__ == "__main__":
    main()
