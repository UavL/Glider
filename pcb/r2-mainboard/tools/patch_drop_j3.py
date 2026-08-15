#!/usr/bin/env python3
"""Delete `J3`, the 16-pin panel connector, and the ten dead nets it carried.

Decision by the hardware owner, 2026-08-15, answering `docs/fpga.md` review
question 2: "Yes, delete J3 connector."

**Why it existed.** Glider is a general-purpose EPD monitor, not a reader.
README "Screen Adapters": *"The motherboard uses a 50pin + 16pin connector. A
single 50pin connector is enough for 8/16-bit screens, the 16 pin connector
additionally adds support for LVDS screens and 32-bit/64-bit screens."* README
"LVDS": the panels that need it are *"higher resolution panels (such as 25.3"
ones, and 11.8" Gallery 3)"*. In the screen list every MiniLVDS entry is 8"
1920x1440 or larger; every 6" 1448x1072 panel -- the whole `ED060*`/`EC060*`
family -- is `TTL`, 34 pins, adapter `34P-A`. So `J3` is the large-panel and
colour-Gallery option, and R2 is a 6" reader.

**Why it is dead in R2 specifically**, which is the stronger argument and does
not depend on the panel choice. `tools/check_ucf.py` reports every FPGA ball the
board wires that no `.ucf` line assigns. All ten of `J3`'s signal pins are on
that list, from two separate causes (`docs/fpga.md` §2.1):

  * `EPDC_D8`-`D11` -- `EPD_SD` is 16 bits in every build variant
    (`caster.v:946-1002`, `top.v:827`) and the UCF maps those 16 to panel pairs
    D0-D7 only. There is no gateware for pairs 8-11 in any variant.
  * `EPDC_CLKP`/`CLKN` -- there is no `EPD_CLK` port in `top.v` and no `EPD_CLK`
    line in the UCF. The gateware's only panel clock is `EPD_SDCLK`, which the
    board calls `EPDC_SE_CLK` and routes on `J6`.

So this is not "unpopulated for now". Nothing in Caster could drive these pins
if the connector were fitted.

What goes, exactly, from the exported netlist rather than from the drawing:

    /EPDC_D8P  J3.15 U41.C7      /EPDC_D10P J3.9  U41.A8
    /EPDC_D8N  J3.14 U41.A7      /EPDC_D10N J3.8  U41.B8
    /EPDC_D9P  J3.12 U41.E7      /EPDC_D11P J3.6  U41.A9
    /EPDC_D9N  J3.11 U41.E8      /EPDC_D11N J3.5  U41.C9
    /EPDC_CLKP J3.3  U41.C8      /EPDC_CLKN J3.2  U41.D8
    GND        J3.{1,4,7,10,13,16}, J3.MP

Ten nets disappear entirely; `GND` loses seven nodes. Every other net on both
sheets is untouched, which `--verify` asserts against a netlist taken before the
patch.

The ten freed balls are all in bank 0 (`VCCO` = 3.3 V) and get no-connect flags,
per the sheet convention. With the 12 flagged when the FMC bus went, R2 now has
22 flagged spare balls -- the largest block of free FPGA I/O on the board, and
worth knowing before someone adds a feature. `docs/fpga.md` §3 records it.

**This touches two frozen sheets.** `epd` was reviewed and accepted as a 1:1
port in WP4, `fpga_io` in WP5, so neither may be regenerated -- both are patched
surgically here. `port_r1.py`'s `HIER` keeps the ten names (a `--force` re-port
must still reproduce R1 faithfully) and grows a `DEAD_ON_R2` set that the
sheet-pin list subtracts; re-porting either sheet now prints a warning telling
the operator to re-run this script.
"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from port_r1 import DEAD_ON_R2, HIER  # noqa: E402
from sheet_pins import set_sheet_pins  # noqa: E402

PROJ = HERE.parent
ROOT = PROJ / "r2.kicad_sch"
EPD = PROJ / "epd.kicad_sch"
FIO = PROJ / "fpga_io.kicad_sch"
KICAD_CLI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/bin/kicad-cli"

# --- epd.kicad_sch, the J3 side -------------------------------------------
# J3 sits at (208.28, 81.28); its sixteen pins run left to x=203.2 on a 2.54
# pitch from y=63.5 to y=101.6, and the mounting pin is at y=106.68.
EPD_LABEL_X = 185.42            # where the hierarchical labels sit
EPD_PIN_X = 203.2               # J3's pin ends
EPD_SIGNALS = {                 # label name -> y
    "EPDC_CLKN": 66.04, "EPDC_CLKP": 68.58,
    "EPDC_D11N": 73.66, "EPDC_D11P": 76.2,
    "EPDC_D10N": 81.28, "EPDC_D10P": 83.82,
    "EPDC_D9N": 88.9, "EPDC_D9P": 91.44,
    "EPDC_D8N": 96.52, "EPDC_D8P": 99.06,
}
EPD_GND_BUS_X = 200.66
EPD_GND_YS = (63.5, 71.12, 78.74, 86.36, 93.98, 101.6)
# y=63.5 is the top end of the bus, so it is a corner and carries no junction
# dot; every other stub is a tee and does.
EPD_GND_TEE_YS = EPD_GND_YS[1:]
EPD_MP_Y = 106.68
EPD_GND_SYM = "#PWR0201"

# --- fpga_io.kicad_sch, the FPGA side --------------------------------------
# U41 unit 1 at (195.58, 93.98); these ten balls stub right to x=218.44.
FIO_BALL_X = 213.36
FIO_LABEL_X = 218.44
FIO_SIGNALS = {                 # label name -> (y, ball)
    "EPDC_D8P": (73.66, "C7"), "EPDC_D8N": (76.2, "A7"),
    "EPDC_D10N": (83.82, "B8"), "EPDC_D10P": (86.36, "A8"),
    "EPDC_D11N": (88.9, "C9"), "EPDC_D11P": (91.44, "A9"),
    "EPDC_D9P": (99.06, "E7"), "EPDC_D9N": (101.6, "E8"),
    "EPDC_CLKN": (109.22, "D8"), "EPDC_CLKP": (111.76, "C8"),
}


def _fmt(v):
    """KiCad writes 203.2 not 203.20, and 63.5 not 63.500."""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def drop_wire(t, x1, y1, x2, y2):
    for a, b, c, d in ((x1, y1, x2, y2), (x2, y2, x1, y1)):
        pat = (r'\n\t\(wire\n\t\t\(pts\n\t\t\t\(xy %s %s\) \(xy %s %s\)\n\t\t\)\n'
               r'\t\t\(stroke\n\t\t\t\(width 0\)\n\t\t\t\(type default\)\n\t\t\)\n'
               r'\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
               % tuple(re.escape(_fmt(v)) for v in (a, b, c, d)))
        new, n = re.subn(pat, "\n", t, count=1)
        if n:
            return new
    raise AssertionError(f"wire ({x1},{y1})-({x2},{y2}) not found")


def drop_symbol(t, ref):
    for m in re.finditer(r"\n\t\(symbol\n", t):
        s = m.start()
        e = t.index("\n\t)\n", s) + 3
        if re.search(r'\(property "Reference" "%s"' % re.escape(ref), t[s:e]):
            return t[:s] + t[e:]
    raise KeyError(ref)


def drop_junction(t, x, y):
    pat = (r'\n\t\(junction\n\t\t\(at %s %s\)\n\t\t\(diameter [-\d.]+\)\n'
           r'\t\t\(color \d+ \d+ \d+ \d+\)\n\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
           % (re.escape(_fmt(x)), re.escape(_fmt(y))))
    new, n = re.subn(pat, "\n", t, count=1)
    assert n == 1, f"junction at ({x},{y}) not found"
    return new


def drop_hlabel(t, name):
    """Delete one hierarchical_label block by name. Asserts it is unique."""
    hits = [m.start() for m in
            re.finditer(r'\n\t\(hierarchical_label "%s"\n' % re.escape(name), t)]
    assert len(hits) == 1, f"{name}: expected 1 hierarchical label, found {len(hits)}"
    s = hits[0]
    e = t.index("\n\t)\n", s) + 3
    return t[:s] + t[e:]


def add_nc(t, x, y):
    import uuid
    blk = (f"\n\t(no_connect\n\t\t(at {_fmt(x)} {_fmt(y)})\n"
           f'\t\t(uuid "{uuid.uuid4()}")\n\t)')
    assert t.endswith(")\n")
    return t[:-2] + blk + "\n)\n"


def netlist(tag):
    out = pathlib.Path(f"/tmp/j3-{tag}.net")
    subprocess.run([str(KICAD_CLI), "sch", "export", "netlist",
                    "--format", "kicadsexpr", "-o", str(out), str(ROOT)],
                   check=True, capture_output=True)
    t = out.read_text()
    nets = {}
    for m in re.finditer(r'\(net\n\t+\(code "\d+"\)\n\t+\(name "([^"]*)"\)', t):
        a = m.start()
        depth, j, ins = 0, a, False
        while True:
            c = t[j]
            if c == '"' and t[j - 1] != "\\":
                ins = not ins
            elif not ins:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        nets[m.group(1)] = frozenset(
            re.findall(r'\(ref "([^"]+)"\)\n\t+\(pin "([^"]+)"\)', t[a:j + 1]))
    return nets


def patch_epd():
    t = EPD.read_text()
    assert '"J3"' in t, "already patched (no J3 on epd)"
    for name, y in EPD_SIGNALS.items():
        t = drop_wire(t, EPD_LABEL_X, y, EPD_PIN_X, y)
        t = drop_hlabel(t, name)
    # the ground comb: six stubs, the vertical bus between them, and the
    # mounting-pin run to the GND symbol
    for y in EPD_GND_YS:
        t = drop_wire(t, EPD_GND_BUS_X, y, EPD_PIN_X, y)
    ys = list(EPD_GND_YS) + [EPD_MP_Y]
    for a, b in zip(ys, ys[1:]):
        t = drop_wire(t, EPD_GND_BUS_X, a, EPD_GND_BUS_X, b)
    t = drop_wire(t, 208.28, EPD_MP_Y, EPD_GND_BUS_X, EPD_MP_Y)
    for y in EPD_GND_TEE_YS:
        t = drop_junction(t, EPD_GND_BUS_X, y)
    t = drop_junction(t, 208.28, EPD_MP_Y)
    t = drop_symbol(t, EPD_GND_SYM)
    t = drop_symbol(t, "J3")
    # the title-block caption claimed a pin-for-pin port, which it no longer is
    old = '"epd — panel connectors, ported from R1 pin-for-pin. See docs/epd-port.md."'
    new = ('"epd — panel connector J6, ported from R1 pin-for-pin. '
           'J3 (16p) deleted; see docs/epd-port.md."')
    assert old in t, "title-block comment 1 is not the text this patch expects"
    t = t.replace(old, new, 1)
    EPD.write_text(t)
    print(f"epd: J3, {EPD_GND_SYM}, 10 labels, 10 signal wires, "
          f"13 ground wires, {len(EPD_GND_TEE_YS) + 1} junctions removed")


def patch_fpga_io():
    t = FIO.read_text()
    assert '"EPDC_D8P"' in t, "already patched (no EPDC_D8P on fpga_io)"
    for name, (y, _ball) in FIO_SIGNALS.items():
        t = drop_wire(t, FIO_BALL_X, y, FIO_LABEL_X, y)
        t = drop_hlabel(t, name)
        t = add_nc(t, FIO_BALL_X, y)
    FIO.write_text(t)
    print(f"fpga_io: 10 labels + 10 wires removed, 10 no-connect flags added "
          f"on {' '.join(b for _, b in FIO_SIGNALS.values())}")


def main():
    assert set(EPD_SIGNALS) == set(FIO_SIGNALS) == set(DEAD_ON_R2), \
        "the three lists of dead nets disagree"

    before = netlist("before")
    patch_epd()
    patch_fpga_io()

    for stem in ("epd", "fpga_io"):
        pins = sorted({v for k, v in HIER[stem].items() if k not in DEAD_ON_R2})
        set_sheet_pins(ROOT, stem, pins)

    subprocess.run([sys.executable, str(HERE / "wire_root.py")], check=True)

    after = netlist("after")
    gone = set(before) - set(after)
    new = set(after) - set(before)
    changed = {n for n in set(before) & set(after) if before[n] != after[n]}
    expect_gone = {f"/{n}" for n in DEAD_ON_R2}
    # A no-connect flag still leaves the ball a one-pin net, which KiCad names
    # `unconnected-(<ref><unit>-<pinname>-Pad<ball>)`. Assert on the ball, not
    # on the pin-function string, so a symbol-library rename does not fail this.
    freed = {m.group(1) for m in
             (re.fullmatch(r"unconnected-\(U41A-.*-Pad(\w+)\)", n) for n in new)
             if m}
    print(f"\nnetlist: {len(before)} nets -> {len(after)}")
    assert freed == {b for _, b in FIO_SIGNALS.values()} and len(freed) == len(new), \
        f"unexpected new nets: {sorted(new)}"
    assert gone == expect_gone, f"nets gone: {sorted(gone)}"
    assert changed == {"GND"}, f"nets changed: {sorted(changed)}"
    lost = before["GND"] - after["GND"]
    assert after["GND"] < before["GND"], "GND gained nodes"
    assert all(r == "J3" for r, _ in lost), f"GND lost non-J3 nodes: {sorted(lost)}"
    print(f"  the 10 dead nets are gone, GND lost exactly its 7 J3 nodes, "
          f"and no other net on the board moved")


if __name__ == "__main__":
    main()
