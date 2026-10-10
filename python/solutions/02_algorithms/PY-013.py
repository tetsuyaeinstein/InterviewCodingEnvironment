"""PY-013 reference solution: sort by start, then one sweep extending the current window -> O(n log n).

Half-open windows [s, e) touch when the next start equals the current end, and touching means
"no uncovered instant in between", so the merge test is `start <= current_end`. The new end is
max(current_end, end) so a short window nested inside a long one never shrinks it.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, TypeVar

T = TypeVar("T", bound=Any)


def merge_intervals(intervals: Iterable[tuple[T, T]]) -> list[tuple[T, T]]:
    windows = []
    for start, end in intervals:
        if start > end:
            raise ValueError(f"invalid window: start {start!r} is after end {end!r}")
        if start < end:                     # zero-length windows cover nothing: drop them
            windows.append((start, end))
    windows.sort(key=lambda w: w[0])        # by start only; ends never need comparing here

    merged: list[tuple[T, T]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:            # overlaps or touches the current window
            cur_start, cur_end = merged[-1]
            if end > cur_end:
                merged[-1] = (cur_start, end)
        else:
            merged.append((start, end))
    return merged
