"""PY-041 reference solution: one static SQL text, all values as named bind parameters.

The optional status filter is expressed in SQL (`%(statuses)s IS NULL OR ... = ANY(...)`), so
the statement text never changes. That is friendly to server-side prepared statements and
trivially injection-proof.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timezone

from psycopg.rows import dict_row

QUERY = """
SELECT transaction_id, transaction_ts, gross_amount, transaction_status
FROM transactions
WHERE customer_id = %(customer_id)s
  AND transaction_ts >= %(start_ts)s
  AND transaction_ts <  %(end_ts)s
  AND (%(statuses)s::text[] IS NULL OR transaction_status = ANY (%(statuses)s::text[]))
ORDER BY transaction_ts, transaction_id
"""


def _utc_midnight(d: date) -> datetime:
    return datetime.combine(d, time(0), tzinfo=timezone.utc)


def fetch_customer_transactions(conn, customer_id: int, start: date, end: date,
                                statuses: Sequence[str] | None = None) -> list[dict]:
    params = {
        "customer_id": customer_id,
        "start_ts": _utc_midnight(start),   # half-open UTC range keeps the predicate sargable
        "end_ts": _utc_midnight(end),
        "statuses": None if statuses is None else list(statuses),
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(QUERY, params)
        return cur.fetchall()
