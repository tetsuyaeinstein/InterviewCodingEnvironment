"""PY-048 alternative: one task per item, throttled by an asyncio.Semaphore.

Shorter, and the usual interview answer. Trade-off: it creates a task (and a coroutine frame) for
EVERY item up front, so memory is O(n) and the factories iterable is fully consumed immediately.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any


async def gather_limited(factories: Iterable[Callable[[], Awaitable[Any]]], *, limit: int,
                         return_exceptions: bool = False) -> list:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be an int >= 1")
    semaphore = asyncio.Semaphore(limit)

    async def run(factory):
        async with semaphore:                 # the work starts only once a slot is held
            return await factory()

    tasks = [asyncio.ensure_future(run(f)) for f in factories]
    try:
        # gather(...) raises the first exception in time; with return_exceptions it collects them.
        return list(await asyncio.gather(*tasks, return_exceptions=return_exceptions))
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()                    # also cancels tasks still waiting for the semaphore
        await asyncio.gather(*tasks, return_exceptions=True)
