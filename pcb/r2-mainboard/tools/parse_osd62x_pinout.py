#!/usr/bin/env python3
"""Extract the OSD62x-PM ball list from Octavo's datasheet and cross-check its two tables.

Source: datasheets/SiC OSD62x-PM/OSD62x-PM-Datasheet.pdf, Rev. 2.0, 2026-01-16.
The datasheet describes every ball twice, independently:
  * Tables 5-1..5-5 -- the ball MAP, a positional top-view grid;
  * Tables 5-6, 5-7 -- the ball DESCRIPTION: name -> ball(s), plus the equivalent AM62x ball.
This script parses both, and exits non-zero unless they agree on every one of the 500 balls.

NOTE: the "AM62x" ball column is the AMC package. PHYTEC's som_pinout.json uses the ALW package,
so the two ball numbers are NOT comparable -- match across them by AM62x signal name only.

Writes datasheets/SiC OSD62x-PM/osd62x_pm_pinout.json.
"""
import json, re, subprocess, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent            # pcb/r2-mainboard
PDF  = ROOT / 'datasheets/SiC OSD62x-PM/OSD62x-PM-Datasheet.pdf'
OUT  = ROOT / 'datasheets/SiC OSD62x-PM/osd62x_pm_pinout.json'
ROWS = list('ABCDEFGHJKLMNPRTUV')                          # JEDEC: no I, O, Q, S -> 18 rows
NCOL = 28
BALL = re.compile(r'^[A-HJ-NPRTUV](?:[1-9]|1\d|2[0-8])$')
NOISE = re.compile(r'Octavo Systems LLC|Copyright 20\d\d|OSD62x-PM Datasheet|Rev\. 2\.0|^\s*\d{1,2}\s*$')

def toks(line):
    return [(m.start() + len(m.group()) / 2, m.start(), m.group()) for m in re.finditer(r'\S+', line)]

def pdf_lines():
    return subprocess.run(['pdftotext', '-layout', str(PDF), '-'],
                          capture_output=True, text=True, check=True).stdout.splitlines()

# --- Tables 5-1..5-5: the positional grid ------------------------------------------------------
# pdftotext squeezes some rows, so a token's x position does not reliably say which column it is
# in. Order does: each row's first line lists one token per populated cell, left to right, and every
# cell whose name is broken over two lines ends that first token with "_". So cells are filled in
# order, and continuation fragments are handed out in order to the "_"-ending cells.
CORNERS = {('A', 1), ('V', 1), ('A', 28), ('V', 28)}

def parse_map(L, errors):
    grid = {}
    i = 0
    while i < len(L):
        if not re.match(r'\s*Table 5-[1-5] ', L[i]):
            i += 1; continue
        j = i + 1
        while not re.fullmatch(r'\s*(\d+\s+)+\d+\s*', L[j]):
            j += 1
        cols = [int(t) for _, _, t in toks(L[j])]
        j += 1
        rows = []                                            # [(letter, first_line_tokens, continuation_tokens)]
        while j < len(L) and not re.match(r'\s*(Table 5-|5\.1 Ball)', L[j]):
            line = L[j]; j += 1
            if not line.strip() or NOISE.search(line):
                continue
            t = [s for _, x0, s in toks(line)]
            x0 = toks(line)[0][1]
            if len(t[0]) == 1 and t[0] in ROWS and x0 < 24:
                rows.append((t[0], t[1:], []))
            elif rows:
                rows[-1][2].extend(t)
        for letter, first, cont in rows:
            want = [c for c in cols if (letter, c) not in CORNERS]
            if len(first) != len(want):
                errors.append(f'map row {letter} cols {cols[0]}-{cols[-1]}: {len(first)} cells for {len(want)} balls: {first}')
                continue
            broken = [k for k, s in enumerate(first) if s.endswith('_')]
            if len(broken) != len(cont):
                errors.append(f'map row {letter} cols {cols[0]}-{cols[-1]}: {len(broken)} broken names, {len(cont)} fragments')
                continue
            names = list(first)
            for k, frag in zip(broken, cont):
                names[k] += frag
            for c, n in zip(want, names):
                grid[f'{letter}{c}'] = n
        i = j
    return grid

# --- Tables 5-6, 5-7: name -> balls, plus the AM62x (AMC) equivalent ---------------------------
def parse_desc(L):
    start = next(k for k, l in enumerate(L) if re.match(r'\s*Table 5-6 ', l))
    end   = next(k for k, l in enumerate(L) if re.match(r'\s*5\.2 Reserved Balls', l))
    split, name, rows = None, None, collections.OrderedDict()
    pending = None                                         # a name broken across two lines, e.g. "GPMC0_" / "ADVN_ALE"
    for line in L[start:end]:
        if not line.strip() or NOISE.search(line) or re.match(r'\s*Table 5-7', line):
            continue
        pn = [m.start() for m in re.finditer(r'Pin Name', line)]
        if len(pn) == 2:                                   # a (repeated) column header: re-measure the split
            split = pn[1] - 3; continue
        if split is None or 'OSD62x-PM' in line and 'AM62x' in line:
            continue
        t = toks(line)
        left  = [s for _, x0, s in t if x0 < split]
        right = [s for _, x0, s in t if x0 >= split]
        if not left:
            continue
        first = left[0].rstrip(',')
        if not BALL.match(first) and re.fullmatch(r'[A-Z][A-Z0-9_]*', first):
            if pending:                                    # continuation of a split name
                name = pending + first; pending = None
                rows[name] = rows.pop(pending_key)
                continue
            name = first
            rows.setdefault(name, {'balls': [], 'am62x_name': None, 'amc_ball': None})
            if name.endswith('_'):
                pending, pending_key = name, name
            left = left[1:]
            nm = [s for s in right if not BALL.match(s.rstrip(',')) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', s)]
            bl = [s.rstrip(',') for s in right if BALL.match(s.rstrip(',')) or re.fullmatch(r'[A-Z]{1,2}\d{1,2}', s.rstrip(','))]
            if nm and rows[name]['am62x_name'] is None: rows[name]['am62x_name'] = nm[0]
            if bl and rows[name]['amc_ball'] is None:   rows[name]['amc_ball'] = bl[0]
        for s in left:
            for b in re.split(r'[,\s]+', s):
                if BALL.match(b):
                    rows[name]['balls'].append(b)
    return rows

def main():
    L = pdf_lines()
    errors = []
    grid = parse_map(L, errors)
    desc = parse_desc(L)

    by_ball = {}
    for nm, r in desc.items():
        for b in r['balls']:
            if b in by_ball: errors.append(f'ball {b} claimed by {by_ball[b]} and {nm}')
            by_ball[b] = nm
    all_balls = {f'{r}{c}' for r in ROWS for c in range(1, NCOL + 1)}
    corners = {'A1', 'A28', 'V1', 'V28'}
    expect = all_balls - corners

    def norm(n): return n[6:] if n.startswith('AM62X_') else n
    if set(grid) != expect:
        errors.append(f'map: {len(grid)} balls; missing {sorted(expect - set(grid))[:8]} extra {sorted(set(grid) - expect)[:8]}')
    if set(by_ball) != expect:
        errors.append(f'description: {len(by_ball)} balls; missing {sorted(expect - set(by_ball))[:12]} extra {sorted(set(by_ball) - expect)[:8]}')
    for b in sorted(expect & set(grid) & set(by_ball)):
        if norm(by_ball[b]) != grid[b]:
            errors.append(f'{b}: map says {grid[b]!r}, description says {by_ball[b]!r}')

    pins = {}
    for b in sorted(by_ball, key=lambda s: (ROWS.index(s[0]), int(s[1:]))):
        r, c = ROWS.index(b[0]), int(b[1:])
        nm = by_ball[b]
        pins[b] = {'name': nm,
                   'am62x_name': desc[nm]['am62x_name'] if len(desc[nm]['balls']) == 1 else None,
                   'amc_ball':  desc[nm]['amc_ball']   if len(desc[nm]['balls']) == 1 else None,
                   'ring': 1 + min(r, len(ROWS) - 1 - r, c - 1, NCOL - c)}
    counts = collections.Counter(p['name'] for p in pins.values())
    json.dump({'source': str(PDF.relative_to(ROOT)), 'revision': 'Rev. 2.0, 2026-01-16',
               'package': '9 x 14 mm, 18 rows (A-V, no I/O/Q/S) x 28 columns, 0.5 mm pitch, corners A1/A28/V1/V28 depopulated',
               'amc_note': 'amc_ball is the AM62x AMC-package ball; PHYTEC som_pinout.json uses ALW -- do not compare balls across them',
               'checks': {'balls': len(pins), 'map_vs_description_mismatches': len(errors)},
               'counts': dict(sorted(counts.items(), key=lambda kv: -kv[1])),
               'pins': pins}, open(OUT, 'w'), indent=1)
    print(f'map balls: {len(grid)}   description balls: {len(by_ball)}   expected: {len(expect)}')
    print(f'distinct names: {len(desc)}   multi-ball names: ' +
          ', '.join(f'{k}x{v}' for k, v in counts.most_common() if v > 1))
    if errors:
        print(f'\n{len(errors)} DISAGREEMENT(S):'); [print('  ', e) for e in errors[:40]]
        sys.exit(1)
    print('OK: map and description agree on every ball ->', OUT.relative_to(ROOT))

if __name__ == '__main__':
    main()
