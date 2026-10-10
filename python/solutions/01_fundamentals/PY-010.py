"""PY-010 reference solution: eager validation + inner generator driven by itertools.islice."""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import islice
from typing import TypeVar

T = TypeVar("T")


def chunked(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    # This is a plain function (no `yield` here), so these checks run at call time.
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError(f"size must be an int, got {type(size).__name__}")
    if size < 1:
        raise ValueError(f"size must be >= 1, got {size}")
    it = iter(iterable)              # TypeError now if not iterable; one shared iterator

    def _chunks() -> Iterator[list[T]]:
        while True:
            chunk = list(islice(it, size))   # takes at most `size` items, never one more
            if not chunk:
                return                       # exhausted: no empty trailing chunk
            yield chunk

    return _chunks()
