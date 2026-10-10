"""PY-001 - De-duplicate transaction records (first occurrence wins).

Question: python/questions/01_fundamentals/PY-001.md   (python -m lab show PY-001)
Check   : python -m lab check PY-001
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def dedupe_transactions(records: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return the records with re-sent duplicates removed.

    Duplicates share an equal ``transaction_id``; the first occurrence wins and input order is
    preserved. Records with a missing or None ``transaction_id`` are always kept.
    The original record objects are returned; the input is not mutated.
    """
    raise NotImplementedError
