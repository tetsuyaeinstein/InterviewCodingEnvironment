"""PY-006 - Daily totals by business date in a local timezone.

Question: python/questions/01_fundamentals/PY-006.md   (python -m lab show PY-006)
Check   : python -m lab check PY-006
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Any, NamedTuple


class DayTotal(NamedTuple):
    transaction_count: int
    gross_amount: Decimal


def daily_totals_by_business_date(transactions: Iterable[Mapping[str, Any]],
                                  business_tz: str) -> dict[date, DayTotal]:
    """Group transactions by their local calendar date in ``business_tz``.

    transaction_ts: aware datetime or ISO string with Z/offset (naive -> ValueError).
    amount: Decimal or int (float -> TypeError). Unknown zone -> ValueError.
    Returns {business_date: DayTotal(count, exact sum)} with keys in ascending date order.
    """
    raise NotImplementedError
