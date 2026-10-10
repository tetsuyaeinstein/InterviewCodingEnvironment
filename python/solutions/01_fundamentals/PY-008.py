"""PY-008 reference solution: hash join (build on right, probe with left).

Build: one pass over the right side into {key: [rows in right order]}; None/missing keys are
never inserted. Probe: stream the left side in order and look each key up in O(1).
Time O(|L| + |R| + |output|); memory O(|R|) for the hash table.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

_JOIN_TYPES = ("inner", "left")


def _merge(left_row: Mapping[str, Any], right_row: Mapping[str, Any], on: str, suffix: str) -> dict[str, Any]:
    merged = dict(left_row)
    for name, value in right_row.items():
        if name == on:
            continue                                   # the key appears once, from the left
        target = name + suffix if name in left_row else name
        if target in merged:
            raise ValueError(f"column name clash on {target!r} while joining on {on!r}")
        merged[target] = value
    return merged


def join_records(left: Iterable[Mapping[str, Any]], right: Iterable[Mapping[str, Any]], on: str, *,
                 how: str = "inner", right_suffix: str = "_right") -> list[dict[str, Any]]:
    if how not in _JOIN_TYPES:
        raise ValueError(f"how must be one of {_JOIN_TYPES}, got {how!r}")
    if not isinstance(right_suffix, str) or not right_suffix:
        raise ValueError("right_suffix must be a non-empty string")

    index: defaultdict[Any, list[Mapping[str, Any]]] = defaultdict(list)
    for row in right:
        key = row.get(on)
        if key is not None:                            # NULL keys can never match: don't index them
            index[key].append(row)

    out: list[dict[str, Any]] = []
    for row in left:
        key = row.get(on)
        matches = index.get(key, ()) if key is not None else ()   # .get: don't grow the defaultdict
        if matches:
            out.extend(_merge(row, match, on, right_suffix) for match in matches)
        elif how == "left":
            out.append(dict(row))
    return out
