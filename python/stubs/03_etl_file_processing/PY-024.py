"""PY-024 - Resolve revisions and conflicts for duplicate business keys.

Question: python/questions/03_etl_file_processing/PY-024.md   (python -m lab show PY-024)
Check   : python -m lab check PY-024
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Conflict:
    key: tuple                  # business key values, in key_fields order
    sequence: int               # the (highest) sequence at which the records disagree
    records: tuple[dict, ...]   # one record per distinct payload, in first-arrival order


def resolve_revisions(records: Iterable[Mapping[str, object]], key_fields: Sequence[str], *,
                      sequence_field: str = "source_seq",
                      ignore_fields: Collection[str] = ()) -> tuple[list[dict], list[Conflict]]:
    """Return (current_records, conflicts), both sorted by business key.

    The current record of a key is the one with the highest source sequence (not the last to
    arrive). Identical duplicates collapse; different payloads at that highest sequence are a
    Conflict and the key is left out of current_records.
    """
    raise NotImplementedError
