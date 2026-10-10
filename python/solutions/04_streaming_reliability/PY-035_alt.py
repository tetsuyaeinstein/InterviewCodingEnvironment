"""PY-035 alternative: one flat dict {(window_start, key): [count, total]}, closing by scanning.

No heap and no per-window nesting: on every event, scan the open entries and emit those whose
end <= closed_until, sorted at the end. Simpler, but O(open aggregates) per event instead of
O(log windows) per closed window. Fine while allowed_lateness is a few windows; it degrades when
many keys x many open windows are live (long lateness). Behaviour is identical.
"""
from __future__ import annotations

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
        self._agg: dict[tuple[datetime, str], list] = {}
        self._late: list[Event] = []

    @property
    def watermark(self) -> datetime | None:
        return None if self._max_time is None else self._max_time - self._lateness

    @property
    def late_events(self) -> list[Event]:
        return list(self._late)

    def _take(self, keys: list[tuple[datetime, str]]) -> list[WindowResult]:
        out = []
        for start, key in sorted(keys):
            count, total = self._agg.pop((start, key))
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
        start = t - ((t - _EPOCH) % self._window)
        if start + self._window <= self._closed_until:
            self._late.append(event)
            return []
        acc = self._agg.setdefault((start, event.key), [0, Decimal(0)])
        acc[0] += 1
        acc[1] += event.value
        return self._take([k for k in self._agg if k[0] + self._window <= self._closed_until])

    def flush(self) -> list[WindowResult]:
        keys = list(self._agg)
        if keys:
            last_end = max(k[0] for k in keys) + self._window
            if self._closed_until is None or last_end > self._closed_until:
                self._closed_until = last_end
        return self._take(keys)
