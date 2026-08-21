#!/usr/bin/env python3
"""Stage D review: the layout rules that can be checked by a machine.

`docs/layout.md` §7 is the human checklist. This is the part of it that does not
need judgement, so it can be run after every session instead of at the end:

    python3 tools/check_pcb.py

Exit status is 0 when everything passes and 1 otherwise. **Nothing here replaces
reading `docs/layout.md`** -- most of what matters at layout (loop area, what a
plane is doing under an island, whether a trace is "quiet") is not measurable
from the file. What *is* measurable is largely the set of rules that are easy to
violate by accident and invisible once the board is routed.

Six groups of check:

1. **Every part on the schematic is on the board**, and nothing extra is. A
   footprint silently missing from the PCB is a part that never gets ordered.
2. **The SoM's three footprints hold their geometry** -- delegated to
   `check_pcb_connectors.py`, which is the one relationship KiCad does not
   enforce for us.
3. **Proximity rules**, from the per-sheet guidelines. A decoupling capacitor's
   whole job is its distance to a pin; "as close as possible" is a number once a
   board exists, and this is where those numbers live.
4. **Nets that must not be poured**, notably the two inverting converters whose
   `GND` pin sits at -20 V and -15 V. `epd-port.md` §11.1 calls this the one
   thing on the board a competent person would "fix" into failure.
5. **Net classes** exist and carry the nets `layout.md` §4 assigns them.
6. **Ratsnest and DRC** -- how much is left to route, and what `kicad-cli` says.

Every rule carries its source, because a check whose reason has been forgotten
gets deleted the first time it is inconvenient.
"""
from __future__ import annotations

import collections
import fnmatch
import json
import math
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent
PCB = PROJ / "r2.kicad_pcb"
SCH = PROJ / "r2.kicad_sch"
PRO = PROJ / "r2.kicad_pro"
KICAD_CLI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/bin/kicad-cli"

# --- 3. proximity -------------------------------------------------------------
# (part, anchor, max centre-to-centre mm, source). The distances are centre to
# centre because a pad-accurate rule would need the placed rotation, and the
# point of these is to catch a capacitor that drifted across the board, not to
# adjudicate a tenth of a millimetre.
PROXIMITY = [
    ("C41", "U20", 4.0, "mcu.md §11.1 -- ST Figure 15: 100 nF at pin 8, and VBAT "
                        "shares the net, so both lose decoupling if it drifts"),
    ("C40", "U20", 6.0, "mcu.md §11.1 -- the 4.7 uF behind C41"),
    ("C44", "U20", 5.0, "mcu.md §11.1/§11.2 -- 100 nF on the pin-7 side of FB20"),
    ("C45", "U20", 5.0, "mcu.md §11.6 -- NRST wants its cap close to pin 12"),
    ("Y20", "U20", 8.0, "mcu.md §11.3 -- the 32.768 kHz oscillator is the most "
                        "layout-sensitive circuit on the board"),
    ("C46", "Y20", 4.0, "mcu.md §11.3 -- load caps at the crystal, same layer, no vias"),
    ("C47", "Y20", 4.0, "mcu.md §11.3"),
    ("R512", "U20", 6.0, "mcu.md §11.6 -- 1 MOhm PG_SOM bias belongs at pin 48"),
    ("C25", "U12", 4.0, "power.md §11.2 item 3 -- CIN at VIN and GND both"),
    ("C26", "U12", 4.0, "power.md §11.2 item 1 -- the output caps ARE the critical loop"),
    ("C27", "U12", 4.0, "power.md §11.2 item 1"),
    ("L10", "U12", 5.0, "power.md §11.2 item 2 -- SW is the aggressor; keep it short"),
    ("C29", "U13", 4.0, "power.md §11.3 item 4"),
    ("C30", "U13", 4.0, "power.md §11.3 item 4"),
    ("L11", "U13", 5.0, "power.md §11.3 item 1 -- a buck-boost has TWO switching nodes"),
    ("C31", "U14", 3.5, "power.md §11.4 item 1"),
    ("C32", "U14", 3.5, "power.md §11.4 item 1"),
    ("L12", "U14", 4.0, "power.md §11.4 item 1"),
    ("C33", "U15", 3.5, "power.md §11.4 item 1"),
    ("C34", "U15", 3.5, "power.md §11.4 item 1"),
    ("L13", "U15", 4.0, "power.md §11.4 item 1"),
    ("C20", "U10", 3.5, "power.md §11.5 item 1"),
    ("C21", "U10", 3.5, "power.md §11.5 item 1"),
    ("C1", "U1", 5.0, "battery.md §11.1 -- C1's ground must land on PGND at the pin"),
    ("C2", "U1", 5.0, "battery.md §11.2 item 1 -- the PMID->SW->PGND hot loop"),
    ("C3", "U1", 5.0, "battery.md §11.2 item 4 -- BTST is a high-dV/dt loop on SW"),
    ("U3", "J1", 8.0, "battery.md §11.2 item 6 -- ESD is stopped where it enters"),
    ("R340", "U41", 8.0, "fpga.md §11.2 -- RZQ close to the FPGA, direct via to ground"),
    ("R102", "U52", 8.0, "fpga.md §11.2 -- ZQ is the DRAM's reference, not the FPGA's"),
    ("C507", "X1", 4.0, "fpga.md §11.4 -- at the oscillator's supply pin"),
    ("R409", "X1", 6.0, "fpga.md §11.4 -- series termination at the SOURCE end"),
    ("D34", "U53", 4.0, "frontlight.md §9 -- SW->D34->C515 is a 28.5 V 1 MHz loop"),
    ("C515", "U53", 5.0, "frontlight.md §9"),
]

# --- 4. nets that must not be poured or plane-connected ------------------------
# `epd-port.md` §11.1. Each of these is an IC's own ground reference sitting tens
# of volts below board ground; a zone on one is a short across the part.
NO_ZONE_NETS = {
    "-VGL": "U9 (LGS5145) pin 2 sits here, about -20 V. epd-port.md §11.1",
    "-VN": "U26 (LGS5145) pin 2 sits here, about -15 V. epd-port.md §11.1",
    "+DRAM_VREF": "quiet 0.750 V divider node; a plane on it is an antenna. fpga.md §11.3",
    "+3V3_VREF": "the MCU's VREF+ island; do not pour +3V3_AON over it. mcu.md §11.2",
}

# --- 5. net classes -----------------------------------------------------------
# ⚠ These live in `r2.kicad_pro`, NOT in the board file. This check used to
# grep `r2.kicad_pcb` for `(net_class "..."` and a JSON `"name":` key, neither
# of which a KiCad 10 .kicad_pcb ever contains -- so it reported "0 of 7
# present" no matter what Board Setup said, which is a check that can only ever
# be wrong. `tools/import_r1_settings.py` writes them.
#
# The count next to each name is what the pattern set is expected to catch; a
# net class with the right name and no nets in it is the failure this catches.
EXPECTED_CLASSES = {
    "DDR3": (45, "bank-3 data/addr/ctrl, length-matched per byte lane. "
                 "ADDR13/14 excluded on purpose -- fpga.md §11.1"),
    "DDR3_CLK": (2, "DRAM_CKP/CKN, differential, R100 at the DRAM end"),
    "DPI": (22, "the DPI_* nets over continuous ground"),
    "EPD": (23, "EPDC_D0P/N..D7P/N plus the gate and source strobes. "
                "Not in layout.md §4's original table; carried over from R1"),
    "USB": (2, "USB_DP/DM, 90 ohm differential"),
    "MMC1": (7, "the microSD nets, matched within 12.7 mm"),
    "HV": (5, "+VP, +VGH, -VCOM, -VGL, -VN -- clearance, not width"),
    "PWR": (16, "every rail plus GND -- a floor on width, not a target"),
}


def footprints(text: str) -> dict:
    out = {}
    for m in re.finditer(r"\n\t\(footprint ", text):
        i = m.start() + 2
        d, j = 0, i
        while True:
            if text[j] == "(":
                d += 1
            elif text[j] == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        blk = text[i:j + 1]
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
        at = re.search(r"\n\t\t\(at ([\d.-]+) ([\d.-]+)", blk)
        if not (ref and at):
            continue
        out[ref.group(1)] = {"xy": (float(at.group(1)), float(at.group(2))),
                             "blk": blk}
    return out


def sch_refs() -> set:
    """Every reference the schematic expects to be on the board."""
    out = subprocess.run(
        [str(KICAD_CLI), "sch", "export", "netlist", "--format", "kicadsexpr",
         "-o", "/dev/stdout", str(SCH)], capture_output=True, text=True)
    return set(re.findall(r'\(comp\n\t+\(ref "([^"]+)"\)', out.stdout)) or \
        set(re.findall(r'\(ref "([^"]+)"\)\n\t+\(value', out.stdout))


def main() -> int:
    if not PCB.exists():
        print(f"{PCB.name} does not exist yet -- Stage D has not started.")
        print("Create it in KiCad (docs/layout.md §6) and run this again.")
        return 0

    text = PCB.read_text()
    fps = footprints(text)
    fail, warn = [], []
    print(f"{PCB.name}: {len(fps)} footprints placed\n")

    # 1. presence
    want = sch_refs()
    if want:
        missing = sorted(want - set(fps))
        extra = sorted(r for r in set(fps) - want if not r.startswith("#"))
        print(f"1. presence: schematic has {len(want)} components, board has {len(fps)}")
        if missing:
            fail.append(f"on the schematic but not on the board: {missing}")
        if extra:
            warn.append(f"on the board but not on the schematic: {extra}")

    # 2. the SoM
    r = subprocess.run([sys.executable, str(HERE / "check_pcb_connectors.py")],
                       capture_output=True, text=True)
    print("\n2. SoM geometry (check_pcb_connectors.py):")
    for ln in r.stdout.strip().split("\n"):
        print("   " + ln)
    if r.returncode:
        fail.append("the SoM's connector geometry is wrong -- see above")

    # 3. proximity
    print("\n3. proximity rules:")
    checked = worst = 0
    for part, anchor, limit, why in PROXIMITY:
        if part not in fps or anchor not in fps:
            continue
        checked += 1
        (ax, ay), (bx, by) = fps[part]["xy"], fps[anchor]["xy"]
        d = math.hypot(ax - bx, ay - by)
        if d > limit:
            fail.append(f"{part} is {d:.1f} mm from {anchor}, limit {limit} mm -- {why}")
            worst = max(worst, d - limit)
    print(f"   {checked} of {len(PROXIMITY)} rules applicable, "
          f"{sum(1 for f in fail if ' mm from ' in f)} violated")

    # 4. nets that must not be poured
    print("\n4. nets that must not carry a zone:")
    zones = re.findall(r'\(zone\n(?:(?!\(zone).)*?\(net_name "([^"]*)"', text, re.S)
    for net, why in NO_ZONE_NETS.items():
        if net in zones:
            fail.append(f"there is a copper zone on {net!r} -- {why}")
    print(f"   {len(set(zones))} distinct nets have zones; "
          f"{sum(1 for n in NO_ZONE_NETS if n in zones)} of them must not")

    # 5. net classes -- from the PROJECT file, and checked for members
    print("\n5. net classes:")
    pro = json.loads(PRO.read_text())
    ns = pro["net_settings"]
    have = {c["name"] for c in ns["classes"]}
    nets = sorted(set(re.findall(r'\(net "([^"]*)"\)', text)))
    got = {}
    for net in nets:
        for pat in ns["netclass_patterns"]:
            if fnmatch.fnmatchcase(net, pat["pattern"]):
                got[net] = pat["netclass"]
                break
    counts = collections.Counter(got.values())
    for cls, (want, why) in EXPECTED_CLASSES.items():
        if cls not in have:
            warn.append(f"no net class {cls!r} -- {why} (layout.md §4)")
        elif counts[cls] != want:
            warn.append(f"net class {cls!r} holds {counts[cls]} nets, "
                        f"expected {want} -- {why}")
    dead = [p["pattern"] for p in ns["netclass_patterns"]
            if not any(fnmatch.fnmatchcase(n, p["pattern"]) for n in nets)]
    for p in dead:
        warn.append(f"netclass pattern {p!r} matches no net on this board")
    print(f"   {len(have & set(EXPECTED_CLASSES))} of {len(EXPECTED_CLASSES)} "
          f"expected classes present, {len(got)} of {len(nets)} nets assigned "
          f"({len(dead)} dead patterns)")

    # 6. ratsnest and DRC
    segs = len(re.findall(r"\n\t\(segment", text))
    vias = len(re.findall(r"\n\t\(via", text))
    print(f"\n6. routing: {segs} track segments, {vias} vias")
    # ⚠ Read the report only if the run succeeded, and delete it first.
    # This used to `json.load` the file unconditionally, so when `kicad-cli`
    # failed to load the board it silently reported the PREVIOUS run's numbers
    # -- which is how "4250 violations" got reported for a board that would not
    # open at all. A check that reports stale data is worse than no check.
    rep_path = pathlib.Path("/tmp/r2-drc.json")
    rep_path.unlink(missing_ok=True)
    d = subprocess.run([str(KICAD_CLI), "pcb", "drc", "--format", "json",
                        "-o", str(rep_path), str(PCB)],
                       capture_output=True, text=True)
    if d.returncode != 0 or not rep_path.exists():
        msg = (d.stdout + d.stderr).strip().splitlines()
        fail.append("kicad-cli could not run DRC: "
                    + (msg[-1] if msg else f"exit {d.returncode}")
                    + ". A board that the CLI cannot load usually means a "
                      "footprint references a layer this board does not have "
                      "-- see docs/layout.md §9.2.")
        print("   DRC: DID NOT RUN")
    else:
        rep = json.loads(rep_path.read_text())
        nv = len(rep.get("violations", []))
        nu = len(rep.get("unconnected_items", []))
        print(f"   DRC: {nv} violations, {nu} unconnected items")
        if nv:
            warn.append(f"DRC reports {nv} violations -- run it in Pcbnew for detail")
        if nu:
            warn.append(f"{nu} unconnected items still to route")

    print()
    for w in warn:
        print(f"WARN  {w}")
    for f in fail:
        print(f"FAIL  {f}")
    if not fail:
        print("\nOK -- every machine-checkable rule in docs/layout.md §8 passes.")
        print("The rest of §7 needs eyes; that list is short and it is in the doc.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
