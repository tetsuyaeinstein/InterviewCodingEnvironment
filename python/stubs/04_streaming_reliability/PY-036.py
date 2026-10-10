"""PY-036 - Apply customer SCD2 changes to a dimension, in order, without overlapping intervals.

Question: python/questions/04_streaming_reliability/PY-036.md   (python -m lab show PY-036)
Check   : python -m lab check PY-036
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Rejected:
    change: dict       # the change exactly as it was received
    reason: str        # "out_of_order" | "same_timestamp_conflict" | "unknown_attribute"


@dataclass(frozen=True)
class Scd2Result:
    rows: list[dict]           # the full new dimension (history + current)
    rejected: list[Rejected]   # in the order the changes were received


def apply_scd2(dimension: Iterable[Mapping], changes: Iterable[Mapping], *,
               tracked: Sequence[str]) -> Scd2Result:
    """Return the new dimension after applying ``changes`` and the rejected changes.

    Dimension row keys: customer_id, version, effective_from, effective_to (None = open),
    is_current, plus one key per tracked attribute. Change keys: customer_id, change_ts
    (timezone-aware datetime) and attributes (a partial dict of tracked attributes).
    The inputs are never mutated. See the question for the full rules.
    """
    raise NotImplementedError
