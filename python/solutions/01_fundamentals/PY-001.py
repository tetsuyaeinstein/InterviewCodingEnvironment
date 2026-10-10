"""PY-001 reference solution: single pass with a set of seen ids (streaming core).

The work happens in a generator, so the same logic can be used lazily on an unbounded feed;
the public function just materialises it. Memory is O(distinct ids), not O(records).
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any


def _iter_unique(records: Iterable[Mapping[str, Any]]) -> Iterator[Mapping[str, Any]]:
    seen: set[Any] = set()
    for record in records:
        tid = record.get("transaction_id")      # missing key and None are treated alike
        if tid is None:
            yield record                        # cannot de-duplicate: keep, in position
            continue
        if tid in seen:                         # O(1) average membership test
            continue                            # later copy: first occurrence already emitted
        seen.add(tid)
        yield record


def dedupe_transactions(records: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return list(_iter_unique(records))
