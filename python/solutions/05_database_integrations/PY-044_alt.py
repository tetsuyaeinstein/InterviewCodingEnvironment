"""PY-044 alternative: OR-expanded keyset predicate, built dynamically with psycopg.sql.

(ts > c_ts) OR (ts = c_ts AND id > c_id) is the portable spelling of the row-value comparison
(SQL Server and older engines have no row constructors). Two separate range conditions are also
the shape some planners handle better when the tuple comparison is not index-matched.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from psycopg import sql
from psycopg.rows import dict_row

Cursor = tuple[datetime, int]
MAX_PAGE_SIZE = 1000


def _midnight(d: date) -> datetime:
    return datetime.combine(d, time(0), tzinfo=timezone.utc)


def fetch_page(conn, store_id: int, start: date, end: date, cursor: Cursor | None = None,
               page_size: int = 100) -> tuple[list[dict], Cursor | None]:
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be an int in 1..{MAX_PAGE_SIZE}")
    where = [sql.SQL("store_id = %s"), sql.SQL("transaction_ts >= %s"), sql.SQL("transaction_ts < %s")]
    params: list = [store_id, _midnight(start), _midnight(end)]
    if cursor is not None:
        if (not isinstance(cursor, tuple) or len(cursor) != 2 or not isinstance(cursor[0], datetime)
                or cursor[0].tzinfo is None or isinstance(cursor[1], bool) or not isinstance(cursor[1], int)):
            raise ValueError("cursor must be (aware datetime, int)")
        where.append(sql.SQL("(transaction_ts > %s OR (transaction_ts = %s AND transaction_id > %s))"))
        params += [cursor[0], cursor[0], cursor[1]]
    query = sql.SQL(
        "SELECT transaction_id, customer_id, transaction_ts, gross_amount, transaction_status "
        "FROM transactions WHERE {w} ORDER BY transaction_ts, transaction_id LIMIT %s"
    ).format(w=sql.SQL(" AND ").join(where))
    params.append(page_size + 1)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    more = len(rows) > page_size
    rows = rows[:page_size]
    return rows, ((rows[-1]["transaction_ts"], rows[-1]["transaction_id"]) if more else None)
