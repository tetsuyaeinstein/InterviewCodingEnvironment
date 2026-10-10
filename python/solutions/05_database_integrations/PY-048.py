"""PY-048 reference solution: a fixed pool of `limit` workers draining one shared iterator.

The number of tasks is bounded by `limit` (not by the input size) and the factories are consumed
lazily, so a generator of millions of items never materialises.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any


async def gather_limited(factories: Iterable[Callable[[], Awaitable[Any]]], *, limit: int,
                         return_exceptions: bool = False) -> list:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be an int >= 1")

    source = enumerate(factories)       # shared by all workers; next() never awaits, so it is race-free
    results: dict[int, Any] = {}
    first_error: list[BaseException] = []

    async def worker() -> None:
        for index, factory in source:
            try:
                results[index] = await factory()
            except Exception as exc:
                if return_exceptions:
                    results[index] = exc
                    continue
                if not first_error:
                    first_error.append(exc)
                raise

    workers = [asyncio.create_task(worker()) for _ in range(limit)]
    try:
        if return_exceptions:
            await asyncio.gather(*workers)
        else:
            # FIRST_EXCEPTION: return as soon as any worker has failed.
            await asyncio.wait(workers, return_when=asyncio.FIRST_EXCEPTION)
    finally:
        # Reached on success, on failure and on outer cancellation alike.
        for w in workers:
            if not w.done():
                w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)   # let finally-blocks run

    if first_error:
        raise first_error[0]
    return [results[i] for i in range(len(results))]
