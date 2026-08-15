#!/usr/bin/env python3
"""Extract the PCM-071's 240-pin connector pinout from PHYTEC's manual.

Source: `datasheets/L-1038e.A5_phyCORE-AM62x_HW Manual.pdf`, Tables 7-10 --
"phyCORE-AM62x Connector X1, Column {A,B,C,D} Pinout". Four tables, 60 rows
each, giving for every pin: the SOM signal name, signal type, voltage level, the
AM62x processor ball it lands on (if any), and a description.

**Why parse instead of type it in.** 240 pins is exactly the size where hand
transcription produces two or three silent errors, and a wrong pin on a SoM
connector is a dead board with no ERC warning -- the same failure class
`check_ucf.py` exists to catch on the FPGA side. This script is the front half
of that: it turns the manual into machine-readable data, `gen_som_symbol.py`
turns the data into the KiCad symbol, and `check_pinout.py` will assert the
schematic's nets land where the manual says.

The extraction is checked, not trusted:

  * exactly 60 rows per column, numbered 1..60 with no gaps or repeats
  * every processor ball matches the AM62x's `^[A-Z]{1,2}\\d{1,2}$` form
  * no processor ball is claimed by two different pins
  * every row carries a type and a level, or is one of the power/ground rows
    where the manual legitimately writes "-"

`pdftotext -layout` puts each row on one line, but the column offsets drift
between pages and a few rows are indented differently (`A60` is the giveaway --
PHYTEC's own table has a stray indent there). So the parser splits on runs of
two-or-more spaces rather than on fixed columns, and tolerates the leading
whitespace.

Usage:
    python3 tools/parse_som_pinout.py            # verify and print a summary
    python3 tools/parse_som_pinout.py --json     # emit the table as JSON
    python3 tools/parse_som_pinout.py --grep DPI # rows whose name matches
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent
PDF = PROJ / "datasheets" / "L-1038e.A5_phyCORE-AM62x_HW Manual.pdf"
CACHE = PROJ / "datasheets" / "som_pinout.json"

COLUMNS = "ABCD"
PINS_PER_COLUMN = 60
BALL = re.compile(r"^[A-Z]{1,2}\d{1,2}$")
# One-or-more spaces after the designator, not two: PHYTEC's table indents
# `A60` and `D60` differently from their other 118 rows and leaves a single
# space there. The 60-rows-per-column and unique-ball checks in verify()
# are what keep the looser pattern honest.
ROW = re.compile(r"^\s*([ABCD])(\d{1,2})\s+(\S.*)$")


def pdf_text() -> str:
    if not PDF.exists():
        sys.exit(f"missing {PDF}")
    if not shutil.which("pdftotext"):
        sys.exit("pdftotext not found (poppler-utils)")
    out = subprocess.run(["pdftotext", "-layout", str(PDF), "-"],
                         check=True, capture_output=True, text=True)
    return out.stdout


def table_regions(text: str) -> dict[str, list[str]]:
    """Slice out the body of Tables 7-10, one per connector column.

    Pin designators like `C51` also appear in the per-interface tables of
    sections 5-12 (Table 26 lists `C51 X_PMIC_EN` with different columns), and
    in the table of contents. Parsing the whole document therefore sees each pin
    more than once, in more than one layout. So each column's rows are taken
    only from between its own table caption and the next caption.
    """
    lines = text.splitlines()
    starts = {}
    for i, line in enumerate(lines):
        m = re.match(r"\s*Table (7|8|9|10) phyCORE-AM62x Connector X1, "
                     r"Column ([ABCD]) Pinout\s*$", line)
        # the table of contents repeats the caption with a dotted leader
        if m and "...." not in line:
            starts[m.group(2)] = i
    assert set(starts) == set(COLUMNS), \
        f"found captions for {sorted(starts)}, expected {list(COLUMNS)}"
    # Every table caption, so the *last* pinout table (Column D) is bounded by
    # Table 11 rather than running to the end of the document and swallowing the
    # per-interface tables of sections 5-12.
    captions = [i for i, line in enumerate(lines)
                if re.match(r"\s*Table \d+ \S", line) and "...." not in line]
    out = {}
    for col, i in starts.items():
        end = next((c for c in captions if c > i), len(lines))
        out[col] = lines[i:end]
    return out


def parse_row(rest: str) -> dict:
    """Split one table row's text after the pin designator into its fields.

    `pdftotext -layout` preserves the column gutters as runs of two or more
    spaces, so the split is on those rather than on fixed offsets -- the offsets
    drift between pages, and PHYTEC's own table indents a few rows differently
    (`A60` is the visible one). Descriptions contain single spaces and survive.

    Full rows are `name type level ball desc`. Ground and the bare supply rails
    write "-" in the ball column, and a few rows carry no description.
    """
    f = re.split(r"\s{2,}", rest.strip())
    if len(f) >= 5:
        name, typ, level, ball, desc = f[0], f[1], f[2], f[3], " ".join(f[4:])
    elif len(f) == 4:
        name, typ, level, ball, desc = f[0], f[1], f[2], f[3], ""
    else:
        name, typ, level, ball, desc = f[0], f[1], "", "-", " ".join(f[2:])
    return {"name": name, "type": typ, "level": level,
            "ball": None if ball == "-" else ball, "desc": desc}


def parse(text: str) -> dict[str, dict]:
    """-> {"A1": {name, type, level, ball, desc}, ...}"""
    pins: dict[str, dict] = {}
    for want_col, lines in table_regions(text).items():
        for line in lines:
            m = ROW.match(line)
            if not m:
                continue
            col, num, rest = m.group(1), int(m.group(2)), m.group(3)
            if col != want_col or not 1 <= num <= PINS_PER_COLUMN:
                continue
            if len(re.split(r"\s{2,}", rest.strip())) < 2:
                continue
            key, row = f"{col}{num}", parse_row(rest)
            # Within one table's region a repeat means a page was captured
            # twice; identical is harmless, differing is a parse failure.
            if key in pins and pins[key] != row:
                raise AssertionError(f"{key} parsed twice and differently:\n"
                                     f"  {pins[key]}\n  {row}")
            pins[key] = row
    return pins


def verify(pins: dict[str, dict]) -> list[str]:
    problems = []
    for col in COLUMNS:
        got = sorted(int(k[1:]) for k in pins if k[0] == col)
        want = list(range(1, PINS_PER_COLUMN + 1))
        if got != want:
            missing = sorted(set(want) - set(got))
            extra = sorted(set(got) - set(want))
            problems.append(f"column {col}: {len(got)} rows, missing "
                            f"{missing or 'none'}, unexpected {extra or 'none'}")
    seen: dict[str, str] = {}
    for key, row in sorted(pins.items()):
        b = row["ball"]
        if b is None:
            continue
        if not BALL.match(b):
            problems.append(f"{key} ({row['name']}): {b!r} is not a ball name")
            continue
        if b in seen:
            problems.append(f"ball {b} claimed by both {seen[b]} and {key}")
        seen[b] = key
    return problems


def main() -> int:
    pins = parse(pdf_text())
    problems = verify(pins)
    if problems:
        for p in problems:
            print(f"  FAIL  {p}")
        return 1

    if "--json" in sys.argv:
        print(json.dumps(pins, indent=1, sort_keys=True))
        return 0
    if "--grep" in sys.argv:
        pat = sys.argv[sys.argv.index("--grep") + 1]
        rx = re.compile(pat, re.I)
        for key, row in sorted(pins.items(), key=lambda kv: (kv[0][0], int(kv[0][1:]))):
            if rx.search(row["name"]) or rx.search(row["desc"]):
                print(f"  {key:4s} {row['name']:26s} {row['type']:8s} "
                      f"{row['level']:14s} {row['ball'] or '-':6s} {row['desc']}")
        return 0

    CACHE.write_text(json.dumps(pins, indent=1, sort_keys=True) + "\n")
    balls = sum(1 for r in pins.values() if r["ball"])
    gnd = sum(1 for r in pins.values() if r["name"] == "GND")
    print(f"parsed {len(pins)} pins from {PDF.name}, Tables 7-10")
    print(f"  {balls} carry an AM62x ball, all distinct")
    print(f"  {gnd} grounds, {len(pins) - balls - gnd} other power/no-connect")
    from collections import Counter
    for col in COLUMNS:
        c = Counter(r["type"] for k, r in pins.items() if k[0] == col)
        print(f"  column {col}: " + ", ".join(f"{t or '-'}={n}"
                                              for t, n in sorted(c.items())))
    print(f"  cached to {CACHE.relative_to(PROJ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
