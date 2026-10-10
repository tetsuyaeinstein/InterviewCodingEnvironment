"""PY-022 - NDJSON reader with a quarantine for bad lines.

Question: python/questions/03_etl_file_processing/PY-022.md   (python -m lab show PY-022)
Check   : python -m lab check PY-022
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass

# Allowed values of Rejected.reason
INVALID_JSON = "invalid_json"
NOT_AN_OBJECT = "not_an_object"
DUPLICATE_KEY = "duplicate_key"
MISSING_KEYS = "missing_keys"


@dataclass(frozen=True)
class Rejected:
    line_number: int      # 1-based physical line number in the input
    raw: str              # the line without its trailing line terminator
    reason: str           # one of the constants above
    detail: str = ""      # human-readable detail (for MISSING_KEYS: the missing key names)


def read_ndjson(lines: Iterable[str], required_keys: Collection[str],
                quarantine: list[Rejected]) -> Iterator[dict]:
    """Lazily yield valid JSON-object records from newline-delimited JSON ``lines``.

    Bad lines are appended to ``quarantine`` (as Rejected) and processing continues.
    Blank lines are skipped. Numbers with a fraction/exponent become Decimal.
    """
    raise NotImplementedError
