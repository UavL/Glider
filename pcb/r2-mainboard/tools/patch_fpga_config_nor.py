#!/usr/bin/env python3
"""Add the config NOR, the master-SPI strap and the INIT_B pull-up to fpga_config.

`fpga_config.kicad_sch` is a port of R1's sheet (tools/port_r1.py), which is a
*slave-serial* design: the MCU streamed the bitstream in on every boot. R2 makes
the FPGA boot itself from a SPI NOR, which is what lets the H750 become a G0 and,
more importantly, what makes resume fast -- R1 measures 360-400 ms to reload, and
`+1V2_FPGA` is off in standby, so a reload happens on every wake.

This script adds what the port cannot: new parts.

1. THE MODE STRAP.  UG380 Table 2-1: Master Serial/SPI is `M[1:0] = 01` with CCLK
   an *output*; Slave Serial is `11`.  R1 straps both mode pins high, so only M1
   moves.  `#PWR0261` on ball `N11` (`IO_L13P_M1_2`) changes from `+3V3` to
   `GND`.  UG380 also requires the mode pins be tied directly to ground or
   VCCO_2 -- not through resistors -- so this is a wire, not a pull-down.

2. THE NOR.  `W25Q128JVSIQ`, LCSC C97521, **a JLC Basic part** at $1.22, already
   scouted in NOTES-R2-hardware-facts.md.  16 Mbyte where the plan asked for 4;
   taken anyway because Basic parts carry no setup fee and the die is cheaper
   than the 4 Mbyte extended alternatives.  KiCad has both the symbol
   (`Memory_Flash:W25Q128JVS`, a derived symbol that schgen flattens) and the
   footprint (`SOIC-8_5.3x5.3mm_P1.27mm`), so nothing is authored.

   The bus is shared three ways and the direction table is the important part
   (docs/fpga.md will carry it in full):

     net            ball                configuring     running        NOR write
     NOR CLK        R11  CCLK           FPGA drives     SCK in <- SoM  SoM drives
     NOR DO         P10  DIN/MISO       FPGA reads      MOSI in <- SoM  --
     NOR DI         T10  MOSI/CSI_B     FPGA drives     MISO out -> SoM SoM drives
     NOR CS         T3   CSO_B          FPGA drives     idle high      SoM drives

   `T10` is the reassuring one: FPGA-driven in every state, so it can never
   contend.  `R11` and `P10` require the SoM to park those pins as inputs until
   `FPGA_DONE`; `R412` and `R413` bound that window if it is ever got wrong.

   **The net names look inverted and are not.** They are R1's, and they are
   host-centric: `FPGA_MOSI` is data *toward* the FPGA, so it lands on the FPGA's
   DIN pin and on the NOR's DO; `FPGA_MISO` is data *out of* the FPGA, so it
   lands on the FPGA's MOSI/CSI_B pin and drives the NOR's DI.  An on-sheet note
   says so, because this is the one thing on the sheet that reads wrong.

   `~WP` and `~HOLD` are tied high: bitgen runs `SPI_buswidth:1`, so IO2 and IO3
   are never used as data and must not float.

   `T3` (`CSO_B`) was unconnected in R1 -- the one pin master-SPI needs was
   already free -- so its no-connect flag is removed and replaced with the net.
   `R410` holds `NOR_CS#` deasserted when every driver has let go.  That matters
   because bitgen currently runs `-g UnusedPin:PullDown` and `CSO_B` is not in
   the UCF, so after configuration the FPGA would weakly hold the flash selected
   while CSR traffic clocks past it.  The agreed fix is on the gateware side
   (assign `CSO_B` and drive it high in `top.v`); `R410` is the board's backstop
   either way.

3. INIT_B.  R1 leaves it floating with no pull-up at all.  With self-boot it is
   the only signal that distinguishes a configuration error from "still loading"
   when `DONE` never arrives, so `R414` pulls it up and a hierarchical label
   carries it to the MCU.
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

# Ball coordinates on the ported sheet, read off the placed unit-3 instance.
M1_PWR_REF = "#PWR0261"          # +3V3 on ball N11, becomes GND
T3 = (83.82, 149.86)             # CSO_B, carries a no_connect from the port
# R1 labels INIT_B *and* no-connects it at the end of the same stub -- "named but
# deliberately unused". Using the pin means that flag has to go, or ERC reports
# no_connect_connected against the new pull-up.
INIT_NC = (92.71, 147.32)
NOR_CS = "NOR_CS#"


def build_new_content() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["fpga_config"], root_uuid, "r2", paper="A4", pwr_base=270)
    s.lib.add_dir("Device", KI / "Device.kicad_symdir")
    s.lib.add_dir("Memory_Flash", KI / "Memory_Flash.kicad_symdir")
    s.lib.add_dir("power", KI / "power.kicad_symdir")
    s.lib.add_dir("symbols", PROJ.parent / "pcb_common/symbols.kicad_sym")

    # ---- the NOR --------------------------------------------------------- #
    nor = s.place("Memory_Flash:W25Q128JVS", "U42", "W25Q128JVSIQ",
                  71.12, 175.26,
                  footprint="Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
                  description="16 MB SPI NOR, FPGA master-SPI boot image "
                              "(LCSC C97521, JLC Basic). x1 mode: bitgen "
                              "SPI_buswidth:1",
                  val_at=(83.82, 187.96))
    LX = 53.34                                    # label column, left of the part
    for pin, net in (("1", NOR_CS), ("6", "FPGA_SCLK"), ("5", "FPGA_MISO"),
                     ("2", "FPGA_MOSI")):
        px, py = nor.pin(pin)
        s.wire((px, py), (LX, py))
        s.label(LX, py, net, rot=180, justify="right")
    # ~WP and ~HOLD are tied high together on one stub taken well clear of the
    # label column, so neither the rail symbol nor its caption lands on a label.
    TIE = 33.02
    p3, p7 = nor.pin("3"), nor.pin("7")
    s.wire(p3, (TIE, p3[1]))
    s.wire(p7, (TIE, p7[1]))
    s.wire((TIE, p3[1]), (TIE, p7[1]))
    s.junction(TIE, p3[1])
    s.junction(TIE, p7[1])
    s.power("+3V3", TIE, p3[1])
    vx, vy = nor.pin("8")
    s.wire((vx, vy), (vx, vy - 2.54))
    s.power("+3V3", vx, vy - 2.54)
    gx, gy = nor.pin("4")
    s.wire((gx, gy), (gx, gy + 2.54))
    s.power("GND", gx, gy + 2.54)

    # decoupling, on its own stub off VCC
    c = s.place("Device:C", "C508", "100nF/16V", 86.36, 165.1,
                footprint="Capacitor_SMD:C_0402_1005Metric",
                description="NOR supply decoupling")
    s.wire((vx, vy - 2.54), (86.36, vy - 2.54), c.pin("1"))
    s.junction(vx, vy - 2.54)
    s.wire(c.pin("2"), (86.36, 171.45))
    s.power("GND", 86.36, 171.45)

    # ---- NOR_CS#: FPGA CSO_B + the SoM, with a pull-up ------------------- #
    node = (LX, nor.pin("1")[1])                  # the label column point
    pu = s.place("Device:R", "R410", "10k", 46.99, 162.56, val_at=(52.07, 161.29),
                 footprint="Resistor_SMD:R_0402_1005Metric",
                 description="NOR_CS# pull-up -- holds the flash deselected "
                             "when neither the FPGA nor the SoM drives it")
    s.wire(pu.pin("2"), (46.99, node[1]), node)
    s.junction(*node)
    s.junction(46.99, node[1])
    s.power("+3V3", *pu.pin("1"))

    ser = s.place("Device:R", "R411", "100R", 38.1, node[1], rot=90,
                  val_at=(38.1, 163.83),
                  footprint="Resistor_SMD:R_0402_1005Metric",
                  description="Series limit on the SoM's NOR chip select: the "
                              "FPGA drives CSO_B during configuration, so the "
                              "two briefly contend if software gets it wrong")
    s.wire(ser.pin("2"), node)
    s.wire((27.94, node[1]), ser.pin("1"))
    s.hlabel(27.94, node[1], "NOR_CS", shape="input", justify="right")

    # the same net reaches the FPGA's CSO_B ball, which the port left flagged
    s.wire(T3, (T3[0] + 12.7, T3[1]))
    s.label(T3[0] + 12.7, T3[1], NOR_CS)

    # ---- INIT_B ---------------------------------------------------------- #
    ip = s.place("Device:R", "R414", "4.7k", 101.6, 168.91, val_at=(93.98, 167.64),
                 footprint="Resistor_SMD:R_0402_1005Metric",
                 description="INIT_B pull-up. R1 leaves this pin floating; with "
                             "self-boot, INIT_B low is what separates a config "
                             "error from 'still loading' when DONE never comes")
    s.power("+3V3", *ip.pin("1"))
    s.wire(ip.pin("2"), (101.6, 172.72), (113.03, 172.72))
    s.label(101.6, 172.72, "FPGA_INIT")
    s.hlabel(113.03, 172.72, "FPGA_INIT", shape="output")

    # ---- the note that stops the next reader mis-reading the bus --------- #
    # The A4 frame stops at ~197.5 mm and the title block owns x >= 177,
    # y >= 164, so the note sits in the block left of it and below R414.
    for i, line in enumerate((
        "Config NOR -- the FPGA boots itself: master SPI,",
        "M[1:0]=01 (UG380 Table 2-1), CCLK an output while",
        "configuring. The net names are host-centric and only",
        "LOOK inverted: FPGA_MOSI is data toward the FPGA, so it",
        "lands on the FPGA's DIN pin and on the NOR's DO, and",
        "FPGA_MISO drives the NOR's DI. Three masters share",
        "these wires -- see docs/fpga.md for the direction table.",
    )):
        s.text(110.49, 175.26 + i * 3.302, line, size=1.05)

    return s.render()


def splice(target: str, new: str) -> str:
    """Merge a rendered scratch sheet's lib_symbols and elements into `target`."""
    # 1. lib_symbols the target does not already carry
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
    _, _, nbody = libs(new)
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

    # 2. every top-level element block from the scratch sheet
    body = new[new.index("\n", new.index("(lib_symbols")):]
    body = new[libs(new)[1]:]
    body = body[:body.rindex("(embedded_fonts")]
    body = body.strip("\n")
    assert out.endswith(")\n")
    return out[:-2] + "\n" + body + "\n)\n"


def main():
    t = SCH.read_text()
    assert '"U42"' not in t, "already patched (U42 exists)"

    # 1. M1 -> GND
    pat = re.compile(r'(\(symbol\n\t\t\(lib_id ")symbols:\+V("\)[\s\S]{0,900}?'
                     r'\(property "Reference" "%s")' % re.escape(M1_PWR_REF))
    blocks = [m for m in re.finditer(r'\n\t\(symbol\n', t)]
    done = False
    for m in blocks:
        s0 = m.start()
        e0 = t.index("\n\t)\n", s0) + 3
        blk = t[s0:e0]
        if f'"{M1_PWR_REF}"' not in blk:
            continue
        assert '"+3V3"' in blk, f"{M1_PWR_REF} is not +3V3 -- already patched?"
        nb = blk.replace('(lib_id "symbols:+V")', '(lib_id "power:GND")')
        nb = re.sub(r'(\(property "Value" ")\+3V3(")', r"\1GND\2", nb, count=1)
        nb = re.sub(r"(\(at [-\d.]+ [-\d.]+ )270(\))", r"\g<1>0\2", nb, count=1)
        t = t[:s0] + nb + t[e0:]
        done = True
        break
    assert done, f"{M1_PWR_REF} not found"

    # 2. free CSO_B
    for x, y in (T3, INIT_NC):
        nc = re.compile(r'\n\t\(no_connect\n\t\t\(at %s %s\)\n\t\t'
                        r'\(uuid "[0-9a-f-]+"\)\n\t\)\n' % (x, y))
        t, n = nc.subn("\n", t, count=1)
        assert n == 1, f"no_connect at ({x},{y}) not found"

    t = splice(t, build_new_content())
    SCH.write_text(t)
    print(f"patched {SCH.name}: M1 -> GND, CSO_B freed, NOR + pull-ups added")


if __name__ == "__main__":
    main()
