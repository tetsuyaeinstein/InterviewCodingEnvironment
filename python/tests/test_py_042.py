"""Tests for PY-042 (requires the seeded lab database; skipped -> INCOMPLETE otherwise)."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from _loader import load

mod = load("PY-042")
pytestmark = pytest.mark.requires_postgres

KEYS = {"transaction_id", "store_id", "transaction_ts", "gross_amount", "transaction_status"}


class _SpyCursor:
    """Counts rows handed to the caller and records cursor configuration."""

    def __init__(self, cur, spy, name):
        object.__setattr__(self, "_cur", cur)
        object.__setattr__(self, "_spy", spy)
        object.__setattr__(self, "name", name)

    def __enter__(self):
        self._cur.__enter__()
        return self

    def __exit__(self, *exc):
        return self._cur.__exit__(*exc)

    def __iter__(self):
        for row in self._cur:
            self._spy.pulled += 1
            yield row

    def fetchone(self):
        row = self._cur.fetchone()
        self._spy.pulled += 1 if row is not None else 0
        return row

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size is not None else self._cur.fetchmany()
        self._spy.fetch_sizes.append(size)
        self._spy.pulled += len(rows)
        return rows

    def fetchall(self):
        rows = self._cur.fetchall()
        self._spy.pulled += len(rows)
        return rows

    def __setattr__(self, key, value):
        if key == "itersize":
            self._spy.itersizes.append(value)
        setattr(self._cur, key, value)

    def __getattr__(self, key):
        return getattr(self._cur, key)


class SpyConn:
    def __init__(self, conn):
        self._conn = conn
        self.cursor_names = []
        self.pulled = 0
        self.fetch_sizes = []
        self.itersizes = []

    def cursor(self, name=None, *a, **kw):
        self.cursor_names.append(name)
        cur = self._conn.cursor(name, *a, **kw) if name is not None else self._conn.cursor(*a, **kw)
        return _SpyCursor(cur, self, name)

    def __getattr__(self, key):
        return getattr(self._conn, key)


def expected(conn, start, end):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT transaction_id, store_id, transaction_ts, gross_amount, transaction_status "
            "FROM transactions WHERE transaction_ts >= %s AND transaction_ts < %s "
            "ORDER BY transaction_ts, transaction_id",
            (datetime(start.year, start.month, start.day, tzinfo=timezone.utc),
             datetime(end.year, end.month, end.day, tzinfo=timezone.utc)))
        rows = cur.fetchall()
    conn.rollback()
    return rows


def open_cursors(conn):
    return conn.execute("SELECT count(*) FROM pg_cursors").fetchone()[0]


def test_rows_match_a_plain_query_in_order(pg_readonly):
    start, end = date(2025, 10, 1), date(2025, 11, 1)
    got = list(mod.stream_transactions(pg_readonly, start, end, batch_size=50))
    assert got == expected(pg_readonly, start, end)
    assert len(got) > 100


def test_row_shape_and_types(pg_readonly):
    got = list(mod.stream_transactions(pg_readonly, date(2025, 10, 5), date(2025, 10, 6), batch_size=10))
    assert got and all(set(r) == KEYS for r in got)
    r = next(r for r in got if r["transaction_id"] == 2602)
    assert r["transaction_ts"] == datetime(2025, 10, 5, 18, tzinfo=timezone.utc)
    assert r["gross_amount"] == Decimal("10.00") and isinstance(r["gross_amount"], Decimal)
    ids = [r["transaction_id"] for r in got]
    assert ids.index(2602) + 1 == ids.index(2603)  # equal timestamps: ordered by id


@pytest.mark.parametrize("batch_size", [1, 7, 100_000])
def test_batch_size_does_not_change_the_result(pg_readonly, batch_size):
    start, end = date(2025, 10, 5), date(2025, 10, 8)
    assert list(mod.stream_transactions(pg_readonly, start, end, batch_size=batch_size)) == \
        expected(pg_readonly, start, end)


def test_half_open_range_and_empty_range(pg_readonly):
    # customer 34 has a purchase at exactly 2025-10-03 00:00:00 UTC
    ids = [r["transaction_id"] for r in mod.stream_transactions(pg_readonly, date(2025, 10, 3), date(2025, 10, 4))]
    assert 3402 in ids
    ids = [r["transaction_id"] for r in mod.stream_transactions(pg_readonly, date(2025, 10, 2), date(2025, 10, 3))]
    assert 3402 not in ids and 3501 in ids  # 3501 is at 2025-10-02 23:59:59
    assert list(mod.stream_transactions(pg_readonly, date(2025, 10, 3), date(2025, 10, 3))) == []
    assert list(mod.stream_transactions(pg_readonly, date(2030, 1, 1), date(2030, 2, 1))) == []


def test_invalid_arguments(pg_readonly):
    with pytest.raises(ValueError):
        next(iter(mod.stream_transactions(pg_readonly, date(2025, 10, 1), date(2025, 10, 2), batch_size=0)))
    with pytest.raises(ValueError):
        next(iter(mod.stream_transactions(pg_readonly, date(2025, 10, 2), date(2025, 10, 1))))


def test_uses_a_server_side_cursor_and_does_not_prefetch_everything(pg_readonly):
    spy = SpyConn(pg_readonly)
    gen = iter(mod.stream_transactions(spy, date(2025, 1, 1), date(2026, 1, 1), batch_size=25))
    first = next(gen)
    assert first["transaction_id"]
    assert any(n for n in spy.cursor_names), "no named (server-side) cursor was created"
    assert spy.pulled <= 25, f"{spy.pulled} rows were pulled before the second row was requested"
    assert 25 in spy.itersizes or 25 in spy.fetch_sizes, "batch_size is not used as the fetch size"
    gen.close()


def test_rows_are_pulled_incrementally(pg_readonly):
    spy = SpyConn(pg_readonly)
    gen = iter(mod.stream_transactions(spy, date(2025, 1, 1), date(2026, 1, 1), batch_size=40))
    for _ in range(100):
        next(gen)
    assert spy.pulled <= 100 + 40
    gen.close()


def test_early_close_releases_cursor_and_transaction(pg_readonly):
    assert pg_readonly.info.transaction_status == TransactionStatus.IDLE
    gen = iter(mod.stream_transactions(pg_readonly, date(2025, 1, 1), date(2026, 1, 1), batch_size=10))
    next(gen)
    assert open_cursors(pg_readonly) == 1  # the stream is really server-side
    gen.close()
    assert pg_readonly.info.transaction_status == TransactionStatus.IDLE
    assert open_cursors(pg_readonly) == 0
    pg_readonly.rollback()


def test_exhaustion_leaves_connection_idle_and_reusable(pg_readonly):
    rows = list(mod.stream_transactions(pg_readonly, date(2025, 10, 5), date(2025, 10, 6), batch_size=3))
    assert rows
    assert pg_readonly.info.transaction_status == TransactionStatus.IDLE
    assert pg_readonly.execute("SELECT 1").fetchone() == (1,)
    pg_readonly.rollback()


def test_consecutive_streams_on_one_connection(pg_readonly):
    start, end = date(2025, 10, 5), date(2025, 10, 7)
    first = list(mod.stream_transactions(pg_readonly, start, end, batch_size=2))
    second = list(mod.stream_transactions(pg_readonly, start, end, batch_size=5))
    assert first == second and len(first) > 3
    assert open_cursors(pg_readonly) == 0
    pg_readonly.rollback()
