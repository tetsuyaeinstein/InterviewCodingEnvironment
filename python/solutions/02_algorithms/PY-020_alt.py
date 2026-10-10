"""PY-020 alternative: set membership, count only from run STARTS (no sorting of days) -> O(n).

A date is the start of a run exactly when the previous calendar day is not in the customer's set.
From each start walk forward while the next day is present. Every date is visited by the walk at
most once (only the walk from its run's start passes over it), so the work per customer is
O(d), not O(d log d). Only the (few) reported streaks are sorted at the end, so the output is
chronological.

Compared with sort + scan: no O(d log d) sort and no need to hold a sorted list, but the same
O(d) set memory and a bit more branching; the walk's "is in set" checks are hash lookups. When
streaks are rare, almost all work is the O(1) "is this a start?" check per date.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone

Record = tuple["int | None", datetime, str]
Streak = tuple[date, date, int]

_ONE_DAY = timedelta(days=1)


def find_purchase_streaks(
    records: Iterable[Record],
    min_days: int = 5,
) -> dict[int, list[Streak]]:
    if isinstance(min_days, bool) or not isinstance(min_days, int):
        raise TypeError(f"min_days must be an int, got {type(min_days).__name__}")
    if min_days < 1:
        raise ValueError(f"min_days must be >= 1, got {min_days}")

    days_by_customer: dict[int, set[date]] = {}
    for customer_id, purchased_at, status in records:
        if status != "COMPLETED" or customer_id is None:
            continue
        if purchased_at.tzinfo is None or purchased_at.utcoffset() is None:
            raise ValueError(f"purchased_at must be timezone-aware, got {purchased_at!r}")
        days_by_customer.setdefault(customer_id, set()).add(purchased_at.astimezone(timezone.utc).date())

    result: dict[int, list[Streak]] = {}
    for customer_id in sorted(days_by_customer):
        days = days_by_customer[customer_id]
        streaks: list[Streak] = []
        for start in days:
            if start - _ONE_DAY in days:                     # not the first day of its run
                continue
            end = start
            while end + _ONE_DAY in days:
                end += _ONE_DAY
            length = (end - start).days + 1
            if length >= min_days:
                streaks.append((start, end, length))
        if streaks:
            streaks.sort()                                   # set iteration order is arbitrary
            result[customer_id] = streaks
    return result
