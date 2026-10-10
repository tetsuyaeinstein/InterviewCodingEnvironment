"""PY-003 reference solution: heapq.nsmallest with a composite key -> O(n log k).

Key (-spend, customer_id): "smallest" under this key means highest spend, then lowest id, so a
single ascending order expresses both ranking rules. nsmallest keeps a bounded heap of k items
while scanning, and falls back to sorted() when k >= n.
"""
from __future__ import annotations

import heapq
from collections.abc import Mapping
from decimal import Decimal


def _validate_k(k: object) -> int:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an int, got {type(k).__name__}")
    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    return k


def top_k_customers(spend: Mapping[int, Decimal], k: int) -> list[tuple[int, Decimal]]:
    k = _validate_k(k)
    if k == 0:
        return []
    return heapq.nsmallest(k, spend.items(), key=lambda item: (-item[1], item[0]))
