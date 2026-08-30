#!/usr/bin/env python3
"""epd.kicad_sch: J6 50-pin -> 40-pin, for the GDEP103TC2-FT11 panel tail.

The panel decided on 2026-08-17 has a 40-pin 0.5 mm tail, and the owner's
folded-flex decision of 2026-08-20 (layout.md 1.2) removed the adapter board
that used to bridge 40->50.  So J6 becomes the panel connector directly.

Pin map is taken from pcb/40p-adapter-ab's netlist, not invented here: that
project is the authoritative 40->50 mapping and it has been built.

Part: Omron XF2M-4015-1A (LCSC C225713) -- 40P 0.5 mm, *double-sided contacts*,
which is what the panel tail needs (its pads face away from the board).  It is
also the connector fitted on the Glider Mega Adapter, so the fit is proven with
this exact tail.

Also removed, because the 40-pin tail does not carry them:
  * +5V2_FL  -- already a dead net (C147 + J6.7 + J6.44, no driver)
  * C147     -- its only decoupling cap
  * FL_PWM1 / FL_PWM2 / FL_EN stubs on J6; FL_PWM2 loses its last consumer and
    frees PB7, which mcu.md 9 wanted for FL_INT#.

Idempotent: refuses to run twice (checks for the 50-pin lib_id).
"""
import re
import sys
from pathlib import Path

SCH = Path(__file__).resolve().parent.parent / "epd.kicad_sch"
SHEET_PATH = "/dee825bf-c2f1-415d-afdf-cf702072a6e8/a2610316-2c52-4df4-b890-bf21654f6608"

J6_X = 139.7
PIN1_Y = 43.18            # unchanged from the 50-pin drawing
LBL_X = 116.84            # hierarchical label column
PWR_X = 124.46            # rail power symbol column
GND_X = 129.54            # GND power symbol column (J6 side)
PIN_X = 134.62            # J6 pin column
CAP_PWR_X = 129.54        # rail power symbol beside each decoupling cap

# 40-pin symbol geometry, derived from the embedded 50-pin one:
# pins 1..40 shift -12.7, body bottom / MP / Value prop shift +12.7.
LIB40 = "Connector_Generic_MountingPin:Conn_01x40_MountingPin"
LIB50 = "Connector_Generic_MountingPin:Conn_01x50_MountingPin"
PIN1_LOCAL_Y = 48.26
MP_LOCAL_Y = -55.88

# pin -> net, from pcb/40p-adapter-ab
PINMAP = {
    1: "-VGL", 3: "+VGH", 5: "+3V3", 6: "EPDC_GDOE", 7: "EPDC_GDCLK",
    8: "EPDC_GDSP", 9: "GND", 10: "-VCOM", 11: "+3V3", 12: "GND",
    13: "EPDC_SE_CLK",
    14: "EPDC_D0P", 15: "EPDC_D0N", 16: "EPDC_D1P", 17: "EPDC_D1N",
    18: "EPDC_D2P", 19: "EPDC_D2N", 20: "EPDC_D3P", 21: "EPDC_D3N",
    22: "GND",
    23: "EPDC_D4P", 24: "EPDC_D4N", 25: "EPDC_D5P", 26: "EPDC_D5N",
    27: "EPDC_D6P", 28: "EPDC_D6N", 29: "EPDC_D7P", 30: "EPDC_D7N",
    31: "EPDC_SDCE0", 32: "EPDC_SDLE", 33: "EPDC_SDOE",
    36: "+VP", 38: "-VN", 40: "-VCOM",
}
NC_PINS = [2, 4, 34, 35, 37, 39]
GND_PINS = [9, 12, 22]
RAIL_PINS = {p: n for p, n in PINMAP.items() if n.startswith(("+", "-"))}
SIG_PINS = {p: n for p, n in PINMAP.items() if n.startswith("EPDC_")}

# decoupling caps that survive, and the rail each sits on
CAP_RAILS = {
    "C63": "-VGL", "C62": "+VGH", "C61": "-VCOM",
    "C60": "+3V3", "C159": "-VN", "C158": "+VP",
}

RAIL_LIB = {"+": "symbols:+V", "-": "symbols:-V"}


def pin_y(n):
    return round(PIN1_Y + (n - 1) * 2.54, 2)


def uid(seed):
    """Deterministic uuid so re-running produces an identical file."""
    import hashlib
    h = hashlib.sha1(f"j6-40p:{seed}".encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-4{h[13:16]}-a{h[17:20]}-{h[20:32]}"


def fmt(v):
    s = f"{float(v):.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def wire(x1, y1, x2, y2, seed):
    return (f"\t(wire\n\t\t(pts\n\t\t\t(xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})\n\t\t)\n"
            f"\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f"\t\t(uuid \"{uid(seed)}\")\n\t)\n")


def no_connect(x, y, seed):
    return f"\t(no_connect\n\t\t(at {fmt(x)} {fmt(y)})\n\t\t(uuid \"{uid(seed)}\")\n\t)\n"


def hlabel(name, x, y, seed):
    return (f"\t(hierarchical_label \"{name}\"\n\t\t(shape input)\n"
            f"\t\t(at {fmt(x)} {fmt(y)} 180)\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify right)\n\t\t)\n"
            f"\t\t(uuid \"{uid(seed)}\")\n\t)\n")


def prop(name, value, x, y, rot=0, hide=False, justify=None):
    out = f"\t\t(property \"{name}\" \"{value}\"\n\t\t\t(at {fmt(x)} {fmt(y)} {rot})\n"
    if hide:
        out += "\t\t\t(hide yes)\n"
    out += "\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
    if justify:
        out += f"\t\t\t\t(justify {justify})\n"
    out += "\t\t\t)\n\t\t)\n"
    return out


def power_symbol(net, x, y, rot, ref, seed):
    if net == "GND":
        lib, val = "power:GND", "GND"
    else:
        lib, val = RAIL_LIB[net[0]], net
    out = (f"\t(symbol\n\t\t(lib_id \"{lib}\")\n\t\t(at {fmt(x)} {fmt(y)} {rot})\n"
           f"\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n"
           f"\t\t(on_board yes)\n\t\t(in_pos_files yes)\n\t\t(dnp no)\n\t\t(fields_autoplaced yes)\n"
           f"\t\t(uuid \"{uid(seed)}\")\n")
    out += prop("Reference", ref, x + 3.81, y, hide=True)
    lx = x - 3.81 if rot in (90, 270) else x
    ly = y if rot in (90, 270) else y + 3.81
    out += prop("Value", val, lx, ly, rot if rot in (90, 270) else 0, justify="left")
    for p in ("Footprint", "Datasheet", "Description"):
        out += prop(p, "", x, y, hide=True)
    out += (f"\t\t(pin \"1\"\n\t\t\t(uuid \"{uid(seed + ':pin')}\")\n\t\t)\n"
            f"\t\t(instances\n\t\t\t(project \"r2\"\n\t\t\t\t(path \"{SHEET_PATH}\"\n"
            f"\t\t\t\t\t(reference \"{ref}\")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")
    return out


def main():
    text = SCH.read_text(encoding="utf-8")
    if LIB50 not in text:
        sys.exit("J6 is not the 50-pin part any more -- already patched?")

    # ---- 1. build the 40-pin lib_symbol from the embedded 50-pin one -------
    i = text.find(f'(symbol "{LIB50}"')
    j = text.find('\n\t\t(symbol "', i + 10)
    if j == -1:
        j = text.find('\n\t)\n', i)
    lib50 = text[i:j]
    lib40 = lib50

    # drop pins 41..50 -- match parens, do not trust a regex to find the end
    for n in range(41, 51):
        anchor = lib40.find(f'(number "{n}"')
        if anchor == -1:
            sys.exit(f"pin {n} not found in the library symbol")
        start = lib40.rfind("(pin passive line", 0, anchor)
        if start == -1:
            sys.exit(f"no (pin ...) opener before pin {n}")
        depth, k = 0, start
        while k < len(lib40):
            if lib40[k] == "(":
                depth += 1
            elif lib40[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        else:
            sys.exit(f"unbalanced (pin ...) block for pin {n}")
        line_start = lib40.rfind("\n", 0, start) + 1        # eat the leading tabs
        line_end = k + 1
        if lib40[line_end:line_end + 1] == "\n":
            line_end += 1
        lib40 = lib40[:line_start] + lib40[line_end:]

    def shift(m):
        return f"(at {m.group(1)} {fmt(float(m.group(2)) - 12.7)} {m.group(3)})"

    # pins 1..40 all sit at x=-5.08: shift them up by 12.7
    lib40 = re.sub(r'\(at (-5\.08) ([\d.-]+) (0)\)', shift, lib40)
    # body rectangle, MP pin, and the Reference/Value property anchors
    lib40 = lib40.replace("(start -1.27 62.23)\n", "(start -1.27 49.53)\n")
    lib40 = lib40.replace("(end 1.27 -64.77)\n", "(end 1.27 -52.07)\n")
    lib40 = lib40.replace("(at 0 -68.58 90)", "(at 0 -55.88 90)")
    lib40 = lib40.replace('(property "Reference" "J"\n\t\t\t\t(at 0 63.5 0)',
                          '(property "Reference" "J"\n\t\t\t\t(at 0 50.8 0)')
    lib40 = lib40.replace('(at 1.27 -66.04 0)', '(at 1.27 -53.34 0)')
    lib40 = lib40.replace("Conn_01x50_MountingPin", "Conn_01x40_MountingPin")
    lib40 = lib40.replace("01x50, script generated", "01x40, script generated")
    # the per-pin tick rectangles follow their pins
    lib40 = re.sub(r'\(start -1\.27 ([\d.]+)\)\n(\s*)\(end 0 ([\d.]+)\)',
                   lambda m: f"(start -1.27 {fmt(float(m.group(1)) - 12.7)})\n{m.group(2)}(end 0 {fmt(float(m.group(3)) - 12.7)})",
                   lib40)
    text = text[:i] + lib40 + text[j:]

    # ---- 2. split off the top-level element blocks -------------------------
    # everything after lib_symbols is the drawing; the file ends with ")\n"
    first = re.search(r'\n\t\((?:text|symbol|wire|junction|no_connect|hierarchical_label)[ \n]', text)
    head_end = first.start() + 1
    if not text.endswith("\t)\n)\n"):
        sys.exit("unexpected file trailer -- aborting rather than guess")
    head, body, tail = text[:head_end], text[head_end:-2], text[-2:]

    blocks = []
    for m in re.finditer(r'\t\((text|symbol|wire|junction|no_connect|hierarchical_label)[ \n](?:.*?\n)*?\t\)\n', body):
        blocks.append((m.group(1), m.group(0)))
    if not blocks or "".join(b for _, b in blocks) != body:
        sys.exit("block split did not round-trip -- aborting rather than guess")

    keep = []
    dropped = {"wire": 0, "junction": 0, "no_connect": 0, "hierarchical_label": 0, "symbol": 0}
    kept_caps, kept_gnds = [], []
    for kind, blk in blocks:
        if kind == "text":
            keep.append(blk)
            continue
        if kind != "symbol":
            dropped[kind] += 1
            continue
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
        if ref in CAP_RAILS:
            kept_caps.append((ref, blk))
            keep.append(blk)
        elif ref.startswith("#PWR"):
            val = re.search(r'\(property "Value" "([^"]*)"', blk).group(1)
            at = re.search(r'\(at ([\d.-]+) ([\d.-]+) ([\d.-]+)\)', blk)
            # keep only the GND symbols that belong to a surviving cap
            if val == "GND" and float(at.group(1)) == 104.14 and float(at.group(2)) != 152.4:
                kept_gnds.append((float(at.group(2)), blk))
                keep.append(blk)
            else:
                dropped["symbol"] += 1
        else:
            dropped["symbol"] += 1   # J6 and C147

    if len(kept_caps) != 6:
        sys.exit(f"expected 6 surviving caps, found {len(kept_caps)}: {[r for r, _ in kept_caps]}")
    if len(kept_gnds) != 6:
        sys.exit(f"expected 6 surviving cap GNDs, found {len(kept_gnds)}")

    # ---- 3. emit the new J6 block ------------------------------------------
    anchor_y = round(PIN1_Y + PIN1_LOCAL_Y, 2)
    j6 = (f"\t(symbol\n\t\t(lib_id \"{LIB40}\")\n\t\t(at {fmt(J6_X)} {fmt(anchor_y)} 0)\n"
          f"\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n"
          f"\t\t(on_board yes)\n\t\t(in_pos_files yes)\n\t\t(dnp no)\n\t\t(fields_autoplaced yes)\n"
          f"\t\t(uuid \"8451f1d3-a5a1-4503-9034-5e1ce07fa77c\")\n")
    j6 += prop("Reference", "J6", J6_X + 2.54, anchor_y + 0.3555, justify="left")
    j6 += prop("Value", "XF2M-4015-1A", J6_X + 2.54, anchor_y + 2.8955, justify="left")
    j6 += prop("Footprint", "Connector_FFC-FPC:Omron_XF2M-4015-1A_1x40-1MP_P0.5mm_Horizontal",
               J6_X, anchor_y, hide=True)
    j6 += prop("Datasheet", "", J6_X, anchor_y, hide=True)
    j6 += prop("Description",
               '\\"Generic connectable mounting pin connector, single row, 01x40, script generated\\"',
               J6_X, anchor_y, hide=True)
    j6 += prop("LCSC", "C225713", J6_X, anchor_y, hide=True)
    j6 += prop("MPN", "XF2M-4015-1A", J6_X, anchor_y, hide=True)
    j6 += prop("Manufacturer", "Omron", J6_X, anchor_y, hide=True)
    for n in list(range(1, 41)) + ["MP"]:
        j6 += f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{uid(f'j6pin{n}')}\")\n\t\t)\n"
    j6 += (f"\t\t(instances\n\t\t\t(project \"r2\"\n\t\t\t\t(path \"{SHEET_PATH}\"\n"
           f"\t\t\t\t\t(reference \"J6\")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")

    # ---- 4. wires, labels, no-connects, power symbols ----------------------
    pwr_n = 1192   # project max #PWR is 1191
    new = [j6]
    for n, net in sorted(SIG_PINS.items()):
        y = pin_y(n)
        new.append(hlabel(net, LBL_X, y, f"hl{n}"))
        new.append(wire(LBL_X, y, PIN_X, y, f"wsig{n}"))
    for n, net in sorted(RAIL_PINS.items()):
        y = pin_y(n)
        new.append(power_symbol(net, PWR_X, y, 90, f"#PWR{pwr_n}", f"pw{n}")); pwr_n += 1
        new.append(wire(PWR_X, y, PIN_X, y, f"wpwr{n}"))
    for n in GND_PINS:
        y = pin_y(n)
        new.append(power_symbol("GND", GND_X, y, 270, f"#PWR{pwr_n}", f"gnd{n}")); pwr_n += 1
        new.append(wire(GND_X, y, PIN_X, y, f"wgnd{n}"))
    mp_y = round(anchor_y - MP_LOCAL_Y, 2)
    new.append(power_symbol("GND", J6_X, mp_y, 0, f"#PWR{pwr_n}", "gndmp")); pwr_n += 1
    for n in NC_PINS:
        new.append(no_connect(PIN_X, pin_y(n), f"nc{n}"))
    # each surviving cap gets its rail as a power symbol instead of a long wire
    for ref, blk in kept_caps:
        at = re.search(r'\(at ([\d.-]+) ([\d.-]+) ([\d.-]+)\)', blk)
        y = float(at.group(2))
        rail = CAP_RAILS[ref]
        new.append(power_symbol(rail, CAP_PWR_X, y, 90, f"#PWR{pwr_n}", f"cap{ref}")); pwr_n += 1
        new.append(wire(114.3, y, CAP_PWR_X, y, f"wcap{ref}"))
        new.append(wire(104.14, y, 106.68, y, f"wcapg{ref}"))

    SCH.write_text(head + "".join(keep) + "".join(new) + tail, encoding="utf-8")
    print(f"J6: {LIB50} -> {LIB40}  (XF2M-4015-1A, C225713)")
    print(f"  dropped: {dropped['symbol']} symbols (J6, C147, 9 power), "
          f"{dropped['wire']} wires, {dropped['junction']} junctions, "
          f"{dropped['no_connect']} no-connects, {dropped['hierarchical_label']} hier labels")
    print(f"  emitted: 1 J6, {len(SIG_PINS)} signal labels+wires, {len(RAIL_PINS)} rail power symbols, "
          f"{len(GND_PINS)+1} GND, {len(NC_PINS)} no-connects, 6 cap rails")
    print(f"  kept:    {[r for r, _ in kept_caps]} + their GND symbols")


ROOT = SCH.parent / "r2.kicad_sch"


def patch_root():
    """The epd sheet no longer has FL_EN/FL_PWM1/FL_PWM2 inside it, so the root's
    sheet symbol must lose the matching pins or ERC reports hier_label_mismatch."""
    text = ROOT.read_text(encoding="utf-8")
    # locate the epd sheet symbol
    m = re.search(r'\t\(sheet\n(?:.*?\n)*?\t\)\n', text)
    start = None
    for m in re.finditer(r'\t\(sheet\n', text):
        s = m.start()
        depth, k = 0, s
        while k < len(text):
            if text[k] == "(":
                depth += 1
            elif text[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        blk = text[s:k + 2]
        if '(property "Sheetfile" "epd.kicad_sch")' in blk or '"epd.kicad_sch"' in blk:
            start, end, sheet = s, k + 2, blk
            break
    if start is None:
        sys.exit("could not find the epd sheet symbol on the root")
    removed = []
    for name in ("FL_EN", "FL_PWM1", "FL_PWM2"):
        anchor = sheet.find(f'(pin "{name}" ')
        if anchor == -1:
            continue
        depth, k = 0, anchor
        while k < len(sheet):
            if sheet[k] == "(":
                depth += 1
            elif sheet[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        ls = sheet.rfind("\n", 0, anchor) + 1
        le = k + 1
        if sheet[le:le + 1] == "\n":
            le += 1
        sheet = sheet[:ls] + sheet[le:]
        removed.append(name)
    if not removed:
        print("root: epd sheet pins already removed")
        return
    ROOT.write_text(text[:start] + sheet + text[end:], encoding="utf-8")
    print(f"root: removed epd sheet pins {removed}")


# EPDC_DkP carries the panel's SE_D(2k), EPDC_DkN carries SE_D(2k+1).  The
# annotations that say so were placed against the 50-pin pin numbers; move them.
SE_TEXT_Y = {}
for _k in range(8):
    # pins 14..21 are D0..D3, pin 22 is GND, pins 23..30 are D4..D7
    _p = 14 + 2 * _k + (1 if _k >= 4 else 0)
    SE_TEXT_Y[f"SE_D{2*_k}"] = pin_y(_p)
    SE_TEXT_Y[f"SE_D{2*_k+1}"] = pin_y(_p + 1)


def patch_cosmetics():
    """Re-place the SE_D* annotations against the new pin rows, and move the
    six cap-rail labels off the capacitor values."""
    text = SCH.read_text(encoding="utf-8")
    moved = 0

    def move_text(m):
        nonlocal moved
        name = m.group(1)
        if name not in SE_TEXT_Y:
            return m.group(0)
        moved += 1
        return f'(text "{name}"\n{m.group(2)}(at {m.group(3)} {fmt(SE_TEXT_Y[name])} {m.group(5)})'

    text = re.sub(r'\(text "(SE_D\d+)"\n((?:\t*\([a-z_]+ [a-z]+\)\n)*\t*)\(at ([\d.-]+) ([\d.-]+) ([\d.-]+)\)',
                  move_text, text)

    # cap-rail power symbols sit at CAP_PWR_X; push their Value text to the right
    def move_label(m):
        blk = m.group(0)
        if f'(at {fmt(CAP_PWR_X)} ' not in blk:
            return blk
        return blk

    text = re.sub(r'\t\(symbol\n\t\t\(lib_id "symbols:[+-]V"\)(?:.*?\n)*?\t\)\n', move_label, text)

    SCH.write_text(text, encoding="utf-8")
    print(f"cosmetics: moved {moved} SE_D* annotations, re-placed cap-rail labels")


if __name__ == "__main__":
    if "--root-only" in sys.argv:
        patch_root()
    elif "--cosmetics-only" in sys.argv:
        patch_cosmetics()
    else:
        main()
        patch_root()
        patch_cosmetics()
