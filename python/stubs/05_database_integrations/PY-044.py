"""PY-044 - Keyset pagination with a stable composite cursor.

Question: python/questions/05_database_integrations/PY-044.md   (python -m lab show PY-044)
Check   : python -m lab check PY-044          (needs: docker compose up -d + lab db seed)
"""
from __future__ import annotations

from datetime import date, datetime

# An opaque-to-the-caller position: (transaction_ts, transaction_id) of the last row already served.
Cursor = tuple[datetime, int]

MAX_PAGE_SIZE = 1000


def fetch_page(conn, store_id: int, start: date, end: date, cursor: Cursor | None = None,
               page_size: int = 100) -> tuple[list[dict], Cursor | None]:
    """Return (rows, next_cursor): one page of the store's transactions after ``cursor``.

    Rows: transaction_id, customer_id, transaction_ts, gross_amount, transaction_status,
    ordered by (transaction_ts, transaction_id). next_cursor is None on the last page.
    """
    raise NotImplementedError
