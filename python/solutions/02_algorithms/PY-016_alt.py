"""PY-016 alternative: the standard library's bisect.bisect_left -> O(log n), no hand-written invariant.

bisect_left returns the leftmost insertion point, which is exactly "first index with
seq[i] >= target". It uses only len() and __getitem__ (it is implemented in C but works on any
Sequence), and compares with `<`.

Trade-off: nothing to get wrong, but you must know it exists and know that bisect_left (not
bisect_right) is the "at or after" variant. The hand-written loop is what interviewers ask for
to see whether you can hold the invariant (half-open range, hi = mid, lo = mid + 1) in your head,
and it is the form you need when the predicate is not a plain comparison (bisect's `key=`
parameter, Python 3.10+, covers many such cases).
"""
from __future__ import annotations

import bisect
from collections.abc import Sequence
from typing import Any


def first_at_or_after(seq: Sequence[Any], target: Any) -> int:
    return bisect.bisect_left(seq, target)
