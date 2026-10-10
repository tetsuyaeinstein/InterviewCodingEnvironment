"""PY-030 alternative: sort once, slice the window with bisect, keep state bucketed by timestamp.

  * The batch is sorted by (updated_at, key); bisect_left on the timestamp column finds the
    first record >= lower and the first record >= upper_bound, so the window is one slice and
    "late" is the prefix. This is the shape of a range scan on an index / a sorted file.
  * The dedup state is held as {updated_at: set(keys)} (a time-bucketed dict). Pruning is then
    "drop buckets older than the floor" instead of filtering every pair, which is what you want
    when the state lives in Redis/RocksDB with per-bucket TTLs.

Trade-off versus the reference: O(n log n) for the sort instead of O(n), and "late" comes out in
time order instead of input order (the contract allows any order for `late`); in exchange the
window logic is two bisects and the state prunes by bucket. The external contract
(WatermarkState with a frozenset of pairs) is converted at the boundaries.
"""
from __future__ import annotations

from bisect import bisect_left
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


def _check_aware(value: object, what: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{what} must be a timezone-aware datetime, got {value!r}")
    return value


def select_incremental(records: Iterable[Mapping[str, object]], state: WatermarkState, *,
                       overlap: timedelta, upper_bound: datetime,
                       key_field: str = "id", ts_field: str = "updated_at") -> BatchResult:
    if overlap < timedelta(0):
        raise ValueError("overlap must not be negative")
    _check_aware(upper_bound, "upper_bound")
    wm = state.watermark
    if wm is not None and upper_bound < wm:
        raise ValueError("upper_bound is before the watermark")

    rows = []
    for rec in records:
        if rec.get(key_field) is None:
            raise ValueError(f"record without {key_field!r}")
        rows.append((_check_aware(rec.get(ts_field), ts_field), rec[key_field], rec))
    rows.sort(key=lambda t: (t[0], t[1]))
    stamps = [t[0] for t in rows]

    start = 0 if wm is None else bisect_left(stamps, wm - overlap)   # inclusive lower bound
    stop = bisect_left(stamps, upper_bound)                         # exclusive upper bound
    late = [r for _, _, r in rows[:start]]

    buckets: dict[datetime, set[Hashable]] = {}
    for key, ts in state.processed:
        buckets.setdefault(ts, set()).add(key)

    to_process = []
    new_wm = wm
    for ts, key, rec in rows[start:stop]:
        seen = buckets.setdefault(ts, set())
        if key in seen:
            continue
        seen.add(key)
        to_process.append(rec)
        if new_wm is None or ts > new_wm:
            new_wm = ts

    if new_wm is None:
        processed: frozenset = frozenset()
    else:
        floor = new_wm - overlap
        processed = frozenset((k, ts) for ts, keys in buckets.items() if ts >= floor for k in keys)
    return BatchResult(to_process=to_process, late=late,
                       state=WatermarkState(watermark=new_wm, processed=processed))
