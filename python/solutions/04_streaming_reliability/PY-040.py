"""PY-040 reference solution: a sorted list of disjoint, non-adjacent runs per customer.

Runs are stored as two parallel lists of day ordinals (starts / ends), sorted by start. A new
day touches at most two runs: the one that starts at or before it (the "left" run) and the one
that starts right after it (the "right" run), both found with a binary search. That gives the
four cases - duplicate (inside a run), new (isolated), extend (adjacent to one run) and bridge
(adjacent to both: two runs merge into one).

add_purchase is O(log r) to find the place plus a list insert/delete (a memmove, O(r) but with
a tiny constant); longest_streak is O(1) because runs only ever grow; nothing ever re-scans the
history. Ordinals (not date + timedelta) mean date.min / date.max need no special casing.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from typing import Hashable

Run = tuple[date, date]


@dataclass(frozen=True)
class StreakChange:
    kind: str
    before: tuple[Run, ...]
    after: Run


class _History:
    __slots__ = ("starts", "ends", "longest")

    def __init__(self) -> None:
        self.starts: list[int] = []
        self.ends: list[int] = []
        self.longest = 0


def _run(start: int, end: int) -> Run:
    return (date.fromordinal(start), date.fromordinal(end))


def _check_day(day: object, what: str) -> int:
    if isinstance(day, date) and not hasattr(day, "hour"):       # a datetime is a date subclass: reject it
        return day.toordinal()
    raise TypeError(f"{what} must be a datetime.date, got {type(day).__name__}")


class StreakTracker:
    def __init__(self) -> None:
        self._by_customer: dict[Hashable, _History] = {}

    def add_purchase(self, customer_id: Hashable, day: date) -> StreakChange:
        o = _check_day(day, "day")
        h = self._by_customer.get(customer_id)
        if h is None:
            h = self._by_customer[customer_id] = _History()
        starts, ends = h.starts, h.ends
        i = bisect_right(starts, o) - 1                  # last run starting on or before o
        if i >= 0 and ends[i] >= o:
            return StreakChange("duplicate", (_run(starts[i], ends[i]),), _run(starts[i], ends[i]))
        left = i >= 0 and ends[i] == o - 1
        j = i + 1                                        # first run starting after o
        right = j < len(starts) and starts[j] == o + 1
        if left and right:
            before = (_run(starts[i], ends[i]), _run(starts[j], ends[j]))
            ends[i] = ends[j]
            del starts[j], ends[j]
            kind, k = "bridge", i
        elif left:
            before = (_run(starts[i], ends[i]),)
            ends[i] = o
            kind, k = "extend", i
        elif right:
            before = (_run(starts[j], ends[j]),)
            starts[j] = o
            kind, k = "extend", j
        else:
            before = ()
            starts.insert(j, o)
            ends.insert(j, o)
            kind, k = "new", j
        h.longest = max(h.longest, ends[k] - starts[k] + 1)
        return StreakChange(kind, before, _run(starts[k], ends[k]))

    def current_streak(self, customer_id: Hashable, as_of: date) -> int:
        o = _check_day(as_of, "as_of")
        h = self._by_customer.get(customer_id)
        if h is None:
            return 0
        i = bisect_right(h.starts, o) - 1
        if i < 0:
            return 0
        start, end = h.starts[i], h.ends[i]
        if end >= o:
            return o - start + 1                         # as_of inside the run: later days do not count
        return end - start + 1 if end == o - 1 else 0    # ended yesterday: still alive today

    def longest_streak(self, customer_id: Hashable) -> int:
        h = self._by_customer.get(customer_id)
        return h.longest if h else 0

    def streaks(self, customer_id: Hashable) -> list[Run]:
        h = self._by_customer.get(customer_id)
        return [_run(s, e) for s, e in zip(h.starts, h.ends)] if h else []
