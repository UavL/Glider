#!/usr/bin/env python3
"""Add or replace the sheet pins on a child sheet's symbol in the root sheet.

Every hierarchical label inside a child sheet needs a matching sheet pin on the
parent's sheet symbol, or ERC raises `hier_label_mismatch`. This edits
r2.kicad_sch in place — it does not regenerate it — so hand edits to the root
survive.

Usage (as a library):
    from sheet_pins import set_sheet_pins
    set_sheet_pins("r2.kicad_sch", "battery",
                   [("SDA_AON", "bidirectional"), ...])
"""
from __future__ import annotations

import pathlib
import re
import uuid as _uuid

PITCH = 2.54
TOP_MARGIN = 5.08
BOT_MARGIN = 5.08


def _sheet_span(text: str, stem: str) -> tuple[int, int]:
    """Byte span of the (sheet ...) block whose Sheetfile is <stem>.kicad_sch."""
    target = f'"Sheetfile" "{stem}.kicad_sch"'
    for m in re.finditer(r"\(sheet\n", text):
        i = m.start()
        depth, j, in_str = 0, i, False
        while j < len(text):
            c = text[j]
            if c == '"' and text[j - 1] != "\\":
                in_str = not in_str
            elif not in_str:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        block = text[i:j + 1]
                        if target in block:
                            return (i, j + 1)
                        break
            j += 1
    raise KeyError(f"no sheet block for {stem}")


def set_sheet_pins(root_path, stem: str, pins: list[tuple[str, str]]) -> None:
    p = pathlib.Path(root_path)
    text = p.read_text()
    a, b = _sheet_span(text, stem)
    block = text[a:b]

    at = re.search(r"\(at ([-\d.]+) ([-\d.]+)\)", block)
    size = re.search(r"\(size ([-\d.]+) ([-\d.]+)\)", block)
    sx, sy = float(at.group(1)), float(at.group(2))
    w, h = float(size.group(1)), float(size.group(2))

    needed = TOP_MARGIN + PITCH * max(len(pins) - 1, 0) + BOT_MARGIN
    if h < needed:
        h = round(needed / PITCH) * PITCH
        block = re.sub(r"\(size [-\d.]+ [-\d.]+\)", f"(size {w} {h})", block, count=1)
        # keep the Sheetfile caption under the (now taller) box
        block = re.sub(
            r'(\(property "Sheetfile" "[^"]*"\n\t\t\t\(at [-\d.]+ )[-\d.]+',
            lambda m: m.group(1) + f"{round(sy + h + 0.5846, 4)}", block, count=1)

    # drop any pins we previously wrote, then re-emit
    block = re.sub(r"\t\t\(pin \"[^\"]*\"[^\n]*\n(?:\t\t\t[^\n]*\n|\t\t\t\)\n)*\t\t\)\n",
                   "", block)

    edge_x = sx + w
    y = sy + TOP_MARGIN
    out = []
    for name, shape in pins:
        out.append(
            f'\t\t(pin "{name}" {shape}\n'
            f"\t\t\t(at {round(edge_x, 4)} {round(y, 4)} 0)\n"
            f'\t\t\t(uuid "{_uuid.uuid4()}")\n'
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
            "\t\t\t\t(justify right)\n\t\t\t)\n\t\t)\n"
        )
        y += PITCH

    block = block.replace("\t\t(instances\n", "".join(out) + "\t\t(instances\n", 1)
    p.write_text(text[:a] + block + text[b:])
    print(f"{stem}: {len(pins)} sheet pins, box {w} x {h}")
