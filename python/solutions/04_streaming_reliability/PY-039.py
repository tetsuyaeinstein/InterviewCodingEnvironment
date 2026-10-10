"""PY-039 reference solution: canonical string per payload + one dict pass.

canon(payload) is a hashable, tagged, order-normalised nested tuple, so equality of canonical
values == the equality policy of the question. Per message id we keep
{canon: [first_payload, count]}; one pass, O(total payload size), no pairwise comparison.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Delivered:
    message_id: str
    payload: dict
    deliveries: int


@dataclass(frozen=True)
class Conflict:
    message_id: str
    payloads: tuple[dict, ...]
    deliveries: int


@dataclass(frozen=True)
class Classification:
    unique: list[Delivered]
    exact_duplicates: list[Delivered]
    conflicts: list[Conflict]


def _number(value: object) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        d = Decimal(repr(value))                 # shortest round-trip text: 0.1 -> Decimal("0.1")
    else:
        d = Decimal(value)
        if d.is_nan():
            return "nan"
        if d.is_infinite():
            return "inf" if d > 0 else "-inf"
    if d == 0:
        return "0"
    sign, digits, exp = d.as_tuple()             # strip trailing zeros without context rounding
    digits = list(digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exp += 1
    return format(Decimal((sign, tuple(digits), exp)), "f")


def _canon(value: object):
    """A hashable, order-normalised, type-tagged form of ``value`` (nested tuples)."""
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("num", str(value))                   # fast path: ints are already canonical text
    if isinstance(value, (float, Decimal)):
        return ("num", _number(value))
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, Mapping):
        if not all(isinstance(k, str) for k in value):
            raise TypeError("payload keys must be strings")
        return ("map", tuple((k, _canon(v)) for k, v in sorted(value.items())))
    if isinstance(value, (list, tuple)):
        return ("list", tuple(_canon(v) for v in value))
    raise TypeError(f"unsupported payload value of type {type(value).__name__}")


def classify_messages(messages: Iterable[tuple[str, Mapping[str, object]]]) -> Classification:
    seen: dict[str, dict[tuple, list]] = {}
    for message_id, payload in messages:
        if not isinstance(message_id, str) or not message_id:
            raise ValueError(f"message_id must be a non-empty string: {message_id!r}")
        if not isinstance(payload, Mapping):
            raise TypeError(f"payload of {message_id!r} must be a mapping")
        variants = seen.setdefault(message_id, {})
        text = _canon(payload)
        entry = variants.get(text)
        if entry is None:
            variants[text] = [payload, 1]
        else:
            entry[1] += 1

    unique, dups, conflicts = [], [], []
    for message_id in sorted(seen):
        variants = seen[message_id]
        total = sum(count for _, count in variants.values())
        if len(variants) > 1:
            ordered = [payload for payload, _ in variants.values()]      # first-arrival order
            conflicts.append(Conflict(message_id, tuple(dict(p) for p in ordered), total))
        else:
            (payload, count), = variants.values()
            (unique if count == 1 else dups).append(Delivered(message_id, dict(payload), count))
    return Classification(unique, dups, conflicts)
