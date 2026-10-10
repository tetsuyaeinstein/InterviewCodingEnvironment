"""PY-048 - Bounded asyncio concurrency with ordered results and defined error handling.

Question: python/questions/05_database_integrations/PY-048.md   (python -m lab show PY-048)
Check   : python -m lab check PY-048
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any


async def gather_limited(factories: Iterable[Callable[[], Awaitable[Any]]], *, limit: int,
                         return_exceptions: bool = False) -> list:
    """Run every factory()'s awaitable with at most ``limit`` running at once.

    Returns the results in input order. See the question for the error and cancellation rules.
    """
    raise NotImplementedError
