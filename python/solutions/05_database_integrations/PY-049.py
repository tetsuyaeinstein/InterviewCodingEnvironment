"""PY-049 reference solution: aggregate both sides to {(store, day): Decimal}, then diff the key sets."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal


@dataclass(frozen=True)
class Mismatch:
    store_id: int
    day: date
    python_total: Decimal
    sql_total: Decimal


@dataclass
class ReconciliationReport:
    matching: list[tuple[int, date]] = field(default_factory=list)
    mismatches: list[Mismatch] = field(default_factory=list)
    only_in_python: list[tuple[int, date, Decimal]] = field(default_factory=list)
    only_in_sql: list[tuple[int, date, Decimal]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.mismatches or self.only_in_python or self.only_in_sql)


SQL_TOTALS = """
SELECT store_id,
       (transaction_ts AT TIME ZONE 'UTC')::date AS day,      -- explicit UTC: independent of session TimeZone
       sum(gross_amount)                          AS total
FROM transactions
WHERE store_id = ANY(%(stores)s)
  AND transaction_status = 'COMPLETED'
  AND transaction_ts >= %(start_ts)s AND transaction_ts < %(end_ts)s
GROUP BY store_id, day
"""


def _midnight(d: date) -> datetime:
    return datetime.combine(d, time(0), tzinfo=timezone.utc)


def _python_totals(rows: Iterable[dict], stores: set[int], start: date, end: date) -> dict:
    totals: dict[tuple[int, date], Decimal] = defaultdict(Decimal)
    for row in rows:
        amount, ts = row["gross_amount"], row["transaction_ts"]
        if not isinstance(amount, Decimal):
            raise TypeError(f"gross_amount must be Decimal, got {type(amount).__name__}")
        if ts.tzinfo is None or ts.utcoffset() is None:
            raise ValueError("transaction_ts must be timezone-aware")
        if row["transaction_status"] != "COMPLETED" or row["store_id"] not in stores:
            continue
        day = ts.astimezone(timezone.utc).date()
        if start <= day < end:
            totals[(row["store_id"], day)] += amount
    return totals


def reconcile_daily_totals(conn, transactions: Iterable[dict], store_ids: Sequence[int],
                           start: date, end: date) -> ReconciliationReport:
    if not store_ids:
        raise ValueError("store_ids must not be empty")
    if start > end:
        raise ValueError("start must not be after end")
    py = _python_totals(transactions, set(store_ids), start, end)

    with conn.cursor() as cur:
        cur.execute(SQL_TOTALS, {"stores": list(store_ids), "start_ts": _midnight(start), "end_ts": _midnight(end)})
        sql_totals = {(s, d): total for s, d, total in cur.fetchall()}

    report = ReconciliationReport()
    for key in sorted(py.keys() | sql_totals.keys()):
        in_py, in_sql = key in py, key in sql_totals
        if in_py and in_sql:
            if py[key] == sql_totals[key]:
                report.matching.append(key)
            else:
                report.mismatches.append(Mismatch(key[0], key[1], py[key], sql_totals[key]))
        elif in_py:
            report.only_in_python.append((key[0], key[1], py[key]))
        else:
            report.only_in_sql.append((key[0], key[1], sql_totals[key]))
    return report
