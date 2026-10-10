"""PY-031 - Order-aware current state from out-of-order business events.

Question: python/questions/04_streaming_reliability/PY-031.md   (python -m lab show PY-031)
Check   : python -m lab check PY-031
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Event:
    key: str
    sequence: int          # assigned by the source system, per key, higher = newer
    ingest_ts: datetime    # when WE received it (timezone-aware); never used for ordering
    payload: dict          # full row image (ignored for deletes)
    op: str                # "I" insert, "U" update, "D" delete


@dataclass(frozen=True)
class Conflict:
    key: str
    sequence: int
    variants: tuple[Event, ...]   # one event per distinct (op, payload), see the question for order


class CurrentState:
    """Current state per key, built from events that may arrive in any order."""

    def apply(self, event: Event) -> str:
        """Fold one event in. Returns "applied", "stale", "duplicate" or "conflict"."""
        raise NotImplementedError

    def apply_all(self, events: Iterable[Event]) -> list[str]:
        """Apply events in iteration order; return the outcome of each."""
        raise NotImplementedError

    def snapshot(self) -> dict[str, dict]:
        """Live (not deleted, not conflicted) keys -> payload. Returns copies."""
        raise NotImplementedError

    def record(self, key: str) -> Event | None:
        """The winning event of ``key`` (a delete event for a tombstone), else None."""
        raise NotImplementedError

    def conflicts(self) -> list[Conflict]:
        """Unresolved conflicts, sorted by key."""
        raise NotImplementedError
