"""PY-035 reference solution: dict of open windows + min-heap of their start times.

  watermark    = max event time seen - allowed_lateness (monotonic by construction)
  closed_until = highest instant up to which windows are closed (watermark, or the end of the
                 last flushed window)
  an event is late  <=>  its window_end <= closed_until
  a window closes   <=>  window_end <= closed_until   (i.e. watermark >= window_end)

The heap makes closing O(log W) per closed window instead of scanning every open window on every
event. Windows are emitted in (window_start, key) order, so output is deterministic.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Event:
    event_time: datetime
    key: str
    value: Decimal


@dataclass(frozen=True)
class WindowResult:
    window_start: datetime
    window_end: datetime
    key: str
    count: int
    total: Decimal


class TumblingWindows:
    def __init__(self, allowed_lateness: timedelta, window: timedelta = timedelta(minutes=5)) -> None:
        if allowed_lateness < timedelta(0):
            raise ValueError("allowed_lateness must be >= 0")
        if window <= timedelta(0):
            raise ValueError("window must be positive")
        self._lateness = allowed_lateness
        self._window = window
        self._max_time: datetime | None = None
        self._closed_until: datetime | None = None
        self._open: dict[datetime, dict[str, list]] = {}
        self._heap: list[datetime] = []
        self._late: list[Event] = []

    @property
    def watermark(self) -> datetime | None:
        return None if self._max_time is None else self._max_time - self._lateness

    @property
    def late_events(self) -> list[Event]:
        return list(self._late)

    def _emit_closed(self) -> list[WindowResult]:
        out: list[WindowResult] = []
        while self._heap and self._heap[0] + self._window <= self._closed_until:
            start = heapq.heappop(self._heap)
            for key, (count, total) in sorted(self._open.pop(start).items()):
                out.append(WindowResult(start, start + self._window, key, count, total))
        return out

    def process(self, event: Event) -> list[WindowResult]:
        if event.event_time.tzinfo is None or event.event_time.utcoffset() is None:
            raise ValueError("event_time must be timezone-aware")
        if not isinstance(event.value, Decimal) or not event.value.is_finite():
            raise ValueError(f"value must be a finite Decimal: {event.value!r}")
        t = event.event_time.astimezone(timezone.utc)
        if self._max_time is None or t > self._max_time:
            self._max_time = t
        wm = self._max_time - self._lateness
        if self._closed_until is None or wm > self._closed_until:
            self._closed_until = wm
        start = _EPOCH + ((t - _EPOCH) // self._window) * self._window
        if start + self._window <= self._closed_until:
            self._late.append(event)
            return []
        bucket = self._open.get(start)
        if bucket is None:
            bucket = self._open[start] = {}
            heapq.heappush(self._heap, start)
        acc = bucket.setdefault(event.key, [0, Decimal(0)])
        acc[0] += 1
        acc[1] += event.value
        return self._emit_closed()

    def flush(self) -> list[WindowResult]:
        out: list[WindowResult] = []
        while self._heap:
            start = heapq.heappop(self._heap)
            for key, (count, total) in sorted(self._open.pop(start).items()):
                out.append(WindowResult(start, start + self._window, key, count, total))
            end = start + self._window
            if self._closed_until is None or end > self._closed_until:
                self._closed_until = end
        return out
