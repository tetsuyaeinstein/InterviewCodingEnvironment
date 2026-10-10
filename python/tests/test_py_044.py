"""Tests for PY-044 (requires the seeded lab database; skipped -> INCOMPLETE otherwise)."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from psycopg.rows import dict_row

from _loader import load

mod = load("PY-044")
pytestmark = pytest.mark.requires_postgres

KEYS = {"transaction_id", "customer_id", "transaction_ts", "gross_amount", "transaction_status"}
ALL = (date(2024, 1, 1), date(2026, 1, 1))


def full_scope(conn, store_id, start, end):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT transaction_id, customer_id, transaction_ts, gross_amount, transaction_status "
            "FROM transactions WHERE store_id = %s AND transaction_ts >= %s AND transaction_ts < %s "
            "ORDER BY transaction_ts, transaction_id",
            (store_id, datetime(start.year, start.month, start.day, tzinfo=timezone.utc),
             datetime(end.year, end.month, end.day, tzinfo=timezone.utc)))
        rows = cur.fetchall()
    conn.rollback()
    return rows


def walk(conn, store_id, start, end, page_size):
    pages, cursor = [], None
    while True:
        rows, cursor = mod.fetch_page(conn, store_id, start, end, cursor=cursor, page_size=page_size)
        pages.append(rows)
        if cursor is None:
            return pages
        assert len(pages) < 5000, "cursor does not advance"


def ids(rows):
    return [r["transaction_id"] for r in rows]


@pytest.mark.parametrize("page_size", [1, 2, 7, 50])
def test_pages_concatenate_to_the_full_ordered_result(pg_readonly, page_size):
    start, end = date(2025, 8, 1), date(2025, 12, 31)
    pages = walk(pg_readonly, 1, start, end, page_size)
    flat = [r for p in pages for r in p]
    assert flat == full_scope(pg_readonly, 1, start, end)
    assert all(len(p) == page_size for p in pages[:-1]) and 1 <= len(pages[-1]) <= page_size


def test_first_page_shape_and_types(pg_readonly):
    scope = full_scope(pg_readonly, 1, date(2025, 10, 5), date(2025, 10, 6))
    rows, nxt = mod.fetch_page(pg_readonly, 1, date(2025, 10, 5), date(2025, 10, 6), page_size=2)
    assert [set(r) for r in rows] == [KEYS, KEYS]
    assert ids(rows) == ids(scope[:2])
    assert all(isinstance(r["gross_amount"], Decimal) and r["transaction_ts"].tzinfo is not None for r in rows)
    assert nxt == (rows[1]["transaction_ts"], rows[1]["transaction_id"])
    fixture = next(r for r in scope if r["transaction_id"] == 2602)       # fixture row, any seed profile
    assert fixture["transaction_ts"] == datetime(2025, 10, 5, 18, tzinfo=timezone.utc)
    assert fixture["gross_amount"] == Decimal("10.00")


def test_equal_timestamps_across_a_page_boundary(pg_readonly):
    # 2602 and 2603 share 2025-10-05 18:00 UTC; page_size=1 puts the page boundary between them.
    start, end = date(2025, 10, 5), date(2025, 10, 7)
    scope = full_scope(pg_readonly, 1, start, end)
    order = ids(scope)
    i = order.index(2602)
    assert order[i + 1] == 2603 and scope[i]["transaction_ts"] == scope[i + 1]["transaction_ts"]
    cursor = None if i == 0 else (scope[i - 1]["transaction_ts"], scope[i - 1]["transaction_id"])
    for expected in scope[i:i + 3]:
        rows, cursor = mod.fetch_page(pg_readonly, 1, start, end, cursor=cursor, page_size=1)
        assert ids(rows) == [expected["transaction_id"]]
        assert cursor == (expected["transaction_ts"], expected["transaction_id"])


def test_large_tie_group_smaller_than_page_size(pg_readonly):
    # customer 64: six rows at exactly 2025-12-15 05:00 UTC in store 1
    start, end = date(2025, 12, 15), date(2025, 12, 16)
    expected = full_scope(pg_readonly, 1, start, end)
    tie = [r for r in expected if r["transaction_ts"] == datetime(2025, 12, 15, 5, tzinfo=timezone.utc)]
    assert len(tie) == 6
    for size in (1, 2, 4, 6):
        flat = [r for p in walk(pg_readonly, 1, start, end, size) for r in p]
        assert ids(flat) == ids(expected), f"page_size={size}"


def test_guest_rows_with_null_customer(pg_readonly):
    pages = walk(pg_readonly, 1, date(2025, 8, 10), date(2025, 8, 11), 3)
    flat = [r for p in pages for r in p]
    guests = [r for r in flat if r["customer_id"] is None]
    assert ids(guests) == [9801, 9802]
    assert ids(flat) == ids(full_scope(pg_readonly, 1, date(2025, 8, 10), date(2025, 8, 11)))


def test_exact_multiple_has_no_trailing_empty_page(pg_readonly):
    start, end = date(2025, 8, 10), date(2025, 8, 11)      # 7 rows in scope
    n = len(full_scope(pg_readonly, 1, start, end))
    rows, nxt = mod.fetch_page(pg_readonly, 1, start, end, page_size=n)
    assert len(rows) == n and nxt is None
    pages = walk(pg_readonly, 1, start, end, 1)
    assert len(pages) == n and all(len(p) == 1 for p in pages)


def test_empty_scope_and_cursor_past_the_end(pg_readonly):
    assert mod.fetch_page(pg_readonly, 1, date(2030, 1, 1), date(2030, 2, 1)) == ([], None)
    assert mod.fetch_page(pg_readonly, 999, *ALL) == ([], None)
    last = full_scope(pg_readonly, 1, date(2025, 8, 10), date(2025, 8, 11))[-1]
    rows, nxt = mod.fetch_page(pg_readonly, 1, date(2025, 8, 10), date(2025, 8, 11),
                               cursor=(last["transaction_ts"], last["transaction_id"]))
    assert rows == [] and nxt is None


def test_cursor_between_rows_and_scope_bounds(pg_readonly):
    # the cursor row does not have to exist; the id breaks the tie at 2025-10-05 18:00
    ts = datetime(2025, 10, 5, 18, tzinfo=timezone.utc)
    start, end = date(2025, 10, 5), date(2025, 10, 6)
    scope = full_scope(pg_readonly, 1, start, end)
    expected = [r for r in scope if (r["transaction_ts"], r["transaction_id"]) > (ts, 2602)][:10]
    rows, _ = mod.fetch_page(pg_readonly, 1, start, end, cursor=(ts, 2602), page_size=10)
    assert ids(rows) == ids(expected) and ids(rows)[0] == 2603
    # `end` is exclusive: 2604 is at 2025-10-06 12:00
    rows, _ = mod.fetch_page(pg_readonly, 1, start, end, cursor=(ts, 0), page_size=10)
    assert 2604 not in ids(rows)


def test_whole_store_walk_has_no_duplicates_or_gaps(pg_readonly):
    pages = walk(pg_readonly, 1, *ALL, 100)
    flat = ids([r for p in pages for r in p])
    assert flat == ids(full_scope(pg_readonly, 1, *ALL))
    assert len(flat) == len(set(flat)) > 1000


def test_validation(pg_readonly):
    for bad in (0, -1, 1001, 10.5, None):
        with pytest.raises(ValueError):
            mod.fetch_page(pg_readonly, 1, *ALL, page_size=bad)
    naive = (datetime(2025, 10, 5, 18), 1)
    for bad in (naive, (1, 2, 3), "abc", (datetime(2025, 10, 5, tzinfo=timezone.utc), "7")):
        with pytest.raises(ValueError):
            mod.fetch_page(pg_readonly, 1, *ALL, cursor=bad)


class _Spy:
    def __init__(self, conn):
        self._conn, self.texts = conn, []

    def cursor(self, *a, **kw):
        return _SpyCur(self._conn.cursor(*a, **kw), self)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _SpyCur:
    def __init__(self, cur, spy):
        self._cur, self._spy = cur, spy

    def __enter__(self):
        self._cur.__enter__()
        return self

    def __exit__(self, *exc):
        return self._cur.__exit__(*exc)

    def execute(self, query, params=None, **kw):
        text = query if isinstance(query, str) else query.as_string(self._spy._conn)
        self._spy.texts.append((text, params))
        return self._cur.execute(query, params, **kw)

    def __getattr__(self, name):
        return getattr(self._cur, name)


def test_sql_has_no_offset_and_binds_values(pg_readonly):
    spy = _Spy(pg_readonly)
    cursor = (datetime(2025, 10, 5, 18, tzinfo=timezone.utc), 2602)
    mod.fetch_page(spy, 1, date(2025, 10, 1), date(2025, 11, 1), cursor=cursor, page_size=5)
    assert spy.texts
    for text, params in spy.texts:
        assert "offset" not in text.lower()
        assert "limit" in text.lower()
        assert params, "values must be bound"
        assert "2602" not in text and "2025" not in text
