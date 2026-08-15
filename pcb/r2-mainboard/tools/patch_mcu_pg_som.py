#!/usr/bin/env python3
"""Claim `PC8` for `PG_SOM`, the module's power-good, on mcu.kicad_sch.

`mcu.md` §9 has owed this since `power.md` §5.1 was corrected on 2026-08-15.
`som.kicad_sch` now declares `PG_SOM` at its end (`X1 C54`, `X_PGOOD`), so
without this the net is the project's last one-sided interface.

**Why the MCU has to see it.** `L-1038e.A5` §5.4 makes it *mandatory* that
nothing drives the SOM's I/O before the module is powered, and `+3V3` is `VCCO`
for the FPGA bank carrying the 22 DPI lines into it. So `+3V3` must come up
*after* the module, gated on the module's own power-good -- and since R2 has no
hardware interlock (a deliberate choice, `power.md` §5.1), firmware is what
does the gating and firmware needs the pin.

    1  SOM_RESET# low          2  MCU_EN_5V        3  wait PG_SOM
    4  MCU_EN_3V3 + PG_3V3     5  release SOM_RESET#

**`PC8` is a plain GPIO**, chosen over the ADC-capable spares (`PC4`, `PC5`,
`PB12`, and `PA11`/`PA12` which are the USB-capable pair) so those stay
available for analogue. Nine spares remain after this.

**Firmware must enable the internal pull-down.** `X_PGOOD` is open-drain with
its pull-up on the *module's* own 3.3 V rail, so while the SoM is unpowered --
which is exactly when firmware is deciding whether to bring `+3V3` up -- the net
floats. A pull-down makes "no SoM" read as "not good" rather than as noise, and
it is the safe direction electrically: it sinks, it never injects into an
unpowered pin. No external resistor, so this is a one-line firmware
requirement, recorded in `mcu.md` §9 as well as here.

The sheet is reviewed and committed, so this is surgical: delete one no-connect
flag, add one stub and one hierarchical label. Nothing else moves.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402
from sheet_pins import set_sheet_pins  # noqa: E402

PROJ = HERE.parent
SCH = PROJ / "mcu.kicad_sch"

# STM32G0B1RCTx pad 48 = PC8, read off the placed symbol rather than assumed.
PC8 = (124.46, 172.72)
# The left-hand local-label column this sheet already uses (21 labels on it).
LABEL_X = 114.30
NET = "PG_SOM"


def drop_nc(t, x, y):
    pat = (r'\n\t\(no_connect\n\t\t\(at %s %s\)\n\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
           % (re.escape(f"{x:g}"), re.escape(f"{y:g}")))
    new, n = re.subn(pat, "\n", t, count=1)
    assert n == 1, f"no_connect at ({x},{y}) not found"
    return new


def splice(target: str, new: str) -> str:
    """Append `new`'s body to `target`, merging lib_symbols."""
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


def build() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["mcu"], root_uuid, "r2", paper="A3", pwr_base=900)
    s.wire(PC8, (LABEL_X, PC8[1]))
    # A *hierarchical* label, not a local one. Most nets on this sheet fan to a
    # local label and meet a hierarchical label of the same name in one of the
    # three interface columns on the right; PG_SOM has no reason to cross the
    # page, so it takes the shape FPGA_INIT already uses on this same column --
    # a hierarchical label directly at the pin. A local label here would leave
    # the root's sheet pin with nothing to match and ERC would say
    # `hier_label_mismatch`, which is exactly what the first attempt did.
    s.hlabel(LABEL_X, PC8[1], NET, shape="input", rot=180)
    return s.render()


def main() -> int:
    t = SCH.read_text()
    assert f'"{NET}"' not in t, f"already patched ({NET} present)"
    t = drop_nc(t, *PC8)
    SCH.write_text(splice(t, build()))

    # The label alone does not leave the sheet; the interface needs the pin too.
    # Read the live pin list off the root rather than off a generator's table --
    # `mcu` is not in port_r1.HIER (it was generated, not ported) and gen_mcu's
    # own list predates the J20 and FPGA_INIT patches.
    from sheet_pins import _sheet_span
    root = PROJ / "r2.kicad_sch"
    text = root.read_text()
    a, b = _sheet_span(text, "mcu")
    have = re.findall(r'\t\t\(pin "([^"]+)" (\w+)\n', text[a:b])
    assert have, "no sheet pins found on the root's mcu box"
    pins = sorted(set(have) | {(NET, "input")})
    # Idempotent on the root: the sheet-level guard above is what refuses a
    # double patch, and re-running after `git checkout mcu.kicad_sch` must not
    # trip over a sheet pin the previous run left behind.
    added = len(pins) - len(have)
    set_sheet_pins(root, "mcu", pins)
    print(f"mcu: PC8 no-connect removed, {NET} wired to the x={LABEL_X} column, "
          f"sheet interface now {len(pins)} pins ({added} added)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
