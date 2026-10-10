"""PY-030 reference solution: stateless window filter + set-based dedup + pruned state.

Per record: validate -> deferred (>= upper) -> late (< lower) -> duplicate (in processed set or
already taken this batch) -> select. The new watermark is the max selected updated_at, never
below the old one. The processed set is pruned to pairs that could still re-enter the next
window (updated_at >= new_watermark - overlap), so state size is bounded by the number of
versions inside one overlap window, not by history.
"""
from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class WatermarkState:
    watermark: datetime | None = None
    processed: frozenset[tuple[Hashable, datetime]] = frozenset()


@dataclass
class BatchResult:
    to_process: list[Mapping[str, object]] = field(default_factory=list)
    late: list[Mapping[str, object]] = field(default_factory=list)
    state: WatermarkState = field(default_factory=WatermarkState)


def _aware(value: object, what: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{what} must be a timezone-aware datetime, got {value!r}")
    return value


def select_incremental(records: Iterable[Mapping[str, object]], state: WatermarkState, *,
                       overlap: timedelta, upper_bound: datetime,
                       key_field: str = "id", ts_field: str = "updated_at") -> BatchResult:
    if overlap < timedelta(0):
        raise ValueError("overlap must not be negative")
    _aware(upper_bound, "upper_bound")
    wm = state.watermark
    if wm is not None and upper_bound < wm:
        raise ValueError(f"upper_bound {upper_bound} is before the watermark {wm}: clock went backwards?")
    lower = wm - overlap if wm is not None else None

    selected: list[tuple[datetime, Hashable, Mapping[str, object]]] = []
    taken: set[tuple[Hashable, datetime]] = set()
    late: list[Mapping[str, object]] = []
    for rec in records:
        if key_field not in rec or rec[key_field] is None:
            raise ValueError(f"record without {key_field!r}: {rec!r}")
        ts = _aware(rec.get(ts_field), ts_field)
        if ts >= upper_bound:
            continue                                   # not yet: picked up by a later run
        if lower is not None and ts < lower:
            late.append(rec)                           # outside the overlap: cannot dedup safely
            continue
        pair = (rec[key_field], ts)
        if pair in state.processed or pair in taken:
            continue                                   # re-delivery inside the overlap
        taken.add(pair)
        selected.append((ts, rec[key_field], rec))

    selected.sort(key=lambda t: (t[0], t[1]))
    new_wm = wm
    if selected:
        top = selected[-1][0]
        new_wm = top if wm is None or top > wm else wm  # never moves backwards
    if new_wm is None:
        processed: frozenset = frozenset()
    else:
        floor = new_wm - overlap
        processed = frozenset(p for p in state.processed | taken if p[1] >= floor)
    return BatchResult(to_process=[r for _, _, r in selected], late=late,
                       state=WatermarkState(watermark=new_wm, processed=processed))
