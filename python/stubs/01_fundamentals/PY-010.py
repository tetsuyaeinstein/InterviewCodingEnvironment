"""PY-010 - Lazy fixed-size chunking of any iterable.

Question: python/questions/01_fundamentals/PY-010.md   (python -m lab show PY-010)
Check   : python -m lab check PY-010
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TypeVar

T = TypeVar("T")


def chunked(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    """Return an iterator of new lists of up to ``size`` consecutive items from ``iterable``.

    Arguments are validated at call time (non-int/bool size or non-iterable -> TypeError,
    size < 1 -> ValueError). Fully lazy: no read-ahead, works on infinite sources,
    no empty trailing chunk.
    """
    raise NotImplementedError
