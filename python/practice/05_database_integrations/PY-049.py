"""PY-049 - Reconcile Python-computed daily totals against PostgreSQL aggregates.

Question: python/questions/05_database_integrations/PY-049.md   (python -m lab show PY-049)
Check   : python -m lab check PY-049          (needs: docker compose up -d + lab db seed)
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Mismatch:
    store_id: int
    day: date
    python_total: Decimal
    sql_total: Decimal


@dataclass
class ReconciliationReport:
    matching: list[tuple[int, date]] = field(default_factory=list)                 # (store_id, day), sorted
    mismatches: list[Mismatch] = field(default_factory=list)                       # sorted by (store_id, day)
    only_in_python: list[tuple[int, date, Decimal]] = field(default_factory=list)  # (store_id, day, python_total)
    only_in_sql: list[tuple[int, date, Decimal]] = field(default_factory=list)     # (store_id, day, sql_total)

    @property
    def ok(self) -> bool:
        raise NotImplementedError


def reconcile_daily_totals(conn, transactions: Iterable[dict], store_ids: Sequence[int],
                           start: date, end: date) -> ReconciliationReport:
    """Compare daily COMPLETED totals per store computed in Python with the database's.

    ``transactions`` rows: transaction_id, store_id, transaction_ts (aware datetime), gross_amount
    (Decimal), transaction_status. Window: UTC business date in [start, end).
    """
    raise NotImplementedError
