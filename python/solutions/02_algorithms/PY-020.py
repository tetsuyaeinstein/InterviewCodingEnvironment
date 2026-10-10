"""PY-020 reference solution: distinct UTC dates per customer, sort, one linear scan per customer.

1. One pass over the records builds {customer_id: set of UTC dates}. This single step removes
   duplicates (same day), non-COMPLETED rows, guests, and time-of-day.
2. Per customer, sort the distinct dates and scan: a run continues while the next date is exactly
   one day later; otherwise the run is closed (kept if its length >= min_days).

Dates are compared with real date arithmetic (timedelta), so month ends, year ends and leap days
need no special handling. O(n) to build the sets, O(d log d) to sort d distinct days.
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
        streaks: list[Streak] = []
        run_start = previous = None
        for day in sorted(days_by_customer[customer_id]):
            if previous is not None and day - previous == _ONE_DAY:
                previous = day                               # run continues
                continue
            if run_start is not None:                        # a gap closes the previous run
                _close(streaks, run_start, previous, min_days)
            run_start = previous = day
        if run_start is not None:
            _close(streaks, run_start, previous, min_days)
        if streaks:
            result[customer_id] = streaks
    return result


def _close(streaks: list[Streak], start: date, end: date, min_days: int) -> None:
    length = (end - start).days + 1
    if length >= min_days:
        streaks.append((start, end, length))
