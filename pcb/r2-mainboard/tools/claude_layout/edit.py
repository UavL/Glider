#!/usr/bin/env python3
"""Surgical moves and rotations of footprints in a `.kicad_pcb`.

KiCad stores a footprint's pads and graphics in the part's own *unrotated*
frame and applies `(at x y rot)` at load time. So moving or rotating a part is
purely a matter of editing `(at ...)` entries, at three places and nowhere else:

  * the footprint's own `(at x y [rot])` -- the only one carrying position;
  * every `(pad ...)`'s `(at lx ly [rot])` -- local position untouched, the
    angle set to the footprint's rotation;
  * `(fp_text user ...)` and the five `(property ...)` texts, whose angle KiCad
    keeps so silkscreen stays readable.

Text angle is cosmetic, but `silk_overlap` and `text_height` are DRC rules, so
it is set the way KiCad sets it: the footprint's angle, normalised so text is
never upside down.
"""
from __future__ import annotations

import re


def _fmt(v: float) -> str:
    s = repr(round(float(v), 6))
    return s[:-2] if s.endswith(".0") else s


def _norm(a: float) -> float:
    a = float(a) % 360.0
    return a - 360.0 if a > 180.0 else a


def _text_angle(rot: float) -> float:
    """KiCad keeps footprint text upright: 180 and -90 fold back."""
    a = _norm(rot)
    if a == 180.0 or a == -180.0:
        return 0.0
    if a == -90.0:
        return 90.0
    return a


class BoardEditor:
    """Applies footprint moves to the raw text, one span at a time."""

    def __init__(self, board):
        self.board = board
        self.text = board.text
        self._edits = {}     # ref -> new block text

    # -- one footprint ------------------------------------------------------ #
    def place(self, ref: str, x: float, y: float, rot: float = None,
              layer: str = None):
        """Move/rotate one footprint.

        Pads, properties and `fp_text` all keep their `(at ...)` at the same
        nesting depth, so they cannot be told apart by indentation -- an
        earlier version did exactly that and silently gave every pad the
        *text* angle. `J21`'s pads carry an intrinsic 270 deg of their own, and
        losing it turned eight 1.1 mm-pitch pads sideways into each other.

        So the block is split into its depth-2 children and each kind is
        handled for what it is: a pad's angle becomes the footprint's rotation
        plus whatever intrinsic offset it was drawn with; text takes the
        upright-normalised angle; local coordinates are never touched.
        """
        fp = self.board.footprints[ref]
        s, e = fp.span
        blk = self._edits.get(ref, self.text[s:e])
        rot = fp.rot if rot is None else _norm(rot)
        if layer is not None and layer != fp.layer:
            raise NotImplementedError("side changes need pad/graphic mirroring")

        parts = re.split(r'(\n\t\t\((?:pad|property|fp_text) )', blk)
        out = [self._set_fp_at(parts[0], ref, x, y, rot)]
        for i in range(1, len(parts), 2):
            sep, body = parts[i], parts[i + 1]
            kind = sep.strip()[1:].split()[0]
            if kind == "pad":
                ang = _norm(rot + self._intrinsic(fp, body))
            else:
                ang = _text_angle(rot)
            out.append(sep)
            out.append(self._set_child_at(body, ang))
        self._edits[ref] = "".join(out)
        fp.x, fp.y, fp.rot = float(x), float(y), rot

    @staticmethod
    def _set_fp_at(head_text, ref, x, y, rot):
        rs = "" if rot == 0 else " " + _fmt(rot)
        new, n = re.subn(r'(\n\t\t\(at )[-\d.]+ [-\d.]+(?: [-\d.]+)?(\))',
                         lambda m: "%s%s %s%s%s" % (m.group(1), _fmt(x),
                                                    _fmt(y), rs, m.group(2)),
                         head_text, count=1)
        assert n == 1, "%s: footprint (at ...) not found" % ref
        return new

    @staticmethod
    def _set_child_at(body, ang):
        """Rewrite the first `(at lx ly [a])` in a child, keeping lx/ly."""
        a = "" if ang == 0 else " " + _fmt(ang)
        return re.sub(r'(\(at )([-\d.]+) ([-\d.]+)(?: [-\d.]+)?(\))',
                      lambda m: "%s%s %s%s%s" % (m.group(1), m.group(2),
                                                 m.group(3), a, m.group(4)),
                      body, count=1)

    @staticmethod
    def _intrinsic(fp, pad_body):
        """A pad's own rotation, independent of the footprint's."""
        m = re.search(r'\(at [-\d.]+ [-\d.]+ ([-\d.]+)\)', pad_body)
        stored = float(m.group(1)) if m else 0.0
        return _norm(stored - fp.rot0)

    # -- whole-document ----------------------------------------------------- #
    def add_before_close(self, chunk: str):
        """Append a top-level element just before the document's final paren."""
        assert self.text.endswith(")\n")
        self.text = self.text[:-2] + chunk + ")\n"

    def render(self) -> str:
        """Splice every edited block back, right to left so spans stay valid."""
        out = self.text
        items = sorted(((self.board.footprints[r].span, b)
                        for r, b in self._edits.items()),
                       key=lambda kv: -kv[0][0])
        for (s, e), blk in items:
            out = out[:s] + blk + out[e:]
        return out

    def save(self, path: str):
        with open(path, "w") as fh:
            fh.write(self.render())


def strip_routing(text: str) -> tuple:
    """Remove every `segment`, `via`, `arc` and `zone` from a board.

    The owner's file carries 54 track segments and 3 vias drawn against the old
    placement. Once parts move they are dangling copper, and KiCad's
    `track_dangling` rule flags them, so a re-place starts from bare pads.
    """
    counts = {}
    for tag in ("segment", "via", "arc", "zone"):
        pat = re.compile(r'\n\t\(%s\n.*?\n\t\)' % tag, re.S)
        # non-greedy across a whole block: match to the first depth-1 close
        out = []
        i = 0
        n = 0
        while True:
            m = re.search(r'\n\t\(%s\n' % tag, text[i:])
            if not m:
                out.append(text[i:])
                break
            s = i + m.start()
            e = text.index("\n\t)", s) + 3
            out.append(text[i:s])
            i = e
            n += 1
        text = "".join(out)
        counts[tag] = n
    return text, counts


def silk_text_to_fab(text: str) -> tuple:
    """Move every footprint *text* off `F.SilkS` and onto `F.Fab`.

    At this board's density (3290 mm2 of courtyard in 7200 mm2) silkscreen
    designators overlap pads and each other however the parts are arranged --
    705 violations on the first pass, and R1's imported rules make
    `silk_overlap`/`silk_over_copper` errors rather than warnings. Reference
    designators live on the fabrication layer instead, which is ordinary for a
    board this dense and costs nothing electrically; the assembly drawing
    carries them. Graphics are left alone -- part outlines are worth keeping.
    """
    n = 0
    out = []
    i = 0
    while True:
        m = re.search(r'\n\t\t\((?:property|fp_text) ', text[i:])
        if not m:
            out.append(text[i:])
            break
        s = i + m.start()
        e = text.index("\n\t\t)", s) + 5
        blk = text[s:e]
        if '(layer "F.SilkS")' in blk:
            blk = blk.replace('(layer "F.SilkS")', '(layer "F.Fab")', 1)
            n += 1
        out.append(text[i:s])
        out.append(blk)
        i = e
    return "".join(out), n


def silk_to_user_drawings(text: str, refs) -> tuple:
    """Move one footprint's silk *graphics* to `Dwgs.User`.

    `X2` is the SoM's 32 x 43 mm outline. The module stands 5 mm off the board
    and low parts legitimately live in its shadow (layout.md §3.2), so its silk
    corner ticks sit over their pads by design -- eight `silk_over_copper`
    errors that are not really errors. som.md §10 already puts the outline on
    `F.Fab` and `Dwgs.User`; this drops the redundant silk copy.
    """
    n = 0
    out, i = [], 0
    while True:
        m = re.search(r'\n\t\(footprint "', text[i:])
        if not m:
            out.append(text[i:])
            break
        s = i + m.start()
        e = text.index("\n\t)\n", s) + 4
        blk = text[s:e]
        r = re.search(r'Reference" "([^"]+)"', blk)
        if r and r.group(1) in refs:
            k = blk.count('(layer "F.SilkS")')
            blk = blk.replace('(layer "F.SilkS")', '(layer "Dwgs.User")')
            n += k
        out.append(text[i:s])
        out.append(blk)
        i = e
    return "".join(out), n
