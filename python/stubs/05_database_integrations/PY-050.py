"""PY-050 - Mini project: validate, dedupe, stage, summarise and reconcile a transaction feed.

Question: python/questions/05_database_integrations/PY-050.md   (python -m lab show PY-050)
Check   : python -m lab check PY-050          (needs: docker compose up -d + lab db seed)
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ALLOWED_STATUSES = frozenset({"COMPLETED", "PENDING", "CANCELLED", "DECLINED"})


@dataclass(frozen=True)
class Rejection:
    line: int          # 1-based line number in the input (blank lines count)
    reason: str        # one of the reason codes listed in the question


@dataclass
class RunReport:
    rows_read: int = 0                 # non-blank input lines
    rejected: list[Rejection] = field(default_factory=list)
    duplicates_dropped: int = 0        # valid rows superseded by another valid row of the same run
    upserted: int = 0                  # staging rows inserted or changed by this run
    unchanged: int = 0                 # winning rows that did not change the staging table
    daily_summary: dict[date, Decimal] = field(default_factory=dict)   # UTC day -> completed total
    reconciliation_ok: bool = True


class ReconciliationError(Exception):
    """Raised in strict mode when the staged totals do not match the Python summary."""


def run_pipeline(conn, lines: Iterable[str], *, batch_size: int = 500, strict: bool = False) -> RunReport:
    """Ingest NDJSON ``lines`` into stg_txn (current schema) and return the run report."""
    raise NotImplementedError
