"""PY-003 alternative: full sort with a composite key, then slice -> O(n log n).

Simplest correct answer and often the fastest in CPython for moderate n (Timsort runs in C and
the key tuple is built once per item). It costs O(n) extra memory for the sorted copy and does
work proportional to n log n even when k is 10. The heap version wins when k << n, when the
input is a stream (it never needs all n items at once), or when memory is tight.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal


def top_k_customers(spend: Mapping[int, Decimal], k: int) -> list[tuple[int, Decimal]]:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an int, got {type(k).__name__}")
    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    # Two stable sorts would also work (by id asc, then by spend desc); one composite key is clearer.
    ranked = sorted(spend.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:k]
