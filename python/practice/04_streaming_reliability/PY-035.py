"""PY-035 - Event-time tumbling windows with a watermark and a late-events side output.

Question: python/questions/04_streaming_reliability/PY-035.md   (python -m lab show PY-035)
Check   : python -m lab check PY-035
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class Event:
    event_time: datetime      # timezone-aware, any offset
    key: str
    value: Decimal


@dataclass(frozen=True)
class WindowResult:
    window_start: datetime    # UTC, inclusive
    window_end: datetime      # UTC, exclusive
    key: str
    count: int
    total: Decimal


class TumblingWindows:
    """Per-key count and sum in fixed event-time windows, closed by a watermark."""

    def __init__(self, allowed_lateness: timedelta, window: timedelta = timedelta(minutes=5)) -> None:
        raise NotImplementedError

    @property
    def watermark(self) -> datetime | None:
        """max event time seen minus allowed_lateness (UTC); None before the first event."""
        raise NotImplementedError

    @property
    def late_events(self) -> list[Event]:
        """Events dropped from aggregation because their window was already closed (arrival order)."""
        raise NotImplementedError

    def process(self, event: Event) -> list[WindowResult]:
        """Add one event; return the windows that this event's arrival caused to close."""
        raise NotImplementedError

    def flush(self) -> list[WindowResult]:
        """End of stream: close and return every remaining open window."""
        raise NotImplementedError
