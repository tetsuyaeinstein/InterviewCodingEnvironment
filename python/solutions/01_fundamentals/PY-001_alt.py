"""PY-001 alternative: an insertion-ordered dict used as both the index and the output.

``dict.setdefault`` only inserts the first value for a key, and dicts preserve insertion order,
so the dict *is* the de-duplicated, ordered result. Records without an id get a unique
sentinel key so they are never merged with anything.

Trade-off vs. the set + generator approach: the dict holds every surviving record until the
end (nothing can be emitted early), but switching to "last occurrence wins" is a one-line change
(``index[key] = record``; note the key keeps its *first* position, which is often exactly what a
"latest version, original order" requirement wants).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def dedupe_transactions(records: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    index: dict[Any, Mapping[str, Any]] = {}
    for record in records:
        tid = record.get("transaction_id")
        # object() is unique and only equal to itself, so id-less records never collide.
        # The tuple tag keeps real ids from ever colliding with the sentinel keys.
        key = ("no-id", object()) if tid is None else ("id", tid)
        index.setdefault(key, record)
    return list(index.values())
