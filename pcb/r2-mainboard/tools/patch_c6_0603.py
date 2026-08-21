#!/usr/bin/env python3
"""C6 (`REGN` decoupling, `BQ25896`) moves from 0805/10 V to 0603/16 V.

Both `battery.kicad_sch` and `r2.kicad_pcb` have been hand-edited, so they --
not `gen_battery.py` -- are the source of truth. This script patches both in
place and refuses to run twice.

Why (long form in `docs/battery.md` §10.14):

`bq25896.pdf` pin 22 asks for "a 4.7 uF (10 V rating) ceramic capacitor from
REGN to analog GND", placed close to the IC. It specifies one number and one
rating -- no range, unlike `tps63802.pdf` §8.2.2.3 which gives an explicit
10-50 uF window for its output cap. So the value stays at 4.7 uF nominal and
the only free variable is the package.

REGN sits at 4.7-4.8 V on this board (`bq25896.pdf` spec table: V(VBUS) = 5 V,
I(REGN) = 20 mA -> 4.7 V min / 4.8 V typ; `battery.md` §3 fixes us at 5 V in).
At that bias a ceramic loses capacitance in proportion to the field across its
dielectric, so for a given value a higher voltage rating in a smaller case can
beat a lower rating in a larger one. 0603/16 V keeps TI's 4.7 uF, exceeds TI's
10 V rating, is a JLCPCB basic part, and is smaller and lower-ESL than the 0805
it replaces -- which serves `bq25896.pdf` §12.1 guideline 6 ("decoupling
capacitors should be placed next to the IC pins").

What it changes:

1. `battery.kicad_sch` -- C6 footprint 0805 -> 0603, value 4.7uF/10V -> /16V.
2. `r2.kicad_pcb` -- C6's flattened footprint geometry swapped for the
   `C_0603_1608Metric` library body (silk, courtyard, fab, pads, 3D model),
   keeping its position, rotation, nets, uuid and sheet path.
3. `r2.kicad_pcb` -- the routed REGN track ended on the 0805 pad-1 centre at
   x = 61.05. Pad 1 moves to x = 61.225, so the track endpoint moves with it.
   (61.05 would still land inside the new 0.9 mm pad, but a track that stops
   short of the pad centre is the kind of thing that survives into fab.)
4. `tools/check_pcb.py` -- C6 gains the proximity rule it never had, at the
   same 5.0 mm as its neighbours C1/C2/C3 on the same IC.
"""
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
SCH = HERE.parent / "battery.kicad_sch"
PCB = HERE.parent / "r2.kicad_pcb"
CHK = HERE / "check_pcb.py"

DESCR_0603 = ('Capacitor SMD 0603 (1608 Metric), square (rectangular) end '
              'terminal, IPC-7351 nominal, (Body size source: IPC-SM-782 page '
              '76, https://www.pcb-3d.com/wordpress/wp-content/uploads/'
              'ipc-sm-782a_amendment_1_and_2.pdf)')

# (old, new) pairs applied inside C6's footprint block only. Geometry is taken
# verbatim from Capacitor_SMD.pretty/C_0603_1608Metric.kicad_mod.
PCB_SUBS = [
    ('(footprint "Capacitor_SMD:C_0805_2012Metric"',
     '(footprint "Capacitor_SMD:C_0603_1608Metric"'),
    ('(at 0 -1.68 0)', '(at 0 -1.43 0)'),          # Reference, silk
    ('(at 0 1.68 0)', '(at 0 1.43 0)'),            # Value, fab
    ('"Value" "4.7uF/10V"', '"Value" "4.7uF/16V"'),
    ('(start -0.261252 -0.735)', '(start -0.14058 -0.51)'),   # silk top
    ('(end 0.261252 -0.735)', '(end 0.14058 -0.51)'),
    ('(start -0.261252 0.735)', '(start -0.14058 0.51)'),     # silk bottom
    ('(end 0.261252 0.735)', '(end 0.14058 0.51)'),
    ('(start -1.7 -0.98)', '(start -1.48 -0.73)'),            # courtyard
    ('(end 1.7 0.98)', '(end 1.48 0.73)'),
    ('(start -1 -0.625)', '(start -0.8 -0.4)'),               # fab body
    ('(end 1 0.625)', '(end 0.8 0.4)'),
    ('(at -0.95 0)', '(at -0.775 0)'),                        # pad 1
    ('(at 0.95 0)', '(at 0.775 0)'),                          # pad 2
    ('C_0805_2012Metric.step', 'C_0603_1608Metric.step'),
]

PROX_RULE = '''    ("C6", "U1", 5.0, "battery.md §10.14 -- bq25896.pdf pin 22: the REGN "
                      "cap \\"should be placed close to the IC\\"; it feeds the "
                      "low-side gate driver and the bootstrap diode at 1.5 MHz"),
'''


def fp_span(text, ref):
    """Byte span of the top-level `(footprint ...)` block whose Reference is `ref`."""
    for m in re.finditer(r'\n\t\(footprint "', text):
        s = m.start()
        e = text.index('\n\t)\n', s) + 4
        if re.search(r'\(property "Reference" "%s"' % re.escape(ref), text[s:e]):
            return s, e
    raise KeyError(ref)


def sym_span(text, ref):
    """Byte span of the top-level `(symbol ...)` block whose Reference is `ref`."""
    for m in re.finditer(r'\n\t\(symbol\n', text):
        s = m.start()
        e = text.index('\n\t)\n', s) + 4
        if re.search(r'\(property "Reference" "%s"' % re.escape(ref), text[s:e]):
            return s, e
    raise KeyError(ref)


def set_prop(blk, name, value):
    new, n = re.subn(r'(\(property "%s" ")[^"]*(")' % re.escape(name),
                     lambda m: m.group(1) + value + m.group(2), blk, count=1)
    assert n == 1, "property %s not found" % name
    return new


def main():
    # ---- 1. schematic ---------------------------------------------------- #
    t = SCH.read_text()
    assert 'C_0603_1608Metric' not in t, "battery.kicad_sch already patched"
    s, e = sym_span(t, "C6")
    blk = t[s:e]
    assert 'C_0805_2012Metric' in blk, "C6 is not an 0805 -- refusing to guess"
    blk = set_prop(blk, "Footprint", "Capacitor_SMD:C_0603_1608Metric")
    blk = set_prop(blk, "Value", "4.7uF/16V")
    SCH.write_text(t[:s] + blk + t[e:])
    print("battery.kicad_sch: C6 -> 0603, 4.7uF/16V")

    # ---- 2. board: footprint body ---------------------------------------- #
    p = PCB.read_text()
    s, e = fp_span(p, "C6")
    blk = p[s:e]
    assert 'C_0805_2012Metric' in blk, "C6 on the board is not an 0805"
    for old, new in PCB_SUBS:
        assert old in blk, "PCB: %r not found in C6's block" % old
        blk = blk.replace(old, new, 1)
    # both pads share one size string; replace_all is correct here
    assert blk.count('(size 1 1.45)') == 2
    blk = blk.replace('(size 1 1.45)', '(size 0.9 0.95)')
    blk = blk.replace(re.search(r'\(descr "[^"]*"\)', blk).group(0),
                      '(descr "%s")' % DESCR_0603, 1)
    p = p[:s] + blk + p[e:]

    # ---- 3. board: the REGN track follows pad 1 -------------------------- #
    old_seg = ('(start 61 35.45)\n\t\t(end 61.05 35.5)')
    new_seg = ('(start 61 35.45)\n\t\t(end 61.225 35.5)')
    assert p.count(old_seg) == 1, "REGN track endpoint not found exactly once"
    p = p.replace(old_seg, new_seg, 1)
    PCB.write_text(p)
    print("r2.kicad_pcb: C6 body swapped, REGN track endpoint 61.05 -> 61.225")

    # ---- 4. the proximity rule C6 never had ------------------------------ #
    c = CHK.read_text()
    assert '("C6", "U1"' not in c, "check_pcb.py already has the C6 rule"
    anchor = '    ("C1", "U1", 5.0,'
    assert anchor in c
    c = c.replace(anchor, PROX_RULE + anchor, 1)
    CHK.write_text(c)
    print("check_pcb.py: C6 -> U1 proximity rule added")


if __name__ == "__main__":
    main()
