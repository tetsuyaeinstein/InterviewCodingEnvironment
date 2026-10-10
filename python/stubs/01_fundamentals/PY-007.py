"""PY-007 - Schema validation with structured row errors.

Question: python/questions/01_fundamentals/PY-007.md   (python -m lab show PY-007)
Check   : python -m lab check PY-007
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

FIELD_TYPES = ("str", "int", "decimal", "bool", "date")
UNKNOWN_FIELD_POLICIES = ("error", "ignore", "keep")


class SchemaError(ValueError):
    """The schema itself is invalid (a configuration bug, not a data problem)."""


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str                       # one of FIELD_TYPES
    required: bool = True           # key must be present
    nullable: bool = False          # None (or blank string for non-str types) allowed
    allowed: Collection[Any] | None = None   # permitted coerced values, or None for any


@dataclass(frozen=True)
class RowError:
    row_index: int                  # 0-based position in the input
    field: str | None               # None for row-level errors (not_a_mapping)
    error_code: str
    message: str


def validate_rows(rows: Iterable[Any], schema: Sequence[FieldSpec], *,
                  unknown_fields: str = "error") -> tuple[list[dict], list[RowError]]:
    """Validate and coerce rows against ``schema``; return (valid_rows, errors).

    Raises SchemaError for a bad schema and ValueError for a bad unknown_fields policy,
    before reading any row. Never raises because of row data.
    """
    raise NotImplementedError
