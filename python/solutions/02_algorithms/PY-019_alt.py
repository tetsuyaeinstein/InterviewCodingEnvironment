"""PY-019 alternative: max-heap with lazy deletion -> O(n log n) time, O(n) worst-case memory.

Push (-value, index) for every reading. The heap top may belong to an index that already left
the window; we do not search for it, we simply discard such tops when they surface ("lazy
deletion"). After the discard loop the top is a valid in-window maximum.

Simpler to write and to reason about than the monotonic deque, and it generalises (any "best in
window" with a comparison, or a heap keyed on something else). Costs: O(log n) per push/pop, and
the heap may keep up to n stale entries (e.g. strictly decreasing input never discards any
until they reach the top), so memory is O(n) instead of O(k).
"""
from __future__ import annotations

import heapq
from collections.abc import Sequence


def sliding_window_max(values: Sequence[int], k: int) -> list[int]:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an int, got {type(k).__name__}")
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    result: list[int] = []
    heap: list[tuple[int, int]] = []
    for i, value in enumerate(values):
        heapq.heappush(heap, (-value, i))
        if i >= k - 1:
            while heap[0][1] <= i - k:           # top is outside the window: drop it lazily
                heapq.heappop(heap)
            result.append(-heap[0][0])
    return result
