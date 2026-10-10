"""PY-008 alternative: sort-merge join.

Both sides are sorted by key (stable, so equal keys keep input order), then walked in lockstep;
for each equal-key run the cross product is emitted. Because the contract wants *left input
order*, results are tagged with the left row's position and re-ordered at the end.

Trade-offs vs. the hash join:
  * O(L log L + R log R) instead of O(L + R) -- but if both inputs arrive already sorted by key
    (sorted files, ORDER BY cursors) the sorts disappear and the merge itself is streaming with
    O(size of one key group) memory, which is how databases join inputs bigger than RAM.
  * Keys must be orderable. Mixed types are handled by sorting on (type name, key), which also
    keeps 1 and "1" apart; numerically-equal keys of different types (1 vs 1.0) would NOT match
    here although they match in the hash join -- a documented limitation.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

_JOIN_TYPES = ("inner", "left")


def _merge(left_row: Mapping[str, Any], right_row: Mapping[str, Any], on: str, suffix: str) -> dict[str, Any]:
    merged = dict(left_row)
    for name, value in right_row.items():
        if name == on:
            continue
        target = name + suffix if name in left_row else name
        if target in merged:
            raise ValueError(f"column name clash on {target!r} while joining on {on!r}")
        merged[target] = value
    return merged


def _sort_key(key: Any) -> tuple[str, Any]:
    return (type(key).__name__, key)


def join_records(left: Iterable[Mapping[str, Any]], right: Iterable[Mapping[str, Any]], on: str, *,
                 how: str = "inner", right_suffix: str = "_right") -> list[dict[str, Any]]:
    if how not in _JOIN_TYPES:
        raise ValueError(f"how must be one of {_JOIN_TYPES}, got {how!r}")
    if not isinstance(right_suffix, str) or not right_suffix:
        raise ValueError("right_suffix must be a non-empty string")

    left_rows = list(left)
    lefts = sorted(((_sort_key(r.get(on)), i) for i, r in enumerate(left_rows) if r.get(on) is not None),
                   key=lambda t: t[0])
    rights = sorted(((_sort_key(r.get(on)), r) for r in right if r.get(on) is not None),
                    key=lambda t: t[0])           # stable: equal keys stay in right input order

    matched: dict[int, list[dict[str, Any]]] = {}
    i = j = 0
    while i < len(lefts) and j < len(rights):
        lk, rk = lefts[i][0], rights[j][0]
        if lk < rk:
            i += 1
        elif rk < lk:
            j += 1
        else:
            j_end = j
            while j_end < len(rights) and rights[j_end][0] == lk:
                j_end += 1
            group = [r for _, r in rights[j:j_end]]
            while i < len(lefts) and lefts[i][0] == lk:    # every left row with this key
                pos = lefts[i][1]
                matched[pos] = [_merge(left_rows[pos], r, on, right_suffix) for r in group]
                i += 1
            j = j_end

    out: list[dict[str, Any]] = []
    for pos, row in enumerate(left_rows):                  # restore left input order
        if pos in matched:
            out.extend(matched[pos])
        elif how == "left":
            out.append(dict(row))
    return out
