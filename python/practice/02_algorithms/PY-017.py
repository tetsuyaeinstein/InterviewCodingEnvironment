"""PY-017 - Merge sorted event streams lazily.

Question: python/questions/02_algorithms/PY-017.md   (python -m lab show PY-017)
Check   : python -m lab check PY-017
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any, TypeVar

T = TypeVar("T")


def merge_sorted_streams(
    streams: Iterable[Iterable[T]],
    key: Callable[[T], Any] | None = None,
) -> Iterator[T]:
    """Lazily merge already-sorted streams into one sorted stream.

    Stable: equal keys come out in stream order. Reads nothing until the first next(), and at
    most one item ahead per stream. key (if given) is called once per item read.
    """
    raise NotImplementedError
