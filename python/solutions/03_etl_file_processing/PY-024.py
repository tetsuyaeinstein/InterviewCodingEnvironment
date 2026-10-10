"""PY-024 reference solution: single pass, one small state entry per business key.

state[key] = (best_sequence, [distinct records seen at best_sequence, first-arrival order])

A higher sequence replaces the entry, an equal one is compared against the distinct list
(usually length 1), a lower one is ignored. Memory is O(keys), not O(records), and the input
can be a one-shot stream. Payloads are compared with == (they may contain lists/dicts, so we
never hash them).
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Conflict:
    key: tuple
    sequence: int
    records: tuple[dict, ...]


def _sequence(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError(f"sequence must be an integer, not {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)               # '10' > '9' numerically, not lexically
    raise ValueError(f"invalid source sequence {value!r}")


def resolve_revisions(records: Iterable[Mapping[str, object]], key_fields: Sequence[str], *,
                      sequence_field: str = "source_seq",
                      ignore_fields: Collection[str] = ()) -> tuple[list[dict], list[Conflict]]:
    ignored = set(ignore_fields)

    def payload(rec: Mapping[str, object]) -> dict:
        return {k: v for k, v in rec.items() if k not in ignored}

    state: dict[tuple, tuple[int, list[tuple[dict, dict]]]] = {}
    for rec in records:
        try:
            key = tuple(rec[f] for f in key_fields)
        except KeyError as e:
            raise ValueError(f"record without key field {e.args[0]!r}: {rec!r}") from None
        if any(v is None for v in key):
            raise ValueError(f"NULL in business key: {rec!r}")
        if sequence_field not in rec:
            raise ValueError(f"record without {sequence_field!r}: {rec!r}")
        seq = _sequence(rec[sequence_field])

        current = state.get(key)
        if current is None or seq > current[0]:
            state[key] = (seq, [(payload(rec), dict(rec))])
        elif seq == current[0]:
            p = payload(rec)
            if all(p != seen for seen, _ in current[1]):
                current[1].append((p, dict(rec)))
        # seq < best: an older revision arriving late - superseded, nothing to do

    winners: list[dict] = []
    conflicts: list[Conflict] = []
    for key in sorted(state):
        seq, distinct = state[key]
        if len(distinct) == 1:
            winners.append(distinct[0][1])
        else:
            conflicts.append(Conflict(key, seq, tuple(r for _, r in distinct)))
    return winners, conflicts
