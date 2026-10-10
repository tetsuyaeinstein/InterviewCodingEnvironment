"""PY-025 - Single-pass column profile for data-quality checks.

Question: python/questions/03_etl_file_processing/PY-025.md   (python -m lab show PY-025)
Check   : python -m lab check PY-025
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class ColumnProfile:
    name: str
    count: int                          # rows seen (every row, including NULL / missing)
    null_count: int
    distinct_count: int                 # distinct non-NULL values
    min: object = None
    max: object = None
    mean: Decimal | None = None
    top_values: list[tuple[object, int]] = field(default_factory=list)   # up to 3 (value, count)
    inferred_type: str = "null"         # null|bool|int|decimal|str|date|datetime|mixed
    types_seen: tuple[str, ...] = ()    # sorted type names of the non-NULL values


def profile_columns(rows: Iterable[Mapping[str, object]]) -> dict[str, ColumnProfile]:
    """Profile every column of ``rows`` in a single pass (``rows`` may be a one-shot iterator).

    Returns column name -> ColumnProfile, columns in first-seen order.
    """
    raise NotImplementedError
