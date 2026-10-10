"""PY-017 reference solution: manual min-heap of one head per stream -> O(N log K) time, O(K) memory.

Heap entries are (key, stream_index, item, iterator). A stream has at most one entry in the heap,
so (key, stream_index) is unique and the comparison never reaches `item` or the iterator. That
gives the tie rule (lower stream index first) and means raw items are never compared.

It is a generator: nothing is read until the first next(). After yielding an item from stream s,
only stream s is advanced (heapreplace = pop + push in one sift), so a stream is read at most one
item ahead of what was yielded from it.
"""
from __future__ import annotations

import heapq
from collections.abc import Callable, Iterable, Iterator
from typing import Any, TypeVar

T = TypeVar("T")


def merge_sorted_streams(
    streams: Iterable[Iterable[T]],
    key: Callable[[T], Any] | None = None,
) -> Iterator[T]:
    heap: list[tuple[Any, int, T, Iterator[T]]] = []
    for index, stream in enumerate(streams):
        it = iter(stream)
        for item in it:                          # first item only, then break
            heap.append((item if key is None else key(item), index, item, it))
            break
    heapq.heapify(heap)

    while heap:
        k, index, item, it = heap[0]
        yield item
        for nxt in it:                           # advance only the stream we just emitted from
            heapq.heapreplace(heap, (nxt if key is None else key(nxt), index, nxt, it))
            break
        else:                                    # exhausted: drop it, never poll it again
            heapq.heappop(heap)
