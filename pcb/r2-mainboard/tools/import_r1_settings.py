#!/usr/bin/env python3
"""Bring R1's board design settings into R2's project file, and build the net
classes `docs/layout.md` §4 asks for.

    python3 tools/import_r1_settings.py            # show what would change
    python3 tools/import_r1_settings.py --write    # do it

R1 (`pcb/mainboard/pcb.kicad_pro`) is opened **read only**. It is a KiCad 8
project and must stay one -- see CLAUDE.md.

Why import at all: R2's stackup is byte-identical to R1's (F.Cu / 0.127 prepreg
/ In1.Cu / 0.6 core / In2.Cu / 0.127 prepreg / B.Cu, 0.035 outer copper, ENIG),
so every trace geometry R1 proved at DDR3-666 on a Spartan-6 transfers with its
impedance intact. R2's own file has never been through Board Setup, so its
numbers are KiCad 10 defaults -- 0.4 mm tracks, 1.651 mm vias, one stray
`power` class matching nets (`-VAA`, `/12Vext`, `HT`, `VCC`) that do not exist
on this board.

Three things are **not** copied verbatim, each marked DEVIATION below with the
measurement or document that overrides R1.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent
R2 = PROJ / "r2.kicad_pro"
R1 = PROJ.parent / "mainboard" / "pcb.kicad_pro"
DRU = PROJ / "r2.kicad_dru"

# --- what comes across from R1 ------------------------------------------------
# `rules` = Board Setup > Constraints. R1 and R2 already agree on all of these
# except `max_error`; the import is nearly a no-op and is done anyway so the two
# boards cannot drift apart silently.
COPY_RULES = [
    "max_error", "min_clearance", "min_connection", "min_copper_edge_clearance",
    "min_hole_clearance", "min_hole_to_hole", "min_microvia_diameter",
    "min_microvia_drill", "min_resolved_spokes", "min_silk_clearance",
    "min_text_height", "min_text_thickness", "min_through_hole_diameter",
    "min_track_width", "min_via_annular_width", "min_via_diameter",
    "solder_mask_to_copper_clearance", "use_height_for_length_calcs",
]

# `defaults` = Board Setup > Text & Graphics. R1's are finer than KiCad's stock
# values throughout, which is what a board this dense wants.
COPY_DEFAULTS = [
    "board_outline_line_width", "copper_line_width", "copper_text_size_h",
    "copper_text_size_v", "copper_text_thickness", "courtyard_line_width",
    "dimension_precision", "dimension_units", "fab_line_width",
    "fab_text_size_h", "fab_text_size_v", "fab_text_thickness",
    "other_line_width", "other_text_size_h", "other_text_size_v",
    "other_text_thickness", "silk_line_width", "silk_text_size_h",
    "silk_text_size_v", "silk_text_thickness",
]

# --- the three deviations -----------------------------------------------------
# 1. Track-width presets: R1's list verbatim, plus 0.8 (a poured rail's neck).
#    This is the toolbar dropdown -- the literal answer to "what width do I
#    draw with".
TRACK_WIDTHS = [0.0, 0.1, 0.11, 0.12, 0.127, 0.13, 0.15, 0.2, 0.25, 0.3,
                0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0]

# 2. Via presets: R1's two, plus 0.6/0.3 -- `layout.md` §6.1's default via, and
#    the one to use for anything that is not escaping a fine-pitch part.
VIA_DIMENSIONS = [
    {"diameter": 0.0, "drill": 0.0},
    {"diameter": 0.45, "drill": 0.3},    # R1: fine-pitch escape
    {"diameter": 0.6, "drill": 0.3},     # general purpose
    {"diameter": 0.8, "drill": 0.35},    # R1: power stitching
]

# 3. Differential-pair presets. R1 shipped none (an empty 0/0/0 row), so these
#    come from the classes below.
DIFF_PAIRS = [
    {"width": 0.0, "gap": 0.0, "via_gap": 0.0},
    {"width": 0.127, "gap": 0.11, "via_gap": 0.25},   # DDR3_CLK, EPD, DQS
    {"width": 0.15, "gap": 0.11, "via_gap": 0.25},    # USB, 90 ohm
    {"width": 0.2, "gap": 0.2, "via_gap": 0.25},      # default
]

# --- net classes --------------------------------------------------------------
# `docs/layout.md` §4's seven, plus EPD (see NOTE below). Widths are R1's
# equivalent class verbatim wherever R1 had one, because the stackup is the same
# board.
#
# ⚠ `clearance` is the ONE number that cannot be chosen freely. KiCad checks it
# between pads inside a single footprint too, so a class clearance above a
# package's own pad gap produces DRC errors no routing can fix. Measured on this
# board's placed footprints (tools/pad_gaps.py logic, run 2026-08-21):
#
#     U1  BQ25792 QFN-24     0.125 mm   <- tightest on the board
#     U7/U8/U54/U55, U14/U15 0.150 mm
#     U53 YFQ0012 DSBGA-12   0.160 mm
#     J26/J27 BTH-060        0.195 mm
#     J1  USB-C              0.200 mm
#
# So 0.11 mm -- R1's number -- is not merely proven, it is the only value with
# headroom under every part here. `layout.md` §6.1's suggested "0.2 mm
# clearance" predates these footprints existing and would flag eight packages
# on import; §6.1 has been corrected.
DEF = dict(bus_width=12, line_style=0, microvia_diameter=0.3, microvia_drill=0.1,
           pcb_color="rgba(0, 0, 0, 0.000)", schematic_color="rgba(0, 0, 0, 0.000)",
           wire_width=6)

CLASSES = [
    # name, track, clearance, via_d, via_drill, dp_w, dp_gap, colour, why
    ("Default", 0.2, 0.11, 0.6, 0.3, 0.2, 0.2, None,
     "0.2 mm track: nothing here needs less unless it is escaping a fine-pitch "
     "part, and a wider default is less lossy and easier to rework. Clearance "
     "0.11 from R1 -- see the pad-gap table above."),
    ("DDR3", 0.127, 0.11, 0.45, 0.3, 0.127, 0.11, "rgb(255, 92, 56)",
     "R1's SDRAM_A/H/L verbatim. Same stackup, same Spartan-6 MCB, same "
     "666.67 Mb/s. fpga.md §11.1 -- and U41 is a -2, so there is 0.05 % margin "
     "and nothing to spend on experiments."),
    ("DDR3_CLK", 0.127, 0.11, 0.45, 0.3, 0.127, 0.11, "rgb(255, 139, 0)",
     "DRAM_CKP/CKN. Split out from DDR3 only so it is visibly a pair and gets "
     "routed first (layout.md §6.4)."),
    ("DPI", 0.15, 0.11, 0.45, 0.3, 0.2, 0.2, "rgb(216, 223, 0)",
     "22 single-ended nets at ~101 MP/s over continuous In1.Cu. Slightly wider "
     "than DDR3 because there is no length-match to hold and the run is long."),
    ("EPD", 0.11, 0.11, 0.45, 0.3, 0.127, 0.11, "rgb(179, 228, 50)",
     "R1's EPD class verbatim, for EPDC_D0P/N..D7P/N and the gate/source "
     "strobes. NOT in layout.md §4's table -- see NOTE."),
    ("USB", 0.11, 0.11, 0.45, 0.3, 0.15, 0.11, "rgb(255, 122, 107)",
     "R1's USB class verbatim: 90 ohm differential, J1 -> U3 -> J26."),
    ("MMC1", 0.15, 0.11, 0.45, 0.3, 0.2, 0.2, "rgb(185, 61, 143)",
     "microSD, matched within 12.7 mm (som.md §8)."),
    ("HV", 0.3, 0.11, 0.6, 0.3, 0.2, 0.2, "rgb(255, 37, 28)",
     "+VP/+VGH/-VCOM/-VGL/-VN. Currents are tiny; 0.3 mm is for handling and "
     "etch tolerance, not ampacity. The clearance that actually matters is "
     "track-to-track and lives in r2.kicad_dru, NOT here -- +VGH lands on a "
     "0.5 mm-pitch VSON, so a wide class clearance would fail on the part's "
     "own pads."),
    ("PWR", 0.6, 0.11, 0.8, 0.35, 0.2, 0.2, "rgb(0, 94, 255)",
     "A FLOOR, not a target. power.md §11.6 item 2: the boost pulls ~2.8 A off "
     "+VSYS at 1 MHz and 'wants real copper, not a 0.25 mm trace'. +VSYS is a "
     "plane. Treat 0.6 mm as the narrowest a rail may ever neck to."),
]

# NOTE (EPD): layout.md §4's table lists seven classes and is silent on the 23
# EPDC_* nets, which are the second-largest routed group on the board. R1 had a
# class for them; not carrying it over would leave them on Default. Added here
# and to layout.md §4; tools/check_pcb.py expects eight classes now.

PATTERNS = [
    # DDR3_CLK before DDR3 -- KiCad 10 resolves by priority (list order),
    # and DRAM_CK[PN] must not fall into the DDR3 bulk pattern.
    ("DDR3_CLK", "/fpga_ddr/DRAM_CKP"),
    ("DDR3_CLK", "/fpga_ddr/DRAM_CKN"),
    # ⚠ DRAM_ADDR13/ADDR14 are DELIBERATELY absent: fpga.md §11.1 -- they are
    # the inert density-expansion nets, and letting a length-match rule see
    # them would drag the real group's tolerance around for two dead traces.
    # That is why the address nets are enumerated by range instead of ADDR*.
    ("DDR3", "/fpga_ddr/DRAM_ADDR[0-9]"),
    ("DDR3", "/fpga_ddr/DRAM_ADDR1[0-2]"),
    ("DDR3", "/fpga_ddr/DRAM_DATA[0-9]"),
    ("DDR3", "/fpga_ddr/DRAM_DATA1[0-5]"),
    ("DDR3", "/fpga_ddr/DRAM_BA[0-2]"),
    ("DDR3", "/fpga_ddr/DRAM_[LU]DM"),
    ("DDR3", "/fpga_ddr/DRAM_[LU]DQS[PN]"),
    ("DDR3", "/fpga_ddr/DRAM_CASB"),
    ("DDR3", "/fpga_ddr/DRAM_RASB"),
    ("DDR3", "/fpga_ddr/DRAM_WEB"),
    ("DDR3", "/fpga_ddr/DRAM_CSB"),
    ("DDR3", "/fpga_ddr/DRAM_CKE"),
    ("DDR3", "/fpga_ddr/DRAM_ODT"),
    ("DDR3", "/fpga_ddr/DRAM_RST"),
    ("DPI", "/DPI_*"),
    ("EPD", "/EPDC_*"),
    ("USB", "/USB_DP"),
    ("USB", "/USB_DM"),
    ("MMC1", "/som/SD_*"),
    ("HV", "+VP"),
    ("HV", "+VGH"),
    ("HV", "-VCOM"),
    ("HV", "-VGL"),
    ("HV", "-VN"),
    ("PWR", "+VSYS"),
    ("PWR", "+VSYS_FL"),
    ("PWR", "+VBAT"),
    ("PWR", "+VBUS"),
    ("PWR", "+5V_SOM"),
    ("PWR", "+5V_EPD"),
    ("PWR", "+5V_DCDC"),
    ("PWR", "+3V3"),
    ("PWR", "+3V3_DCDC"),
    ("PWR", "+3V3_AON"),
    ("PWR", "+3V3_AON_DCDC"),
    ("PWR", "+1V2_FPGA"),
    ("PWR", "+1V2_DCDC"),
    ("PWR", "+1V5"),
    ("PWR", "+1V5_DCDC"),
]

# ⚠ GND is deliberately NOT in PWR, removed 2026-08-22 on the owner's objection:
# "I can't always have a 0.6 mm GND trace. Sometimes for signals it's just not
# necessary." Correct, and the class was the thing at fault. GND's current path
# is the In1.Cu plane; a GND *segment* is almost always a short stub from a pad
# to a stitching via, where 0.6 mm buys nothing and just gets overridden by hand
# every time. On Default it routes at 0.2 mm and takes a 0.6/0.3 via, which is
# also the more useful stitching via -- PWR's 0.8/0.35 is clumsy under a BGA.
# Clearance is 0.11 either way, so nothing is lost.
#
# +VSYS stays in PWR even though power.md §11.6 calls it a plane too, because
# unlike GND it has real routed runs to the four converters that genuinely want
# to start wide.

# ⚠ NOT in PWR, on purpose: +DRAM_VREF and +3V3_VREF are divider taps that must
# stay hairline and unpoured (check_pcb.py NO_ZONE_NETS), and +5V_EG / +5V_ES /
# +5V2_FL are panel-side rails that leave through J6 rather than being poured.

NET_COLORS = {name: col for name, _, _, _, _, _, _, col, _ in CLASSES if col}

DRU_TEXT = """\
(version 1)

# R2 custom DRC rules. KiCad loads this automatically because it is named after
# the board; Board Setup > Custom Rules shows and syntax-checks it.
#
# Delete this file and the board still routes -- nothing here is load-bearing.

# The HV rails run to +28.4 V (+VGH) and down to -20 V (-VGL): 48 V between the
# two extremes. IPC-2221 wants 0.13 mm between them under permanent solder mask,
# so 0.4 mm is roughly 3x the requirement and costs nothing on a board with this
# much room in the EPD corner.
#
# This is a rule and not a net-class clearance because a class clearance is also
# checked pad-to-pad INSIDE a footprint, and +VGH lands on a 0.5 mm-pitch
# VSON-HR-10 whose own pads are 0.25 mm apart. Excluding pads keeps the check on
# the copper we actually draw.
(rule "HV track separation"
	(constraint clearance (min 0.4mm))
	(condition "A.NetClass == 'HV' && B.NetClass != 'HV' && A.Type != 'Pad' && B.Type != 'Pad'"))
"""


def kicad_is_open() -> str | None:
    """Return a reason string if it is not safe to write, else None."""
    # `pgrep -x` matches the process NAME only. `-f` matches the full command
    # line and so matches this script's own invocation -- that bug made an
    # earlier tool refuse to run every single time.
    if subprocess.run(["pgrep", "-x", "kicad"],
                      capture_output=True).returncode == 0:
        return "KiCad is running"
    locks = sorted(PROJ.glob("~*.lck"))
    if locks:
        return "lock files present: " + ", ".join(p.name for p in locks)
    return None


def build(r1: dict, r2: dict) -> tuple[dict, list[str]]:
    out = copy.deepcopy(r2)
    log: list[str] = []

    def note(what, old, new):
        if old != new:
            log.append(f"  {what:<44} {old!r:>26}  ->  {new!r}")

    a, b = r1["board"]["design_settings"], out["board"]["design_settings"]

    for k in COPY_RULES:
        if k in a["rules"] and k in b["rules"]:
            note(f"constraints.{k}", b["rules"][k], a["rules"][k])
            b["rules"][k] = a["rules"][k]
    for k in COPY_DEFAULTS:
        if k in a["defaults"] and k in b["defaults"]:
            note(f"defaults.{k}", b["defaults"][k], a["defaults"][k])
            b["defaults"][k] = a["defaults"][k]

    # DEVIATION: zone clearance. R1 pours at 0.11 mm. Keep pours off tracks by
    # more than that -- a 0.11 mm gap between a pour and a track is a solder
    # mask sliver, and unlike a pad gap nothing forces it to be tight.
    note("defaults.zones.min_clearance", b["defaults"]["zones"]["min_clearance"], 0.2)
    b["defaults"]["zones"]["min_clearance"] = 0.2

    note("track_widths", b["track_widths"], TRACK_WIDTHS)
    b["track_widths"] = list(TRACK_WIDTHS)
    note("via_dimensions", len(b["via_dimensions"]), len(VIA_DIMENSIONS))
    b["via_dimensions"] = copy.deepcopy(VIA_DIMENSIONS)
    note("diff_pair_dimensions", len(b["diff_pair_dimensions"]), len(DIFF_PAIRS))
    b["diff_pair_dimensions"] = copy.deepcopy(DIFF_PAIRS)

    # KiCad 10 keeps the tuning-pattern spacing here; R1's 0.5 mm is tighter
    # than KiCad 10's 0.6 mm stock value and matters for DDR3 serpentines.
    b["tuning_pattern_settings"] = copy.deepcopy(a["tuning_pattern_settings"])
    for grp in b["tuning_pattern_settings"].values():
        grp.setdefault("corner_style", 1)   # KiCad 10 default: rounded
    log.append("  tuning patterns                              "
               "KiCad 10 stock  ->  R1's 0.5 mm spacing")

    ns = out["net_settings"]
    old_names = [c["name"] for c in ns["classes"]]
    classes = []
    for name, tw, cl, vd, vdr, dw, dg, col, _why in CLASSES:
        c = dict(DEF, name=name, track_width=tw, clearance=cl,
                 via_diameter=vd, via_drill=vdr,
                 diff_pair_width=dw, diff_pair_gap=dg, diff_pair_via_gap=0.25)
        if name == "Default":
            # KiCad marks Default as lowest priority so every pattern wins.
            c["priority"] = 2147483647
        if col:
            c["pcb_color"] = col
        c["tuning_profile"] = ""
        classes.append(c)
    # ⚠ Keep any class the owner added by hand. This used to assign `classes`
    # wholesale, which would have silently deleted `Signals_NET` the second time
    # anyone ran it -- a tool that eats the user's work on a re-run is worse than
    # no tool. Same for their patterns: only ours are replaced.
    ours = {c["name"] for c in classes}
    kept = [c for c in ns["classes"] if c["name"] not in ours]
    ns["classes"] = classes + kept
    kept_pats = [q for q in ns["netclass_patterns"] if q["netclass"] not in ours]
    ns["netclass_patterns"] = [{"netclass": n, "pattern": p} for n, p in PATTERNS] \
        + kept_pats
    if kept:
        log.append(f"  kept {len(kept)} hand-made class(es) untouched:  "
                   f"{[c['name'] for c in kept]} "
                   f"({len(kept_pats)} of their patterns)")
    ns["net_colors"] = dict(NET_COLORS)
    log.append(f"  net classes                     {old_names}  ->  "
               f"{[c['name'] for c in ns['classes']]}")
    log.append(f"  netclass patterns                                "
               f"{len(PATTERNS)} rules, {len(CLASSES) - 1} classes assigned")
    return out, log


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="actually modify r2.kicad_pro (default: dry run)")
    args = ap.parse_args()

    r1 = json.loads(R1.read_text())
    r2 = json.loads(R2.read_text())
    out, log = build(r1, r2)

    print(f"R1 -> R2 design settings\n  from {R1}\n  into {R2}\n")
    print("\n".join(log) or "  (nothing to change)")
    print("\nnet classes written:")
    for name, tw, cl, vd, vdr, dw, dg, _c, why in CLASSES:
        print(f"  {name:<9} track {tw:<6} clr {cl:<5} via {vd}/{vdr}  "
              f"pair {dw}/{dg}")
        print(f"            {why}")

    if not args.write:
        print("\nDry run. Re-run with --write to apply.")
        return 0

    why = kicad_is_open()
    if why:
        print(f"\nREFUSING TO WRITE: {why}.\n"
              "KiCad holds the whole project in memory and rewrites "
              "r2.kicad_pro on save, which would silently undo this. "
              "Close KiCad and run it again.", file=sys.stderr)
        return 1

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = R2.with_suffix(f".kicad_pro.bak-{stamp}")
    bak.write_text(R2.read_text())
    R2.write_text(json.dumps(out, indent=2) + "\n")
    if not DRU.exists():
        DRU.write_text(DRU_TEXT)
        print(f"\nwrote {DRU.name} (custom DRC rules)")
    else:
        print(f"\n{DRU.name} already exists -- left alone")
    print(f"wrote {R2.name}, backup at {bak.name}")
    print("\nReopen the project and check two things:\n"
          "  Board Setup > Net Classes  -- nine classes, assignment columns\n"
          "                                populated rather than empty.\n"
          "  Board Setup > Custom Rules -- press 'Check rule syntax'. This is\n"
          "                                the ONLY way to validate the .dru:\n"
          "                                `kicad-cli pcb drc` silently ignores\n"
          "                                a rules file it cannot parse (tested\n"
          "                                2026-08-21 with a deliberately broken\n"
          "                                one -- no error, no exit code, rules\n"
          "                                just not applied).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
