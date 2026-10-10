"""PY-013 - Merge kiosk outage windows.

Question: python/questions/02_algorithms/PY-013.md   (python -m lab show PY-013)
Check   : python -m lab check PY-013
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, TypeVar

T = TypeVar("T", bound=Any)   # int, datetime, ... (any totally ordered type)


def merge_intervals(intervals: Iterable[tuple[T, T]]) -> list[tuple[T, T]]:
    """Return the union of half-open [start, end) windows as sorted, non-touching tuples.

    Touching windows merge; zero-length windows are dropped; start > end -> ValueError.
    The input is not mutated.
    """
    raise NotImplementedError
