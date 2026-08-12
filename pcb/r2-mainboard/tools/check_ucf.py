#!/usr/bin/env python3
"""Cross-check the R2 schematic against Caster's own pin constraints.

Why this exists
---------------
The FPGA's pinout is not a design choice -- it is fixed by Caster's
`constraint.ucf`, and most of it is fixed harder than that by the silicon: the
48 DDR pins are bonded to the MCB3 hard macro, the configuration pins are
dedicated, `VCCO` is per bank, and clock inputs must land on `GCLK` balls. A
single swapped ball is fatal and, crucially, **invisible to ERC** -- the
schematic is perfectly legal, it just no longer matches the gateware.

Two things went wrong during WP5 that ERC did not notice and a netlist
comparison did:

  * `fpga_io`'s sheet box grew past `epd_power`'s on the root, so seven FPGA
    balls silently shorted to `VCOM_MEA_EN`, `SHDN` and friends;
  * five DDR decoupling capacitors ported across still attached to `+1V35`,
    a rail that had already been renamed to `+1V5`.

So this script asserts, ball by ball, that the schematic connects what the
gateware expects, and reports the two interesting asymmetries in both
directions: pins the gateware constrains but the board leaves unconnected, and
pins the board wires up but the gateware never assigns.

It is deliberately noisy about what it cannot check yet: units of the FPGA
symbol that no sheet has placed are reported as pending, not as failures.

Usage
-----
    python3 tools/check_ucf.py            # exports a netlist and checks it
    python3 tools/check_ucf.py some.net   # checks an existing netlist
Exit status is non-zero if any assertion fails.
"""
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent
REPO = PROJ.parent.parent
UCF = REPO / "Caster/rtl/spartan6/constraint.ucf"
SYMS = PROJ.parent / "pcb_common/symbols.kicad_sym"
KICAD_CLI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/bin/kicad-cli"

FPGA_REF = "U41"
SYMBOL = "XC6SLX-FTG256"

# Which sheet holds which unit of the symbol, for reporting what is not drawn.
UNIT_SHEET = {1: "fpga_io", 2: "fpga_io", 3: "fpga_config", 4: "fpga_ddr",
              5: "fpga_config", 6: "(unassigned -- was power.kicad_sch on R1)"}

# VCCO each bank must be at, and what each IOSTANDARD needs. Bank voltages come
# from docs/power.md; the IOSTANDARD figures from ds162.pdf Table 7 and Table 8.
BANK_RAIL = {0: "+3V3", 1: "+3V3", 2: "+3V3", 3: "+1V5"}
IOSTD_VOLTS = {
    "LVCMOS33": "+3V3", "LVDS_33": "+3V3",
    "LVCMOS15": "+1V5", "SSTL15_II": "+1V5", "DIFF_SSTL15_II": "+1V5",
}

# UCF port name -> schematic net name, for the cases the UCF's own trailing
# comments do not give us. Everything else is derived: `EPD_SD[n]` and
# `DPI_PIXEL[n]` carry a comment naming the board signal (`# D0P`, `# B2`).
EXPLICIT = {
    "CLK_IN": "FPGA_CLK33",
    "SPI_SCK": "FPGA_SCLK", "SPI_MOSI": "FPGA_MOSI",
    "SPI_MISO": "FPGA_MISO", "SPI_CS": "FPGA_CS",
    "DPI_HSYNC": "DPI_HS", "DPI_VSYNC": "DPI_VS",
    "DPI_PCLK": "DPI_PCLK", "DPI_DE": "DPI_DE",
    "LED": "LED",
    # The one irregular EPD name: the gateware calls the source-driver clock
    # SDCLK, the board has always called it SE_CLK.
    "EPD_SDCLK": "EPDC_SE_CLK",
    **{f"EPD_{s}": f"EPDC_{s}" for s in ("GDCLK", "GDOE", "GDSP", "SDCE0",
                                         "SDLE", "SDOE")},
}

# Ports the board deliberately does not connect, with the reason. Anything here
# is expected to be unconnected in the schematic; anything unconnected and *not*
# here is a finding.
INTENTIONALLY_UNCONNECTED = {
    **{n: "FPD-Link input: R2 deletes the PTN3460 that drove it, and the "
          "constraint is being removed from the UCF (docs/fpga.md)"
       for n in ("LVDS_ODD_CK_P", "LVDS_ODD_CK_N")},
}


def _bank(pin_name: str):
    """Bank number from the ball's own pin name, e.g. IO_L1P_CCLK_2 -> 2."""
    m = re.search(r"_(\d)$", pin_name)
    return int(m.group(1)) if m else None


def parse_ucf(text: str):
    """-> ({port: {loc, iostd, comment}}, [commented-out alternatives])"""
    live, alts = {}, []
    for raw in text.splitlines():
        line = raw.strip()
        commented = line.startswith("#")
        body = line.lstrip("#").strip()
        m = re.match(r'NET\s+"([^"]+)"\s+(LOC|IOSTANDARD)\s*=\s*"?([A-Za-z0-9_]+)"?\s*;'
                     r'\s*(?:#\s*(.*))?$', body)
        if not m:
            continue
        port, key, val, comment = m.group(1), m.group(2), m.group(3), m.group(4)
        if "/" in port:                      # an internal net, not a top-level port
            continue
        if commented:
            if key == "LOC":
                alts.append((port, val))
            continue
        e = live.setdefault(port, {})
        e[key.lower()] = val
        if comment:
            e["comment"] = comment.strip()
    return live, alts


def parse_symbol():
    """-> {ball: (pin_name, unit)} for the FPGA symbol."""
    t = SYMS.read_text()
    i = t.index(f'(symbol "{SYMBOL}"')
    depth, j = 0, i
    while True:
        if t[j] == "(":
            depth += 1
        elif t[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    body, out = t[i:j], {}
    for m in re.finditer(rf'\(symbol "{SYMBOL}_(\d+)_\d+"', body):
        unit, s = int(m.group(1)), m.start()
        d, k = 0, s
        while True:
            if body[k] == "(":
                d += 1
            elif body[k] == ")":
                d -= 1
                if d == 0:
                    break
            k += 1
        for pm in re.finditer(r'\(name "([^"]+)"[\s\S]{0,140}?\(number "([^"]+)"',
                              body[s:k]):
            out[pm.group(2)] = (pm.group(1), unit)
    return out


def parse_netlist(path: pathlib.Path):
    """-> ({ball: net}, {net: {nodes}}) for the FPGA reference."""
    t = path.read_text()
    ball2net, nets = {}, {}
    for m in re.finditer(r'\(net\s+\(code "\d+"\)\s+\(name "([^"]*)"\)', t):
        name, i = m.group(1), m.start()
        d = 0
        while True:
            if t[i] == "(":
                d += 1
            elif t[i] == ")":
                d -= 1
                if d == 0:
                    break
            i += 1
        body = t[m.start():i]
        nodes = set()
        for n in re.finditer(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', body):
            nodes.add(f"{n.group(1)}.{n.group(2)}")
            if n.group(1) == FPGA_REF:
                ball2net[n.group(2)] = name
        nets[name] = nodes
    return ball2net, nets


def expected_net(port: str, info: dict):
    if port in EXPLICIT:
        return EXPLICIT[port]
    c = info.get("comment")
    if re.fullmatch(r"EPD_SD\[\d+\]", port) and c:
        return f"EPDC_{c}"
    if re.fullmatch(r"DPI_PIXEL\[\d+\]", port) and c:
        return f"DPI_{c}"
    return None                              # DDR_*, LVDS_* and anything new


def main() -> int:
    if not UCF.exists():
        print(f"FAIL: {UCF} missing -- is the Caster submodule checked out?")
        return 2

    if len(sys.argv) > 1:
        net_path = pathlib.Path(sys.argv[1])
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".net", delete=False)
        tmp.close()
        net_path = pathlib.Path(tmp.name)
        subprocess.run([str(KICAD_CLI), "sch", "export", "netlist", "--format",
                        "kicadsexpr", "-o", str(net_path),
                        str(PROJ / "r2.kicad_sch")],
                       check=True, capture_output=True)

    ucf, alts = parse_ucf(UCF.read_text())
    sym = parse_symbol()
    ball2net, nets = parse_netlist(net_path)

    placed_units = {u for (_, u) in (sym[b] for b in ball2net if b in sym)}
    bad, pending, notes = [], [], []

    # --- 1. every constrained ball carries the net the gateware expects ------
    checked = 0
    for port, info in sorted(ucf.items()):
        loc = info.get("loc")
        if not loc:
            continue
        if loc not in sym:
            bad.append(f"{port}: LOC {loc} is not a ball on {SYMBOL}")
            continue
        pin_name, unit = sym[loc]
        if unit not in placed_units:
            pending.append(f"{port:<16} {loc:<5} unit {unit} "
                           f"({UNIT_SHEET.get(unit, '?')}) not drawn yet")
            continue
        got = ball2net.get(loc, "<absent>")
        want = expected_net(port, info)
        if port in INTENTIONALLY_UNCONNECTED:
            if not got.startswith("unconnected-"):
                bad.append(f"{port}: expected no board connection on {loc}, "
                           f"found {got}")
            continue
        if want is None:
            notes.append(f"{port:<16} {loc:<5} -> {got}   (no expected-name rule)")
            continue
        leaf = got.split("/")[-1]
        if leaf == want:
            checked += 1
        else:
            bad.append(f"{port}: {loc} should be {want!r}, schematic has "
                       f"{got!r}  [{pin_name}]")

        # --- 2. bank voltage must suit the IOSTANDARD -----------------------
        iostd = info.get("iostandard")
        b = _bank(pin_name)
        if iostd and b is not None:
            need = IOSTD_VOLTS.get(iostd)
            if need and BANK_RAIL.get(b) != need:
                bad.append(f"{port}: {iostd} on {loc} needs VCCO {need}, but "
                           f"bank {b} is {BANK_RAIL.get(b)}")

    # --- 3. balls the board wires but the gateware never assigns ------------
    # Three quite different things end up here, and only the third is a finding:
    # dedicated config/JTAG pins (which never appear in a .ucf), the alternative
    # CLK_IN location the UCF keeps commented out, and genuine reserved-but-
    # undriven signals.
    DEDICATED = re.compile(
        r"^(TMS|TDI|TCK|TDO|DONE|SUSPEND|PROGRAM_B|AWAKE)"
        r"|(INIT_B|CSO_B|CMPCS_B|_M0_|_M1_|_M1$|CMPMISO|CMPMOSI|CMPCLK)")
    constrained = {i["loc"] for i in ucf.values() if i.get("loc")}
    alt_locs = {l for _, l in alts}
    board_only, expected_extra = [], []
    for ball, net in sorted(ball2net.items()):
        if ball in constrained or net.startswith("unconnected-"):
            continue
        pin_name, unit = sym.get(ball, ("?", None))
        if re.match(r"(VCCO|VCCINT|VCCAUX|GND|VSS|VBATT|VFS)", pin_name):
            continue
        row = f"{ball:<5} {net.split('/')[-1]:<20} {pin_name}"
        if DEDICATED.search(pin_name):
            expected_extra.append(row + "   dedicated config/JTAG pin")
        elif ball in alt_locs:
            expected_extra.append(row + "   UCF's commented-out alternative")
        else:
            board_only.append(row)

    # --- report -------------------------------------------------------------
    print(f"UCF: {UCF.relative_to(REPO)}")
    print(f"  top-level ports with a LOC : {len(constrained)}")
    print(f"  commented-out alternatives : {len(alts)}"
          + (f"  ({', '.join(f'{p}->{l}' for p, l in alts)})" if alts else ""))
    print(f"  FPGA units placed          : {sorted(placed_units)}")
    print()
    print(f"MATCHED  {checked} balls carry exactly the net the gateware expects")
    print(f"PENDING  {len(pending)} balls on units not yet drawn")
    print(f"NOTES    {len(notes)} balls with no expected-name rule")
    print(f"FAILURES {len(bad)}")
    print()
    for b in bad:
        print(f"  FAIL  {b}")
    if board_only:
        print(f"\n  RESERVED BUT NOT DRIVEN -- {len(board_only)} balls the board wires"
              f" and no .ucf assigns.")
        print("  Not errors, but each one is a signal nothing in the gateware"
              " implements:")
        for b in board_only:
            print(f"        {b}")
    if expected_extra:
        print(f"\n  Expected extras ({len(expected_extra)}):")
        for b in expected_extra:
            print(f"        {b}")
    if pending:
        print(f"\n  Pending ({len(pending)}):")
        for p in pending[:6]:
            print(f"        {p}")
        if len(pending) > 6:
            print(f"        ... and {len(pending) - 6} more")
    if notes:
        print(f"\n  No expected-name rule ({len(notes)}):")
        for n in notes[:6]:
            print(f"        {n}")
        if len(notes) > 6:
            print(f"        ... and {len(notes) - 6} more")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
