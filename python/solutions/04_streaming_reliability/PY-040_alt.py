"""PY-040 alternative: union-find over purchase days (no sorted structure at all).

Each distinct day is a node. Adding day d unions it with d-1 and d+1 if those days exist, and
every set keeps (min, max, size) of its run. Everything is a dict lookup: add is O(alpha(n))
amortised (vs O(log r) + memmove), "is this day already known" is O(1), current_streak is a
couple of finds, longest_streak is a running maximum.

Trade-off: it cannot answer "which run precedes this day" or list the runs in order without
collecting the roots and sorting them, so streaks() is O(r log r) instead of O(r). It also needs
one dict entry per distinct *day* (not per run), so memory is O(days) instead of O(runs).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Hashable

Run = tuple[date, date]


@dataclass(frozen=True)
class StreakChange:
    kind: str
    before: tuple[Run, ...]
    after: Run


def _run(start: int, end: int) -> Run:
    return (date.fromordinal(start), date.fromordinal(end))


def _check_day(day: object, what: str) -> int:
    if isinstance(day, date) and not hasattr(day, "hour"):
        return day.toordinal()
    raise TypeError(f"{what} must be a datetime.date, got {type(day).__name__}")


class _Days:
    """Union-find keyed by day ordinal; each root stores the run's (start, end)."""

    def __init__(self) -> None:
        self.parent: dict[int, int] = {}
        self.span: dict[int, list[int]] = {}      # root -> [start, end]
        self.longest = 0

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:             # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> int:
        ra, rb = self.find(a), self.find(b)
        sa, sb = self.span[ra], self.span[rb]
        if sa[1] - sa[0] < sb[1] - sb[0]:         # union by run length
            ra, rb, sa, sb = rb, ra, sb, sa
        self.parent[rb] = ra
        sa[0], sa[1] = min(sa[0], sb[0]), max(sa[1], sb[1])
        del self.span[rb]
        return ra


class StreakTracker:
    def __init__(self) -> None:
        self._by_customer: dict[Hashable, _Days] = {}

    def add_purchase(self, customer_id: Hashable, day: date) -> StreakChange:
        o = _check_day(day, "day")
        d = self._by_customer.get(customer_id)
        if d is None:
            d = self._by_customer[customer_id] = _Days()
        if o in d.parent:
            s, e = d.span[d.find(o)]
            return StreakChange("duplicate", (_run(s, e),), _run(s, e))
        has_left, has_right = (o - 1) in d.parent, (o + 1) in d.parent
        before = []
        if has_left:
            before.append(_run(*d.span[d.find(o - 1)]))
        if has_right:
            before.append(_run(*d.span[d.find(o + 1)]))
        d.parent[o] = o
        d.span[o] = [o, o]
        root = o
        if has_left:
            root = d.union(root, o - 1)
        if has_right:
            root = d.union(root, o + 1)
        s, e = d.span[root]
        d.longest = max(d.longest, e - s + 1)
        kind = "bridge" if has_left and has_right else "extend" if before else "new"
        return StreakChange(kind, tuple(before), _run(s, e))

    def current_streak(self, customer_id: Hashable, as_of: date) -> int:
        o = _check_day(as_of, "as_of")
        d = self._by_customer.get(customer_id)
        if d is None:
            return 0
        if o in d.parent:
            return o - d.span[d.find(o)][0] + 1      # days after as_of do not count
        if (o - 1) in d.parent:                      # as_of itself is empty, so that run ends yesterday
            s, e = d.span[d.find(o - 1)]
            return e - s + 1
        return 0

    def longest_streak(self, customer_id: Hashable) -> int:
        d = self._by_customer.get(customer_id)
        return d.longest if d else 0

    def streaks(self, customer_id: Hashable) -> list[Run]:
        d = self._by_customer.get(customer_id)
        return [_run(s, e) for s, e in sorted(map(tuple, d.span.values()))] if d else []
