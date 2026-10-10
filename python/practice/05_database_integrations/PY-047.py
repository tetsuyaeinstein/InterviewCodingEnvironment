"""PY-047 - Respect API rate limits (HTTP 429 / Retry-After) with injectable time.

Question: python/questions/05_database_integrations/PY-047.md   (python -m lab show PY-047)
Check   : python -m lab check PY-047
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(eq=False)
class RateLimited(Exception):
    """The server answered 429. ``retry_after`` is the Retry-After value in seconds (None = absent)."""

    retry_after: float | None = None


def call_with_rate_limit(call: Callable[[], T], *, sleep: Callable[[float], None],
                         clock: Callable[[], float], max_attempts: int = 5,
                         max_total_wait: float = 60.0, default_backoff: float = 1.0) -> T:
    """Call ``call()``; on RateLimited wait as the server asks and retry. See the question."""
    raise NotImplementedError


class RateLimiter:
    """Client-side limiter: at most ``max_calls`` acquisitions in any window of ``period`` seconds."""

    def __init__(self, max_calls: int, period: float, *, clock: Callable[[], float],
                 sleep: Callable[[float], None]):
        raise NotImplementedError

    def acquire(self) -> float:
        """Block (via the injected sleep) until a call is allowed; return the total seconds waited."""
        raise NotImplementedError
