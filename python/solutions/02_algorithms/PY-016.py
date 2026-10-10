"""PY-016 reference solution: hand-written lower bound on a half-open range [lo, hi) -> O(log n).

Invariant: every index < lo holds a value < target; every index >= hi holds a value >= target.
hi starts at len(seq), so "no element qualifies" naturally ends with lo == hi == len(seq).
When seq[mid] >= target, mid may be the answer, so hi = mid (not mid - 1); that is what keeps
the FIRST of several equal elements.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def first_at_or_after(seq: Sequence[Any], target: Any) -> int:
    lo, hi = 0, len(seq)
    while lo < hi:
        mid = (lo + hi) // 2
        if seq[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo
