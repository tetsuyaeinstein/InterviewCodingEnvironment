"""PY-033 alternative: separate the schedule (a generator of un-jittered delays) from the loop.

`backoff_delays()` is a pure, independently testable iterator; `retry()` consumes it one value
per failed attempt. This is the shape of libraries like tenacity / backoff (wait strategies as
objects). Behaviour is identical to the plain loop.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable, Iterator
from itertools import islice
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


def backoff_delays(base_delay: float, multiplier: float, max_delay: float) -> Iterator[float]:
    delay = min(base_delay, max_delay)
    while True:
        yield delay
        delay = min(max_delay, delay * multiplier)


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
    modes: dict[str, Callable[[float], float]] = {
        "none": lambda d: d,
        "full": lambda d: rng.uniform(0, d),
        "equal": lambda d: d / 2 + rng.uniform(0, d / 2),
    }
    if jitter not in modes:
        raise ValueError(f"unknown jitter mode {jitter!r}")

    start = clock()
    schedule = islice(backoff_delays(base_delay, multiplier, max_delay), retries)
    attempts = 0
    while True:
        attempts += 1
        try:
            return fn()
        except retry_on as exc:
            nxt = next(schedule, None)
            if nxt is None:
                raise _give_up(f"gave up after {attempts} attempts: {exc!r}", attempts, exc) from exc
            delay = modes[jitter](nxt)
            if budget is not None and clock() + delay > start + budget:
                raise _give_up(f"time budget exhausted after {attempts} attempts: {exc!r}", attempts, exc) from exc
            if on_retry is not None:
                on_retry(attempts, exc, delay)
            sleep(delay)
