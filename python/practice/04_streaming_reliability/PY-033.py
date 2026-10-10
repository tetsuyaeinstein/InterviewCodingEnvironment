"""PY-033 - Retry transient failures with capped exponential backoff.

Question: python/questions/04_streaming_reliability/PY-033.md   (python -m lab show PY-033)
Check   : python -m lab check PY-033
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class TransientError(Exception):
    """A failure worth retrying (timeout, 503, deadlock victim, ...)."""


class RetryError(Exception):
    """All attempts failed (or the time budget ran out).

    Build it with a message only, then set the two attributes before raising it.
    """

    attempts: int                  # number of times fn was called
    last_error: BaseException      # the exception of the final attempt


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
    """Call ``fn()`` until it returns, retrying ``retry_on`` errors with capped exponential backoff.

    See the question for the exact delay, jitter, budget and error semantics.
    """
    raise NotImplementedError
