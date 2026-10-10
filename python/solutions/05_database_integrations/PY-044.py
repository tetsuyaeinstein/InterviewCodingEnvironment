"""PY-044 reference solution: row-value comparison (ts, id) > (cursor_ts, cursor_id), LIMIT page_size + 1."""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from psycopg.rows import dict_row

Cursor = tuple[datetime, int]
MAX_PAGE_SIZE = 1000

QUERY = """
SELECT transaction_id, customer_id, transaction_ts, gross_amount, transaction_status
FROM transactions
WHERE store_id = %(store_id)s
  AND transaction_ts >= %(start_ts)s
  AND transaction_ts <  %(end_ts)s
  AND (%(use_cursor)s = false OR (transaction_ts, transaction_id) > (%(cur_ts)s, %(cur_id)s))
ORDER BY transaction_ts, transaction_id
LIMIT %(limit)s
"""


def _midnight(d: date) -> datetime:
    return datetime.combine(d, time(0), tzinfo=timezone.utc)


def _check_cursor(cursor) -> tuple[datetime, int]:
    if (not isinstance(cursor, tuple) or len(cursor) != 2
            or not isinstance(cursor[0], datetime) or cursor[0].tzinfo is None
            or isinstance(cursor[1], bool) or not isinstance(cursor[1], int)):
        raise ValueError("cursor must be (aware datetime, int)")
    return cursor


def fetch_page(conn, store_id: int, start: date, end: date, cursor: Cursor | None = None,
               page_size: int = 100) -> tuple[list[dict], Cursor | None]:
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be an int in 1..{MAX_PAGE_SIZE}")
    if cursor is not None:
        cur_ts, cur_id = _check_cursor(cursor)
    else:
        cur_ts, cur_id = _midnight(start), 0  # placeholders; ignored by use_cursor = false
    params = {
        "store_id": store_id, "start_ts": _midnight(start), "end_ts": _midnight(end),
        "use_cursor": cursor is not None, "cur_ts": cur_ts, "cur_id": cur_id,
        "limit": page_size + 1,  # the extra row tells us whether another page exists
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(QUERY, params)
        rows = cur.fetchall()
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    next_cursor = (rows[-1]["transaction_ts"], rows[-1]["transaction_id"]) if has_more else None
    return rows, next_cursor
