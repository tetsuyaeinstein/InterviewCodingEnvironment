"""PY-018 alternative: dict + hand-built doubly linked list with sentinels (what OrderedDict does).

Layout: head <-> oldest <-> ... <-> newest <-> tail. The dict maps key -> node, so find is O(1);
unlinking a node needs its predecessor, which is why the list is doubly linked; the two
sentinel nodes mean there is no "empty list" or "first/last node" special case in link/unlink.

Trade-off vs OrderedDict: about 40 lines instead of 10, and slower in CPython (the C-implemented
OrderedDict wins), but it is the version an interviewer usually wants to see, and the pattern
carries over to languages without an ordered map.
"""
from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Any


class _Node:
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: Any = None, value: Any = None) -> None:
        self.key = key
        self.value = value
        self.prev: _Node | None = None
        self.next: _Node | None = None


class LRUCache:
    def __init__(self, capacity: int, on_evict: Callable[[Any, Any], None] | None = None) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError(f"capacity must be an int, got {type(capacity).__name__}")
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._on_evict = on_evict
        self._nodes: dict[Hashable, _Node] = {}
        self._head = _Node()                    # sentinel before the oldest entry
        self._tail = _Node()                    # sentinel after the newest entry
        self._head.next = self._tail
        self._tail.prev = self._head

    def _unlink(self, node: _Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev

    def _append_newest(self, node: _Node) -> None:
        last = self._tail.prev
        last.next = node
        node.prev = last
        node.next = self._tail
        self._tail.prev = node

    def get(self, key: Hashable, default: Any = None) -> Any:
        node = self._nodes.get(key)
        if node is None:
            return default
        self._unlink(node)
        self._append_newest(node)
        return node.value

    def put(self, key: Hashable, value: Any) -> None:
        node = self._nodes.get(key)
        if node is not None:
            node.value = value
            self._unlink(node)
            self._append_newest(node)
            return
        node = _Node(key, value)
        self._nodes[key] = node
        self._append_newest(node)
        if len(self._nodes) > self._capacity:
            oldest = self._head.next
            self._unlink(oldest)
            del self._nodes[oldest.key]
            if self._on_evict is not None:
                self._on_evict(oldest.key, oldest.value)

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, key: object) -> bool:
        return key in self._nodes
