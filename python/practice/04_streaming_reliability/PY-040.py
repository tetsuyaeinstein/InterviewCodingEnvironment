"""PY-040 - Incremental purchase streaks that repair themselves when a late day arrives.

Question: python/questions/04_streaming_reliability/PY-040.md   (python -m lab show PY-040)
Check   : python -m lab check PY-040
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Hashable

Run = tuple[date, date]    # (first_day, last_day), both inclusive


@dataclass(frozen=True)
class StreakChange:
    kind: str                  # "new" | "extend" | "bridge" | "duplicate"
    before: tuple[Run, ...]    # the existing run(s) this purchase touched, in date order
    after: Run                 # the run that now covers the purchase day


class StreakTracker:
    """Per-customer runs of consecutive purchase days, maintained incrementally."""

    def add_purchase(self, customer_id: Hashable, day: date) -> StreakChange:
        """Record a purchase on ``day`` (any arrival order) and describe how the runs changed."""
        raise NotImplementedError

    def current_streak(self, customer_id: Hashable, as_of: date) -> int:
        """Length of the run that is alive on ``as_of``, counting only days <= as_of."""
        raise NotImplementedError

    def longest_streak(self, customer_id: Hashable) -> int:
        """Length of the longest run ever (0 for a customer without purchases)."""
        raise NotImplementedError

    def streaks(self, customer_id: Hashable) -> list[Run]:
        """All runs of the customer, sorted by first day."""
        raise NotImplementedError
