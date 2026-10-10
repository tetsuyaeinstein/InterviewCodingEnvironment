"""PY-018 - Design a small LRU cache.

Question: python/questions/02_algorithms/PY-018.md   (python -m lab show PY-018)
Check   : python -m lab check PY-018
"""
from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Any


class LRUCache:
    """Fixed-capacity cache that evicts the least recently used entry. O(1) average operations.

    get() and put() mark a key most recently used; `in` and len() do not change recency.
    """

    def __init__(self, capacity: int, on_evict: Callable[[Any, Any], None] | None = None) -> None:
        """capacity: int >= 1 (bool/non-int -> TypeError, < 1 -> ValueError).

        on_evict(key, value) is called once per entry evicted to make room (not on updates).
        """
        raise NotImplementedError

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Return the value (and mark the key most recently used), or `default` if missing."""
        raise NotImplementedError

    def put(self, key: Hashable, value: Any) -> None:
        """Insert or update a key as most recently used; evict the LRU entry if over capacity."""
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError

    def __contains__(self, key: object) -> bool:
        """Membership test that does NOT change recency."""
        raise NotImplementedError
