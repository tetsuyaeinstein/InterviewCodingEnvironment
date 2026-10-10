"""PY-008 - In-memory inner and left join with SQL semantics.

Question: python/questions/01_fundamentals/PY-008.md   (python -m lab show PY-008)
Check   : python -m lab check PY-008
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def join_records(left: Iterable[Mapping[str, Any]], right: Iterable[Mapping[str, Any]], on: str, *,
                 how: str = "inner", right_suffix: str = "_right") -> list[dict[str, Any]]:
    """Join two collections of dict rows on field ``on`` ("inner" or "left").

    Missing/None keys never match. Duplicate keys fan out (many-to-many). Right fields whose
    name exists in the left row get ``right_suffix``; a resulting name clash -> ValueError.
    Output follows left order, then right order. Bad how/right_suffix -> ValueError.
    """
    raise NotImplementedError
