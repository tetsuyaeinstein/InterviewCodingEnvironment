"""PY-041 alternative: compose the WHERE clause dynamically with psycopg.sql.

Useful when filters are genuinely optional and numerous (search screens). Identifiers and SQL
fragments come from code, never from users; values still travel as positional parameters.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timezone

from psycopg import sql
from psycopg.rows import dict_row


def fetch_customer_transactions(conn, customer_id: int, start: date, end: date,
                                statuses: Sequence[str] | None = None) -> list[dict]:
    conditions = [sql.SQL("customer_id = %s"), sql.SQL("transaction_ts >= %s"), sql.SQL("transaction_ts < %s")]
    params: list = [customer_id,
                    datetime.combine(start, time(0), tzinfo=timezone.utc),
                    datetime.combine(end, time(0), tzinfo=timezone.utc)]
    if statuses is not None:
        conditions.append(sql.SQL("transaction_status = ANY (%s)"))
        params.append(list(statuses))
    query = sql.SQL(
        "SELECT transaction_id, transaction_ts, gross_amount, transaction_status "
        "FROM transactions WHERE {where} ORDER BY transaction_ts, transaction_id"
    ).format(where=sql.SQL(" AND ").join(conditions))
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()
