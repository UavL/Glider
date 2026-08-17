#!/usr/bin/env python3
"""Minimal KiCad schematic writer for bootstrapping R2 sheets.

Writes KiCad 9 format (20250114); run `kicad-cli sch upgrade` afterwards to
normalise to KiCad 10. This exists only to create a sheet the *first* time.
Once a sheet has been opened and saved in Eeschema, the .kicad_sch file is the
source of truth and is edited in place — never regenerate over hand edits.

Coordinates are millimetres, KiCad screen convention (+x right, +y DOWN).
Symbol-space coordinates in .kicad_sym files are +y UP, which `_xf` handles.
"""
from __future__ import annotations

import math
import pathlib
import re
import sys
import uuid as _uuid

_SKILL = pathlib.Path(
    "/home/lum/.claude/plugins/cache/kicad-happy/kicad-happy/2.1.0/skills/kicad/scripts"
)
sys.path.insert(0, str(_SKILL))
from sexp_parser import parse, find_all, find_first, get_value  # noqa: E402

GRID = 1.27


def u() -> str:
    return str(_uuid.uuid4())


def snap(v: float) -> float:
    """Snap to the 1.27 mm grid Eeschema uses, so wires meet pins exactly."""
    return round(round(v / GRID) * GRID, 4)


def _fmt(v: float) -> str:
    s = f"{round(v, 4):.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _xf(px: float, py: float, angle: int) -> tuple[float, float]:
    """Symbol-space point -> schematic offset, for a symbol placed at `angle`.

    Symbol space is +y up; schematic is +y down, hence the initial (px, -py).
    Rotation is counter-clockwise on screen.
    """
    x, y = px, -py
    a = math.radians(angle)
    ca, sa = round(math.cos(a)), round(math.sin(a))
    return (x * ca + y * sa, -x * sa + y * ca)


class Pin:
    __slots__ = ("name", "number", "x", "y", "rot", "etype")

    def __init__(self, name, number, x, y, rot, etype):
        self.name, self.number = name, number
        self.x, self.y, self.rot, self.etype = x, y, rot, etype


class Symbol:
    """One symbol definition, with its source text and pin geometry."""

    def __init__(self, lib_id: str, source: str, node: list):
        self.lib_id = lib_id
        self.pins: dict[str, Pin] = {}
        self.by_name: dict[str, list[Pin]] = {}
        # Re-head the block as "Lib:Name" for embedding in lib_symbols.
        self.source = re.sub(
            r'^\(symbol\s+"[^"]*"', f'(symbol "{lib_id}"', source.strip(), count=1
        )
        for unit in find_all(node, "symbol"):          # e.g. R_1_1
            for p in find_all(unit, "pin"):
                at = find_first(p, "at")
                nnode = find_first(p, "number")
                nmnode = find_first(p, "name")
                number = nnode[1] if nnode and len(nnode) > 1 else None
                name = nmnode[1] if nmnode and len(nmnode) > 1 else ""
                if not at or number is None:
                    continue
                etype = p[1] if len(p) > 1 else "passive"
                pin = Pin(name, number, float(at[1]), float(at[2]),
                          int(float(at[3])) if len(at) > 3 else 0, etype)
                self.pins[number] = pin
                self.by_name.setdefault(name, []).append(pin)


class SymbolLib:
    """Loads symbols from .kicad_sym files (single-symbol or multi-symbol)."""

    def __init__(self):
        self._files: dict[str, pathlib.Path] = {}
        self._cache: dict[str, Symbol] = {}

    def add_file(self, lib_name: str, path: str | pathlib.Path) -> None:
        self._files[lib_name] = pathlib.Path(path)

    def add_dir(self, lib_name: str, path: str | pathlib.Path) -> None:
        self._files[lib_name] = pathlib.Path(path)

    def get(self, lib_id: str) -> Symbol:
        if lib_id in self._cache:
            return self._cache[lib_id]
        lib, name = lib_id.split(":", 1)
        src = self._files.get(lib)
        if src is None:
            raise KeyError(f"no source registered for library {lib!r}")
        path = src / f"{name}.kicad_sym" if src.is_dir() else src
        text = path.read_text()
        block = _extract_symbol_block(text, name)
        if block is None:
            raise KeyError(f"symbol {name!r} not found in {path}")

        # KiCad derived symbols carry only overridden properties and inherit
        # all geometry from their parent. Flatten so the embedded lib_symbols
        # entry is self-contained.
        parent = get_value(parse(block), "extends")
        if parent:
            ptext = ((src / f"{parent}.kicad_sym").read_text()
                     if src.is_dir() else text)
            pblock = _extract_symbol_block(ptext, parent)
            if pblock is None:
                raise KeyError(f"parent symbol {parent!r} of {name!r} not found")
            block = _flatten(pblock, block, parent, name)

        node = parse(block)
        sym = Symbol(lib_id, block, node)
        self._cache[lib_id] = sym
        return sym


def _flatten(parent_block: str, child_block: str, parent: str, child: str) -> str:
    """Merge a derived symbol into its parent's geometry.

    Takes the parent's full definition, renames it (and its unit sub-symbols)
    to the child, and overrides any property the child redefines.
    """
    out = re.sub(r'^\(symbol\s+"[^"]*"', f'(symbol "{child}"',
                 parent_block.strip(), count=1)
    out = re.sub(r'\(symbol\s+"' + re.escape(parent) + r'_(\d+_\d+)"',
                 lambda m: f'(symbol "{child}_{m.group(1)}"', out)
    for p in find_all(parse(child_block), "property"):
        if len(p) < 3:
            continue
        pname, pval = p[1], p[2]
        pat = r'(\(property\s+"' + re.escape(pname) + r'"\s+)"[^"]*"'
        if re.search(pat, out):
            out = re.sub(pat, lambda m: m.group(1) + f'"{pval}"', out, count=1)
    return out


def _extract_symbol_block(text: str, name: str) -> str | None:
    """Pull one top-level (symbol "name" ...) block out of a .kicad_sym file."""
    m = re.search(r'\(symbol\s+"' + re.escape(name) + r'"[\s\n]', text)
    if not m:
        return None
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
                    return text[i:j + 1]
        j += 1
    return None


class Placed:
    """A symbol instance on a sheet; `.pin()` gives absolute coordinates."""

    def __init__(self, sym: Symbol, x: float, y: float, rot: int, ref: str):
        self.sym, self.x, self.y, self.rot, self.ref = sym, x, y, rot, ref

    def pin(self, key: str) -> tuple[float, float]:
        p = self.sym.pins.get(str(key))
        if p is None:
            cands = self.sym.by_name.get(str(key))
            if not cands:
                raise KeyError(
                    f"{self.ref}: no pin {key!r}; have numbers "
                    f"{sorted(self.sym.pins)} names {sorted(self.sym.by_name)}"
                )
            p = cands[0]
        dx, dy = _xf(p.x, p.y, self.rot)
        return (round(self.x + dx, 4), round(self.y + dy, 4))

    def pins_named(self, name: str) -> list[tuple[float, float]]:
        out = []
        for p in self.sym.by_name.get(name, []):
            dx, dy = _xf(p.x, p.y, self.rot)
            out.append((round(self.x + dx, 4), round(self.y + dy, 4)))
        return out


class Sheet:
    def __init__(self, sheet_uuid: str, root_uuid: str, project: str,
                 paper: str = "A3", title: str = "", rev: str = "",
                 date: str = "", comments: tuple[str, ...] = (),
                 pwr_base: int = 0):
        """`pwr_base` offsets this sheet's #PWRnnn designators. References must
        be unique across the whole design, so each sheet takes its own block."""
        self.uuid, self.root_uuid, self.project = sheet_uuid, root_uuid, project
        self.paper, self.title, self.rev, self.date = paper, title, rev, date
        self.comments = comments
        self.lib = SymbolLib()
        self._used: dict[str, Symbol] = {}
        self._symbols: list[str] = []
        self._graphics: list[str] = []
        self._segs: list = []
        self._anchors: list = []
        self._pwr_n = pwr_base

    # ---------- placement ----------

    def place(self, lib_id: str, ref: str, value: str, x: float, y: float,
              rot: int = 0, footprint: str = "", datasheet: str = "",
              description: str = "", dnp: bool = False,
              extra: dict[str, str] | None = None,
              ref_at: tuple[float, float] | None = None,
              val_at: tuple[float, float] | None = None,
              hide_value: bool = False, hide_ref: bool = False,
              justify: str | None = None, unit: int = 1,
              prop_angle: int | None = None) -> Placed:
        sym = self.lib.get(lib_id)
        self._used[lib_id] = sym
        uid = u()
        rx, ry = ref_at if ref_at else (x, y - 5.08)
        vx, vy = val_at if val_at else (x, y + 5.08)

        # KiCad adds the symbol's rotation to each property's own angle, so a
        # property on a 90-degree symbol renders sideways unless counter-rotated.
        # The counter-rotation below is right for 90 and 270 but not for 180:
        # KiCad renders a 180-degree symbol's properties upside down anyway, so
        # a part placed at 180 (a diode drawn anode-left, say) prints its
        # reference mirrored. `prop_angle` overrides it; pass 0 for that case.
        prop_angle = (-rot) % 360 if prop_angle is None else prop_angle % 360

        def prop(n, v, px, py, hide, size=1.27, just=justify):
            h = "\n\t\t\t(hide yes)" if hide else ""
            j = f"\n\t\t\t\t(justify {just})" if just and not hide else ""
            return (
                f'\t\t(property "{n}" "{v}"\n'
                f"\t\t\t(at {_fmt(px)} {_fmt(py)} {prop_angle}){h}\n"
                f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size {size} {size})\n"
                f"\t\t\t\t){j}\n\t\t\t)\n\t\t)\n"
            )

        s = [
            "\t(symbol\n",
            f'\t\t(lib_id "{lib_id}")\n',
            f"\t\t(at {_fmt(x)} {_fmt(y)} {rot})\n",
            f"\t\t(unit {unit})\n",
            "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n",
            f"\t\t(dnp {'yes' if dnp else 'no'})\n",
            f'\t\t(uuid "{uid}")\n',
            prop("Reference", ref, rx, ry, hide_ref),
            prop("Value", value, vx, vy, hide_value),
            prop("Footprint", footprint, x, y, True, 1.27),
            prop("Datasheet", datasheet, x, y, True),
            prop("Description", description, x, y, True),
        ]
        for k, v in (extra or {}).items():
            s.append(prop(k, v, x, y, True))
        s.append(
            "\t\t(instances\n"
            f'\t\t\t(project "{self.project}"\n'
            f'\t\t\t\t(path "/{self.root_uuid}/{self.uuid}"\n'
            f'\t\t\t\t\t(reference "{ref}")\n\t\t\t\t\t(unit {unit})\n'
            "\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n"
        )
        self._symbols.append("".join(s))
        return Placed(sym, x, y, rot, ref)

    def power(self, rail: str, x: float, y: float, rot: int = 0) -> Placed:
        """Place a power symbol. `rail` sets the net name (Value field).

        The reference is hidden — visible #PWRnnn designators on every rail
        stub swamp a dense sheet and carry no information.
        """
        self._pwr_n += 1
        ref = f"#PWR{self._pwr_n:03d}"
        lib_id = "power:GND" if rail == "GND" else "symbols:+V"
        val_at = (x, y + 3.81) if rail == "GND" else (x, y - 3.81)
        return self.place(lib_id, ref, rail, x, y, rot,
                          ref_at=(x, y), val_at=val_at, hide_ref=True)

    # ---------- connectivity ----------

    def wire(self, *pts: tuple[float, float]) -> None:
        for a, b in zip(pts, pts[1:]):
            if a != b:
                self._segs.append((a, b))
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            self._graphics.append(
                "\t(wire\n\t\t(pts\n"
                f"\t\t\t(xy {_fmt(a[0])} {_fmt(a[1])}) (xy {_fmt(b[0])} {_fmt(b[1])})\n"
                "\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
                f'\t\t(uuid "{u()}")\n\t)\n'
            )

    def junction(self, x: float, y: float) -> None:
        self._graphics.append(
            f"\t(junction\n\t\t(at {_fmt(x)} {_fmt(y)})\n\t\t(diameter 0)\n"
            "\t\t(color 0 0 0 0)\n"
            f'\t\t(uuid "{u()}")\n\t)\n'
        )

    def nc(self, x: float, y: float) -> None:
        self._graphics.append(
            f"\t(no_connect\n\t\t(at {_fmt(x)} {_fmt(y)})\n"
            f'\t\t(uuid "{u()}")\n\t)\n'
        )

    def label(self, x: float, y: float, text: str, rot: int = 0,
              justify: str = "left") -> None:
        self._anchors.append((x, y, text))
        self._graphics.append(
            f'\t(label "{text}"\n\t\t(at {_fmt(x)} {_fmt(y)} {rot})\n'
            "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {justify} bottom)\n\t\t)\n"
            f'\t\t(uuid "{u()}")\n\t)\n'
        )

    def hlabel(self, x: float, y: float, text: str, shape: str = "bidirectional",
               rot: int = 0, justify: str | None = None) -> None:
        """A hierarchical label. `justify` defaults to match the rotation.

        A label at rot 180 points left, so its text must extend left too --
        `justify left` would run the text back along the wire it is attached to
        and print it on top of the line. Callers can still override.
        """
        if justify is None:
            justify = "right" if rot == 180 else "left"
        self._anchors.append((x, y, text))
        self._graphics.append(
            f'\t(hierarchical_label "{text}"\n\t\t(shape {shape})\n'
            f"\t\t(at {_fmt(x)} {_fmt(y)} {rot})\n"
            "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {justify})\n\t\t)\n"
            f'\t\t(uuid "{u()}")\n\t)\n'
        )

    def text(self, x: float, y: float, s: str, size: float = 1.27) -> None:
        self._graphics.append(
            f'\t(text "{s}"\n\t\t(exclude_from_sim no)\n'
            f"\t\t(at {_fmt(x)} {_fmt(y)} 0)\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n\t\t\t)\n"
            "\t\t\t(justify left bottom)\n\t\t)\n"
            f'\t\t(uuid "{u()}")\n\t)\n'
        )

    # ---------- output ----------

    def check_label_crossings(self) -> None:
        """No wire may pass *through* a label anchor it does not belong to.

        This is the bug that has bitten this project four times and that ERC is
        blind to: a wire routed past a label's anchor point silently merges that
        label's net into the wire's. WP5 shorted seven FPGA balls to
        `VCOM_MEA_EN`; WP7 shorted seven `DPI_*` to the panel bus; WP8 shorted
        `SOM_IRQ#`/`SOM_WAKE#` to `+VBUS`; WP6 shorted the always-on I2C bus to
        `GND`. Every one looked correct on the page.

        Ending *at* an anchor is how a label is attached and is fine. Passing
        through its interior is not, so that is what this rejects.
        """
        bad = []
        for (x1, y1), (x2, y2) in self._segs:
            for ax, ay, text in self._anchors:
                if (abs(ax - x1) < 1e-4 and abs(ay - y1) < 1e-4) or \
                   (abs(ax - x2) < 1e-4 and abs(ay - y2) < 1e-4):
                    continue                      # the wire ends here: fine
                if abs(x1 - x2) < 1e-4 and abs(ax - x1) < 1e-4:
                    lo, hi = sorted((y1, y2))
                    if lo - 1e-4 < ay < hi + 1e-4:
                        bad.append(f"vertical wire x={x1:g} y={lo:g}..{hi:g} "
                                   f"runs through label {text!r} at ({ax:g}, {ay:g})")
                elif abs(y1 - y2) < 1e-4 and abs(ay - y1) < 1e-4:
                    lo, hi = sorted((x1, x2))
                    if lo - 1e-4 < ax < hi + 1e-4:
                        bad.append(f"horizontal wire y={y1:g} x={lo:g}..{hi:g} "
                                   f"runs through label {text!r} at ({ax:g}, {ay:g})")
        if bad:
            raise AssertionError(
                f"{len(bad)} wire(s) pass through a label anchor and would "
                f"silently merge nets:\n  " + "\n  ".join(sorted(set(bad))[:8]))

    def check_grid(self) -> None:
        """Every wire endpoint and label must sit on the 1.27 mm grid.

        Eeschema's default schematic grid is 1.27 mm, and KiCad's ERC reports an
        off-grid endpoint as `endpoint_off_grid` -- correctly, because a wire
        that ends 0.36 mm from a pin looks connected and is not. The usual cause
        is a symbol origin chosen for looks rather than as a multiple of the
        grid, which then shifts every pin on that part. `gen_dpi_in.py` did
        exactly that with `UY = 130.0` and put all 22 of its wires off-grid, so
        this runs automatically at render time rather than on request.
        """
        bad = []
        for kind, blocks in (("wire", self._graphics),):
            for blk in blocks:
                if not blk.lstrip().startswith(f"({kind}"):
                    continue
                for m in re.finditer(r"\(xy ([-\d.]+) ([-\d.]+)\)", blk):
                    x, y = float(m.group(1)), float(m.group(2))
                    for v, ax in ((x, "x"), (y, "y")):
                        if abs(round(v / GRID) * GRID - v) > 1e-4:
                            bad.append(f"{kind} endpoint {ax}={v} at ({x}, {y})")
        if bad:
            shown = "\n  ".join(sorted(set(bad))[:6])
            raise AssertionError(
                f"{len(set(bad))} off-grid endpoints; the symbol origin is "
                f"probably not a multiple of {GRID} mm:\n  {shown}")

    def render(self) -> str:
        self.check_grid()
        self.check_label_crossings()
        tb = [f'\t\t(title "{self.title}")\n'] if self.title else []
        if self.date:
            tb.append(f'\t\t(date "{self.date}")\n')
        if self.rev:
            tb.append(f'\t\t(rev "{self.rev}")\n')
        for i, c in enumerate(self.comments, 1):
            tb.append(f'\t\t(comment {i} "{c}")\n')
        libs = "".join(
            "\n".join("\t\t" + ln for ln in s.source.splitlines()) + "\n"
            for s in self._used.values()
        )
        return (
            "(kicad_sch\n\t(version 20250114)\n\t(generator \"eeschema\")\n"
            '\t(generator_version "9.0")\n'
            f'\t(uuid "{self.uuid}")\n\t(paper "{self.paper}")\n'
            + ("\t(title_block\n" + "".join(tb) + "\t)\n" if tb else "")
            + "\t(lib_symbols\n" + libs + "\t)\n"
            + "".join(self._graphics)
            + "".join(self._symbols)
            + "\t(embedded_fonts no)\n)\n"
        )

    def write(self, path: str | pathlib.Path) -> None:
        pathlib.Path(path).write_text(self.render())


def sheet_uuids(root_sch: str | pathlib.Path) -> tuple[str, dict[str, str]]:
    """Read the root sheet's uuid and each child's uuid, keyed by Sheetfile stem."""
    root = parse(pathlib.Path(root_sch).read_text())
    ruid = get_value(root, "uuid")
    out = {}
    for sh in find_all(root, "sheet"):
        suid = get_value(sh, "uuid")
        fname = None
        for p in find_all(sh, "property"):
            if len(p) > 2 and p[1] == "Sheetfile":
                fname = p[2]
        if fname:
            out[fname.replace(".kicad_sch", "")] = suid
    return ruid, out
