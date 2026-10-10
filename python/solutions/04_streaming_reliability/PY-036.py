"""PY-036 reference solution: group by customer, sort the batch by (change_ts, arrival), fold.

Per customer we keep the rows sorted by effective_from; the current row is always the last
one (open interval). Applying a change either appends a new current row (after closing the
previous one at exactly change_ts - a half-open boundary, so intervals can never overlap or
leave a gap), or is a no-op, or is rejected. Sorting the batch first means the only way a change
can be "older than the current version" is an older change against PRE-EXISTING history.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Rejected:
    change: dict
    reason: str


@dataclass(frozen=True)
class Scd2Result:
    rows: list[dict]
    rejected: list[Rejected]


def _aware(value: object, what: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{what} must be a timezone-aware datetime, got {value!r}")
    return value


def apply_scd2(dimension: Iterable[Mapping], changes: Iterable[Mapping], *,
               tracked: Sequence[str]) -> Scd2Result:
    tracked = list(tracked)
    history: dict[object, list[dict]] = defaultdict(list)
    for row in dimension:
        history[row["customer_id"]].append(dict(row))
    for cid, rows in history.items():
        rows.sort(key=lambda r: r["effective_from"])
        currents = [r for r in rows if r["is_current"]]
        if not currents:
            raise ValueError(f"customer {cid!r} has history but no current row")
        if len(currents) > 1:
            raise ValueError(f"customer {cid!r} has {len(currents)} current rows")
        if currents and (rows[-1] is not currents[0] or currents[0]["effective_to"] is not None):
            raise ValueError(f"customer {cid!r}: the current row must be the latest and open-ended")
        if any(r["effective_to"] is None and not r["is_current"] for r in rows):
            raise ValueError(f"customer {cid!r}: open-ended row that is not current")

    batch = []
    for idx, ch in enumerate(changes):
        if "customer_id" not in ch or ch["customer_id"] is None:
            raise ValueError(f"change without customer_id: {ch!r}")
        batch.append((_aware(ch.get("change_ts"), "change_ts"), idx, ch))
    batch.sort(key=lambda t: (t[0], t[1]))

    rejected: list[tuple[int, Rejected]] = []
    for ts, idx, ch in batch:
        attrs = dict(ch.get("attributes") or {})
        if any(a not in tracked for a in attrs):
            rejected.append((idx, Rejected(dict(ch), "unknown_attribute")))
            continue
        rows = history[ch["customer_id"]]
        cur = rows[-1] if rows and rows[-1]["is_current"] else None
        if cur is None:
            rows.append({"customer_id": ch["customer_id"], "version": 1, "effective_from": ts,
                         "effective_to": None, "is_current": True,
                         **{a: attrs.get(a) for a in tracked}})
            continue
        if ts < cur["effective_from"]:
            rejected.append((idx, Rejected(dict(ch), "out_of_order")))
            continue
        merged = {a: attrs.get(a, cur.get(a)) for a in tracked}
        if all(merged[a] == cur.get(a) for a in tracked):
            continue                                            # nothing changed: no new version
        if ts == cur["effective_from"]:
            rejected.append((idx, Rejected(dict(ch), "same_timestamp_conflict")))
            continue
        cur["effective_to"] = ts
        cur["is_current"] = False
        rows.append({"customer_id": ch["customer_id"], "version": cur["version"] + 1,
                     "effective_from": ts, "effective_to": None, "is_current": True, **merged})

    out = [r for cid in sorted(history) for r in history[cid]]
    rejected.sort(key=lambda t: t[0])
    return Scd2Result(out, [r for _, r in rejected])
