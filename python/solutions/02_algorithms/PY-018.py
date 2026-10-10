"""PY-018 reference solution: OrderedDict as hash map + recency list in one structure.

OrderedDict keeps insertion order and supports move_to_end() and popitem(last=False) in O(1), so
the "oldest" entry is always at the front and the "newest" at the back.
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any


class LRUCache:
    def __init__(self, capacity: int, on_evict: Callable[[Any, Any], None] | None = None) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError(f"capacity must be an int, got {type(capacity).__name__}")
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._on_evict = on_evict
        self._data: OrderedDict[Hashable, Any] = OrderedDict()

    def get(self, key: Hashable, default: Any = None) -> Any:
        if key not in self._data:
            return default
        self._data.move_to_end(key)             # a hit makes the key most recently used
        return self._data[key]

    def put(self, key: Hashable, value: Any) -> None:
        if key in self._data:
            self._data[key] = value             # update: no eviction, no callback
            self._data.move_to_end(key)
            return
        self._data[key] = value
        if len(self._data) > self._capacity:
            old_key, old_value = self._data.popitem(last=False)     # least recently used
            if self._on_evict is not None:
                self._on_evict(old_key, old_value)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data                # plain membership: no move_to_end
