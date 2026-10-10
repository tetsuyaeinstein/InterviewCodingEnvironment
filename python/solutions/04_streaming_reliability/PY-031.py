"""PY-031 reference solution: per key keep (top sequence, distinct variants at that sequence).

Because the winner is a pure function of the *set* of events seen per key (max sequence, then
distinct variants at it, earliest ingest_ts per variant), any arrival order yields the same
final state. apply() only reports what happened to the one event it was given.
"""
from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime

_OPS = ("I", "U", "D")


@dataclass(frozen=True)
class Event:
    key: str
    sequence: int
    ingest_ts: datetime
    payload: dict
    op: str


@dataclass(frozen=True)
class Conflict:
    key: str
    sequence: int
    variants: tuple[Event, ...]


def _variant_id(e: Event) -> tuple:
    # deletes carry no meaningful payload; everything else is compared by value (==)
    return ("D", None) if e.op == "D" else (e.op, e.payload)


class CurrentState:
    def __init__(self) -> None:
        # key -> [top_sequence, [variant events, ordered by (op, ingest_ts-first-seen)]]
        self._state: dict[str, list] = {}

    @staticmethod
    def _validate(e: Event) -> None:
        if e.op not in _OPS:
            raise ValueError(f"unknown op {e.op!r}")
        if isinstance(e.sequence, bool) or not isinstance(e.sequence, int):
            raise ValueError(f"sequence must be an int, got {e.sequence!r}")
        if e.ingest_ts.tzinfo is None:
            raise ValueError("ingest_ts must be timezone-aware")

    def apply(self, event: Event) -> str:
        self._validate(event)
        entry = self._state.get(event.key)
        if entry is None or event.sequence > entry[0]:
            self._state[event.key] = [event.sequence, [event]]
            return "applied"
        if event.sequence < entry[0]:
            return "stale"
        variants: list[Event] = entry[1]
        vid = _variant_id(event)
        for i, v in enumerate(variants):
            if _variant_id(v) == vid:
                if event.ingest_ts < v.ingest_ts:       # keep the earliest copy: order independent
                    variants[i] = event
                return "duplicate"
        variants.append(event)
        return "conflict"

    def apply_all(self, events: Iterable[Event]) -> list[str]:
        return [self.apply(e) for e in events]

    def snapshot(self) -> dict[str, dict]:
        out = {}
        for key in sorted(self._state):
            _, variants = self._state[key]
            if len(variants) == 1 and variants[0].op != "D":
                out[key] = copy.deepcopy(variants[0].payload)
        return out

    def record(self, key: str) -> Event | None:
        entry = self._state.get(key)
        if entry is None or len(entry[1]) != 1:
            return None
        return entry[1][0]

    def conflicts(self) -> list[Conflict]:
        res = []
        for key in sorted(self._state):
            seq, variants = self._state[key]
            if len(variants) > 1:
                ordered = sorted(variants, key=lambda e: (e.op, "" if e.op == "D" else json.dumps(e.payload, sort_keys=True, default=str)))
                res.append(Conflict(key, seq, tuple(ordered)))
        return res
