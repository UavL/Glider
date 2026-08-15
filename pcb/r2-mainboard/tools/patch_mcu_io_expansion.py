#!/usr/bin/env python3
"""Claim seven MCU pins for touch and pen, on mcu.kicad_sch.

`io_expansion.kicad_sch` declares the far end; without this the seven nets are
one-sided. `NOTES-R2-plan.md` constraint 3 wants touch and pen addable "without
a respin", and **the MCU pins are the half of that promise which is certain** --
the FPC pad order is a guess (docs/io-expansion.md §5), but a routed pin is a
routed pin.

| Net | Pin | Pad | Why |
| --- | --- | --- | --- |
| `PEN_TXD` | `PC4` | 25 | **`USART3_TX`, AF0** |
| `PEN_RXD` | `PC5` | 26 | **`USART3_RX`, AF0** |
| `PEN_INT#` | `PC6` | 38 | GPIO/EXTI, next to its UART |
| `MCU_EN_PEN` | `PC9` | 49 | GPIO out |
| `TOUCH_INT#` | `PC3` | 16 | GPIO/EXTI |
| `TOUCH_RST#` | `PD9` | 41 | GPIO out |
| `MCU_EN_TOUCH` | `PA11` | 43 | GPIO out — the only one on the right side |

`USART3` on `PC4`/`PC5` is the one allocation that is not interchangeable: both
are `USART3_TX`/`USART3_RX` at AF0 in `stm32g0b1.pdf`'s alternate-function
table, and both were free. Everything else is ordinary GPIO and can move for
layout convenience.

Touch adds **no I²C pins** -- it sits on the existing always-on bus
`SCL_AON`/`SDA_AON` (`PB8`/`PB9`) with the charger, the gauge and the three
`INA3221`s. A touch controller is one more address on it.

**Two spares are left afterwards, and which two was deliberate**: `PA12`
(USB-DP capable) and `PB12` (ADC-capable) are the two with a capability the rest
lack, so they are the two worth keeping.

The sheet is reviewed and committed, so this is surgical: seven no-connect flags
out, seven stubs and hierarchical labels in. Nothing else moves.
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

# pad -> (x, y, net, shape). Positions read off the placed symbol, not assumed.
PINS = {
    "16": (124.46, 160.02, "TOUCH_INT#", "input"),
    "25": (124.46, 162.56, "PEN_TXD", "output"),
    "26": (124.46, 165.10, "PEN_RXD", "input"),
    "38": (124.46, 167.64, "PEN_INT#", "input"),
    "41": (124.46, 147.32, "TOUCH_RST#", "output"),
    "49": (124.46, 175.26, "MCU_EN_PEN", "output"),
    "43": (180.34, 134.62, "MCU_EN_TOUCH", "output"),
}
LEFT_X, RIGHT_X = 114.30, 190.50      # the label columns this sheet already uses


def drop_nc(t, x, y):
    pat = (r'\n\t\(no_connect\n\t\t\(at %s %s\)\n\t\t\(uuid "[0-9a-f-]+"\)\n\t\)\n'
           % (re.escape(f"{x:g}"), re.escape(f"{y:g}")))
    new, n = re.subn(pat, "\n", t, count=1)
    assert n == 1, f"no_connect at ({x},{y}) not found"
    return new


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


def build() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["mcu"], root_uuid, "r2", paper="A3", pwr_base=1200)
    for x, y, net, shape in PINS.values():
        left = x < 150
        end = LEFT_X if left else RIGHT_X
        s.wire((x, y), (end, y))
        s.hlabel(end, y, net, shape=shape, rot=180 if left else 0)
    return s.render()


def main() -> int:
    t = SCH.read_text()
    for _x, _y, net, _shape in PINS.values():
        assert f'"{net}"' not in t, f"already patched ({net} present)"
    for x, y, _net, _shape in PINS.values():
        t = drop_nc(t, x, y)
    SCH.write_text(splice(t, build()))

    from sheet_pins import _sheet_span
    root = PROJ / "r2.kicad_sch"
    text = root.read_text()
    a, b = _sheet_span(text, "mcu")
    have = re.findall(r'\t\t\(pin "([^"]+)" (\w+)\n', text[a:b])
    assert have, "no sheet pins found on the root's mcu box"
    # The shape on the root must be the complement of nothing -- set_sheet_pins
    # writes what we give it, and io_expansion declares the mirror image.
    pins = sorted(set(have) | {(n, s) for _x, _y, n, s in PINS.values()})
    set_sheet_pins(root, "mcu", pins)
    print(f"mcu: {len(PINS)} no-connects removed, {len(PINS)} nets wired, "
          f"sheet interface now {len(pins)} pins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
