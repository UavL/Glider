#!/usr/bin/env python3
"""Add the host-only USB1 port to io_expansion, som and mcu.

Owner's decision 2026-08-30: a second USB port, host only, on the SoM's unused
USB1.  Closes NOTES-R2-review-round-2.md D-3.

Design, all of it from datasheets in ../datasheets/:

  J28  TYPE-C-31-M-12 (C165948) -- same receptacle as J1, no new BOM line.
  R52/R53  56k Rp from CC1/CC2 to +5V.  A Type-C source advertising Default USB
       Power (500 mA).  Rp goes to +5V and not to the switched output so the port
       advertises before VBUS; with nothing plugged in CC floats, so it leaks
       nothing.
  U56  TPS2553DBVR (C55266), SOT-23-6, EN active high -- driven straight from the
       SoM's X_USB1_DRVVBUS.  Chosen over a plain load switch because the +5V rail
       is shared with the SoM: tIOS = 2 us to a short (datasheet 7.5) is what stops
       a bad stick browning out the module.
  R54  49.9k on ILIM -> IOS = 475 / 520 / 565 mA over -40..125 C (datasheet 7.5,
       "Current-limit threshold ... RILIM = 49.9 kohm").  power.md 8.1's budget
       moves from 1.3 A to 1.865 A worst case; see the note added there.
  R55  100k pull-up on the open-drain FAULT, reported to the MCU on PB7 -- the pin
       freed when FL_PWM2 was retired (mcu.md 16.1).
  U57  USBLC6-2SC6 (C7519), same ESD part and same wiring style as U3 on battery.
  C519 100nF at IN (datasheet pin table: "0.1 uF or greater ... as close as
       possible"); C520 22uF + C521 100nF on the switched output.

Idempotent: refuses to run twice.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

IOX, SOM, MCU, ROOT = (HERE / n for n in
                       ("io_expansion.kicad_sch", "som.kicad_sch", "mcu.kicad_sch", "r2.kicad_sch"))
SYMLIB = HERE / "r2.kicad_sym"
IOX_PATH = "/dee825bf-c2f1-415d-afdf-cf702072a6e8/bfb4a282-c959-4a7b-92d0-a4a500453c0c"

PWR_N = 1220          # the J6 patch used 1192..1209; start clear of it


def uid(seed: str) -> str:
    h = hashlib.sha1(f"usb-host:{seed}".encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-4{h[13:16]}-a{h[17:20]}-{h[20:32]}"


def fmt(v) -> str:
    s = f"{float(v):.4f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def wire(x1, y1, x2, y2, seed):
    return (f"\t(wire\n\t\t(pts\n\t\t\t(xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})\n\t\t)\n"
            f"\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f"\t\t(uuid \"{uid(seed)}\")\n\t)\n")


def junction(x, y, seed):
    return (f"\t(junction\n\t\t(at {fmt(x)} {fmt(y)})\n\t\t(diameter 0)\n"
            f"\t\t(color 0 0 0 0)\n\t\t(uuid \"{uid(seed)}\")\n\t)\n")


def no_connect(x, y, seed):
    return f"\t(no_connect\n\t\t(at {fmt(x)} {fmt(y)})\n\t\t(uuid \"{uid(seed)}\")\n\t)\n"


def label(name, x, y, rot, seed, hier=False, shape="bidirectional"):
    kind = "hierarchical_label" if hier else "label"
    shp = f"\t\t(shape {shape})\n" if hier else ""
    just = "right" if rot == 180 else "left"
    return (f"\t({kind} \"{name}\"\n{shp}\t\t(at {fmt(x)} {fmt(y)} {rot})\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify {just})\n\t\t)\n"
            f"\t\t(uuid \"{uid(seed)}\")\n\t)\n")


def prop(name, value, x, y, rot=0, hide=False, justify=None):
    out = f"\t\t(property \"{name}\" \"{value}\"\n\t\t\t(at {fmt(x)} {fmt(y)} {rot})\n"
    if hide:
        out += "\t\t\t(hide yes)\n"
    out += ("\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n\t\t\t(effects\n"
            "\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n")
    if justify:
        out += f"\t\t\t\t(justify {justify})\n"
    out += "\t\t\t)\n\t\t)\n"
    return out


def symbol(lib, ref, value, x, y, rot, pins, seed, props=(), path=IOX_PATH, mirror=None):
    global PWR_N
    out = (f"\t(symbol\n\t\t(lib_id \"{lib}\")\n\t\t(at {fmt(x)} {fmt(y)} {rot})\n")
    if mirror:
        out += f"\t\t(mirror {mirror})\n"
    out += (f"\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n"
            f"\t\t(on_board yes)\n\t\t(in_pos_files yes)\n\t\t(dnp no)\n\t\t(fields_autoplaced yes)\n"
            f"\t\t(uuid \"{uid(seed)}\")\n")
    hidden = ref.startswith("#PWR")
    out += prop("Reference", ref, x + 2.54, y - 1.27, hide=hidden, justify="left")
    out += prop("Value", value, x + 2.54, y + 1.27, justify="left")
    for pname, pval in props:
        out += prop(pname, pval, x, y, hide=True)
    for p in pins:
        out += f"\t\t(pin \"{p}\"\n\t\t\t(uuid \"{uid(seed + ':' + p)}\")\n\t\t)\n"
    out += (f"\t\t(instances\n\t\t\t(project \"r2\"\n\t\t\t\t(path \"{path}\"\n"
            f"\t\t\t\t\t(reference \"{ref}\")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")
    return out


def power(net, x, y, rot, seed):
    global PWR_N
    lib = "power:GND" if net == "GND" else ("symbols:+V" if net[0] == "+" else "symbols:-V")
    ref = f"#PWR{PWR_N}"
    PWR_N += 1
    return symbol(lib, ref, net, x, y, rot, ["1"], seed)


TPS2553_SYM = '''\t(symbol "TPS2553DBV"
\t\t(pin_names
\t\t\t(offset 1.016)
\t\t)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(in_pos_files yes)
\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t(property "Reference" "U"
\t\t\t(at -10.16 10.16 0)
\t\t\t(show_name no)
\t\t\t(do_not_autoplace no)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(justify left bottom)
\t\t\t)
\t\t)
\t\t(property "Value" "TPS2553DBV"
\t\t\t(at -10.16 -10.16 0)
\t\t\t(show_name no)
\t\t\t(do_not_autoplace no)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(justify left bottom)
\t\t\t)
\t\t)
\t\t(property "Footprint" "Package_TO_SOT_SMD:SOT-23-6"
\t\t\t(at 0 0 0)
\t\t\t(show_name no)
\t\t\t(do_not_autoplace no)
\t\t\t(hide yes)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps2553.pdf"
\t\t\t(at 0 0 0)
\t\t\t(show_name no)
\t\t\t(do_not_autoplace no)
\t\t\t(hide yes)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Description" "Adjustable current-limited power-distribution switch, EN active high, SOT-23-6"
\t\t\t(at 0 0 0)
\t\t\t(show_name no)
\t\t\t(do_not_autoplace no)
\t\t\t(hide yes)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "ki_keywords" "usb power switch current limit"
\t\t\t(at 0 0 0)
\t\t\t(show_name no)
\t\t\t(do_not_autoplace no)
\t\t\t(hide yes)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(symbol "TPS2553DBV_0_1"
\t\t\t(rectangle
\t\t\t\t(start -10.16 7.62)
\t\t\t\t(end 10.16 -7.62)
\t\t\t\t(stroke
\t\t\t\t\t(width 0.254)
\t\t\t\t\t(type default)
\t\t\t\t)
\t\t\t\t(fill
\t\t\t\t\t(type background)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(symbol "TPS2553DBV_1_1"
%s\t\t)
\t\t(embedded_fonts no)
\t)
'''

_PINS = [("power_in", "IN", "1", -12.7, 5.08, 0),
         ("input", "EN", "3", -12.7, 0, 0),
         ("open_collector", "~{FAULT}", "4", -12.7, -5.08, 0),
         ("power_out", "OUT", "6", 12.7, 5.08, 180),
         ("passive", "ILIM", "5", 12.7, -5.08, 180),
         ("power_in", "GND", "2", 0, -10.16, 90)]


def _sym_pins() -> str:
    out = ""
    for etype, name, num, x, y, rot in _PINS:
        out += (f"\t\t\t(pin {etype} line\n\t\t\t\t(at {fmt(x)} {fmt(y)} {rot})\n\t\t\t\t(length 2.54)\n"
                f"\t\t\t\t(name \"{name}\"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n"
                f"\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n"
                f"\t\t\t\t(number \"{num}\"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n"
                f"\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)\n")
    return out


def lib_block(path: Path, name: str) -> str:
    """Pull one embedded lib_symbol out of a sheet, verbatim."""
    t = path.read_text(encoding="utf-8")
    i = t.find(f'\t\t(symbol "{name}"')
    if i == -1:
        sys.exit(f"lib symbol {name} not found in {path.name}")
    j = t.find('\n\t\t(symbol "', i + 10)
    if j == -1:
        j = t.find('\n\t)\n', i)
    return t[i:j] + "\n"


def add_symbol_to_lib():
    t = SYMLIB.read_text(encoding="utf-8")
    if '(symbol "TPS2553DBV"' in t:
        print("r2.kicad_sym: TPS2553DBV already present")
        return
    body = TPS2553_SYM % _sym_pins()
    anchor = t.rfind("\n)")
    SYMLIB.write_text(t[:anchor + 1] + body + t[anchor + 1:], encoding="utf-8")
    print("r2.kicad_sym: added TPS2553DBV")


C_PROPS = lambda mpn, lcsc, mfr: (("MPN", mpn), ("LCSC", lcsc), ("Manufacturer", mfr))


def build_iox() -> str:
    """Everything the USB1 host port adds to io_expansion.kicad_sch."""
    e = []
    R, C = "Device:R", "Device:C"
    FP_R = "Resistor_SMD:R_0402_1005Metric"
    FP_C = "Capacitor_SMD:C_0402_1005Metric"

    # ---- U56, the current-limited switch -------------------------------
    e.append(symbol("r2:TPS2553DBV", "U56", "TPS2553DBVR", 228.6, 76.2, 0,
                    ["1", "2", "3", "4", "5", "6"], "U56",
                    (("Footprint", "Package_TO_SOT_SMD:SOT-23-6"),) + C_PROPS(
                        "TPS2553DBVR", "C55266", "Texas Instruments")))
    e.append(power("+5V_DCDC", 215.9, 66.04, 0, "p5v_in"))
    e.append(wire(215.9, 66.04, 215.9, 71.12, "w_in_v"))
    e.append(symbol(C, "C519", "100nF/50V", 208.28, 74.93, 0, ["1", "2"], "C519",
                    (("Footprint", FP_C),)))
    e.append(wire(208.28, 71.12, 215.9, 71.12, "w_c519"))
    e.append(power("GND", 208.28, 78.74, 0, "g_c519"))
    e.append(junction(215.9, 71.12, "j_in"))
    e.append(label("USB1_DRVVBUS", 200.66, 76.2, 180, "hl_drv", hier=True, shape="input"))
    e.append(wire(200.66, 76.2, 215.9, 76.2, "w_en"))
    e.append(power("GND", 228.6, 86.36, 0, "g_u56"))

    # FAULT: open drain, pulled to +3V3, reported to the MCU on PB7
    e.append(wire(215.9, 81.28, 203.2, 81.28, "w_flt1"))
    e.append(symbol(R, "R523", "100k", 203.2, 74.93, 0, ["1", "2"], "R523", (("Footprint", FP_R),)))
    e.append(power("+3V3", 203.2, 71.12, 0, "p3v3_flt"))
    e.append(wire(203.2, 78.74, 203.2, 81.28, "w_flt2"))
    e.append(label("USB1_FAULT#", 195.58, 81.28, 180, "hl_flt", hier=True, shape="output"))
    e.append(wire(195.58, 81.28, 203.2, 81.28, "w_flt3"))
    e.append(junction(203.2, 81.28, "j_flt"))

    # ILIM -> 49.9k -> GND  => IOS 475 / 520 / 565 mA
    e.append(symbol(R, "R522", "49.9k/1%", 241.3, 85.09, 0, ["1", "2"], "R522", (("Footprint", FP_R),)))
    e.append(power("GND", 241.3, 88.9, 0, "g_r522"))

    # the switched output rail
    e.append(wire(241.3, 71.12, 261.62, 71.12, "w_out"))
    e.append(symbol(C, "C520", "22uF/10V", 248.92, 74.93, 0, ["1", "2"], "C520",
                    (("Footprint", "Capacitor_SMD:C_0805_2012Metric"),)))
    e.append(power("GND", 248.92, 78.74, 0, "g_c520"))
    e.append(junction(248.92, 71.12, "j_c520"))
    e.append(symbol(C, "C521", "100nF/50V", 256.54, 74.93, 0, ["1", "2"], "C521",
                    (("Footprint", FP_C),)))
    e.append(power("GND", 256.54, 78.74, 0, "g_c521"))
    e.append(junction(256.54, 71.12, "j_c521"))
    e.append(label("USB1_VBUS", 261.62, 71.12, 0, "l_vbus_out"))

    # ---- U57, ESD, wired like U3 on battery ----------------------------
    e.append(symbol("r2:USBLC6-2SC6", "U57", "USBLC6-2SC6", 271.78, 96.52, 0,
                    ["1", "2", "3", "4", "5", "6"], "U57",
                    (("Footprint", "Package_TO_SOT_SMD:SOT-23-6"),) + C_PROPS(
                        "USBLC6-2SC6", "C7519", "STMicroelectronics")))
    for (px, py, nm, sd, rot) in ((266.7, 96.52, "USB1_DM", "esd_dm_l", 180),
                                  (276.86, 96.52, "USB1_DM", "esd_dm_r", 0),
                                  (266.7, 99.06, "USB1_DP", "esd_dp_l", 180),
                                  (276.86, 99.06, "USB1_DP", "esd_dp_r", 0)):
        ex = px - 5.08 if rot == 180 else px + 5.08
        e.append(wire(px, py, ex, py, "w_" + sd))
        e.append(label(nm, ex, py, rot, "l_" + sd))
    e.append(power("GND", 271.78, 104.14, 0, "g_u57"))
    e.append(wire(271.78, 91.44, 271.78, 88.9, "w_u57v"))
    e.append(label("USB1_VBUS", 271.78, 88.9, 90, "l_u57v"))

    # ---- J28, the receptacle -------------------------------------------
    e.append(symbol("Connector:USB_C_Receptacle_USB2.0_16P", "J28", "USB-C 16P",
                    308.61, 88.9, 0,
                    ["A1", "A4", "A5", "A6", "A7", "A8", "A9", "A12",
                     "B1", "B4", "B5", "B6", "B7", "B8", "B9", "B12", "SH"], "J28",
                    (("Footprint", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"),)
                    + C_PROPS("TYPE-C-31-M-12", "C165948", "HRO")))
    e.append(wire(323.85, 73.66, 330.2, 73.66, "w_j28v"))
    e.append(label("USB1_VBUS", 330.2, 73.66, 0, "l_j28v"))
    # CC1/CC2: 56k Rp to the 5 V rail -- a source advertising Default USB Power
    e.append(wire(323.85, 78.74, 330.2, 78.74, "w_cc1"))
    e.append(symbol(R, "R520", "56k", 330.2, 74.93, 0, ["1", "2"], "R520", (("Footprint", FP_R),)))
    e.append(power("+5V_DCDC", 330.2, 71.12, 0, "p_cc1"))
    e.append(wire(323.85, 81.28, 340.36, 81.28, "w_cc2a"))
    e.append(wire(340.36, 81.28, 340.36, 78.74, "w_cc2b"))
    e.append(symbol(R, "R521", "56k", 340.36, 74.93, 0, ["1", "2"], "R521", (("Footprint", FP_R),)))
    e.append(power("+5V_DCDC", 340.36, 71.12, 0, "p_cc2"))
    # the two D+ and the two D- contacts, tied as J1 does
    for (ya, yb, nm, sd) in ((86.36, 88.9, "USB1_DM", "dm"), (91.44, 93.98, "USB1_DP", "dp")):
        e.append(wire(323.85, ya, 328.93, ya, f"w_{sd}a"))
        e.append(wire(323.85, yb, 328.93, yb, f"w_{sd}b"))
        e.append(wire(328.93, ya, 328.93, yb, f"w_{sd}c"))
        e.append(wire(328.93, yb, 334.01, yb, f"w_{sd}d"))
        e.append(junction(328.93, yb, f"j_{sd}"))
        e.append(label(nm, 334.01, yb, 0, f"l_{sd}j28"))
    e.append(no_connect(323.85, 101.6, "nc_sbu1"))
    e.append(no_connect(323.85, 104.14, "nc_sbu2"))
    e.append(power("GND", 308.61, 111.76, 0, "g_j28"))
    e.append(power("GND", 300.99, 111.76, 0, "g_j28sh"))

    # ---- the sheet's interface -----------------------------------------
    for (y, nm, shape, sd) in ((106.68, "USB1_VBUS", "output", "x_vbus"),
                               (109.22, "USB1_DM", "bidirectional", "x_dm"),
                               (111.76, "USB1_DP", "bidirectional", "x_dp")):
        e.append(wire(195.58, y, 203.2, y, "w_" + sd))
        e.append(label(nm, 195.58, y, 180, "hl_" + sd, hier=True, shape=shape))
        e.append(label(nm, 203.2, y, 0, "l_" + sd))
    return "".join(e)


NEEDED_LIBS = [("Device:R", "battery.kicad_sch"),
               ("Connector:USB_C_Receptacle_USB2.0_16P", "battery.kicad_sch"),
               ("r2:USBLC6-2SC6", "battery.kicad_sch")]


def patch_iox():
    t = IOX.read_text(encoding="utf-8")
    if "USB1_DRVVBUS" in t:
        print("io_expansion.kicad_sch: already patched")
        return
    # 1. embed the library symbols this block needs
    add = ""
    for name, src in NEEDED_LIBS:
        if f'\t\t(symbol "{name}"' not in t:
            add += lib_block(HERE / src, name)
    if '(symbol "r2:TPS2553DBV"' not in t:
        # the library form is indented one tab; a sheet's lib_symbols wants two
        blk = (TPS2553_SYM % _sym_pins()).replace(
            '(symbol "TPS2553DBV"', '(symbol "r2:TPS2553DBV"', 1)
        add += "".join((f"\t{ln}\n" if ln.strip() else f"{ln}\n")
                       for ln in blk.split("\n")[:-1])
    if add:
        anchor = t.index("\n\t)\n", t.index("\t(lib_symbols"))
        t = t[:anchor + 1] + add + t[anchor + 1:]
    # 2. append the circuit just before the closing paren
    if not t.endswith("\t)\n)\n") and not t.endswith(")\n"):
        sys.exit("io_expansion.kicad_sch: unexpected trailer")
    tail_at = t.rfind("\n)")
    t = t[:tail_at + 1] + build_iox() + t[tail_at + 1:]
    IOX.write_text(t, encoding="utf-8")
    print("io_expansion.kicad_sch: USB1 host port added (J28, U56, U57, R520-R523, C519-C521)")


SOM_PINS = {"USB1_DM": 64.77, "USB1_DP": 67.31, "USB1_VBUS": 69.85, "USB1_DRVVBUS": 72.39}
SOM_SHAPE = {"USB1_DM": "bidirectional", "USB1_DP": "bidirectional",
             "USB1_VBUS": "input", "USB1_DRVVBUS": "output"}
SOM_PATH = None


def patch_som():
    global SOM_PATH
    t = SOM.read_text(encoding="utf-8")
    # careful: the J26 pin is *named* X_USB1_DRVVBUS, so match the label, not the substring
    if '(hierarchical_label "USB1_DRVVBUS"' in t:
        print("som.kicad_sch: already patched")
        return
    out = []
    for nm, y in SOM_PINS.items():
        pat = re.compile(r'\t\(no_connect\n\t\t\(at 386\.08 %s\)\n(?:.*?\n)*?\t\)\n' % re.escape(f"{y:g}"))
        m = pat.search(t)
        if not m:
            sys.exit(f"som.kicad_sch: no no-connect at (386.08, {y}) for {nm}")
        t = t[:m.start()] + t[m.end():]
        out.append(wire(386.08, y, 391.16, y, "som_w_" + nm))
        out.append(label(nm, 391.16, y, 0, "som_hl_" + nm, hier=True, shape=SOM_SHAPE[nm]))
    tail_at = t.rfind("\n)")
    t = t[:tail_at + 1] + "".join(out) + t[tail_at + 1:]
    SOM.write_text(t, encoding="utf-8")
    print(f"som.kicad_sch: 4 no-connects on J26 B39-B42 -> wires + hierarchical labels")


def patch_mcu():
    t = MCU.read_text(encoding="utf-8")
    if "USB1_FAULT#" in t:
        print("mcu.kicad_sch: already patched")
        return
    # PB7 got a no-connect when FL_PWM2 was retired; it now carries USB1_FAULT#
    pat = re.compile(r'\t\(no_connect\n\t\t\(at 180\.34 172\.72\)\n(?:.*?\n)*?\t\)\n')
    m = pat.search(t)
    if not m:
        sys.exit("mcu.kicad_sch: no no-connect on PB7 at (180.34, 172.72)")
    t = t[:m.start()] + t[m.end():]
    add = [wire(180.34, 172.72, 190.5, 172.72, "mcu_w_pb7"),
           label("USB1_FAULT#", 190.5, 172.72, 0, "mcu_l_pb7"),
           # the export stub, in the slot FL_PWM2 vacated
           wire(358.14, 102.87, 365.76, 102.87, "mcu_w_x"),
           label("USB1_FAULT#", 358.14, 102.87, 180, "mcu_l_x"),
           label("USB1_FAULT#", 365.76, 102.87, 0, "mcu_hl_x", hier=True, shape="input")]
    tail_at = t.rfind("\n)")
    t = t[:tail_at + 1] + "".join(add) + t[tail_at + 1:]
    MCU.write_text(t, encoding="utf-8")
    print("mcu.kicad_sch: USB1_FAULT# on PB7 (U20.61)")


def main():
    add_symbol_to_lib()
    patch_iox()
    patch_som()
    patch_mcu()
    print("\nNow run, in this order:")
    print("  python3 tools/sheet_pins_refresh.py   (or set_sheet_pins for io_expansion/som/mcu)")
    print("  python3 tools/wire_root.py")


if __name__ == "__main__":
    main()
