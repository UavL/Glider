#!/usr/bin/env python3
"""Renumber every reference designator to the owner's page-based scheme.

  classifier + sheet page number + two-digit part, counted from 00

battery is page 2 -> U200, J201; io_expansion is page 14 -> U1400, J1402.
Pages 2-9 give three digits, pages 10-14 give four.  CLAUDE.md carries the rule.

Three parts appear on more than one sheet -- J26/J27 (pages 5 and 6) and U41
(7, 8, 9).  A part has one designator, so they take their **lowest** page.

Three substitution hazards, handled differently per file type:

  .kicad_sch / .kicad_pcb  quoted "REF" only -- exact, no false positives
  tools/*.py               quoted "REF" only -- comments are reported, not touched
  docs, NOTES              backtick `REF` only

The last one matters: docs use bare "R200" and "R201" to mean *board revisions*
hundreds of times, and R1/R2 are also real resistors on battery.  Only the
backtick form is a component reference in this project's prose, so only that is
rewritten.  Anything missed is listed at the end rather than guessed at.

--check prints the mapping and the stragglers without writing.
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
CHECK = "--check" in sys.argv


def sheet_pages() -> dict[str, int]:
    t = (ROOT / "r2.kicad_sch").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"\t\(sheet\n", t):
        s = m.start()
        d, k = 0, s
        while k < len(t):
            if t[k] == "(":
                d += 1
            elif t[k] == ")":
                d -= 1
                if d == 0:
                    break
            k += 1
        b = t[s:k + 1]
        f = re.search(r'\(property "Sheetfile" "([^"]+)"', b)
        p = re.search(r'\(page "(\d+)"\)', b)
        if f and p:
            out[f.group(1)] = int(p.group(1))
    return out


def build_map():
    pages = sheet_pages()
    where = collections.defaultdict(set)
    for f, pg in pages.items():
        t = (ROOT / f).read_text(encoding="utf-8")
        for m in re.finditer(r"\n\t\(symbol\n", t):
            s = m.end()
            n = t.find("\n\t(symbol\n", s)
            b = t[s:(n if n != -1 else len(t))]
            r = re.search(r'\(property "Reference" "([^"]+)"', b)
            if r and not r.group(1).startswith("#"):
                where[r.group(1)].add(pg)
    # group by (page, classifier); a part already in the target form keeps its slot
    buckets = collections.defaultdict(list)
    for ref, pgs in where.items():
        m = re.match(r"^([A-Z]+)(\d+)$", ref)
        if not m:
            sys.exit(f"unparsable designator: {ref}")
        buckets[(min(pgs), m.group(1))].append((int(m.group(2)), ref))
    mapping = {}
    for (pg, cls), items in buckets.items():
        prefix = f"{cls}{pg}"
        taken, floating = set(), []
        for _, ref in sorted(items):
            m = re.match(r"^%s(\d{2})$" % re.escape(prefix), ref)
            if m:                      # already correct for this page: keep it
                mapping[ref] = ref
                taken.add(int(m.group(1)))
            else:
                floating.append(ref)
        nxt = 0
        for ref in floating:
            while nxt in taken:
                nxt += 1
            mapping[ref] = f"{prefix}{nxt:02d}"
            taken.add(nxt)
            nxt += 1
    return mapping, pages, {k: sorted(v) for k, v in where.items() if len(v) > 1}


def main():
    mapping, pages, multi = build_map()

    # collisions: no target may equal another target, or any untouched source
    targets = list(mapping.values())
    if len(set(targets)) != len(targets):
        dupes = [t for t, c in collections.Counter(targets).items() if c > 1]
        sys.exit(f"target collision: {dupes}")
    # A target may well equal some *other* part's current name -- legacy R207 sits
    # where page 2 wants R207.  That is safe because the substitution is a single
    # atomic pass, so R2->R207 and R207->R1203 happen at once and cannot chain.
    # The only fatal case is two parts wanting the same new name, checked above.

    changing = {k: v for k, v in mapping.items() if k != v}
    print(f"{len(mapping)} designators, {len(changing)} change")
    for pg in sorted(set(pages.values())):
        sheet = [f for f, p in pages.items() if p == pg][0].replace(".kicad_sch", "")
        rows = sorted((k, v) for k, v in changing.items() if v[len(re.match(r'[A-Z]+', v).group(0)):].startswith(str(pg)))
        if rows:
            print(f"  page {pg:>2} {sheet:<14} {len(rows):>3}: " +
                  ", ".join(f"{k}->{v}" for k, v in rows[:4]) + (" ..." if len(rows) > 4 else ""))
    if multi:
        print("\nmulti-sheet parts, assigned to their lowest page:")
        for k, v in sorted(multi.items()):
            print(f"   {k} on pages {v} -> {mapping[k]}")
    if CHECK:
        return

    sch = sorted(ROOT.glob("*.kicad_sch")) + [ROOT / "r2.kicad_pcb"]
    sch = [p for p in sch if not p.name.startswith("r2_claude")]
    py = sorted(ROOT.glob("tools/*.py"))
    md = sorted(ROOT.glob("docs/*.md")) + sorted(REPO.glob("NOTES-*.md")) + [REPO / "CLAUDE.md"]

    alts = "|".join(re.escape(k) for k in sorted(changing, key=len, reverse=True))

    # Ball names on the BGAs look exactly like designators -- C1, D2, R4, N11, T1
    # and 16 others.  A blanket "quoted string" substitution rewrites those and
    # silently rewires the board.  So match only the two places a schematic or a
    # board actually stores an instance's designator.
    BALLS = set()
    for f in ROOT.glob("*.kicad_sch"):
        BALLS |= set(re.findall(r'\(pin "([A-Z]{1,2}\d{1,2})"', f.read_text(encoding="utf-8")))

    def apply_pat(paths, patterns):
        """One regex pass per file, so R2->R200 can never then match R200->R1203."""
        total = 0
        for p in paths:
            if not p.exists():
                continue
            t = p.read_text(encoding="utf-8")
            n = 0
            for lo, hi in patterns:
                pat = re.compile(f"{lo}({alts}){hi}")
                t, c = pat.subn(lambda m: f"{m.group(0)[:m.start(1)-m.start(0)]}"
                                          f"{changing[m.group(1)]}"
                                          f"{m.group(0)[m.end(1)-m.start(0):]}", t)
                n += c
            if n:
                p.write_text(t, encoding="utf-8")
                total += n
                print(f"   {n:5}  {p.relative_to(REPO)}")
        return total

    SCH = [(r'\(property "Reference" "', r'"'), (r'\(reference "', r'"\)')]
    PCB = [(r'\(property "Reference" "', r'"')]
    MD  = [(r'`', r'`')]

    print("\nschematics (Reference + instance reference only):")
    a = apply_pat([p for p in sch if p.suffix == ".kicad_sch"], SCH)
    print("board (Reference only):")
    a += apply_pat([p for p in sch if p.suffix == ".kicad_pcb"], PCB)
    print("docs (backticked):")
    c = apply_pat(md, MD)
    print("tools -- quoted, skipping anything that is also a BGA ball name:")
    safe = {k: v for k, v in changing.items() if k not in BALLS}
    held = sorted(set(changing) & BALLS)
    saved = dict(changing)
    changing.clear(); changing.update(safe)
    alts_all = alts
    alts = "|".join(re.escape(k) for k in sorted(safe, key=len, reverse=True))
    b = apply_pat(py, [(r'"', r'"')])
    changing.clear(); changing.update(saved)
    alts = alts_all
    if held:
        print(f"   held back from tools/ (ball-name collision): {held}")
    print(f"\n{a + b + c} replacements total")

    # anything left that looks like an old designator, so nothing is silently missed
    print("\nstragglers -- old names still present, for a human to judge:")
    hits = collections.Counter()
    for p in py + md:
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        for old in changing:
            for m in re.finditer(r"(?<![A-Za-z0-9_`])%s(?![0-9A-Za-z_`])" % old, t):
                hits[(p.name, old)] += 1
    if hits:
        for (f, r), c in sorted(hits.items()):
            print(f"   {c:3}x {r:6} in {f}")
    else:
        print("   none")


if __name__ == "__main__":
    main()
