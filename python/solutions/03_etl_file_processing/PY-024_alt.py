"""PY-024 alternative: decorate, sort by (key, sequence, arrival), then groupby key.

Each key's group ends with its highest-sequence records, already in arrival order, so the
winner/conflict decision only looks at the tail of the group.

Trade-offs versus the single-pass dict:
  * O(n log n) time and O(n) memory here (sorted() materialises everything), versus O(n) time
    and O(keys) memory for the dict;
  * BUT the sort+group shape is the one that scales past RAM: replace sorted() with an external
    merge sort (PY-029) or let the engine do it (Spark sortWithinPartitions / SQL
    ROW_NUMBER() OVER (PARTITION BY key ORDER BY seq DESC)), and the grouping step then needs
    memory for one key's group only;
  * output order falls out of the sort for free.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import groupby
from operator import itemgetter


@dataclass(frozen=True)
class Conflict:
    key: tuple
    sequence: int
    records: tuple[dict, ...]


def _sequence(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise ValueError(f"invalid source sequence {value!r}")


def resolve_revisions(records: Iterable[Mapping[str, object]], key_fields: Sequence[str], *,
                      sequence_field: str = "source_seq",
                      ignore_fields: Collection[str] = ()) -> tuple[list[dict], list[Conflict]]:
    ignored = set(ignore_fields)
    decorated = []
    for arrival, rec in enumerate(records):
        if any(f not in rec or rec[f] is None for f in key_fields):
            raise ValueError(f"missing or NULL business key: {rec!r}")
        if sequence_field not in rec:
            raise ValueError(f"record without {sequence_field!r}: {rec!r}")
        decorated.append((tuple(rec[f] for f in key_fields), _sequence(rec[sequence_field]), arrival, dict(rec)))
    decorated.sort(key=itemgetter(0, 1, 2))

    winners: list[dict] = []
    conflicts: list[Conflict] = []
    for key, group in groupby(decorated, key=itemgetter(0)):
        group = list(group)
        top_seq = group[-1][1]
        distinct: list[tuple[dict, dict]] = []
        for _, seq, _, rec in group:
            if seq != top_seq:
                continue
            p = {k: v for k, v in rec.items() if k not in ignored}
            if all(p != seen for seen, _ in distinct):
                distinct.append((p, rec))
        if len(distinct) == 1:
            winners.append(distinct[0][1])
        else:
            conflicts.append(Conflict(key, top_seq, tuple(r for _, r in distinct)))
    return winners, conflicts
