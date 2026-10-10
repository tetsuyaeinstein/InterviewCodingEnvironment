"""PY-014 - Most frequently scanned SKUs.

Question: python/questions/02_algorithms/PY-014.md   (python -m lab show PY-014)
Check   : python -m lab check PY-014
"""
from __future__ import annotations

from collections.abc import Iterable


def top_k_frequent(skus: Iterable[str | None], k: int) -> list[tuple[str, int]]:
    """Return up to k (sku, count) pairs: count descending, then sku ascending.

    None entries are ignored. The stream is read once. k == 0 -> []; k < 0 -> ValueError;
    non-int k (including bool) -> TypeError, raised before the stream is read.
    """
    raise NotImplementedError
