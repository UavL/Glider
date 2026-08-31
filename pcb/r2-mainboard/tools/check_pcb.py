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
7. **Width on the nets that carry current**, and only those. Not a per-class
   width rule -- see the comment on `HIGH_CURRENT` for why that idea was wrong.

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
    ("C401", "U400", 4.0, "mcu.md §11.1 -- ST Figure 15: 100 nF at pin 8, and VBAT "
                        "shares the net, so both lose decoupling if it drifts"),
    ("C400", "U400", 6.0, "mcu.md §11.1 -- the 4.7 uF behind C41"),
    ("C403", "U400", 5.0, "mcu.md §11.1/§11.2 -- 100 nF on the pin-7 side of FB20"),
    ("C404", "U400", 5.0, "mcu.md §11.6 -- NRST wants its cap close to pin 12"),
    ("Y400", "U400", 8.0, "mcu.md §11.3 -- the 32.768 kHz oscillator is the most "
                        "layout-sensitive circuit on the board"),
    ("C405", "Y400", 4.0, "mcu.md §11.3 -- load caps at the crystal, same layer, no vias"),
    ("C406", "Y400", 4.0, "mcu.md §11.3"),
    ("R408", "U400", 6.0, "mcu.md §11.6 -- 1 MOhm PG_SOM bias belongs at pin 48"),
    ("C303", "U12", 4.0, "power.md §11.2 item 3 -- CIN at VIN and GND both"),
    ("C304", "U12", 4.0, "power.md §11.2 item 1 -- the output caps ARE the critical loop"),
    ("C305", "U12", 4.0, "power.md §11.2 item 1"),
    ("L300", "U12", 5.0, "power.md §11.2 item 2 -- SW is the aggressor; keep it short"),
    ("C307", "U13", 4.0, "power.md §11.3 item 4"),
    ("C308", "U13", 4.0, "power.md §11.3 item 4"),
    ("L301", "U13", 5.0, "power.md §11.3 item 1 -- a buck-boost has TWO switching nodes"),
    ("C309", "U14", 3.5, "power.md §11.4 item 1"),
    ("C310", "U14", 3.5, "power.md §11.4 item 1"),
    ("L302", "U14", 4.0, "power.md §11.4 item 1"),
    ("C311", "U15", 3.5, "power.md §11.4 item 1"),
    ("C312", "U15", 3.5, "power.md §11.4 item 1"),
    ("L303", "U15", 4.0, "power.md §11.4 item 1"),
    ("C300", "U10", 3.5, "power.md §11.5 item 1"),
    ("C301", "U10", 3.5, "power.md §11.5 item 1"),
    ("C205", "U1", 5.0, "battery.md §10.14 -- bq25896.pdf pin 22: the REGN "
                      "cap \"should be placed close to the IC\"; it feeds the "
                      "low-side gate driver and the bootstrap diode at 1.5 MHz"),
    ("C200", "U1", 5.0, "battery.md §11.1 -- C1's ground must land on PGND at the pin"),
    ("C201", "U1", 5.0, "battery.md §11.2 item 1 -- the PMID->SW->PGND hot loop"),
    ("C202", "U1", 5.0, "battery.md §11.2 item 4 -- BTST is a high-dV/dt loop on SW"),
    ("U202", "J1", 8.0, "battery.md §11.2 item 6 -- ESD is stopped where it enters"),
    ("R806", "U700", 8.0, "fpga.md §11.2 -- RZQ close to the FPGA, direct via to ground"),
    ("R802", "U800", 8.0, "fpga.md §11.2 -- ZQ is the DRAM's reference, not the FPGA's"),
    ("C918", "X900", 4.0, "fpga.md §11.4 -- at the oscillator's supply pin"),
    ("R903", "X900", 6.0, "fpga.md §11.4 -- series termination at the SOURCE end"),
    ("D1300", "U1300", 4.0, "frontlight.md §9 -- SW->D34->C515 is a 28.5 V 1 MHz loop"),
    ("C1301", "U1300", 5.0, "frontlight.md §9"),
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
    "PWR": (15, "every rail except GND -- see HIGH_CURRENT for why GND left"),
}


# --- 7. the nets that actually carry current ----------------------------------
# ⚠ This is NOT "every segment must meet its net class width", which was the
# first idea and was wrong. GND killed it: GND sits in PWR for its via size, but
# almost every GND segment is a 0.2 mm stub from a pad to a stitching via, and
# the current path is the In1.Cu plane, not the trace. Flagging those is noise,
# and a noisy check gets switched off -- taking the real findings with it.
#
# So the rule is inverted: only nets where a document states a current, with the
# width that current needs. Working figure is IPC-2152, 1 oz outer copper, 20 C
# rise, which lands near 0.5 mm per amp in this range -- deliberately rounded
# DOWN to a floor, because a trace that passes here is merely not a fire risk.
# Thermal design is still the doc's job.
#
# A net not listed here is not thereby unimportant; it is a net nobody has put a
# number on. Add it with its source when someone does.
HIGH_CURRENT = {
    "Net-(U12-SW)": (0.6, "boost inductor current: ~2.8 A avg, 3.4 A peak. "
                          "power.md §3.2 and §11.2 -- and TI §10.1 wants this "
                          "node SHORT as well as fat, so widen, do not pour"),
    "+VSYS": (0.6, "up to ~2.8 A into the boost alone. power.md §11.6 item 1 "
                   "calls it a plane, not a trace -- this floor is for the "
                   "stubs off it"),
    "+VBAT": (0.6, "full charge AND discharge current; charger runs 1.5 A in. "
                   "battery.md §11 item 8: 'give it real copper'"),
    "+VBUS": (0.5, "USB-C input, 1.5 A at the charger. battery.md §11 item 10"),
    "+5V_DCDC": (0.5, "SoM VIN design bound 1.0 A plus an EPD refresh, and "
                      "they coincide. power.md §8.1"),
    "+5V_SOM": (0.5, "same rail past the shunt. power.md §8.1"),
    "Net-(U13-L1)": (0.5, "TPS63802 buck-boost switch node, 2 A part, L11 "
                          "rated 7.4 A Isat. power.md §11.3 item 1"),
    "Net-(U13-L2)": (0.5, "the buck-boost's SECOND switch node -- both are "
                          "aggressors. power.md §11.3 item 1"),
    "Net-(U14-SW)": (0.4, "TPS62A02 buck, 2 A part. power.md §11.4 item 1"),
    "Net-(U15-SW)": (0.4, "TPS62A02 buck, 2 A part. power.md §11.4 item 1"),
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
    #
    # ⚠ This used to grep for `(net_name "...")`. A KiCad 10 .kicad_pcb writes
    # `(net "GND")` on a zone -- the bare net NAME, not the number, and not
    # `net_name` -- so the old pattern matched nothing and this check reported
    # "0 distinct nets have zones" with three zones on the board. Same failure
    # mode as check 5 had. If you touch this, verify against the file, not
    # against what the S-expression looks like it should be.
    print("\n4. nets that must not carry a zone:")
    # The terminator is a LOOKAHEAD on purpose. Zones sit back-to-back, so a
    # consuming `\n\t\)\n` eats the newline that the next zone's `\n\t\(zone`
    # needs and every second zone vanishes -- that is how the SW pour went
    # unreported here while sitting in the file.
    zblocks = re.findall(r'\n\t\(zone\n([\s\S]*?)(?=\n\t\)\n)', text)
    zones = []
    for b in zblocks:
        n = re.search(r'\(net "([^"]*)"\)', b)
        lyr = re.search(r'\(layers? "([^"]+)"\)', b)
        nm = re.search(r'\(name "([^"]*)"\)', b)
        zones.append((n.group(1) if n else "", lyr.group(1) if lyr else "?",
                      nm.group(1) if nm else ""))
    names = [z[0] for z in zones]
    for net, why in NO_ZONE_NETS.items():
        if net in names:
            fail.append(f"there is a copper zone on {net!r} -- {why}")
    print(f"   {len(zones)} zones on {len(set(names))} distinct nets; "
          f"{sum(1 for n in NO_ZONE_NETS if n in names)} of them must not")
    for net, lyr, nm in zones:
        tag = f"  [{nm}]" if nm else ""
        print(f"     {lyr:<8} {net}{tag}")
    # A zone whose stored name does not mention its own net is usually a
    # copy-paste of another pour; harmless in copper, misleading to read.
    for net, lyr, nm in zones:
        if nm and net and net.split("-")[0].strip("+") not in nm:
            warn.append(f"zone on {net!r} ({lyr}) is still named {nm!r} -- "
                        f"looks copied from another pour; rename it")

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

    # 7. current-carrying nets
    print("\n7. nets with a stated current:")
    widths = {}
    for m in re.finditer(r"\n\t\(segment\b", text):
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
        n = re.search(r'\(net "([^"]*)"\)', blk)
        w = re.search(r"\(width ([\d.]+)\)", blk)
        if n and w:
            widths.setdefault(n.group(1), []).append(float(w.group(1)))
    routed = [k for k in HIGH_CURRENT if k in widths]
    for net in routed:
        floor, why = HIGH_CURRENT[net]
        thin = [w for w in widths[net] if w < floor - 1e-9]
        if thin:
            fail.append(f"{net} has {len(thin)} of {len(widths[net])} segments "
                        f"below {floor} mm (narrowest {min(thin)}) -- {why}")
    print(f"   {len(routed)} of {len(HIGH_CURRENT)} listed nets are routed; "
          f"{sum(1 for n in routed if min(widths[n]) < HIGH_CURRENT[n][0] - 1e-9)}"
          f" too thin somewhere")
    print("   (GND is absent on purpose -- its path is the In1.Cu plane, not "
          "its traces)")

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
