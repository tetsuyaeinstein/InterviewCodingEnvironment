"""PY-043 - Batched, idempotent upserts with a stale-version guard.

Question: python/questions/05_database_integrations/PY-043.md   (python -m lab show PY-043)
Check   : python -m lab check PY-043          (needs: docker compose up -d + lab db seed)
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class LoadResult:
    inserted: int
    updated: int
    skipped: int


def load_batch(conn, rows: Iterable[dict], *, table: str = "txn_load", batch_size: int = 500) -> LoadResult:
    """Upsert ``rows`` (keys: business_key, amount, status, seq) into ``table``.

    Idempotent and all-or-nothing; see the question for the exact semantics of the counts.
    """
    raise NotImplementedError
