"""PY-011 - Match a refund to a pair of charges.

Question: python/questions/02_algorithms/PY-011.md   (python -m lab show PY-011)
Check   : python -m lab check PY-011
"""
from __future__ import annotations

from collections.abc import Sequence


def find_refund_pair(amounts_cents: Sequence[int], target_cents: int) -> tuple[int, int] | None:
    """Return positions (i, j), i < j, whose amounts sum to target_cents, or None.

    Policy: smallest j first, then smallest i. A position is never used twice.
    Non-int target_cents (including bool) -> TypeError. The input is not mutated.
    """
    raise NotImplementedError
