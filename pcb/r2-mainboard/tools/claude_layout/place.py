#!/usr/bin/env python3
"""Place R2.

Follows `docs/layout.md` §6.3's order: the enclosure-fixed parts are anchors and
everything else arranges around them.

  anchors   `X2`/`J26`/`J27` (SoM, top right, §1.1), `U41`+`U52` (FPGA+DRAM as a
            pair, §6.3 step 5), `J6` (panel flex landing zone, §1.2) and the
            other panel tails.
  regions   every other part gets a preferred rectangle from its sheet, so the
            optimiser starts from a floorplan rather than from noise.
  cost      half-perimeter wire length per net, plus penalties for courtyard
            overlap, leaving the board, and breaking a `check_pcb.py`
            proximity rule.

Three phases: force-directed spread inside the region, legalisation that pushes
courtyards apart, then simulated annealing over moves/swaps/rotations.

`GND` and the named rails are weighted down to 0.05 -- they are solved by the
`In1.Cu`/`In2.Cu` planes, not by placement, so letting them pull parts around
would distort the signal floorplan for nothing.
"""
from __future__ import annotations

import collections
import math
import random

import board

# --------------------------------------------------------------------------- #
# board and floorplan
# --------------------------------------------------------------------------- #
BOARD = (100.0, 20.0, 190.0, 100.0)          # R1's 90 x 80 mm, layout.md §1.2
EDGE = 1.0                                   # keep courtyards off the rout
GAP = 0.15                                   # courtyard-to-courtyard air

PLANE_NETS = {"GND"}
RAIL_NETS = {"+3V3", "+1V5", "+3V3_AON", "+VSYS", "+1V2_FPGA", "+5V_EPD",
             "+1V8", "+2V5", "+5V", "+VBAT", "+VBUS", "+3V3_SOM", "+5V_SOM"}
PLANE_W, RAIL_W, SIG_W = 0.02, 0.15, 1.0

# Anchors keep the owner's placement where it was a deliberate decision
# (layout.md §1.1 SoM top-right, §6.3 step 5 FPGA+DRAM pair). J6 and the other
# panel tails move to the left edge: the SoM owns the right-hand side, and
# §1.1 says the HV chain is what moves when the two compete for a corner.
ANCHORS = {
    "X2":  (164.20, 41.03,  90),
    "J26": (161.80, 52.23,  90),
    "J27": (166.60, 29.83,  90),
    "U41": (167.00, 81.50, -90),
    "U52": (146.70, 81.00, 180),
    "J6":  (105.00, 62.00,  90),     # panel flex, left edge, facing the fold
    "J23": (104.00, 33.00,  90),     # pen tail
    "J22": (104.00, 41.00,  90),     # touch tail
    "J24": (104.00, 88.00,  90),     # frontlight tail
    "J1":  (183.50, 63.00, 180),     # USB-C, right edge next to the SoM (§1.1)
    # §6.3 step 8: the MCU and its crystal are placed *against* their
    # constraint, not into the space that is left. Left alone the optimiser
    # kept squeezing this 13.4 mm part onto the board edge and then could not
    # get its four decoupling caps inside their 4-6 mm limits.
    "U20": (120.00, 30.00,   0),
    "Y20": (120.00, 38.00,   0),     # mcu.md §11.3, hard against U20
}

# Preferred rectangle per sheet (x0, y0, x1, y1). The HV chain follows J6 on
# the left (epd-port.md §11); the DDR3 group hugs the two BGAs; battery and
# power sit top-left away from the panel tails.
REGIONS = {
    # Disjoint by construction, sized against each sheet's courtyard area.
    # The SoM stands 5 mm off the board (layout.md §3.2), so its shadow is a
    # legal home for low parts -- that is where /som/'s own passives go.
    "/mcu/":          (108.0, 20.0, 142.0, 45.0),
    "/io_expansion/": (106.0, 36.0, 126.0, 48.0),
    "/som/":          (146.0, 35.0, 184.0, 47.0),
    "/power/":        (126.0, 34.0, 152.0, 58.0),
    "/epd/":          (108.0, 45.0, 130.0, 62.0),
    "/power_mon/":    (120.0, 45.0, 142.0, 62.0),
    "/epd_power/":    (108.0, 60.0, 142.0, 100.0),
    "/frontlight/":   (100.0, 84.0, 118.0, 100.0),
    "/fpga_ddr/":     (140.0, 58.0, 178.0, 100.0),
    "/fpga_config/":  (150.0, 88.0, 190.0, 100.0),
    "/fpga_io/":      (158.0, 68.0, 190.0, 96.0),
    "/battery/":      (166.0, 66.0, 190.0, 100.0),
}

# check_pcb.py's PROXIMITY table, as hard constraints here
PROXIMITY = [
    ("C41", "U20", 4.0), ("C40", "U20", 6.0), ("C44", "U20", 5.0),
    ("C45", "U20", 5.0), ("Y20", "U20", 8.0), ("C46", "Y20", 4.0),
    ("C47", "Y20", 4.0), ("R512", "U20", 6.0), ("C25", "U12", 4.0),
    ("C26", "U12", 4.0), ("C27", "U12", 4.0), ("L10", "U12", 5.0),
    ("C29", "U13", 4.0), ("C30", "U13", 4.0), ("L11", "U13", 5.0),
    ("C31", "U14", 3.5), ("C32", "U14", 3.5), ("L12", "U14", 4.0),
    ("C33", "U15", 3.5), ("C34", "U15", 3.5), ("L13", "U15", 4.0),
    ("C20", "U10", 3.5), ("C21", "U10", 3.5), ("C6", "U1", 5.0),
    ("C1", "U1", 5.0), ("C2", "U1", 5.0), ("C3", "U1", 5.0),
    ("U3", "J1", 8.0), ("R340", "U41", 8.0), ("R102", "U52", 8.0),
    ("C507", "X1", 4.0), ("R409", "X1", 6.0), ("D34", "U53", 4.0),
    ("C515", "U53", 5.0),
]


class Placer:
    def __init__(self, b: board.Board, seed=20260821):
        self.b = b
        self.rng = random.Random(seed)
        self.fps = b.footprints
        self.fixed = set(ANCHORS)
        self.movable = [r for r in self.fps if r not in self.fixed]
        self.size = {}          # ref -> (w, h) of the courtyard, unrotated
        for r, fp in self.fps.items():
            if fp.courtyard:
                x0, y0, x1, y1 = fp.courtyard
                self.size[r] = (x1 - x0, y1 - y0)
            else:
                self.size[r] = (1.0, 1.0)
        self.apply_anchors()
        self.build_keepouts()
        self.nets = self._nets()
        self.conn = self._conn()
        # Six of check_pcb.py's 34 limits are smaller than the closest two
        # non-overlapping courtyards can physically get -- five of them against
        # U20 (13.4 mm courtyard) and one against U41 (18 mm). Chasing an
        # impossible number would drag the whole neighbourhood around for
        # nothing, so each limit is raised to what geometry allows and the
        # shortfall is reported instead of optimised.
        self.prox_pairs = collections.defaultdict(list)
        self.prox_floor = {}
        for a, other, d in PROXIMITY:
            if a not in self.fps or other not in self.fps:
                continue
            aw, ah = self.size[a]
            ow, oh = self.size[other]
            floor = min(ow, oh) / 2 + GAP + min(aw, ah) / 2
            eff = max(d, floor + 0.02)
            self.prox_floor[(a, other)] = (d, floor)
            self.prox_pairs[a].append((other, eff))
            self.prox_pairs[other].append((a, eff))

    def prox_report(self):
        """Achieved centre-to-centre vs the documented and physical limits."""
        rows = []
        for (a, other), (lim, floor) in self.prox_floor.items():
            d = math.hypot(self.fps[a].x - self.fps[other].x,
                           self.fps[a].y - self.fps[other].y)
            rows.append((a, other, lim, floor, d,
                         d <= lim + 1e-6,
                         d <= max(lim, floor) + 0.05))
        return rows

    def apply_anchors(self):
        """Put the enclosure-fixed parts where layout.md §6.3 says they go."""
        for ref, (x, y, rot) in ANCHORS.items():
            if ref not in self.fps:
                raise KeyError("anchor %s is not on the board" % ref)
            f = self.fps[ref]
            f.x, f.y, f.rot = float(x), float(y), float(rot)

    # -- model -------------------------------------------------------------- #
    def _nets(self):
        d = collections.defaultdict(set)
        for fp in self.fps.values():
            for p in fp.pads:
                if p.net:
                    d[p.net].add(fp.ref)
        out = {}
        for n, refs in d.items():
            if len(refs) < 2 or len(refs) > 40:
                continue          # 1-pin nets and the plane fan-outs
            w = (PLANE_W if n in PLANE_NETS
                 else RAIL_W if n in RAIL_NETS else SIG_W)
            out[n] = (sorted(refs), w)
        return out

    def _conn(self):
        c = collections.defaultdict(list)
        for n, (refs, w) in self.nets.items():
            for r in refs:
                c[r].append(n)
        return c

    def build_keepouts(self):
        """Every NPTH hole is a hard obstacle -- notably `X2`'s two M2.5.

        A hole is tagged with the footprint that owns it, because a part's own
        mounting holes sit inside its own courtyard: counting those as
        violations made the figure a constant 11.8 mm2 that legalisation could
        never drive to zero.
        """
        self.keepouts = []
        for fp in self.fps.values():
            for p in fp.pads:
                if p.kind != "np_thru_hole":
                    continue
                cx, cy = fp.pad_xy(p)
                w, h = p.w / 2 + 0.25, p.h / 2 + 0.25
                self.keepouts.append((cx - w, cy - h, cx + w, cy + h, fp.ref))

    def keepout_overlap(self, ref):
        x0, y0, x1, y1 = self.box(ref)
        tot = 0.0
        for a0, b0, a1, b1, owner in self.keepouts:
            if owner == ref:
                continue
            dx = min(x1, a1) - max(x0, a0)
            dy = min(y1, b1) - max(y0, b0)
            if dx > 0 and dy > 0:
                tot += dx * dy
        return tot

    def box(self, ref, x=None, y=None, rot=None):
        """Board-space AABB of the courtyard.

        Not `centre +- w/2`: a connector's courtyard is rarely centred on its
        footprint origin (`J6`'s runs 15 mm one way and 16 mm the other), so
        centring a w x h box on the origin puts the obstacle in the wrong
        place. KiCad found eight overlaps this metric called zero.
        """
        fp = self.fps[ref]
        x = fp.x if x is None else x
        y = fp.y if y is None else y
        rot = fp.rot if rot is None else rot
        cy = fp.courtyard
        if cy is None:
            return (x - 0.5, y - 0.5, x + 0.5, y + 0.5)
        a = math.radians(rot)
        ca, sa = math.cos(a), math.sin(a)
        xs, ys = [], []
        for lx in (cy[0], cy[2]):
            for ly in (cy[1], cy[3]):
                xs.append(x + lx * ca + ly * sa)
                ys.append(y - lx * sa + ly * ca)
        return (min(xs), min(ys), max(xs), max(ys))

    # -- cost --------------------------------------------------------------- #
    def hpwl(self, pos=None):
        pos = pos or {r: (f.x, f.y) for r, f in self.fps.items()}
        total = 0.0
        for n, (refs, w) in self.nets.items():
            xs = [pos[r][0] for r in refs]
            ys = [pos[r][1] for r in refs]
            total += w * ((max(xs) - min(xs)) + (max(ys) - min(ys)))
        return total

    # -- spatial index for overlap ------------------------------------------ #
    def _grid_key(self, x, y):
        return (int(x // 4), int(y // 4))

    def build_index(self):
        self.idx = collections.defaultdict(set)
        for r in self.fps:
            self._index_add(r)

    def _cells(self, ref):
        x0, y0, x1, y1 = self.box(ref)
        for gx in range(int((x0 - GAP) // 4), int((x1 + GAP) // 4) + 1):
            for gy in range(int((y0 - GAP) // 4), int((y1 + GAP) // 4) + 1):
                yield (gx, gy)

    def _index_add(self, ref):
        for c in self._cells(ref):
            self.idx[c].add(ref)

    def _index_del(self, ref):
        for c in self._cells(ref):
            self.idx[c].discard(ref)

    def overlap_of(self, ref):
        """Total courtyard overlap area between `ref` and its neighbours."""
        x0, y0, x1, y1 = self.box(ref)
        seen, tot = set(), 0.0
        for c in self._cells(ref):
            for o in self.idx.get(c, ()):
                if o == ref or o in seen:
                    continue
                seen.add(o)
                a0, b0, a1, b1 = self.box(o)
                dx = min(x1 + GAP, a1) - max(x0 - GAP, a0)
                dy = min(y1 + GAP, b1) - max(y0 - GAP, b0)
                if dx > 0 and dy > 0:
                    tot += dx * dy
        return tot

    def outside_of(self, ref):
        x0, y0, x1, y1 = self.box(ref)
        bx0, by0, bx1, by1 = BOARD
        dx = max(0.0, (bx0 + EDGE) - x0) + max(0.0, x1 - (bx1 - EDGE))
        dy = max(0.0, (by0 + EDGE) - y0) + max(0.0, y1 - (by1 - EDGE))
        return dx + dy

    def prox_of(self, ref):
        """How far a proximity rule involving `ref` is being broken, in mm."""
        pen = 0.0
        s = self.fps[ref]
        for other, lim in self.prox_pairs.get(ref, ()):
            o = self.fps[other]
            pen += max(0.0, math.hypot(s.x - o.x, s.y - o.y) - lim)
        return pen

    def local_cost(self, ref, W_OVL=40.0, W_OUT=60.0, W_PROX=25.0):
        fps = self.fps
        c = 0.0
        for n in self.conn.get(ref, ()):
            refs, w = self.nets[n]
            x0 = y0 = 1e9
            x1 = y1 = -1e9
            for r in refs:
                f = fps[r]
                if f.x < x0: x0 = f.x
                if f.x > x1: x1 = f.x
                if f.y < y0: y0 = f.y
                if f.y > y1: y1 = f.y
            c += w * ((x1 - x0) + (y1 - y0))
        c += W_OVL * (self.overlap_of(ref) + self.keepout_overlap(ref))
        c += W_OUT * self.outside_of(ref)
        c += W_PROX * self.prox_of(ref)
        return c

    # -- phases ------------------------------------------------------------- #
    def seed_regions(self):
        """Drop every movable part into its sheet's rectangle on a lattice."""
        bysheet = collections.defaultdict(list)
        for r in self.movable:
            bysheet[self.fps[r].sheet].append(r)
        for sheet, refs in bysheet.items():
            x0, y0, x1, y1 = REGIONS.get(sheet, BOARD)
            refs.sort(key=lambda r: -self.size[r][0] * self.size[r][1])
            n = len(refs)
            cols = max(1, int(math.ceil(math.sqrt(n * (x1 - x0) / max(y1 - y0, 1)))))
            rows = int(math.ceil(n / cols))
            for i, r in enumerate(refs):
                cx = x0 + (x1 - x0) * ((i % cols) + 0.5) / cols
                cy = y0 + (y1 - y0) * ((i // cols) + 0.5) / rows
                f = self.fps[r]
                f.x, f.y = cx, cy

    def anneal(self, iters=400000, t0=6.0, t1=0.05, log=None):
        self.build_index()
        rng = self.rng
        mov = self.movable
        cur = sum(self.local_cost(r) for r in mov)
        best = cur
        bx0, by0, bx1, by1 = BOARD
        for it in range(iters):
            T = t0 * (t1 / t0) ** (it / iters)
            ref = rng.choice(mov)
            f = self.fps[ref]
            old = (f.x, f.y, f.rot)
            before = self.local_cost(ref)
            kind = rng.random()
            if kind < 0.55:                      # jitter
                s = 0.6 + 14.0 * (T / t0)
                nx = min(bx1 - EDGE, max(bx0 + EDGE, f.x + rng.gauss(0, s)))
                ny = min(by1 - EDGE, max(by0 + EDGE, f.y + rng.gauss(0, s)))
                nr = f.rot
            elif kind < 0.75:                    # rotate
                nx, ny = f.x, f.y
                nr = rng.choice([0, 90, 180, -90])
            else:                                # teleport near a net partner
                ns = self.conn.get(ref)
                if not ns:
                    continue
                refs, _ = self.nets[rng.choice(ns)]
                tgt = self.fps[rng.choice(refs)]
                nx = min(bx1 - EDGE, max(bx0 + EDGE, tgt.x + rng.gauss(0, 3)))
                ny = min(by1 - EDGE, max(by0 + EDGE, tgt.y + rng.gauss(0, 3)))
                nr = f.rot
            self._index_del(ref)
            f.x, f.y, f.rot = nx, ny, nr
            self._index_add(ref)
            after = self.local_cost(ref)
            d = after - before
            if d <= 0 or rng.random() < math.exp(-d / max(T, 1e-9)):
                cur += d
            else:
                self._index_del(ref)
                f.x, f.y, f.rot = old
                self._index_add(ref)
            if log and it % (iters // 10) == 0:
                log(it, T, cur, self.report())
        return cur

    def report(self):
        ovl = sum(self.overlap_of(r) for r in self.fps) / 2.0
        out = sum(self.outside_of(r) for r in self.fps)
        prox = sum(self.prox_of(r) for r in self.fps) / 2.0
        return dict(hpwl=round(self.hpwl(), 1), overlap=round(ovl, 2),
                    outside=round(out, 2), prox=round(prox, 2))

    # -- legalisation ------------------------------------------------------- #
    def overlapping_pairs(self):
        """Every pair of parts whose courtyards (plus GAP) intersect."""
        pairs = set()
        for ref in self.fps:
            x0, y0, x1, y1 = self.box(ref)
            for c in self._cells(ref):
                for o in self.idx.get(c, ()):
                    if o == ref:
                        continue
                    a0, b0, a1, b1 = self.box(o)
                    dx = min(x1 + GAP, a1) - max(x0 - GAP, a0)
                    dy = min(y1 + GAP, b1) - max(y0 - GAP, b0)
                    if dx > 0 and dy > 0:
                        pairs.add(tuple(sorted((ref, o))))
        return pairs

    def legalize(self, rounds=4000):
        """Push overlapping courtyards, and parts sitting on NPTH holes, apart.

        Both kinds of violation get the same treatment: displace along the
        shortest escape from the overlap rectangle. Random jitter was tried
        first and is worse -- it fights the pair separation and neither
        converges.
        """
        bx0, by0, bx1, by1 = BOARD

        def shove(ref, ox0, oy0, ox1, oy1):
            """Move `ref` out of the box it overlaps, the short way."""
            f = self.fps[ref]
            x0, y0, x1, y1 = self.box(ref)
            left = x1 - ox0 + GAP
            right = ox1 - x0 + GAP
            up = y1 - oy0 + GAP
            down = oy1 - y0 + GAP
            d, dx, dy = min((left, -left, 0.0), (right, right, 0.0),
                            (up, 0.0, -up), (down, 0.0, down))
            self._index_del(ref)
            f.x = min(bx1 - EDGE, max(bx0 + EDGE, f.x + dx + 1e-3))
            f.y = min(by1 - EDGE, max(by0 + EDGE, f.y + dy + 1e-3))
            self._index_add(ref)

        for it in range(rounds):
            pairs = self.overlapping_pairs()
            ko = [(r, k[:4]) for r in self.movable
                  for k in self.keepouts
                  if k[4] != r and self._hits(r, k[:4])]
            if not pairs and not ko:
                return it
            for ref, k in ko:
                shove(ref, *k)
            for a, c in pairs:
                movable = [r for r in (a, c) if r not in self.fixed]
                if not movable:
                    continue
                # the anchor never yields; between two movables, split the move
                if len(movable) == 1:
                    other = a if movable[0] == c else c
                    shove(movable[0], *self.box(other))
                else:
                    shove(a, *self.box(c))
        return -rounds

    def _hits(self, ref, k):
        x0, y0, x1, y1 = self.box(ref)
        a0, b0, a1, b1 = k
        return min(x1, a1) > max(x0, a0) and min(y1, b1) > max(y0, b0)

    def polish(self, iters=300000, t0=0.8, t1=0.005, w_ovl=4000.0, log=None):
        """Low-temperature pass with overlap made near-prohibitive."""
        rng = self.rng
        mov = self.movable
        bx0, by0, bx1, by1 = BOARD

        def cost(ref):
            return self.local_cost(ref, W_OVL=w_ovl, W_OUT=4000.0, W_PROX=400.0)

        for it in range(iters):
            T = t0 * (t1 / t0) ** (it / iters)
            ref = rng.choice(mov)
            f = self.fps[ref]
            old = (f.x, f.y, f.rot)
            before = cost(ref)
            if rng.random() < 0.8:
                s = 0.15 + 2.0 * (T / t0)
                nx = min(bx1 - EDGE, max(bx0 + EDGE, f.x + rng.gauss(0, s)))
                ny = min(by1 - EDGE, max(by0 + EDGE, f.y + rng.gauss(0, s)))
                nr = f.rot
            else:
                nx, ny = f.x, f.y
                nr = rng.choice([0, 90, 180, -90])
            self._index_del(ref)
            f.x, f.y, f.rot = nx, ny, nr
            self._index_add(ref)
            d = cost(ref) - before
            if d > 0 and rng.random() >= math.exp(-d / max(T, 1e-9)):
                self._index_del(ref)
                f.x, f.y, f.rot = old
                self._index_add(ref)
            if log and it % (iters // 6) == 0:
                log(it, T, 0.0, self.report())
