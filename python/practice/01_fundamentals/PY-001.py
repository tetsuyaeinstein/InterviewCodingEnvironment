"""PY-001 - De-duplicate transaction records (first occurrence wins).

Question: python/questions/01_fundamentals/PY-001.md   (python -m lab show PY-001)
Check   : python -m lab check PY-001
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Iterator
from typing import Any


def __iter_records(records: Iterable[Mapping[str, Any]]) -> Iterator[Mapping[str, Any]]:
    seen: set[Any] = set()

    for dict in records:
        id = dict.get("transaction_id")
        if id is None:
            yield dict
            continue
        if id not in seen:
            seen.add(id)
            yield dict


def dedupe_transactions(records: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return the records with re-sent duplicates removed.

    Duplicates share an equal ``transaction_id``; the first occurrence wins and input order is
    preserved. Records with a missing or None ``transaction_id`` are always kept.
    The original record objects are returned; the input is not mutated.
    """
    # raise NotImplementedError

    # return list(__iter_records(records))

    seen = set()
    deduped = []

    for item in records:
        key = item.get("transaction_id")
        if key is None:
            deduped.append(item)
            continue

        if key not in seen:
            # print(key)
            seen.add(key)
            deduped.append(item)

    return deduped