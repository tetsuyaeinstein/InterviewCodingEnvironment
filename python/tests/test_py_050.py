"""Tests for PY-050 (requires the seeded lab database; everything happens in a sandbox schema)."""
import json
from datetime import date
from decimal import Decimal

import psycopg
import pytest

from _loader import load

mod = load("PY-050")
pytestmark = pytest.mark.requires_postgres

D = Decimal


def rec(tid=1, store=2, ts="2025-03-03T10:00:00+00:00", amount="10.00", status="COMPLETED", seq=1, **extra):
    d = {"transaction_id": tid, "store_id": store, "transaction_ts": ts, "amount": amount,
         "status": status, "sequence": seq}
    d.update(extra)
    return {k: v for k, v in d.items() if v is not ...}


def nd(*records):
    return [r if isinstance(r, str) else json.dumps(r) for r in records]


def staged(conn):
    conn.rollback()
    out = {r[0]: r[1:] for r in conn.execute(
        "SELECT transaction_id, store_id, transaction_ts, amount, status, sequence FROM stg_txn")}
    conn.rollback()     # leave no transaction open: the code under test must commit its own work
    return out


def reasons(report):
    return [(r.line, r.reason) for r in report.rejected]


def test_happy_path_report_and_staging(pg_sandbox):
    lines = nd(rec(1, amount="10.50"), rec(2, amount="4.25", seq=3), rec(3, status="PENDING", amount="99.00"),
               rec(4, ts="2025-03-04T01:00:00Z", amount="1.00"))
    rep = mod.run_pipeline(pg_sandbox, lines)
    assert (rep.rows_read, rep.rejected, rep.duplicates_dropped, rep.upserted, rep.unchanged) == (4, [], 0, 4, 0)
    assert rep.daily_summary == {date(2025, 3, 3): D("14.75"), date(2025, 3, 4): D("1.00")}
    assert all(isinstance(v, Decimal) for v in rep.daily_summary.values())
    assert rep.reconciliation_ok is True
    rows = staged(pg_sandbox)
    assert set(rows) == {1, 2, 3, 4}
    assert rows[2][2:] == (D("4.25"), "COMPLETED", 3)
    assert rows[3][3] == "PENDING"          # non-completed rows are staged but not summed


def test_table_is_created_in_the_current_schema_with_a_primary_key(pg_sandbox):
    mod.run_pipeline(pg_sandbox, nd(rec()))
    schema = pg_sandbox.execute("SELECT current_schema()").fetchone()[0]
    assert pg_sandbox.execute("SELECT to_regclass(%s)", (f'"{schema}".stg_txn',)).fetchone()[0] is not None
    assert pg_sandbox.execute("SELECT count(*) FROM pg_tables WHERE tablename = 'stg_txn' AND schemaname = 'public'").fetchone()[0] == 0
    pk = pg_sandbox.execute(
        "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE i.indrelid = to_regclass('stg_txn') AND i.indisprimary").fetchall()
    assert pk == [("transaction_id",)]
    pg_sandbox.rollback()


def test_rerunning_the_same_file_is_idempotent(pg_sandbox):
    lines = nd(rec(1), rec(2, amount="5.00"), rec(3, amount="7.25"))
    first = mod.run_pipeline(pg_sandbox, lines)
    before = staged(pg_sandbox)
    second = mod.run_pipeline(pg_sandbox, lines)
    assert (first.upserted, first.unchanged) == (3, 0)
    assert (second.upserted, second.unchanged) == (0, 3)
    assert staged(pg_sandbox) == before
    assert second.daily_summary == first.daily_summary and second.reconciliation_ok


def test_newer_sequence_updates_and_older_sequence_is_ignored(pg_sandbox):
    mod.run_pipeline(pg_sandbox, nd(rec(1, amount="10.00", seq=5)))
    rep = mod.run_pipeline(pg_sandbox, nd(rec(1, amount="12.00", seq=6, status="CANCELLED")))
    assert (rep.upserted, rep.unchanged) == (1, 0)
    assert staged(pg_sandbox)[1][2:] == (D("12.00"), "CANCELLED", 6)
    assert rep.daily_summary == {} and rep.reconciliation_ok     # cancelled: nothing to sum on either side

    rep = mod.run_pipeline(pg_sandbox, nd(rec(1, amount="3.00", seq=2)))      # an old file arrives late
    assert (rep.upserted, rep.unchanged) == (0, 1)
    assert staged(pg_sandbox)[1][2:] == (D("12.00"), "CANCELLED", 6)
    assert rep.reconciliation_ok is False                          # the table does not reflect this run's input


@pytest.mark.parametrize("bad,reason", [
    ("{not json", "invalid_json"),
    ("[1, 2, 3]", "not_an_object"),
    ('"text"', "not_an_object"),
    (rec(tid=...), "missing_field:transaction_id"),
    (rec(store=...), "missing_field:store_id"),
    (rec(ts=...), "missing_field:transaction_ts"),
    (rec(amount=...), "missing_field:amount"),
    (rec(status=...), "missing_field:status"),
    (rec(seq=...), "missing_field:sequence"),
    (rec(tid="7"), "invalid_transaction_id"),
    (rec(tid=0), "invalid_transaction_id"),
    (rec(tid=True), "invalid_transaction_id"),
    (rec(tid=2**63), "invalid_transaction_id"),
    (rec(store=0), "invalid_store_id"),
    (rec(store=2**31), "invalid_store_id"),
    (rec(ts="2025-03-03T10:00:00"), "naive_timestamp"),
    (rec(ts="2025-03-03"), "naive_timestamp"),
    (rec(ts="yesterday"), "invalid_timestamp"),
    (rec(ts=1741000000), "invalid_timestamp"),
    (rec(amount="1.234"), "invalid_amount"),
    (rec(amount="-1.00"), "invalid_amount"),
    (rec(amount="abc"), "invalid_amount"),
    (rec(amount="NaN"), "invalid_amount"),
    (rec(amount=None), "invalid_amount"),
    (rec(amount=True), "invalid_amount"),
    (rec(amount="10000000000.00"), "invalid_amount"),
    (rec(status="completed"), "invalid_status"),
    (rec(status="COMPLETED'; DROP TABLE stg_txn; --"), "invalid_status"),
    (rec(seq=-1), "invalid_sequence"),
    (rec(seq="1"), "invalid_sequence"),
    (rec(seq=1.5), "invalid_sequence"),
])
def test_invalid_lines_are_rejected_with_a_reason_code(pg_sandbox, bad, reason):
    rep = mod.run_pipeline(pg_sandbox, nd(rec(tid=100), bad, rec(tid=101)))
    assert reasons(rep) == [(2, reason)]
    assert (rep.rows_read, rep.upserted) == (3, 2)
    assert set(staged(pg_sandbox)) == {100, 101}


def test_first_failing_check_wins(pg_sandbox):
    both = rec(tid="x", amount="-5", status="nope")
    missing_and_bad = {"transaction_id": "x", "store_id": 1}
    rep = mod.run_pipeline(pg_sandbox, nd(both, missing_and_bad))
    assert reasons(rep) == [(1, "invalid_transaction_id"), (2, "missing_field:transaction_ts")]


def test_blank_lines_are_skipped_but_counted_for_numbering(pg_sandbox):
    lines = ["", json.dumps(rec(1)), "   \n", "oops", "\n", json.dumps(rec(2))]
    rep = mod.run_pipeline(pg_sandbox, lines)
    assert rep.rows_read == 3 and reasons(rep) == [(4, "invalid_json")]
    assert rep.upserted == 2


def test_lines_with_trailing_newlines_and_extra_fields(pg_sandbox):
    lines = [json.dumps(rec(1, note="ignored", extra={"a": 1})) + "\n"]
    rep = mod.run_pipeline(pg_sandbox, lines)
    assert rep.rejected == [] and rep.upserted == 1


def test_dedupe_highest_sequence_wins_regardless_of_position(pg_sandbox):
    lines = nd(rec(1, amount="1.00", seq=3), rec(1, amount="9.00", seq=7), rec(1, amount="2.00", seq=5),
               rec(2, amount="4.00", seq=1), rec(2, amount="4.00", seq=1))      # exact repeat
    rep = mod.run_pipeline(pg_sandbox, lines)
    assert rep.rows_read == 5 and rep.duplicates_dropped == 3 and rep.upserted == 2
    assert staged(pg_sandbox)[1][2:] == (D("9.00"), "COMPLETED", 7)
    assert rep.daily_summary == {date(2025, 3, 3): D("13.00")}
    assert rep.rows_read == len(rep.rejected) + rep.duplicates_dropped + rep.upserted + rep.unchanged


def test_equal_sequence_later_line_wins(pg_sandbox):
    mod.run_pipeline(pg_sandbox, nd(rec(1, amount="1.00", seq=4), rec(1, amount="2.00", seq=4)))
    assert staged(pg_sandbox)[1][2] == D("2.00")


def test_invalid_rows_do_not_take_part_in_deduplication(pg_sandbox):
    lines = nd(rec(1, amount="1.00", seq=1), rec(1, amount="-1", seq=99))
    rep = mod.run_pipeline(pg_sandbox, lines)
    assert rep.duplicates_dropped == 0 and reasons(rep) == [(2, "invalid_amount")]
    assert staged(pg_sandbox)[1][2:] == (D("1.00"), "COMPLETED", 1)


def test_amounts_stay_exact_decimals(pg_sandbox):
    lines = ['{"transaction_id": 1, "store_id": 1, "transaction_ts": "2025-03-03T00:00:00Z", "amount": 0.1, "status": "COMPLETED", "sequence": 1}',
             '{"transaction_id": 2, "store_id": 1, "transaction_ts": "2025-03-03T00:00:00Z", "amount": "0.20", "status": "COMPLETED", "sequence": 1}',
             '{"transaction_id": 3, "store_id": 1, "transaction_ts": "2025-03-03T00:00:00Z", "amount": 20, "status": "COMPLETED", "sequence": 1}',
             '{"transaction_id": 4, "store_id": 1, "transaction_ts": "2025-03-03T00:00:00Z", "amount": 0.3, "status": "COMPLETED", "sequence": 1}']
    rep = mod.run_pipeline(pg_sandbox, lines)
    assert rep.rejected == []
    assert rep.daily_summary == {date(2025, 3, 3): D("20.60")}
    assert staged(pg_sandbox)[1][2] == D("0.10") and staged(pg_sandbox)[3][2] == D("20.00")
    assert rep.reconciliation_ok


def test_offsets_are_converted_to_utc_days(pg_sandbox):
    lines = nd(rec(1, ts="2025-03-02T23:30:00-07:00", amount="10.00"),     # 06:30 UTC on 03-03
               rec(2, ts="2025-03-03T23:30:00-07:00", amount="1.00"),      # 06:30 UTC on 03-04
               rec(3, ts="2025-03-04T05:30:00+09:00", amount="2.00"),      # 20:30 UTC on 03-03
               rec(4, ts="2025-03-03T00:00:00Z", amount="3.00"))
    rep = mod.run_pipeline(pg_sandbox, lines)
    assert rep.daily_summary == {date(2025, 3, 3): D("15.00"), date(2025, 3, 4): D("1.00")}
    from datetime import datetime, timezone
    assert staged(pg_sandbox)[1][1] == datetime(2025, 3, 3, 6, 30, tzinfo=timezone.utc)
    assert rep.reconciliation_ok


def test_summary_only_counts_completed_winners(pg_sandbox):
    lines = nd(rec(1, amount="10.00", seq=1, status="COMPLETED"),
               rec(1, amount="10.00", seq=2, status="CANCELLED"),     # the cancellation supersedes
               rec(2, amount="5.00", status="DECLINED"), rec(3, amount="6.00", status="PENDING"),
               rec(4, amount="7.00"))
    rep = mod.run_pipeline(pg_sandbox, lines)
    assert rep.daily_summary == {date(2025, 3, 3): D("7.00")}
    assert rep.reconciliation_ok


def test_empty_input_still_creates_the_table(pg_sandbox):
    rep = mod.run_pipeline(pg_sandbox, [])
    assert (rep.rows_read, rep.rejected, rep.duplicates_dropped, rep.upserted, rep.unchanged) == (0, [], 0, 0, 0)
    assert rep.daily_summary == {} and rep.reconciliation_ok is True
    assert staged(pg_sandbox) == {}


def test_only_rejected_lines(pg_sandbox):
    rep = mod.run_pipeline(pg_sandbox, ["x", "y"])
    assert rep.rows_read == 2 and len(rep.rejected) == 2 and rep.upserted == 0 and rep.daily_summary == {}


def test_database_failure_rolls_back_the_whole_run(pg_sandbox):
    pg_sandbox.execute("""CREATE TABLE stg_txn (
        transaction_id bigint PRIMARY KEY, store_id integer NOT NULL, transaction_ts timestamptz NOT NULL,
        amount numeric(12,2) NOT NULL CHECK (amount <> 13.13), status text NOT NULL, sequence integer NOT NULL)""")
    pg_sandbox.commit()
    lines = nd(*[rec(i, amount="1.00") for i in range(1, 7)], rec(7, amount="13.13"), rec(8))
    with pytest.raises(psycopg.errors.CheckViolation):
        mod.run_pipeline(pg_sandbox, lines, batch_size=2)
    pg_sandbox.rollback()
    assert staged(pg_sandbox) == {}               # earlier batches were rolled back too


def test_precreated_table_is_used_as_is(pg_sandbox):
    pg_sandbox.execute("""CREATE TABLE stg_txn (
        transaction_id bigint PRIMARY KEY, store_id integer NOT NULL, transaction_ts timestamptz NOT NULL,
        amount numeric(12,2) NOT NULL, status text NOT NULL, sequence integer NOT NULL, note text DEFAULT 'pre')""")
    pg_sandbox.commit()
    mod.run_pipeline(pg_sandbox, nd(rec(1)))
    assert pg_sandbox.execute("SELECT note FROM stg_txn").fetchone() == ("pre",)
    pg_sandbox.rollback()


def test_batching_with_many_rows(pg_sandbox):
    lines = nd(*[rec(i, amount="0.10", ts=f"2025-03-{1 + i % 28:02d}T12:00:00Z") for i in range(1, 2501)])
    rep = mod.run_pipeline(pg_sandbox, iter(lines), batch_size=300)
    assert rep.upserted == 2500 and rep.reconciliation_ok
    assert sum(rep.daily_summary.values()) == D("250.00")
    assert len(staged(pg_sandbox)) == 2500


def test_strict_mode_raises_and_leaves_nothing_behind(pg_sandbox):
    mod.run_pipeline(pg_sandbox, nd(rec(1, amount="10.00", seq=9)))
    with pytest.raises(mod.ReconciliationError):
        mod.run_pipeline(pg_sandbox, nd(rec(1, amount="1.00", seq=2), rec(2, amount="5.00")), strict=True)
    pg_sandbox.rollback()
    assert set(staged(pg_sandbox)) == {1}          # row 2 of the failed run was rolled back
    assert staged(pg_sandbox)[1][2] == D("10.00")
    ok = mod.run_pipeline(pg_sandbox, nd(rec(2, amount="5.00")), strict=True)
    assert ok.reconciliation_ok and set(staged(pg_sandbox)) == {1, 2}


def test_invalid_batch_size(pg_sandbox):
    with pytest.raises(ValueError):
        mod.run_pipeline(pg_sandbox, nd(rec()), batch_size=0)
