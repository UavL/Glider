#!/usr/bin/env python3
"""Wire the NOR's IO2/IO3 to the FPGA, so x4 boot stays a software change.

Decision by the hardware owner, 2026-08-13.

The config NOR exists to cut resume latency: R1 reloads the bitstream from the
MCU's SPIFFS on every wake and measures 360-400 ms doing it, and `+1V2_FPGA` is
off in standby so that happens every time. Self-boot only pays if it is faster,
and how much faster is set by two things -- the configuration clock rate and the
SPI bus width. Bus width is the one with a board cost, and it is nearly free to
provide now and a respin to add later.

The arithmetic, from sources rather than memory:

    bitstream                3,731,264 bits   UG380 Table 5-5, XC6SLX16
    max master CCLK          40 MHz           DS162, FMCCK, -3 speed grade
    master CCLK tolerance    +-50%            DS162, FMCCKTOL

    x1 @ ConfigRate 2 (today) 1866 ms typ   <- 5x WORSE than R1
    x1 @ ConfigRate 22         170 ms typ   (339 ms worst case)
    x4 @ ConfigRate 22          42 ms typ   ( 85 ms worst case)

UG380 Figure 2-13 gives the x4 connection. Everything in it is already wired
except the top two rows:

    Spartan-6                     W25Q128JVS
    CCLK          R11   ------->  CLK        already
    CSO_B         T3    ------->  CS#        already
    MOSI/MISO[0]  T10   ------->  DI/IO0     already
    DIN/MISO[1]   P10   <-------  DO/IO1     already
    MISO[2]       N12   <----->   WP#/IO2    this patch
    MISO[3]       P12   <----->   HOLD#/IO3  this patch

`N12` and `P12` were spare, no-connect flagged, and no `.ucf` assigns them --
they are dedicated configuration pins, which is why no constraint file ever
names them. On the NOR side, pins 3 and 7 were tied hard to `+3V3`, which is
correct for x1 and wrong for x4. Figure 2-13 note 4: "These two pins also
require pull-ups to VCCO_2." So the hard tie becomes `R412`/`R413`, 10k to
`+3V3`, which is `VCCO_2`.

This changes nothing about how the board behaves today. In x1 the FPGA leaves
both pins alone and the pull-ups hold `WP#`/`HOLD#` high exactly as the hard tie
did. Two consequences to carry into the gateware, both recorded in
docs/fpga.md rather than fixed here because they are not schematic changes:

  * `-g UnusedPin:PullDown` would, after configuration, pull `N12`/`P12` against
    the new 10k pull-ups and sit `WP#`/`HOLD#` near mid-rail. Harmless while the
    NOR is idle, and harmless during a SoM-driven NOR write (`PROG#` low
    tri-states the FPGA and the pull-ups win), but it should be made explicit
    with a `PULLUP` constraint on those two balls rather than left to chance.
  * x4 needs the flash's QE bit set -- UG380 Figure 2-13 note 3 -- plus
    `-g spi_buswidth:4`.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402

PROJ = HERE.parent
SCH = PROJ / "fpga_config.kicad_sch"
KI = pathlib.Path.home() / "Apps/kicad-10.0.4/usr/share/kicad/symbols"

# FPGA balls, from unit 3 at (63.5, 99.06); read off the symbol, not guessed.
N12 = (83.82, 71.12)     # IO_L12P_D1_MISO2_2
P12 = (83.82, 73.66)     # IO_L12N_D2_MISO3_2
LABEL_X = 101.6          # clear of the N11 ground stub two rows below

# The NOR ends: U42 pin 3 and pin 7 already run left to here, where a vertical
# wire shorted them together onto a +3V3 rail symbol.
NOR_IO2_END = (33.02, 177.8)
NOR_IO3_END = (33.02, 180.34)
OLD_JOIN = (33.02, 177.8, 33.02, 180.34)
OLD_RAIL = "#PWR271"

# The pull-ups go in the empty block in the middle of the sheet, well clear of
# U41C's pin labels (which stop at x=90.5) and U41E's box (which starts at 135.7
# but only above y=72).
PULLUPS = [("R412", "NOR_IO2", 114.3), ("R413", "NOR_IO3", 139.7)]
PU_Y = 96.52

NOTE = [
    "R412/R413 and the two nets to N12/P12 exist so that master-SPI x4 boot is",
    "a gateware change, not a respin. UG380 Fig 2-13; its note 4 requires these",
    "pull-ups to VCCO_2, which is why pins 3/7 are no longer tied hard to +3V3.",
    "Nothing changes in x1: the pull-ups hold WP#/HOLD# high as the tie did.",
    "Owed in Caster: -g ConfigRate 2 -> 22 (2 makes self-boot 1.9 s, five times",
    "slower than R1's 360-400 ms), -g Binary:no -> yes, and a PULLUP constraint",
    "on N12/P12 so -g UnusedPin:PullDown does not fight R412/R413.",
]


def drop_wire(t, x1, y1, x2, y2):
    for a, b, c, d in ((x1, y1, x2, y2), (x2, y2, x1, y1)):
        pat = (r'\n\t\(wire\n\t\t\(pts\n\t\t\t\(xy %s %s\) \(xy %s %s\)\n\t\t\)\n'
               r'\t\t\(stroke\n\t\t\t\(width 0\)\n\t\t\t\(type default\)\n\t\t\)\n'
               r'\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
               % tuple(re.escape(str(v)) for v in (a, b, c, d)))
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
           % (re.escape(str(x)), re.escape(str(y))))
    new, n = re.subn(pat, "\n", t, count=1)
    assert n == 1, f"junction at ({x},{y}) not found"
    return new


def drop_nc(t, x, y):
    pat = (r'\n\t\(no_connect\n\t\t\(at %s %s\)\n\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
           % (re.escape(str(x)), re.escape(str(y))))
    new, n = re.subn(pat, "\n", t, count=1)
    assert n == 1, f"no_connect at ({x},{y}) not found"
    return new


def build() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["fpga_config"], root_uuid, "r2", paper="A4", pwr_base=600)
    s.lib.add_dir("Device", KI / "Device.kicad_symdir")
    s.lib.add_dir("power", KI / "power.kicad_symdir")
    s.lib.add_dir("symbols", PROJ.parent / "pcb_common/symbols.kicad_sym")

    for (px, py), name in ((N12, "NOR_IO2"), (P12, "NOR_IO3")):
        s.wire((px, py), (LABEL_X, py))
        s.label(LABEL_X, py, name)

    for end, name in ((NOR_IO2_END, "NOR_IO2"), (NOR_IO3_END, "NOR_IO3")):
        s.label(end[0], end[1], name, rot=180, justify="right")

    for ref, name, x in PULLUPS:
        r = s.place("Device:R", ref, "10k", x, PU_Y,
                    footprint="Resistor_SMD:R_0402_1005Metric",
                    ref_at=(x + 2.54, PU_Y - 1.27),
                    val_at=(x + 2.54, PU_Y + 2.54), justify="left",
                    description="UG380 Fig 2-13 note 4: MISO[2]/MISO[3] need "
                                "pull-ups to VCCO_2.")
        top, bot = r.pin("1"), r.pin("2")
        s.wire(top, (x, top[1] - 3.81))
        s.power("+3V3", x, top[1] - 3.81)
        s.wire(bot, (x, bot[1] + 3.81))
        s.label(x, bot[1] + 3.81, name)

    y = 118.11
    for line in NOTE:
        s.text(101.6, y, line, size=1.27)
        y += 3.302
    assert y <= 155.0, f"note runs to y={y:.1f}, into the decoupling block"
    return s.render()


def splice(target: str, new: str) -> str:
    def libs(text):
        i = text.index("(lib_symbols")
        d, j = 0, i
        while True:
            if text[j] == "(":
                d += 1
            elif text[j] == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        return i, j + 1, text[i:j + 1]

    ti, tj, tbody = libs(target)
    _, nj, nbody = libs(new)
    have = set(re.findall(r'\(symbol "([^"]+:[^"]+)"', tbody))
    add = []
    for m in re.finditer(r'\n\t\t\(symbol "([^"]+:[^"]+)"', nbody):
        if m.group(1) in have:
            continue
        s0 = nbody.index("(", m.start())
        d, k = 0, s0
        while True:
            if nbody[k] == "(":
                d += 1
            elif nbody[k] == ")":
                d -= 1
                if d == 0:
                    break
            k += 1
        add.append("\n\t\t" + nbody[s0:k + 1])
    merged = tbody[:-1].rstrip() + "".join(add) + "\n\t)"
    out = target[:ti] + merged + target[tj:]
    body = new[nj:]
    body = body[:body.rindex("(embedded_fonts")].strip("\n")
    assert out.endswith(")\n")
    return out[:-2] + "\n" + body + "\n)\n"


def main():
    t = SCH.read_text()
    assert '"R412"' not in t, "already patched (R412 present)"

    t = drop_wire(t, *OLD_JOIN)
    t = drop_symbol(t, OLD_RAIL)
    # The vertical join left a junction dot at each end. Two collinear wire ends
    # under a dot is electrically nothing, but it draws a tee that is not there.
    t = drop_junction(t, *NOR_IO2_END)
    t = drop_junction(t, *NOR_IO3_END)
    t = drop_nc(t, *N12)
    t = drop_nc(t, *P12)

    SCH.write_text(splice(t, build()))
    print("patched fpga_config.kicad_sch: NOR IO2/IO3 reach N12/P12, "
          "R412/R413 pull-ups replace the hard tie")


if __name__ == "__main__":
    main()
