"""Tests for PY-049 (requires the seeded lab database; read-only)."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from psycopg.rows import dict_row

from _loader import load

mod = load("PY-049")
pytestmark = pytest.mark.requires_postgres

YEAR = (date(2025, 1, 1), date(2026, 1, 1))
D = Decimal


def db_rows(conn, stores, start, end):
    """All statuses, straight from the table, as the 'Python side' would have received them."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT transaction_id, store_id, transaction_ts, gross_amount, transaction_status "
            "FROM transactions WHERE store_id = ANY(%s) AND transaction_ts >= %s AND transaction_ts < %s "
            "ORDER BY transaction_id",
            (list(stores), datetime(start.year, start.month, start.day, tzinfo=timezone.utc),
             datetime(end.year, end.month, end.day, tzinfo=timezone.utc)))
        rows = cur.fetchall()
    conn.rollback()
    return rows


def test_identical_data_reconciles_for_fixture_stores(pg_readonly):
    rows = db_rows(pg_readonly, [4, 5], *YEAR)
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4, 5], *YEAR)
    assert rep.ok is True
    assert rep.mismatches == [] and rep.only_in_python == [] and rep.only_in_sql == []
    # store 4: 11 completed days of 25.00; store 5: 5 days in November + 1 in December
    assert len(rep.matching) == 11 + 6
    assert rep.matching == sorted(rep.matching)
    assert (4, date(2025, 3, 15)) in rep.matching      # the day with COMPLETED + CANCELLED rows
    assert (4, date(2025, 2, 14)) in rep.matching      # COMPLETED + PENDING
    assert (5, date(2025, 11, 21)) not in rep.matching  # only a CANCELLED row


def test_generator_input_is_accepted(pg_readonly):
    rows = db_rows(pg_readonly, [5], *YEAR)
    assert mod.reconcile_daily_totals(pg_readonly, (r for r in rows), [5], *YEAR).ok


def test_missing_day_in_python_is_reported_as_sql_only(pg_readonly):
    rows = [r for r in db_rows(pg_readonly, [4, 5], *YEAR)
            if not (r["store_id"] == 5 and r["transaction_ts"].date() == date(2025, 11, 10))]
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4, 5], *YEAR)
    assert rep.ok is False
    assert rep.only_in_sql == [(5, date(2025, 11, 10), D("66.00"))]
    assert rep.mismatches == [] and rep.only_in_python == []
    assert len(rep.matching) == 16


def test_off_by_one_cent_is_a_mismatch_with_both_values(pg_readonly):
    rows = db_rows(pg_readonly, [4, 5], *YEAR)
    for r in rows:
        if r["transaction_id"] == 6001:                 # store 5, 78.00
            r["gross_amount"] = D("78.01")
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4, 5], *YEAR)
    assert rep.mismatches == [mod.Mismatch(5, date(2025, 11, 3), D("78.01"), D("78.00"))]
    assert not rep.ok and (5, date(2025, 11, 3)) not in rep.matching


def test_extra_day_in_python_is_reported(pg_readonly):
    rows = db_rows(pg_readonly, [4], *YEAR)
    rows.append({"transaction_id": 999_001, "store_id": 4, "transaction_ts": datetime(2025, 8, 8, 12, tzinfo=timezone.utc),
                 "gross_amount": D("12.50"), "transaction_status": "COMPLETED"})
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4], *YEAR)
    assert rep.only_in_python == [(4, date(2025, 8, 8), D("12.50"))]
    assert not rep.ok and len(rep.matching) == 11


def test_duplicate_python_row_is_a_discrepancy_not_deduplicated(pg_readonly):
    rows = db_rows(pg_readonly, [4], *YEAR)
    rows.append(dict(next(r for r in rows if r["transaction_id"] == 6201)))
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4], *YEAR)
    assert rep.mismatches == [mod.Mismatch(4, date(2025, 1, 5), D("50.00"), D("25.00"))]


def test_status_filter_on_both_sides(pg_readonly):
    rows = db_rows(pg_readonly, [4], *YEAR)
    for r in rows:
        if r["transaction_id"] == 6201:
            r["transaction_status"] = "PENDING"          # python thinks it was not completed
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4], *YEAR)
    assert rep.only_in_sql == [(4, date(2025, 1, 5), D("25.00"))]


def test_rows_outside_stores_window_are_ignored(pg_readonly):
    rows = db_rows(pg_readonly, [4, 5], *YEAR) + db_rows(pg_readonly, [1], date(2025, 10, 1), date(2025, 10, 8))
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4, 5], *YEAR)
    assert rep.ok
    rep = mod.reconcile_daily_totals(pg_readonly, db_rows(pg_readonly, [4], *YEAR), [4], date(2025, 3, 1), date(2025, 3, 16))
    assert rep.ok and [d for _, d in rep.matching] == [date(2025, 3, 1), date(2025, 3, 2), date(2025, 3, 3), date(2025, 3, 15)]


def test_window_end_is_exclusive(pg_readonly):
    rows = db_rows(pg_readonly, [4], *YEAR)
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4], date(2025, 3, 1), date(2025, 3, 15))
    assert (4, date(2025, 3, 15)) not in rep.matching and rep.ok
    assert mod.reconcile_daily_totals(pg_readonly, rows, [4], date(2025, 3, 1), date(2025, 3, 1)).matching == []


def test_timestamps_in_other_offsets_are_bucketed_by_utc_day(pg_readonly):
    phoenix = timezone(timedelta(hours=-7))
    rows = db_rows(pg_readonly, [1, 2, 3], date(2025, 10, 1), date(2025, 11, 1))
    shifted = [dict(r, transaction_ts=r["transaction_ts"].astimezone(phoenix)) for r in rows]
    # sanity: some rows really do change their local date
    assert any(r["transaction_ts"].date() != s["transaction_ts"].date() for r, s in zip(rows, shifted))
    rep = mod.reconcile_daily_totals(pg_readonly, shifted, [1, 2, 3], date(2025, 10, 1), date(2025, 11, 1))
    assert rep.ok and len(rep.matching) > 30


def test_sql_bucketing_does_not_depend_on_the_session_time_zone(pg_readonly):
    rows = db_rows(pg_readonly, [1, 2, 3], date(2025, 10, 1), date(2025, 11, 1))
    pg_readonly.execute("SET TIME ZONE 'Pacific/Auckland'")
    try:
        rep = mod.reconcile_daily_totals(pg_readonly, rows, [1, 2, 3], date(2025, 10, 1), date(2025, 11, 1))
    finally:
        pg_readonly.rollback()
    assert rep.ok, f"session time zone leaked into the result: {rep.mismatches[:2]} {rep.only_in_sql[:2]}"


def test_python_total_is_exact_decimal(pg_readonly):
    rows = [{"transaction_id": i, "store_id": 4, "transaction_ts": datetime(2030, 1, 1, 10, i, tzinfo=timezone.utc),
             "gross_amount": D("0.10"), "transaction_status": "COMPLETED"} for i in range(3)]
    rows.append({"transaction_id": 9, "store_id": 4, "transaction_ts": datetime(2030, 1, 1, 11, tzinfo=timezone.utc),
                 "gross_amount": D("0.20"), "transaction_status": "COMPLETED"})
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4], date(2030, 1, 1), date(2030, 1, 2))
    assert rep.only_in_python == [(4, date(2030, 1, 1), D("0.50"))]
    assert isinstance(rep.only_in_python[0][2], Decimal)


def test_zero_total_day_is_still_one_sided(pg_readonly):
    rows = [{"transaction_id": 1, "store_id": 4, "transaction_ts": datetime(2030, 1, 1, 10, tzinfo=timezone.utc),
             "gross_amount": D("0.00"), "transaction_status": "COMPLETED"}]
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [4], date(2030, 1, 1), date(2030, 1, 2))
    assert rep.only_in_python == [(4, date(2030, 1, 1), D("0.00"))] and not rep.ok


def test_input_validation(pg_readonly):
    good = {"transaction_id": 1, "store_id": 4, "transaction_ts": datetime(2025, 1, 5, 15, tzinfo=timezone.utc),
            "gross_amount": D("25.00"), "transaction_status": "COMPLETED"}
    with pytest.raises(TypeError):
        mod.reconcile_daily_totals(pg_readonly, [dict(good, gross_amount=25.0)], [4], *YEAR)
    with pytest.raises(ValueError):
        mod.reconcile_daily_totals(pg_readonly, [dict(good, transaction_ts=datetime(2025, 1, 5, 15))], [4], *YEAR)
    with pytest.raises(ValueError):
        mod.reconcile_daily_totals(pg_readonly, [good], [], *YEAR)
    with pytest.raises(ValueError):
        mod.reconcile_daily_totals(pg_readonly, [good], [4], date(2026, 1, 1), date(2025, 1, 1))


def test_larger_generated_store_reconciles(pg_readonly):
    rows = db_rows(pg_readonly, [1, 2, 3, 6], date(2025, 6, 1), date(2025, 9, 1))
    assert len(rows) > 500
    rep = mod.reconcile_daily_totals(pg_readonly, rows, [1, 2, 3, 6], date(2025, 6, 1), date(2025, 9, 1))
    assert rep.ok and len(rep.matching) > 100
