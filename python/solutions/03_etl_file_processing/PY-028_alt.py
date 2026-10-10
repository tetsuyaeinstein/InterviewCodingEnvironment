"""PY-028 alternative: sort-merge join of two key-ordered streams.

The merge itself (`_merge`) needs O(1) memory: it holds one row from each side and advances the
smaller key, exactly like a SQL merge join or `comm` on sorted files. Here the inputs arrive in
arbitrary order, so they are first sorted in memory (O(n) memory, O(n log n) time); at scale that
sort is an external merge sort (PY-029) or the inputs are already produced in key order
(ORDER BY on both databases), and only the merge runs - with bounded memory on both sides.

Canonicalisation is an equally valid but different encoding from the reference: a length-prefixed
byte string ("<len>:<bytes>" per token) instead of JSON. Both are injective; the test suite only
checks properties (equal iff canonically equal), never a specific digest.
"""
from __future__ import annotations

import hashlib
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class DiffResult:
    missing: list[tuple] = field(default_factory=list)
    extra: list[tuple] = field(default_factory=list)
    changed: list[tuple[tuple, tuple[str, ...]]] = field(default_factory=list)
    unchanged: int = 0



def _plain_number(d: Decimal) -> str:
    """Exact canonical text for a finite non-zero number: trailing zeros stripped via the digit
    tuple (Decimal.normalize() would round to the 28-digit context precision)."""
    sign, digits, exp = d.as_tuple()
    digits = list(digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exp += 1
    return format(Decimal((sign, tuple(digits), exp)), "f")


def _canon(value: object) -> bytes:
    if isinstance(value, bool):
        return b"B1" if value else b"B0"
    if isinstance(value, (int, Decimal)):
        d = Decimal(value)
        if not d.is_finite():
            raise ValueError(f"non-finite number {value!r}")
        return b"N" + (b"0" if d == 0 else _plain_number(d).encode())
    if isinstance(value, str):
        return b"S" + value.encode("utf-8")
    raise TypeError(f"unsupported type {type(value).__name__}")


def _tokens(row: Mapping[str, object], exclude: Collection[str]) -> dict[str, bytes]:
    return {k: _canon(v) for k, v in row.items() if v is not None and k not in exclude}


def _hash(tokens: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for name in sorted(tokens):
        for part in (name.encode("utf-8"), tokens[name]):
            h.update(b"%d:" % len(part))          # length prefix: no delimiter can be forged
            h.update(part)
    return h.hexdigest()


def canonical_row_hash(row: Mapping[str, object], *, exclude: Collection[str] = ()) -> str:
    return _hash(_tokens(row, set(exclude)))


def _keyed_sorted(rows: Iterable[Mapping[str, object]], key_fields: Sequence[str],
                  excl: set[str], side: str) -> Iterator[tuple[tuple, dict[str, bytes]]]:
    decorated = []
    for row in rows:
        k = tuple(row.get(f) for f in key_fields)
        if any(v is None for v in k):
            raise ValueError(f"missing/NULL key in {side}: {row!r}")
        decorated.append((k, _tokens(row, excl)))
    decorated.sort(key=lambda t: t[0])             # stand-in for an external sort
    prev = None
    for k, toks in decorated:
        if k == prev:
            raise ValueError(f"duplicate key {k!r} in {side}")
        prev = k
        yield k, toks


def _merge(src: Iterator, tgt: Iterator, result: DiffResult) -> None:
    sentinel = object()
    s, t = next(src, sentinel), next(tgt, sentinel)
    while s is not sentinel or t is not sentinel:
        if t is sentinel or (s is not sentinel and s[0] < t[0]):
            result.missing.append(s[0])
            s = next(src, sentinel)
        elif s is sentinel or t[0] < s[0]:
            result.extra.append(t[0])
            t = next(tgt, sentinel)
        else:
            if _hash(s[1]) == _hash(t[1]):
                result.unchanged += 1
            else:
                a, b = s[1], t[1]
                result.changed.append((s[0], tuple(sorted(f for f in a.keys() | b.keys() if a.get(f) != b.get(f)))))
            s, t = next(src, sentinel), next(tgt, sentinel)


def diff_streams(source: Iterable[Mapping[str, object]], target: Iterable[Mapping[str, object]],
                 key_fields: Sequence[str], *, exclude: Collection[str] = ()) -> DiffResult:
    excl = set(exclude)
    result = DiffResult()
    _merge(_keyed_sorted(source, key_fields, excl, "source"),
           _keyed_sorted(target, key_fields, excl, "target"), result)
    return result
