"""PY-028 reference solution: hash-map one side, stream the other.

Canonical form = sorted list of [field, type_tag, text] for every non-excluded, non-NULL field,
serialised with json.dumps. JSON string escaping makes the encoding injective (no value can
"contain" a delimiter), the type tag separates True / 1 / "1", and numbers are rendered from the
normalised Decimal so 1 == 1.0 == 1.00. NULL and an absent field both mean "no entry".

Memory: O(|target|) for the map (key -> (hash, row)) plus O(|source| keys) to detect
duplicate source keys; the source rows themselves are streamed.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Iterable, Mapping, Sequence
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


def _canonical_value(value: object) -> tuple[str, str]:
    if isinstance(value, bool):                       # before int: True is not 1
        return ("b", "true" if value else "false")
    if isinstance(value, (int, Decimal)):
        d = Decimal(value)
        if not d.is_finite():
            raise ValueError(f"non-finite number {value!r} cannot be canonicalised")
        if d == 0:
            return ("n", "0")                         # -0, 0.00, 0E+3 -> 0
        return ("n", _plain_number(d))                # 1.50 -> 1.5, 1E+2 -> 100
    if isinstance(value, str):
        return ("s", value)
    raise TypeError(f"unsupported type {type(value).__name__} for canonical hashing")


def _canonical_items(row: Mapping[str, object], exclude: Collection[str]) -> dict[str, tuple[str, str]]:
    return {k: _canonical_value(v) for k, v in row.items() if k not in exclude and v is not None}


def _digest(items: dict[str, tuple[str, str]]) -> str:
    payload = json.dumps(sorted([k, t, s] for k, (t, s) in items.items()),
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_row_hash(row: Mapping[str, object], *, exclude: Collection[str] = ()) -> str:
    return _digest(_canonical_items(row, set(exclude)))


def _key(row: Mapping[str, object], key_fields: Sequence[str]) -> tuple:
    key = tuple(row.get(f) for f in key_fields)
    if any(v is None for v in key):
        raise ValueError(f"missing/NULL key in {row!r}")
    return key


def _diff_fields(a: dict, b: dict) -> tuple[str, ...]:
    return tuple(sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k)))


def diff_streams(source: Iterable[Mapping[str, object]], target: Iterable[Mapping[str, object]],
                 key_fields: Sequence[str], *, exclude: Collection[str] = ()) -> DiffResult:
    excl = set(exclude)
    target_map: dict[tuple, tuple[str, dict]] = {}
    for row in target:
        k = _key(row, key_fields)
        if k in target_map:
            raise ValueError(f"duplicate key {k!r} in target")
        items = _canonical_items(row, excl)
        target_map[k] = (_digest(items), items)

    result = DiffResult()
    seen: set[tuple] = set()
    for row in source:
        k = _key(row, key_fields)
        if k in seen:
            raise ValueError(f"duplicate key {k!r} in source")
        seen.add(k)
        items = _canonical_items(row, excl)
        other = target_map.pop(k, None)
        if other is None:
            result.missing.append(k)
        elif other[0] == _digest(items):
            result.unchanged += 1
        else:
            result.changed.append((k, _diff_fields(items, other[1])))
    result.extra = sorted(target_map)
    result.missing.sort()
    result.changed.sort()
    return result
