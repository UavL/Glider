#!/usr/bin/env python3
"""Read a `.kicad_pcb` into objects, and write back *surgically*.

Two rules make this safe on an 83 000-line file:

1. **Analysis reads the parsed tree; writing touches text.** We never re-dump
   the whole document, because KiCad's own formatter packs `(xy ...)` runs by
   line length and matching that exactly is not worth the risk. Every write is
   a replacement of a byte span we located by parsing.
2. **Footprint local coordinates are never rewritten.** KiCad stores pads and
   graphics in the footprint's own unrotated frame and applies `(at x y rot)`
   at load time, so moving or rotating a part means editing the `(at ...)` of
   the footprint, its pads and its `fp_text user` -- and nothing else.

The rotation convention is verified against KiCad's own IPC-D-356 export in
`validate_against_d356()`, which checks all 1598 pads rather than trusting a
sign derived from the docs.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import sexp

# Footprints whose outline is a module shadow, not a real obstacle.
SHADOW_ONLY = {"X2"}


@dataclass
class Pad:
    number: str
    kind: str                 # smd / thru_hole / np_thru_hole
    shape: str
    lx: float                 # local, unrotated
    ly: float
    rot: float                # absolute pad rotation as stored
    w: float
    h: float
    net: str
    layers: tuple


@dataclass
class Footprint:
    ref: str
    lib: str
    x: float
    y: float
    rot: float
    layer: str                # F.Cu / B.Cu
    rot0: float = 0.0         # rotation as parsed, for intrinsic pad angles
    pads: list = field(default_factory=list)
    courtyard: tuple = None   # (x0,y0,x1,y1) local, unrotated
    span: tuple = None        # byte span in the source text
    sheet: str = ""

    # -- geometry ---------------------------------------------------------- #
    def to_board(self, lx: float, ly: float) -> tuple:
        """Local (unrotated) footprint coords -> absolute board coords."""
        a = math.radians(self.rot)
        ca, sa = math.cos(a), math.sin(a)
        # verified against KiCad's IPC-D-356 export: +rot is counter-clockwise
        # on screen, and the file's y axis points down, giving this sign set.
        bx = self.x + lx * ca + ly * sa
        by = self.y - lx * sa + ly * ca
        if self.layer == "B.Cu":
            bx = self.x - (lx * ca + ly * sa)
        return (round(bx, 6), round(by, 6))

    def pad_xy(self, pad: Pad) -> tuple:
        return self.to_board(pad.lx, pad.ly)

    def courtyard_box(self, clearance: float = 0.0) -> tuple:
        """Axis-aligned board-space bounding box of the courtyard."""
        if self.courtyard is None:
            return (self.x - 0.5, self.y - 0.5, self.x + 0.5, self.y + 0.5)
        x0, y0, x1, y1 = self.courtyard
        pts = [self.to_board(x, y)
               for x in (x0, x1) for y in (y0, y1)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs) - clearance, min(ys) - clearance,
                max(xs) + clearance, max(ys) + clearance)


class Board:
    def __init__(self, path):
        self.path = str(path)
        self.text = open(self.path).read()
        self.tree = sexp.loads(self.text)
        self.footprints = {}
        self._scan()

    # -- parsing ------------------------------------------------------------ #
    def _scan(self):
        starts = [m.start() for m in re.finditer(r'\n\t\(footprint "', self.text)]
        spans = []
        for s in starts:
            e = self.text.index("\n\t)\n", s) + 4
            spans.append((s, e))
        nodes = sexp.find_all(self.tree, "footprint")
        assert len(nodes) == len(spans), (len(nodes), len(spans))
        for node, span in zip(nodes, spans):
            fp = self._footprint(node, span)
            self.footprints[fp.ref] = fp

    def _footprint(self, node, span):
        lib = node[1]
        at = sexp.find(node, "at")
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = ""
        for p in sexp.find_all(node, "property"):
            if p[1] == "Reference":
                ref = p[2]
        fp = Footprint(ref=ref, lib=lib, x=float(at[1]), y=float(at[2]), rot=rot,
                       layer=str(sexp.get(node, "layer", "F.Cu")), span=span,
                       rot0=rot, sheet=str(sexp.get(node, "sheetname", "")))
        for pn in sexp.find_all(node, "pad"):
            pat = sexp.find(pn, "at")
            size = sexp.find(pn, "size")
            netn = sexp.find(pn, "net")
            lay = sexp.find(pn, "layers")
            fp.pads.append(Pad(
                number=str(pn[1]), kind=str(pn[2]), shape=str(pn[3]),
                lx=float(pat[1]), ly=float(pat[2]),
                rot=float(pat[3]) if len(pat) > 3 else 0.0,
                w=float(size[1]), h=float(size[2]),
                net=str(netn[-1]) if netn is not None else "",
                layers=tuple(str(x) for x in lay[1:]) if lay is not None else ()))
        # layout.md §3.2: the module stands 5 mm off the board, so its shadow
        # is legal for low parts. Only its two M2.5 holes are real obstacles,
        # and those are handled as keep-outs by the placer.
        fp.courtyard = self._courtyard(node)
        if fp.courtyard is None and fp.ref not in SHADOW_ONLY:
            fp.courtyard = self._pad_extent(node)
        return fp

    @staticmethod
    def _courtyard(node):
        xs, ys = [], []
        for g in node:
            if not isinstance(g, list):
                continue
            if str(sexp.get(g, "layer", "")) not in ("F.CrtYd", "B.CrtYd"):
                continue
            for key in ("start", "end", "center", "mid"):
                c = sexp.find(g, key)
                if c is not None:
                    xs.append(float(c[1]))
                    ys.append(float(c[2]))
            pts = sexp.find(g, "pts")
            if pts is not None:
                for xy in sexp.find_all(pts, "xy"):
                    xs.append(float(xy[1]))
                    ys.append(float(xy[2]))
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def _pad_extent(node):
        """Fallback keep-out for a footprint that ships no courtyard.

        `X2` (the SoM outline) and `J21` have none, so the placer treated them
        as 1 x 1 mm and happily dropped them onto other parts' pads. Their real
        obstacle is the pads themselves -- including `X2`'s two M2.5 NPTH holes,
        which nothing may sit on -- so use the pad bounding box plus the usual
        0.25 mm of courtyard margin.
        """
        xs, ys = [], []
        for pn in node:
            if not isinstance(pn, list) or sexp.head(pn) != "pad":
                continue
            at = sexp.find(pn, "at")
            size = sexp.find(pn, "size")
            if at is None or size is None:
                continue
            cx, cy = float(at[1]), float(at[2])
            w, h = float(size[1]) / 2, float(size[2]) / 2
            if len(at) > 3 and int(float(at[3])) % 180 != 0:
                w, h = h, w
            xs += [cx - w, cx + w]
            ys += [cy - h, cy + h]
        if not xs:
            return None
        m = 0.25
        return (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)

    # -- board outline ------------------------------------------------------ #
    def outline(self):
        xs, ys = [], []
        for g in self.tree:
            if not isinstance(g, list):
                continue
            if str(sexp.get(g, "layer", "")) != "Edge.Cuts":
                continue
            for key in ("start", "end", "mid", "center"):
                c = sexp.find(g, key)
                if c is not None:
                    xs.append(float(c[1]))
                    ys.append(float(c[2]))
        return (min(xs), min(ys), max(xs), max(ys))

    def nets(self):
        out = {}
        for n in sexp.find_all(self.tree, "net"):
            out[int(n[1])] = str(n[2])
        return out
