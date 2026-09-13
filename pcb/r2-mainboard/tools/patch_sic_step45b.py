#!/usr/bin/env python3
"""Step 4 connectivity on `sic`: the floating power pins, VMON_VSYS and VPP.

Appends to the owner's sheet; nothing existing is moved. Every new segment is checked against
the wires already on the page before anything is written.

  * `VDDSHV0..6`, `_MCU`, `_CANUART` -- 18 pins, the whole left column of unit 2, all floating.
    The owner had already placed the `+3V3_SIC` rail symbol at (76.2, 96.52) directly above the
    column, so this draws the trunk that was missing: one vertical wire from that symbol down the
    column with a stub and a junction per pin.
  * `VDDA_CORE_CSIRX0` / `VDDA_CORE_USB` -- floating; both belong to the core group
    (`docs/sic.md` §2), so they get their own `+0V75_SIC` stub.
  * `VMON_VSYS` -- was tied to the 3.3 V trunk, where it would read a constant 3.3 V and never
    trip. The stub into the trunk is deleted and the pin labelled instead; its 100k/16.9k divider
    from `+VSYS_SIC` is step 8 (`docs/sic.md` §7).
  * `VPP` -- a no-connect flag, so "deliberately floating" is on the page and ERC stays quiet.
"""
import json, pathlib, re, subprocess, sys, uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / 'tools'))
sys.path.insert(0, '/home/lum/.claude/plugins/cache/kicad-happy/kicad-happy/2.1.0/skills/kicad/scripts')
import schgen                                                              # noqa: E402
from sexp_parser import parse_file, find_all, find_first                   # noqa: E402

SIC = HERE / 'sic.kicad_sch'
UNIT2 = (106.68, 99.06, 0)          # PWR_IO, as placed by the owner
UNIT1 = (106.68, 30.48, 0)          # PWR_CORE
TRUNK_X = 76.2                      # the owner's +3V3_SIC symbol sits here
RAIL_Y = 96.52
CORE_X = 78.74


def u():
    return str(uuid.uuid4())


def wire(a, b):
    return ('\t(wire\n\t\t(pts\n'
            f'\t\t\t(xy {a[0]:g} {a[1]:g}) (xy {b[0]:g} {b[1]:g})\n'
            '\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            f'\t\t(uuid "{u()}")\n\t)\n')


def junction(p):
    return (f'\t(junction\n\t\t(at {p[0]:g} {p[1]:g})\n\t\t(diameter 0)\n'
            f'\t\t(color 0 0 0 0)\n\t\t(uuid "{u()}")\n\t)\n')


def nc(p):
    return f'\t(no_connect\n\t\t(at {p[0]:g} {p[1]:g})\n\t\t(uuid "{u()}")\n\t)\n'


def label(p, text, rot=0, just='left'):
    return (f'\t(label "{text}"\n\t\t(at {p[0]:g} {p[1]:g} {rot})\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            f'\t\t\t(justify {just} bottom)\n\t\t)\n'
            f'\t\t(uuid "{u()}")\n\t)\n')


def power_sym(rail, x, y, root, sheet, ref):
    """A `symbols:+V` rail stub -- the same symbol schgen.Sheet.power() uses."""
    def prop(n, v, px, py, hide, ):
        h = '\n\t\t\t(hide yes)' if hide else ''
        return (f'\t\t(property "{n}" "{v}"\n\t\t\t(at {px:g} {py:g} 0){h}\n'
                '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')
    return ('\t(symbol\n\t\t(lib_id "symbols:+V")\n'
            f'\t\t(at {x:g} {y:g} 0)\n\t\t(unit 1)\n'
            '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n'
            f'\t\t(uuid "{u()}")\n'
            + prop('Reference', ref, x, y, True)
            + prop('Value', rail, x, y - 3.81, False)
            + prop('Footprint', '', x, y, True)
            + prop('Datasheet', '', x, y, True)
            + prop('Description', '', x, y, True)
            + '\t\t(instances\n\t\t\t(project "r2"\n'
            f'\t\t\t\t(path "/{root}/{sheet}"\n'
            f'\t\t\t\t\t(reference "{ref}")\n\t\t\t\t\t(unit 1)\n'
            '\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')


def main():
    run = [n for n in ('kicad', 'eeschema', 'pcbnew') if
           subprocess.run(['pgrep', '-x', n], capture_output=True).returncode == 0]
    if run:
        sys.exit(f'{", ".join(run)} running -- close KiCad first (CLAUDE.md).')

    lib = schgen.SymbolLib(); lib.add_file('Reflow', HERE / 'library/Reflow.kicad_sym')
    sym = lib.get('Reflow:OSD6254-1G-IPM')
    pins = json.load(open(HERE / 'datasheets/SiC OSD62x-PM/osd62x_pm_pinout.json'))['pins']
    upath = pathlib.Path('/tmp/claude-1000/-home-lum-Ereader-Projekt-Glider-OG/'
                         'c9f9396e-2815-476b-9a8b-a6fffb6af53a/scratchpad/unit_pins.json')
    unit_pins = json.load(open(upath))
    p2 = schgen.Placed(sym, *UNIT2, 'U600')
    p1 = schgen.Placed(sym, *UNIT1, 'U600')

    shv = sorted((p2.pin(b)[1], b) for b in unit_pins['2']
                 if pins[b]['name'].startswith('VDDSHV'))
    assert len(shv) == 18, len(shv)
    core = sorted((p1.pin(b)[1], b) for b in unit_pins['1']
                  if pins[b]['name'] in ('VDDA_CORE_CSIRX0', 'VDDA_CORE_USB'))
    assert len(core) == 2
    vpp = p2.pin([b for b in unit_pins['2'] if pins[b]['name'] == 'VPP'][0])
    vmon = p2.pin([b for b in unit_pins['2'] if pins[b]['name'] == 'VMON_VSYS'][0])

    text = SIC.read_text(encoding='utf-8')
    root = re.search(r'\(uuid "([^"]+)"\)', text).group(1)
    m = re.search(r'"([0-9a-f-]{36})",\s*\n\s*"sic"', (HERE / 'r2.kicad_pro').read_text())
    sheet_uuid = m.group(1) if m else '767172a6-43e9-4684-bdc5-5dc2ecddbb44'

    # ---- existing geometry, for the collision check -------------------------------------------
    d = parse_file(str(SIC))
    def walk(n):
        if isinstance(n, list):
            yield n
            for c in n:
                yield from walk(c)
    old = []
    for w in [n for n in walk(d) if n and n[0] == 'wire']:
        xy = [(round(float(p[1]), 3), round(float(p[2]), 3))
              for p in find_all(find_first(w, 'pts'), 'xy')]
        old.append((xy[0], xy[1]))

    def hits(a, b):
        """Does a new segment share interior space with an existing one?"""
        for c, e in old:
            if a[0] == b[0] == c[0] == e[0]:                       # both vertical, same x
                lo1, hi1 = sorted((a[1], b[1])); lo2, hi2 = sorted((c[1], e[1]))
                if lo1 < hi2 - 1e-6 and lo2 < hi1 - 1e-6:
                    return (c, e)
            if a[1] == b[1] == c[1] == e[1]:                       # both horizontal, same y
                lo1, hi1 = sorted((a[0], b[0])); lo2, hi2 = sorted((c[0], e[0]))
                if lo1 < hi2 - 1e-6 and lo2 < hi1 - 1e-6:
                    return (c, e)
        return None

    add, n_j = [], 0
    # ---- VDDSHV trunk -------------------------------------------------------------------------
    top, bot = RAIL_Y, shv[-1][0]
    seg = ((TRUNK_X, top), (TRUNK_X, bot))
    bad = hits(*seg)
    assert not bad, f'the VDDSHV trunk at x={TRUNK_X} would overlap an existing wire {bad}'
    add.append(wire(*seg))
    for y, b in shv:
        s = ((81.28, y), (TRUNK_X, y))
        bad = hits(*s)
        assert not bad, f'stub for {b} at y={y} overlaps {bad}'
        add.append(wire(*s))
        if abs(y - bot) > 1e-6:
            add.append(junction((TRUNK_X, y))); n_j += 1

    # ---- the two core analog pins -------------------------------------------------------------
    ys = [y for y, _ in core]
    add.append(wire((CORE_X, min(ys) - 2.54), (CORE_X, max(ys))))
    for y, b in core:
        add.append(wire((83.82, y), (CORE_X, y)))
    add.append(junction((CORE_X, min(ys))))
    add.append(power_sym('+0V75_SIC', CORE_X, min(ys) - 2.54, root, sheet_uuid, '#PWR1590'))

    # ---- VMON_VSYS: cut the stub into the 3.3 V trunk, label the pin --------------------------
    cut = re.search(r'\t\(wire\n\t\t\(pts\n\t\t\t\(xy 132\.08 134\.62\) \(xy 138\.43 134\.62\)\n'
                    r'\t\t\)\n\t\t\(stroke\n\t\t\t\(width 0\)\n\t\t\t\(type default\)\n\t\t\)\n'
                    r'\t\t\(uuid "[^"]+"\)\n\t\)\n', text)
    assert cut, 'the VMON_VSYS stub into +3V3_SIC is not where the audit found it'
    text = text[:cut.start()] + text[cut.end():]
    add.append(wire(vmon, (vmon[0] + 5.08, vmon[1])))
    add.append(label((vmon[0] + 5.08, vmon[1]), 'VMON_VSYS'))

    # ---- VPP ----------------------------------------------------------------------------------
    add.append(nc(vpp))

    # the sheet ends with its last symbol block and a bare closing paren
    tail = text.rstrip()
    assert tail.endswith(')'), 'cannot find the tail of the sheet'
    j = len(tail) - 1
    SIC.write_text(text[:j] + ''.join(add) + text[j:], encoding='utf-8')

    print(f'  VDDSHV trunk: 18 pins -> +3V3_SIC at x={TRUNK_X} (y {top}..{bot}), {n_j} junctions')
    print(f'  VDDA_CORE_CSIRX0 / VDDA_CORE_USB -> +0V75_SIC stub at x={CORE_X}')
    print(f'  VMON_VSYS: cut from the +3V3_SIC trunk, labelled at {(vmon[0] + 5.08, vmon[1])}')
    print(f'  VPP: no-connect at {vpp}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
