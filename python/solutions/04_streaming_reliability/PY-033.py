"""PY-033 reference solution: a plain attempt loop.

delay(n) = min(max_delay, base_delay * multiplier**n) is computed with a loop-carried value
(capped each step) so huge retry counts cannot overflow a float. Jitter is applied after the
cap. sleep/rng/clock are injected, so tests assert the exact sleep sequence.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class TransientError(Exception):
    pass


class RetryError(Exception):
    attempts: int
    last_error: BaseException


def _give_up(message: str, attempts: int, last_error: BaseException) -> RetryError:
    err = RetryError(message)
    err.attempts = attempts
    err.last_error = last_error
    return err


def retry(fn: Callable[[], T], *,
          retries: int = 3,
          base_delay: float = 0.1,
          max_delay: float = 10.0,
          multiplier: float = 2.0,
          jitter: str = "none",
          retry_on: tuple[type[BaseException], ...] = (TransientError,),
          sleep: Callable[[float], Any] = time.sleep,
          rng: Any = random,
          clock: Callable[[], float] = time.monotonic,
          budget: float | None = None,
          on_retry: Callable[[int, BaseException, float], Any] | None = None) -> T:
    if retries < 0 or base_delay < 0 or max_delay < 0 or multiplier < 1:
        raise ValueError("retries, base_delay, max_delay must be >= 0 and multiplier >= 1")
    if budget is not None and budget < 0:
        raise ValueError("budget must be >= 0")
    if jitter not in ("none", "full", "equal"):
        raise ValueError(f"unknown jitter mode {jitter!r}")

    start = clock()
    ceiling = min(base_delay, max_delay)
    for attempt in range(1, retries + 2):
        try:
            return fn()
        except retry_on as exc:
            if attempt > retries:
                raise _give_up(f"gave up after {attempt} attempts: {exc!r}", attempt, exc) from exc
            if jitter == "full":
                delay = rng.uniform(0, ceiling)
            elif jitter == "equal":
                delay = ceiling / 2 + rng.uniform(0, ceiling / 2)
            else:
                delay = ceiling
            if budget is not None and clock() + delay > start + budget:
                raise _give_up(f"time budget of {budget}s exhausted after {attempt} attempts: {exc!r}", attempt, exc) from exc
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            sleep(delay)
            ceiling = min(max_delay, ceiling * multiplier)
    raise AssertionError("unreachable")
