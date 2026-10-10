"""PY-020 - Customer purchase streaks (pure Python).

Question: python/questions/02_algorithms/PY-020.md   (python -m lab show PY-020)
Check   : python -m lab check PY-020
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

Record = tuple["int | None", datetime, str]       # (customer_id, purchased_at, status)
Streak = tuple[date, date, int]                    # (first_date, last_date inclusive, length_in_days)


def find_purchase_streaks(
    records: Iterable[Record],
    min_days: int = 5,
) -> dict[int, list[Streak]]:
    """Return, per customer, every maximal run of >= min_days consecutive UTC purchase dates.

    Only status == "COMPLETED" and customer_id is not None count; purchased_at must be timezone
    aware (naive -> ValueError); several purchases on one UTC date are one day. Dict ordered by
    customer_id, streaks chronological; customers without a streak are omitted.
    min_days: int >= 1 (bool/non-int -> TypeError, < 1 -> ValueError), validated first.
    """
    raise NotImplementedError
