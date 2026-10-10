"""PY-041 - Parameterized customer transaction lookup with psycopg.

Question: python/questions/05_database_integrations/PY-041.md   (python -m lab show PY-041)
Check   : python -m lab check PY-041          (needs: docker compose up -d + lab db seed)
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date


def fetch_customer_transactions(conn, customer_id: int, start: date, end: date,
                                statuses: Sequence[str] | None = None) -> list[dict]:
    """Return the customer's transactions with UTC business date in [start, end).

    Keys per row: transaction_id, transaction_ts, gross_amount, transaction_status.
    Ordered by transaction_ts, transaction_id. All inputs must be bind parameters.
    """
    raise NotImplementedError
