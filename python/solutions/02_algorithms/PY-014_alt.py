"""PY-014 alternative: bucket by count, walk buckets from the highest count down -> O(n + d) + tie sorts.

After counting, every count is an integer in 1..n. Put each SKU in the bucket for its count, then
visit buckets from the largest count down, sorting only the bucket being taken (the tie-break),
until k SKUs are collected. Only the buckets actually visited are sorted, so with small k this is
close to linear. Worst case (everything tied) it degrades to sorting one big bucket: O(d log d).

A dict of buckets (instead of a list of n+1 slots) keeps memory O(d) even when one SKU has
a huge count; we then sort the d' <= d distinct count values, which is cheap in practice.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable


def top_k_frequent(skus: Iterable[str | None], k: int) -> list[tuple[str, int]]:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an int, got {type(k).__name__}")
    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    if k == 0:
        return []

    counts = Counter(sku for sku in skus if sku is not None)
    buckets: dict[int, list[str]] = defaultdict(list)
    for sku, c in counts.items():
        buckets[c].append(sku)

    result: list[tuple[str, int]] = []
    for c in sorted(buckets, reverse=True):
        for sku in sorted(buckets[c]):          # tie-break inside one count: sku ascending
            result.append((sku, c))
            if len(result) == k:
                return result
    return result
