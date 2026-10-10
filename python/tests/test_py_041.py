"""Tests for PY-041 (requires the seeded lab database; skipped -> INCOMPLETE otherwise)."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-041")
pytestmark = pytest.mark.requires_postgres


class _SpyCursor:
    def __init__(self, cur, calls, conn):
        self._cur, self._calls, self._conn = cur, calls, conn

    def execute(self, query, params=None, **kw):
        self._calls.append((query, params))
        return self._cur.execute(query, params, **kw)

    def __enter__(self):
        self._cur.__enter__()
        return self

    def __exit__(self, *exc):
        return self._cur.__exit__(*exc)

    def __iter__(self):
        return iter(self._cur)

    def __getattr__(self, name):
        return getattr(self._cur, name)


class SpyConn:
    """Wraps a psycopg connection and records every (query, params) sent."""

    def __init__(self, conn):
        self._conn, self.calls = conn, []

    def execute(self, query, params=None, **kw):
        self.calls.append((query, params))
        return self._conn.execute(query, params, **kw)

    def cursor(self, *a, **kw):
        return _SpyCursor(self._conn.cursor(*a, **kw), self.calls, self._conn)

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def query_texts(self):
        out = []
        for q, _ in self.calls:
            out.append(q if isinstance(q, str) else q.as_string(self._conn) if hasattr(q, "as_string") else str(q))
        return out


def ids(rows):
    return [r["transaction_id"] for r in rows]


def test_returns_rows_in_deterministic_order(pg_readonly):
    rows = mod.fetch_customer_transactions(pg_readonly, 26, date(2025, 10, 1), date(2025, 11, 1))
    assert ids(rows) == [2602, 2603, 2604]


def test_row_shape_and_types(pg_readonly):
    rows = mod.fetch_customer_transactions(pg_readonly, 26, date(2025, 10, 1), date(2025, 11, 1))
    assert set(rows[0]) == {"transaction_id", "transaction_ts", "gross_amount", "transaction_status"}
    assert rows[0]["transaction_ts"] == datetime(2025, 10, 5, 18, tzinfo=timezone.utc)
    assert rows[0]["gross_amount"] == Decimal("10.00") and isinstance(rows[0]["gross_amount"], Decimal)


def test_status_filter(pg_readonly):
    rows = mod.fetch_customer_transactions(pg_readonly, 26, date(2025, 10, 1), date(2025, 11, 1), ["COMPLETED"])
    assert ids(rows) == [2602, 2603]
    assert mod.fetch_customer_transactions(pg_readonly, 26, date(2025, 10, 1), date(2025, 11, 1), ["PENDING"])[0]["transaction_id"] == 2604


def test_empty_status_list_returns_nothing(pg_readonly):
    assert mod.fetch_customer_transactions(pg_readonly, 26, date(2025, 1, 1), date(2026, 1, 1), []) == []


def test_half_open_date_range(pg_readonly):
    # customer 34 has a purchase at exactly 2025-10-03 00:00:00 UTC
    assert ids(mod.fetch_customer_transactions(pg_readonly, 34, date(2025, 10, 3), date(2025, 10, 4))) == [3402]
    assert mod.fetch_customer_transactions(pg_readonly, 34, date(2025, 10, 2), date(2025, 10, 3)) == []
    # customer 35 purchased at 2025-10-02 23:59:59 UTC: belongs to 10-02 only
    assert ids(mod.fetch_customer_transactions(pg_readonly, 35, date(2025, 10, 2), date(2025, 10, 3))) == [3501]


def test_hostile_status_value_matches_nothing(pg_readonly):
    rows = mod.fetch_customer_transactions(pg_readonly, 26, date(2025, 1, 1), date(2026, 1, 1),
                                           ["COMPLETED' OR '1'='1"])
    assert rows == []


def test_non_integer_customer_id_cannot_widen_the_query(pg_readonly):
    try:
        rows = mod.fetch_customer_transactions(pg_readonly, "26 OR 1=1", date(2025, 1, 1), date(2026, 1, 1))
    except NotImplementedError:
        raise
    except Exception:  # rejected by the driver/database: the safe outcome
        pg_readonly.rollback()
        return
    assert all(r["transaction_id"] in (2601, 2602, 2603, 2604) for r in rows), "query was widened by input"


def test_values_are_sent_as_bind_parameters(pg_readonly):
    spy = SpyConn(pg_readonly)
    mod.fetch_customer_transactions(spy, 26, date(2025, 10, 1), date(2025, 11, 1), ["COMPLETED"])
    assert spy.calls, "no query was executed through the given connection"
    for text, (q, params) in zip(spy.query_texts(), spy.calls):
        assert params, "query executed without parameters"
        assert "COMPLETED" not in text and "2025-10" not in text and "26" not in text.replace("%s", ""), \
            f"user values were interpolated into the SQL text: {text!r}"
