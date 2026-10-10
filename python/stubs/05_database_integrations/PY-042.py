"""PY-042 - Stream a large Postgres result set with bounded memory.

Question: python/questions/05_database_integrations/PY-042.md   (python -m lab show PY-042)
Check   : python -m lab check PY-042          (needs: docker compose up -d + lab db seed)
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import date


def stream_transactions(conn, start: date, end: date, batch_size: int = 1000) -> Iterator[dict]:
    """Yield one dict per transaction with UTC business date in [start, end).

    Keys: transaction_id, store_id, transaction_ts, gross_amount, transaction_status.
    Order: transaction_ts, transaction_id. Rows must be fetched from the server lazily,
    at most ``batch_size`` per round trip. Raise ValueError for batch_size < 1 or start > end.
    """
    raise NotImplementedError
