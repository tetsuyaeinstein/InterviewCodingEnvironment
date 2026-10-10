"""PY-017 alternative: tournament (winner) tree over the K stream heads -> O(N log K), O(K) memory.

Instead of a heap, keep a complete binary tree whose leaves are the streams and whose internal
nodes store the index of the winning stream of their subtree. The overall winner is at the root.
After emitting the winner we advance ONLY that stream and replay the matches on its leaf-to-root
path: one comparison per level (log2 K comparisons), where a heap sift-down does about two per
level. The tree has a fixed shape and size (no push/pop), and the winner is available at the root
in O(1).

Tie rule: a match between streams a and b is won by the smaller (key, stream_index) pair, and an
exhausted stream loses to everything.

Trade-offs vs the heap: fewer comparisons per output and predictable memory layout, but more code,
a power-of-two sized array, and no standard-library support. In CPython the heap usually wins on
speed because heapq is implemented in C; the tree mostly matters in languages/hardware where
comparisons are the cost (external merge sort, k-way merges of huge runs).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any, TypeVar

T = TypeVar("T")

_EXHAUSTED = object()


def merge_sorted_streams(
    streams: Iterable[Iterable[T]],
    key: Callable[[T], Any] | None = None,
) -> Iterator[T]:
    iterators = [iter(s) for s in streams]
    k = len(iterators)
    if k == 0:
        return
    size = 1
    while size < k:
        size *= 2

    keys: list[Any] = [_EXHAUSTED] * size        # head key per leaf (or _EXHAUSTED)
    items: list[Any] = [None] * size

    def advance(s: int) -> None:
        for item in iterators[s]:
            items[s] = item
            keys[s] = item if key is None else key(item)
            return
        keys[s] = _EXHAUSTED

    def beats(a: int, b: int) -> bool:           # does stream a beat stream b?
        if keys[a] is _EXHAUSTED:
            return False
        if keys[b] is _EXHAUSTED:
            return True
        ka, kb = keys[a], keys[b]
        return ka < kb or (not kb < ka and a < b)

    for s in range(k):
        advance(s)

    tree = [0] * (2 * size)                      # tree[size + s] is leaf s; tree[1] is the root
    for s in range(size):
        tree[size + s] = s
    for node in range(size - 1, 0, -1):
        left, right = tree[2 * node], tree[2 * node + 1]
        tree[node] = left if beats(left, right) else right

    while True:
        winner = tree[1]
        if keys[winner] is _EXHAUSTED:
            return
        yield items[winner]
        advance(winner)                          # only the emitted stream moves
        node = (size + winner) // 2
        while node >= 1:
            left, right = tree[2 * node], tree[2 * node + 1]
            tree[node] = left if beats(left, right) else right
            node //= 2
