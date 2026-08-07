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
}

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

TITLE = "Glider-R2 / Specter mainboard"
NOTE = {
    "epd": "epd — panel connectors, ported from R1 pin-for-pin. See docs/epd-port.md.",
    "epd_power": "epd_power — EPD HV chain, ported unchanged from R1. See docs/epd-port.md.",
    "power_mon": "power_mon — 3x INA3221, ported from R1; three channels repurposed.",
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
    text = rewrite_labels(text, HIER[sheet])

    # project identity: every symbol's instance path moves under r2's root
    text = re.sub(r'\(project "pcb"', '(project "r2"', text)
    text = re.sub(r'\(path "/[0-9a-f-]{36}/[0-9a-f-]{36}"',
                  f'(path "/{root_uuid}/{sheet_uuid}"', text)

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


def main():
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    for name in ("epd", "epd_power", "power_mon"):
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
    for name in ("epd", "epd_power", "power_mon"):
        pins = sorted({v for v in HIER[name].values()})
        set_sheet_pins(PROJ / "r2.kicad_sch", name, pins)


if __name__ == "__main__":
    main()
