#!/usr/bin/env python3
"""A minimal, lossless s-expression reader/writer for KiCad files.

KiCad's format is a plain s-expression tree of atoms and lists. The only
subtlety is string quoting: KiCad quotes any atom that is not a bare symbol
or number, and escapes `"` and `\\` inside. Round-tripping matters -- a board
we rewrite must still open -- so `dumps(loads(x))` is checked against KiCad's
own output in `tests/test_roundtrip.py`.

Nodes are plain Python lists; atoms are `str`, `Sym` (unquoted), `int`/`float`.
`Sym` exists so we can tell `(at 0 0)` (symbol `at`) from a quoted `"at"`.
"""
from __future__ import annotations


class Sym(str):
    """A bare, unquoted s-expression symbol."""
    __slots__ = ()


def loads(text: str):
    """Parse one s-expression document. Returns the root list."""
    n = len(text)
    i = 0
    stack = []
    root = None
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "(":
            node = []
            if stack:
                stack[-1].append(node)
            else:
                root = node
            stack.append(node)
            i += 1
            continue
        if c == ")":
            stack.pop()
            i += 1
            continue
        if c == '"':
            i += 1
            out = []
            while text[i] != '"':
                if text[i] == "\\":
                    nxt = text[i + 1]
                    out.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
                    i += 2
                else:
                    out.append(text[i])
                    i += 1
            i += 1
            stack[-1].append("".join(out))
            continue
        j = i
        while j < n and text[j] not in ' \t\r\n()"':
            j += 1
        stack[-1].append(_atom(text[i:j]))
        i = j
    return root


def _atom(s: str):
    try:
        return int(s)
    except ValueError:
        pass
    try:
        f = float(s)
        # keep "1.0" from collapsing to "1"; KiCad is tolerant but diffs are not
        return f
    except ValueError:
        return Sym(s)


_ESC = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\r"}


def _fmt(a) -> str:
    if isinstance(a, Sym):
        return str(a)
    if isinstance(a, bool):
        return "yes" if a else "no"
    if isinstance(a, float):
        s = repr(round(a, 6))
        if s.endswith(".0"):
            s = s[:-2]
        return s
    if isinstance(a, int):
        return str(a)
    return '"' + "".join(_ESC.get(ch, ch) for ch in a) + '"'


def dumps(node, indent: int = 0) -> str:
    """Serialise back to KiCad's tab-indented style."""
    pad = "\t" * indent
    if not isinstance(node, list):
        return pad + _fmt(node)
    # a list whose members are all atoms goes on one line
    if all(not isinstance(x, list) for x in node):
        return pad + "(" + " ".join(_fmt(x) for x in node) + ")"
    head = node[0]
    parts = [pad + "(" + _fmt(head)]
    rest = node[1:]
    # leading atoms stay on the head line, as KiCad writes them
    k = 0
    while k < len(rest) and not isinstance(rest[k], list):
        parts[0] += " " + _fmt(rest[k])
        k += 1
    for child in rest[k:]:
        parts.append(dumps(child, indent + 1))
    parts.append(pad + ")")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# tree helpers
# --------------------------------------------------------------------------- #

def head(node) -> str:
    return str(node[0]) if isinstance(node, list) and node else ""


def find_all(node, name: str):
    """Direct children of `node` whose head is `name`."""
    return [c for c in node if isinstance(c, list) and head(c) == name]


def find(node, name: str):
    for c in node:
        if isinstance(c, list) and head(c) == name:
            return c
    return None


def get(node, name: str, default=None):
    """The single value of `(name value)`."""
    c = find(node, name)
    return c[1] if c is not None and len(c) > 1 else default
