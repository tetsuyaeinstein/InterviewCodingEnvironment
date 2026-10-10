"""PY-013 alternative: boundary events with a coverage counter (+1 at start, -1 at end) -> O(n log n).

Each window contributes two events. Sorted by time, the running depth says how many windows
cover the instants just after that time. A merged window opens when the depth goes 0 -> 1 and
closes when it goes back to 0.

Tie rule at equal times: process starts BEFORE ends. Then [1, 5) and [5, 9) never drop to depth
zero at t = 5, so touching windows merge, which is exactly the half-open contract. (Processing
ends first would implement "touching windows stay separate".) Zero-length windows are filtered
out first, otherwise a lone one would emit an empty (t, t) output window.

Same complexity as sort + sweep, with 2n events instead of n windows. It generalises to "times
covered by at least K windows" (concurrency, overlapping sessions) by changing the thresholds.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, TypeVar

T = TypeVar("T", bound=Any)

START, END = 0, 1          # sort order at equal timestamps: starts first


def merge_intervals(intervals: Iterable[tuple[T, T]]) -> list[tuple[T, T]]:
    events: list[tuple[T, int]] = []
    for start, end in intervals:
        if start > end:
            raise ValueError(f"invalid window: start {start!r} is after end {end!r}")
        if start < end:
            events.append((start, START))
            events.append((end, END))
    events.sort()

    merged: list[tuple[T, T]] = []
    depth = 0
    opened_at = None
    for time, kind in events:
        if kind == START:
            if depth == 0:
                opened_at = time
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                merged.append((opened_at, time))
    return merged
