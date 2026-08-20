#!/usr/bin/env python3
"""Move two interrupts off EXTI lines that were already taken, and give
`FL_INT#` the pin it never had.

`mcu.md` §3.4 found this in the review round of 2026-08-19 and specified the
fix; this applies it. The rule is `mcu.md` §3.3's: **an EXTI line is chosen by
the pin's number, not its port**, so `PA3`, `PB3`, `PC3` and `PD3` all land on
EXTI3 and only one of them can be an interrupt at a time.

    TOUCH_INT#  PC3  EXTI3   already held by PD3 GAUGE_ALRT#   -> dead
    PEN_INT#    PC6  EXTI6   already held by PD6 QON_SNS       -> dead

Both were wired without re-checking, and as drawn neither touch nor pen can
raise an interrupt at all. The fix costs nothing because the pins they swap with
are **outputs**, which do not need an interrupt line:

    TOUCH_INT#     PC3  -> PD9    EXTI9 free
    TOUCH_RST#     PD9  -> PC3    plain output
    PEN_INT#       PC6  -> PA11   EXTI11 free
    MCU_EN_TOUCH   PA11 -> PC6    plain output
    FL_INT#        --   -> PB12   EXTI12 free; also ADC_IN16, which nothing needs

On the schematic the first four are a **relabel**: every pad is already wired to
a hierarchical label at the sheet edge, so swapping the two labels' positions
moves the net without touching a wire. `TOUCH_INT#`/`TOUCH_RST#` share the left
column, so only the `at` needs exchanging; `PEN_INT#`/`MCU_EN_TOUCH` are on
opposite sides of the symbol, so the justify swaps with it.

**Nothing changes on the root for those four.** A net's shape travels with its
name, not with its pad -- `TOUCH_INT#` is still an input to the MCU after it
moves -- so the root's `mcu` box already declares all four correctly. Only
`FL_INT#` is new, and it is the one that needs a sheet pin and therefore a
`wire_root.py` re-run (`patch_som_mcu_recovery.py`'s docstring records why that
is not optional).

`FL_INT#` is `frontlight.md` §10.3's open item: `LM3630A` pin 5 is an open-drain
fault flag, declared on `frontlight.kicad_sch` and dangling ever since. §10.3's
*first* suggestion was `PA12`/`PB12` and it was always the clean one; `mcu.md`
§9's later push for `PB7` was the mistake, because `PB7` is EXTI7 and `PC7`
`KEY_PREV#` holds it.

Cost: `PB12` was one of the two spares deliberately kept for a capability the
rest lack (ADC). Afterwards **`PA12` is the only spare left** -- and `PA11`,
which was held back with it as the USB-capable pair, is spent here. That is
deliberate and `mcu.md` §5.7 already argued it: USB DFU needs the USB-C data
pair, which is committed to the SoM, and §5.8 has since given the SoM its own
way to flash the MCU.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schgen import Sheet, sheet_uuids  # noqa: E402
from sheet_pins import set_sheet_pins, _sheet_span  # noqa: E402
from patch_mcu_pg_som import drop_nc, splice  # noqa: E402

PROJ = HERE.parent
SCH = PROJ / "mcu.kicad_sch"

# (net a, net b) -- exchange their positions, justify included.
SWAPS = (("TOUCH_INT#", "TOUCH_RST#"), ("PEN_INT#", "MCU_EN_TOUCH"))

# PB12, pad 32, right side. Read off the placed symbol, not assumed.
FL_PIN = (180.34, 185.42)
FL_LABEL_X = 190.5
FL_NET = "FL_INT#"


def _block(text: str, net: str):
    """The whole `(hierarchical_label "net" ...)` s-expression, with its span."""
    i = text.index(f'(hierarchical_label "{net}"')
    i = text.rindex("(", 0, i + 1)
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


def swap_positions(text: str, a: str, b: str) -> str:
    """Exchange `at` and `justify` between two hierarchical labels."""
    def parts(blk):
        at = re.search(r"\(at [\d.-]+ [\d.-]+ \d+\)", blk)
        ju = re.search(r"\(justify \w+\)", blk)
        assert at and ju, f"label has no at/justify: {blk[:60]}"
        return at.group(0), ju.group(0)

    ia, ja, ba = _block(text, a)
    ib, jb, bb = _block(text, b)
    at_a, ju_a = parts(ba)
    at_b, ju_b = parts(bb)
    assert at_a != at_b, f"{a} and {b} are already in the same place"

    new_a = ba.replace(at_a, at_b).replace(ju_a, ju_b)
    new_b = bb.replace(at_b, at_a).replace(ju_b, ju_a)
    # Splice the later one first so the earlier span stays valid.
    if ia < ib:
        text = text[:ib] + new_b + text[jb:]
        text = text[:ia] + new_a + text[ja:]
    else:
        text = text[:ia] + new_a + text[ja:]
        text = text[:ib] + new_b + text[jb:]
    return text


def build_fl() -> str:
    root_uuid, sheets = sheet_uuids(PROJ / "r2.kicad_sch")
    s = Sheet(sheets["mcu"], root_uuid, "r2", paper="A3", pwr_base=1220)
    x, y = FL_PIN
    s.wire((x, y), (FL_LABEL_X, y))
    s.hlabel(FL_LABEL_X, y, FL_NET, shape="input", rot=0)
    s.check_grid()
    return s.render()


def main() -> int:
    t = SCH.read_text()
    assert f'"{FL_NET}"' not in t, "already patched (FL_INT# is on mcu)"

    # 1-2. the two relabels
    for a, b in SWAPS:
        t = swap_positions(t, a, b)

    # 3. FL_INT# on PB12
    t = drop_nc(t, *FL_PIN)
    SCH.write_text(splice(t, build_fl()))

    # 4. one new sheet pin on the root's mcu box
    root = PROJ / "r2.kicad_sch"
    text = root.read_text()
    a, b = _sheet_span(text, "mcu")
    have = re.findall(r'\t\t\(pin "([^"]+)" (\w+)\n', text[a:b])
    assert have, "no sheet pins found on the root's mcu box"
    pins = sorted(set(have) | {(FL_NET, "input")})
    assert len(pins) == len(have) + 1, "FL_INT# was already declared on mcu"
    set_sheet_pins(root, "mcu", pins)

    print("mcu: TOUCH_INT#<->TOUCH_RST#, PEN_INT#<->MCU_EN_TOUCH relabelled")
    print(f"mcu: {FL_NET} wired to PB12 (pad 32), 1 sheet pin added")

    import subprocess
    r = subprocess.run([sys.executable, str(HERE / "wire_root.py")],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    assert r.returncode == 0, "wire_root.py failed; the root is now inconsistent"
    return 0


if __name__ == "__main__":
    sys.exit(main())
