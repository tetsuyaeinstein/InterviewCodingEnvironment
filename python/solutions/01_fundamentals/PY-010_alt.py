"""PY-010 alternative: Python 3.12's itertools.batched, adapted to the list contract.

batched() is implemented in C, validates n < 1 eagerly, and is lazy in the same way (it pulls
at most n items per batch). Differences to know: it yields *tuples* (immutable; here mapped to
lists, which costs one copy per chunk) and it only exists on 3.12+. Its eager ValueError
message is its own; the bool/type checks still have to be ours.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import batched
from typing import TypeVar

T = TypeVar("T")


def chunked(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError(f"size must be an int, got {type(size).__name__}")
    if size < 1:
        raise ValueError(f"size must be >= 1, got {size}")
    return map(list, batched(iterable, size))   # batched() calls iter() eagerly -> TypeError now
