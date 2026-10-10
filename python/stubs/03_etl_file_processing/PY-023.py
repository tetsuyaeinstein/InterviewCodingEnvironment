"""PY-023 - Normalise messy dates, numbers and nulls to a canonical schema.

Question: python/questions/03_etl_file_processing/PY-023.md   (python -m lab show PY-023)
Check   : python -m lab check PY-023
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

# Column kinds
DATE = "date"
TIMESTAMP = "timestamp"
DECIMAL = "decimal"
INT = "int"
STR = "str"

# Strings that mean NULL (compared case-insensitively after stripping whitespace)
NULL_TOKENS = frozenset({"", "null", "n/a"})

# FieldError.reason values
NULL_NOT_ALLOWED = "null_not_allowed"
INVALID_DATE = "invalid_date"
INVALID_TIMESTAMP = "invalid_timestamp"
NAIVE_TIMESTAMP = "naive_timestamp"
INVALID_DECIMAL = "invalid_decimal"
INVALID_INT = "invalid_int"


@dataclass(frozen=True)
class Column:
    name: str
    kind: str              # DATE | TIMESTAMP | DECIMAL | INT | STR
    nullable: bool = True


@dataclass(frozen=True)
class FieldError:
    row_index: int         # 0-based index of the input row
    column: str
    value: str | None      # the original input value (None if the key was absent / None)
    reason: str            # one of the reason constants above


def normalise_rows(rows: Iterable[Mapping[str, str | None]], schema: Sequence[Column], *,
                   slash_date_order: str) -> tuple[list[dict], list[FieldError]]:
    """Convert raw string rows to the canonical schema.

    Returns (normalised_rows, errors): one output dict per input row containing exactly the
    schema columns (failed fields are None) and one FieldError per failed field.
    ``slash_date_order`` must be "MDY" or "DMY" and decides how 'A/B/YYYY' dates are read.
    """
    raise NotImplementedError
