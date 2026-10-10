"""PY-011 reference solution: one pass with a "first position of each amount" hash map -> O(n).

Scanning j left to right, the first j that has an earlier partner is, by construction, the
smallest possible j. Remembering only the FIRST position of each amount makes i the smallest
partner for that j. Looking up the complement BEFORE recording amounts[j] means a charge can
never pair with itself (amount == target / 2 needs a second occurrence).
"""
from __future__ import annotations

from collections.abc import Sequence


def find_refund_pair(amounts_cents: Sequence[int], target_cents: int) -> tuple[int, int] | None:
    if isinstance(target_cents, bool) or not isinstance(target_cents, int):
        raise TypeError(f"target_cents must be an int, got {type(target_cents).__name__}")
    first_pos: dict[int, int] = {}
    for j, amount in enumerate(amounts_cents):
        i = first_pos.get(target_cents - amount)
        if i is not None:
            return (i, j)
        first_pos.setdefault(amount, j)      # keep the earliest position; never overwrite
    return None
