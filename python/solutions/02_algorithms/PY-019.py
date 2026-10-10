"""PY-019 reference solution: monotonic deque of candidate indices -> O(n) amortised, O(k) memory.

The deque holds indices whose values are in strictly DEcreasing order from front to back, so the
front is always the maximum of the current window. For each new value:
  1. pop from the back every index whose value is <= the new one (they can never be a window max
     while the newer, at-least-as-large value is in the window, and they expire sooner);
  2. push the new index;
  3. pop from the front if that index has slid out of the window (index <= i - k);
  4. once the first full window exists (i >= k - 1) record values[deque[0]].
Every index is pushed once and popped at most once, hence O(n) in total.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Sequence


def sliding_window_max(values: Sequence[int], k: int) -> list[int]:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an int, got {type(k).__name__}")
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    result: list[int] = []
    candidates: deque[int] = deque()
    for i, value in enumerate(values):
        while candidates and values[candidates[-1]] <= value:
            candidates.pop()
        candidates.append(i)
        if candidates[0] <= i - k:
            candidates.popleft()
        if i >= k - 1:
            result.append(values[candidates[0]])
    return result
