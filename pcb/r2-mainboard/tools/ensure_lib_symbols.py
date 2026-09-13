#!/usr/bin/env python3
"""Make sure a sheet's `lib_symbols` block defines every `lib_id` the sheet places.

A KiCad sheet carries its own copy of each symbol it uses. Scripts that append symbol instances
must add the definition too, or the sheet loads with "symbol not found" and the pins -- and so the
netlist -- vanish. Idempotent: a lib_id already defined is left alone.

    tools/ensure_lib_symbols.py sic.kicad_sch
"""
import pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / 'tools'))
import schgen                                                              # noqa: E402

KICAD = pathlib.Path('/home/lum/Apps/kicad-10.0.4/share/kicad/symbols')
SOURCES = {
    'Device': ('dir', KICAD / 'Device.kicad_symdir'),
    'power': ('dir', KICAD / 'power.kicad_symdir'),
    'Reflow': ('file', HERE / 'library/Reflow.kicad_sym'),
    'r2': ('file', HERE / 'r2.kicad_sym'),
    'symbols': ('file', HERE.parent / 'pcb_common/symbols.kicad_sym'),
    'Connector': ('dir', KICAD / 'Connector.kicad_symdir'),
}


def main(path):
    path = pathlib.Path(path)
    text = path.read_text(encoding='utf-8')
    used = set(re.findall(r'\(lib_id "([^"]+)"\)', text))
    have = set(re.findall(r'\n\t\t\(symbol "([^"]+)"', text))
    missing = sorted(u for u in used if u not in have)
    if not missing:
        print(f'  {path.name}: lib_symbols already complete ({len(used)} lib_ids)')
        return 0

    lib = schgen.SymbolLib()
    for name, (kind, p) in SOURCES.items():
        (lib.add_dir if kind == 'dir' else lib.add_file)(name, p)

    blocks = []
    for lib_id in missing:
        sym = lib.get(lib_id)
        blocks.append('\n'.join('\t\t' + ln for ln in sym.source.splitlines()) + '\n')

    m = re.search(r'\n\t\(lib_symbols\n', text)
    assert m, 'no lib_symbols block'
    text = text[:m.end()] + ''.join(blocks) + text[m.end():]
    path.write_text(text, encoding='utf-8')
    print(f'  {path.name}: added {len(missing)} definition(s): {", ".join(missing)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'sic.kicad_sch'))
