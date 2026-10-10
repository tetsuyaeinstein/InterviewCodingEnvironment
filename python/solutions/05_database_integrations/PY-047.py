"""PY-047 reference solution: honour Retry-After exactly, bounded by attempts and elapsed time."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RateLimited(Exception):
    def __init__(self, retry_after: float | None = None):
        super().__init__(f"rate limited (retry after {retry_after})")
        self.retry_after = retry_after


def call_with_rate_limit(call: Callable[[], T], *, sleep: Callable[[float], None],
                         clock: Callable[[], float], max_attempts: int = 5,
                         max_total_wait: float = 60.0, default_backoff: float = 1.0) -> T:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    start = clock()
    for attempt in range(max_attempts):
        try:
            return call()
        except RateLimited as exc:
            if attempt == max_attempts - 1:
                raise                                   # out of attempts: do not wait for nothing
            if exc.retry_after is None:
                wait = default_backoff * (2 ** attempt)
            else:
                wait = max(0.0, exc.retry_after)
            if (clock() - start) + wait > max_total_wait:
                raise                                   # the server asks for more than we can afford
            if wait > 0:
                sleep(wait)
    raise AssertionError("unreachable")                 # pragma: no cover


class RateLimiter:
    """Sliding-window log: remembers the admission times of the last window."""

    def __init__(self, max_calls: int, period: float, *, clock: Callable[[], float],
                 sleep: Callable[[float], None]):
        if max_calls < 1 or period <= 0:
            raise ValueError("max_calls must be >= 1 and period > 0")
        self._max, self._period, self._clock, self._sleep = max_calls, period, clock, sleep
        self._admitted: deque[float] = deque()

    def acquire(self) -> float:
        waited = 0.0
        while True:
            now = self._clock()
            while self._admitted and self._admitted[0] <= now - self._period:
                self._admitted.popleft()
            if len(self._admitted) < self._max:
                self._admitted.append(now)
                return waited
            wait = self._admitted[0] + self._period - now
            self._sleep(wait)
            waited += wait
