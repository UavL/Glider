#!/usr/bin/env python3
"""A* maze router for R2.

Layer plan (`layout.md` §6.1 step 2, §4):

    F.Cu    signal + GND pour
    In1.Cu  solid GND plane -- never routed on, so §7.2's "keep the whole DDR3
            bus over one continuous In1.Cu" holds by construction
    In2.Cu  R1 calls this "mixed"; it is the third routing layer here, which is
            what gives the 256-ball FTG256 somewhere to escape to
    B.Cu    signal + GND pour

`GND` is poured, not routed (see `plane.py`), so the router only sees the rails
and signals.

Grid is 0.1 mm: every pad pitch in the design (0.4, 0.5, 0.65, 0.8, 1.0 mm) is
an exact multiple, so pads sit on grid nodes instead of between them.

Occupancy is one int16 per cell per layer holding a net id, and a cell is
usable by net N when it is empty or already owned by N. Pads and finished
tracks are stamped with a halo of clearance + half a track width, which is what
keeps two different nets apart without a separate clearance test in the inner
loop.
"""
from __future__ import annotations

import heapq
from array import array

import numpy as np

GRID = 0.1
LAYERS = ["F.Cu", "In2.Cu", "B.Cu"]
LAYER_IX = {n: i for i, n in enumerate(LAYERS)}
EMPTY = 0
BLOCKED = -1

VIA_COST = 14          # cells; a via is worth ~1.4 mm of detour
CLEARANCE = 0.11


class Router:
    def __init__(self, b, bounds, edge=0.35):
        self.b = b
        x0, y0, x1, y1 = bounds
        self.x0, self.y0 = x0 + edge, y0 + edge
        self.nx = int((x1 - x0 - 2 * edge) / GRID) + 1
        self.ny = int((y1 - y0 - 2 * edge) / GRID) + 1
        self.n = self.nx * self.ny
        self.cell = [array("h", [EMPTY]) * self.n for _ in LAYERS]
        self.tracks = []       # (layer, x1,y1, x2,y2, width, net)
        self.vias = []         # (x, y, net)
        self.netid = {}
        self.netname = {}

    # -- coordinates -------------------------------------------------------- #
    def cx(self, x):
        return int(round((x - self.x0) / GRID))

    def cy(self, y):
        return int(round((y - self.y0) / GRID))

    def mm(self, ix, iy):
        return (round(self.x0 + ix * GRID, 4), round(self.y0 + iy * GRID, 4))

    def nid(self, net):
        if net not in self.netid:
            i = len(self.netid) + 1
            self.netid[net] = i
            self.netname[i] = net
        return self.netid[net]

    # -- stamping ----------------------------------------------------------- #
    def stamp_rect(self, li, x0, y0, x1, y1, val, only_empty=False):
        a, b = self.cx(x0), self.cy(y0)
        c, d = self.cx(x1), self.cy(y1)
        cell = self.cell[li]
        for iy in range(max(0, b), min(self.ny - 1, d) + 1):
            row = iy * self.nx
            for ix in range(max(0, a), min(self.nx - 1, c) + 1):
                k = row + ix
                if only_empty and cell[k] != EMPTY:
                    continue
                cell[k] = val

    def stamp_pad_body(self, li, x, y, w, h, val):
        self.stamp_rect(li, x - w, y - h, x + w, y + h, val)

    def stamp_halo(self, li, x, y, w, h, nid):
        """Grow a pad's keep-out, without letting it eat a neighbour's pad.

        Two passes are needed because pad halos overlap: `U14` is a SOT-563
        whose pads are 0.35 mm tall on a 0.5 mm pitch, so a 0.19 mm halo
        reaches well into the next pad. A single pass let whichever pad was
        stamped last own the overlap, and a track then routed straight across
        its neighbour -- fifteen shorts, `GND` to `Net-(U14-SW)` among them.

        So: bodies first, then halos, and a halo cell that already belongs to a
        *different* net becomes BLOCKED rather than changing hands.
        """
        a, b = self.cx(x - w), self.cy(y - h)
        c, d = self.cx(x + w), self.cy(y + h)
        cell = self.cell[li]
        for iy in range(max(0, b), min(self.ny - 1, d) + 1):
            row = iy * self.nx
            for ix in range(max(0, a), min(self.nx - 1, c) + 1):
                k = row + ix
                v = cell[k]
                if v == EMPTY:
                    cell[k] = nid
                elif v != nid:
                    cell[k] = BLOCKED

    def stamp_pads(self, halo=None):
        halo = CLEARANCE + 0.09 if halo is None else halo
        jobs = []
        for fp in self.b.footprints.values():
            for p in fp.pads:
                x, y = fp.pad_xy(p)
                pw, ph = fp.pad_size(p)
                w, h = pw / 2, ph / 2
                val = BLOCKED if (not p.net or p.kind == "np_thru_hole") \
                    else self.nid(p.net)
                layers = (list(range(len(LAYERS))) if p.kind != "smd"
                          else [LAYER_IX.get(fp.layer, 0)])
                jobs.append((layers, x, y, w, h, val))
        for layers, x, y, w, h, val in jobs:          # pass 1: bodies
            for li in layers:
                self.stamp_pad_body(li, x, y, w, h, val)
        for layers, x, y, w, h, val in jobs:          # pass 2: halos
            for li in layers:
                self.stamp_halo(li, x, y, w + halo, h + halo, val)

    def stamp_keepouts(self, rects, layers=None):
        for (x0, y0, x1, y1) in rects:
            for li in (layers or range(len(LAYERS))):
                self.stamp_rect(li, x0, y0, x1, y1, BLOCKED)

    def stamp_existing_vias(self, vias, halo=0.41):
        for (x, y, net) in vias:
            val = self.nid(net) if net else BLOCKED
            for li in range(len(LAYERS)):
                self.stamp_rect(li, x - halo, y - halo, x + halo, y + halo, val)

    # -- A* ----------------------------------------------------------------- #
    def _astar(self, nid, sources, targets, width):
        """Cheapest path from any source cell to any target cell.

        `sources`/`targets` are sets of flat (layer, index) keys. Returns the
        path as a list of (li, ix, iy), or None.
        """
        nx, ny, n = self.nx, self.ny, self.n
        cell = self.cell

        tgt = set(targets)
        # heuristic: Manhattan to the nearest target, ignoring layers
        tpts = [(k % n % nx, (k % n) // nx) for k in tgt]

        def h(li, ix, iy):
            return min(abs(ix - tx) + abs(iy - ty) for tx, ty in tpts)

        openq = []
        g = {}
        came = {}
        for k in sources:
            li, idx = k // n, k % n
            ix, iy = idx % nx, idx // nx
            g[k] = 0
            heapq.heappush(openq, (h(li, ix, iy), 0, k))
        seen = set()
        while openq:
            f, gc, k = heapq.heappop(openq)
            if k in seen:
                continue
            seen.add(k)
            if k in tgt:
                path = []
                while k is not None:
                    li, idx = k // n, k % n
                    path.append((li, idx % nx, idx // nx))
                    k = came.get(k)
                return path[::-1]
            li, idx = k // n, k % n
            ix, iy = idx % nx, idx // nx
            # in-plane neighbours
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                jx, jy = ix + dx, iy + dy
                if not (0 <= jx < nx and 0 <= jy < ny):
                    continue
                if not self._clear(li, jx, jy, nid):
                    continue
                nk = li * n + jy * nx + jx
                ng = gc + 1
                if ng < g.get(nk, 1 << 30):
                    g[nk] = ng
                    came[nk] = k
                    heapq.heappush(openq, (ng + h(li, jx, jy), ng, nk))
            # Layer changes. A via is 0.45 mm across plus clearance, so a
            # single-cell test is not enough -- checking only the centre put
            # vias 0.016 mm from other nets' copper. This is the one place a
            # box test is worth its cost, because layer changes are rare.
            if self._via_clear(li, ix, iy, nid):
                for lj in range(len(LAYERS)):
                    if lj == li:
                        continue
                    nk = lj * n + idx
                    ng = gc + VIA_COST
                    if ng < g.get(nk, 1 << 30):
                        g[nk] = ng
                        came[nk] = k
                        heapq.heappush(openq, (ng + h(lj, ix, iy), ng, nk))
        return None

    def build_via_tables(self, nid):
        """Summed-area tables so via legality is O(1) instead of a 243-cell scan.

        A via is 0.45 mm across plus clearance -- nine cells a side -- and A*
        asks about a layer change at every node it expands. Scanning that box
        three layers deep per node made the router unusable (it did not finish
        60 nets in 110 s). Two integral images, one of all occupancy and one of
        this net's own, answer the same question with four lookups: the via is
        legal where every occupied cell in the box already belongs to us.

        Rebuilt per net; in numpy that is a few milliseconds.
        """
        ny, nx = self.ny, self.nx
        occ = np.zeros((ny, nx), np.int32)
        own = np.zeros((ny, nx), np.int32)
        for li in range(len(LAYERS)):
            a = np.frombuffer(self.cell[li], dtype=np.int16).reshape(ny, nx)
            occ += (a != EMPTY)
            own += (a == nid)
        self._sat_occ = occ.cumsum(0).cumsum(1)
        self._sat_own = own.cumsum(0).cumsum(1)

    @staticmethod
    def _boxsum(sat, x0, y0, x1, y1):
        s = sat[y1, x1]
        if y0 > 0:
            s -= sat[y0 - 1, x1]
        if x0 > 0:
            s -= sat[y1, x0 - 1]
        if x0 > 0 and y0 > 0:
            s += sat[y0 - 1, x0 - 1]
        return s

    def _via_rows(self):
        """Half-widths of a via's disc, row by row, in cells.

        A *square* test cannot escape a BGA. Under the FTG256 (1.0 mm pitch)
        the free space between four balls is a diamond about 0.5 mm across;
        a 0.4 mm half-width box reaches 0.566 mm into its corners and always
        hits a pad, so no inner ball could ever fan out and the whole DDR3
        group failed. The via is round -- test it round.
        """
        if getattr(self, "_vrows", None) is None:
            r = (0.45 / 2 + CLEARANCE) / GRID
            ri = int(r)
            self._vrows = [(dy, int((r * r - dy * dy) ** 0.5))
                           for dy in range(-ri, ri + 1)
                           if r * r - dy * dy >= 0]
        return self._vrows

    def _via_clear(self, li, ix, iy, nid):
        occ = own = 0
        for dy, half in self._via_rows():
            jy = iy + dy
            if not (0 <= jy < self.ny):
                return False
            x0, x1 = ix - half, ix + half
            if x0 < 0 or x1 >= self.nx:
                return False
            occ += self._boxsum(self._sat_occ, x0, jy, x1, jy)
            own += self._boxsum(self._sat_own, x0, jy, x1, jy)
        return occ == own

    def _clear(self, li, ix, iy, nid, halo=0):
        """Usable when the cell is empty or already ours.

        Deliberately a *single* cell read. Clearance is not tested here -- it
        is baked in when obstacles are stamped, inflated by
        `CLEARANCE + width/2`. Testing a halo box inside the inner loop instead
        costs ~200 reads per expansion and makes the router unusable.
        """
        v = self.cell[li][iy * self.nx + ix]
        return v == EMPTY or v == nid

    # -- net routing -------------------------------------------------------- #
    def _pad_cells(self, fp, p, nid, shrink=0.0):
        """Grid cells that count as landing *inside* this pad.

        Shrunk by half a track width so the endpoint sits in pad copper rather
        than at the nearest node, which on a 0.305 mm connector pad can be
        just outside it -- 52 dangling-track warnings. Snapping the endpoint to
        the pad centre instead fixes the dangling but drags the last segment
        sideways across the pad's neighbours, which cost 7 clearance and
        shorting errors. Shrinking keeps the track on grid and legal.
        """
        x, y = fp.pad_xy(p)
        pw, ph = fp.pad_size(p)
        w, h = max(pw / 2 - shrink, 0.0), max(ph / 2 - shrink, 0.0)
        out = []
        layers = (range(len(LAYERS)) if p.kind != "smd"
                  else [LAYER_IX.get(fp.layer, 0)])
        for li in layers:
            for iy in range(self.cy(y - h), self.cy(y + h) + 1):
                for ix in range(self.cx(x - w), self.cx(x + w) + 1):
                    if 0 <= ix < self.nx and 0 <= iy < self.ny:
                        out.append(li * self.n + iy * self.nx + ix)
            if not out:                      # pad smaller than the track
                ix, iy = self.cx(x), self.cy(y)
                if 0 <= ix < self.nx and 0 <= iy < self.ny:
                    out.append(li * self.n + iy * self.nx + ix)
        return out

    def lay(self, path, net, width, snap=None):
        """Turn a cell path into tracks and vias, and stamp it as occupied.

        `snap` maps a path cell to the exact pad centre it belongs to. Ending a
        track on the grid node nearest a pad is not the same as ending it *in*
        the pad: on a 0.305 mm connector pad the nearest node can sit just
        outside the copper, which KiCad reports as a dangling track. Snapping
        both ends to the pad centre is also what a person would draw.
        """
        nid = self.nid(net)
        halo = int((CLEARANCE + width / 2) / GRID) + 1
        runs = []
        cur = [path[0]]
        for prev, node in zip(path, path[1:]):
            if node[0] != prev[0]:
                runs.append(cur)
                x, y = self.mm(prev[1], prev[2])
                self.vias.append((x, y, net))
                cur = [node]
            else:
                cur.append(node)
        runs.append(cur)
        for run in runs:
            if len(run) < 2:
                continue
            li = run[0][0]
            # collapse collinear cells into straight segments
            seg = [run[0]]
            for k in range(1, len(run)):
                if k == len(run) - 1:
                    seg.append(run[k])
                    continue
                a, b, c = run[k - 1], run[k], run[k + 1]
                if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
                    seg.append(run[k])
            pts = [self.mm(s[1], s[2]) for s in seg]
            if snap:
                k0 = seg[0][0] * self.n + seg[0][2] * self.nx + seg[0][1]
                k1 = seg[-1][0] * self.n + seg[-1][2] * self.nx + seg[-1][1]
                if k0 in snap:
                    pts[0] = snap[k0]
                if k1 in snap:
                    pts[-1] = snap[k1]
            for a, b in zip(pts, pts[1:]):
                if a != b:
                    self.tracks.append((LAYERS[li], a, b, width, net))
        # stamp the whole path, inflated, so later nets keep away
        for (li, ix, iy) in path:
            for jy in range(max(0, iy - halo), min(self.ny - 1, iy + halo) + 1):
                row = jy * self.nx
                for jx in range(max(0, ix - halo), min(self.nx - 1, ix + halo) + 1):
                    if self.cell[li][row + jx] == EMPTY:
                        self.cell[li][row + jx] = nid
        for (x, y, _n) in self.vias[-len(runs) + 1:] if len(runs) > 1 else []:
            for li in range(len(LAYERS)):
                self.stamp_rect(li, x - 0.41, y - 0.41, x + 0.41, y + 0.41,
                                nid, only_empty=True)

    def route_net(self, net, terms, width, snap=None, passes=3):
        """Grow a tree: connect terminals in sweeps, deferring the ones that fail.

        The obvious loop -- rescan every remaining terminal from the start after
        each success -- is quadratic in the number of *unroutable* terminals,
        and each of those costs a full-budget search. On `+3V3` (63 pads) that
        is on the order of 20 x 43 = 860 hopeless 30 000-expansion searches for
        one net, and it is why a full run sat on a single net for 25 minutes.

        Instead: one sweep over the outstanding terminals, laying whatever
        connects and setting the rest aside. A deferred terminal is only
        retried on the next sweep, because the only thing that can change its
        answer is the tree having grown -- and then only while a sweep is still
        making progress.
        """
        nid = self.nid(net)
        self.build_via_tables(nid)
        connected = set(terms[0])
        rest = list(terms[1:])
        done = 0
        for _ in range(passes):
            if not rest:
                break
            deferred = []
            progressed = False
            for t in rest:
                path = self._astar(nid, connected, set(t), width)
                if path is None:
                    deferred.append(t)
                    continue
                self.lay(path, net, width, snap)
                self.build_via_tables(nid)
                connected |= set(t)
                connected |= {li * self.n + iy * self.nx + ix
                              for (li, ix, iy) in path}
                done += 1
                progressed = True
            rest = deferred
            if not progressed:
                break
        return done, len(rest)
