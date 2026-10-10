"""PY-003 - Top-K customers by spend with deterministic ties.

Question: python/questions/01_fundamentals/PY-003.md   (python -m lab show PY-003)
Check   : python -m lab check PY-003
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal


def top_k_customers(spend: Mapping[int, Decimal], k: int) -> list[tuple[int, Decimal]]:
    """Return up to k (customer_id, spend) pairs: spend descending, then customer_id ascending.

    k > len(spend) returns everyone; k == 0 returns []; k < 0 -> ValueError;
    non-int k (including bool) -> TypeError. The input is not mutated.
    """
    raise NotImplementedError
