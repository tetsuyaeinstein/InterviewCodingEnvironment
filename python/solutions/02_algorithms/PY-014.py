"""PY-014 reference solution: Counter for O(n) counting, then a bounded heap -> O(n + d log k).

Ranking key (-count, sku): ascending order on it means "count descending, sku ascending", and
it is a total order (SKUs are unique after counting), so the result never depends on the order
the stream arrived in. Counter.most_common(k) is NOT used: it breaks ties by first-seen order.
"""
from __future__ import annotations

import heapq
from collections import Counter
from collections.abc import Iterable


def _validate_k(k: object) -> int:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an int, got {type(k).__name__}")
    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    return k


def top_k_frequent(skus: Iterable[str | None], k: int) -> list[tuple[str, int]]:
    k = _validate_k(k)
    if k == 0:
        return []
    counts = Counter(sku for sku in skus if sku is not None)
    return heapq.nsmallest(k, counts.items(), key=lambda item: (-item[1], item[0]))
