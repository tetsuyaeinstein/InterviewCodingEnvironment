"""PY-042 reference solution: named cursor inside conn.transaction(), generator with cleanup."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date, datetime, time, timezone

from psycopg.rows import dict_row

QUERY = """
SELECT transaction_id, store_id, transaction_ts, gross_amount, transaction_status
FROM transactions
WHERE transaction_ts >= %(start_ts)s AND transaction_ts < %(end_ts)s
ORDER BY transaction_ts, transaction_id
"""


def _utc_midnight(d: date) -> datetime:
    return datetime.combine(d, time(0), tzinfo=timezone.utc)


def stream_transactions(conn, start: date, end: date, batch_size: int = 1000) -> Iterator[dict]:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    if start > end:
        raise ValueError("start must not be after end")
    return _stream(conn, start, end, batch_size)


def _stream(conn, start, end, batch_size):
    params = {"start_ts": _utc_midnight(start), "end_ts": _utc_midnight(end)}
    # Unique name: two concurrent streams on one connection must not collide.
    name = f"stream_txn_{uuid.uuid4().hex}"
    # The transaction block ends (COMMIT on exhaustion, ROLLBACK on early close/exception), and the
    # `with cursor` block CLOSEs the server-side cursor either way.
    with conn.transaction():
        with conn.cursor(name=name, row_factory=dict_row) as cur:
            cur.itersize = batch_size
            cur.execute(QUERY, params)
            yield from cur
