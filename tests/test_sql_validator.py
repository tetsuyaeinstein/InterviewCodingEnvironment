"""Self-tests for SQL parsing, canonical comparison and the validator modes."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from lab import sql_validator as v
from lab.exercise_catalog import Exercise
from lab.sql_runner import is_blank, split_statements, strip_comments


# ---------------------------------------------------------------- lexing
def test_split_respects_strings_comments_and_dollar_quotes():
    text = """
    -- comment; with semicolon
    SELECT 'a;b' AS x, "we;ird" FROM t; /* block ; comment */
    SELECT $$ dollar ; quoted $$, $tag$ also ; $tag$;
    SELECT 1  -- trailing
    """
    stmts = split_statements(text)
    assert len(stmts) == 3
    assert "'a;b'" in stmts[0].text
    assert stmts[1].keyword == "SELECT" and "$tag$ also ; $tag$" in stmts[1].text
    assert stmts[2].code == "SELECT 1"


def test_blank_detection_ignores_comments_only_files():
    assert is_blank("-- just a comment\n/* and a block */\n;\n")
    assert not is_blank("-- comment\nSELECT 1")
    assert strip_comments("SELECT 1 -- x\n/* y */ + 2").split() == ["SELECT", "1", "+", "2"]


def test_statement_offset_points_into_source():
    src = "-- header\n\nSELECT 1;\n  SELECT 2"
    s1, s2 = split_statements(src)
    assert src[s1.offset:].startswith(s1.text) and s1.code == "SELECT 1"
    assert src[s2.offset:].startswith("SELECT 2")


@pytest.mark.parametrize("stmt", ["COMMIT", "begin", "SET ROLE lab_admin", "set search_path = x", "DROP SCHEMA public",
                                  "COPY t FROM PROGRAM 'x'", "DO $$ BEGIN END $$", "RESET ALL", "GRANT SELECT ON t TO x"])
def test_forbidden_statements(stmt):
    assert v.FORBIDDEN_ALWAYS.match(stmt)


@pytest.mark.parametrize("stmt", ["SELECT 1", "WITH x AS (SELECT 1) SELECT * FROM x", "INSERT INTO t VALUES (1)",
                                  "CREATE INDEX ON t (a)", "SET LOCAL enable_seqscan = off"])
def test_allowed_statements(stmt):
    assert not v.FORBIDDEN_ALWAYS.match(stmt)


# ---------------------------------------------------------------- canonical values
def test_canonical_numbers_ignore_type_and_trailing_zeros():
    assert v.canon_value(Decimal("12.50"), "number", 2) == v.canon_value(12.5, "number", 2) == "12.50"
    assert v.canon_value(3, "number", 6) == v.canon_value(Decimal("3.000"), "number", 6)
    assert v.canon_value(Decimal("0.125"), "number", 2) == "0.13"  # half-up rounding


def test_canonical_timestamps_are_utc():
    ny = timezone(timedelta(hours=-5))
    a = datetime(2025, 1, 1, 7, 0, tzinfo=ny)
    b = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert v.canon_value(a, "timestamptz", 6) == v.canon_value(b, "timestamptz", 6)
    assert v.canon_literal("2025-01-01T12:00:00Z", "timestamptz", 6) == v.canon_value(b, "timestamptz", 6)


def test_canonical_misc():
    assert v.canon_value(None, "number", 2) is None
    assert v.canon_value(date(2024, 2, 29), "date", 6) == "2024-02-29"
    assert v.canon_value({"b": 1, "a": [1, 2]}, "json", 6) == '{"a":[1,2],"b":1}'
    assert v.canon_value(timedelta(minutes=1, seconds=30), "interval", 6) == "90.000000s"
    assert v.canon_literal(True, "boolean", 6) == v.canon_value(True, "boolean", 6) == "true"


def test_type_categories():
    assert v.category("int8") == v.category("numeric") == v.category("float8") == "number"
    assert v.category("varchar") == v.category("text") == "text"
    assert v.category("timestamptz") == "timestamptz" and v.category("timestamp") == "timestamp"
    assert v.category("_int4") == "array"


# ---------------------------------------------------------------- comparison
def canon(cols, cats, rows):
    return v.Canon(cols, cats, [tuple(r) for r in rows])


def test_unordered_multiset_detects_duplicates():
    exp = canon(["id"], ["number"], [["1"], ["2"]])
    act = canon(["id"], ["number"], [["2"], ["1"], ["1"]])
    problems = v.compare(exp, act, ordered=False)
    assert problems and "1 unexpected" in problems[0] and "fan-out" in problems[0]
    assert v.compare(exp, canon(["id"], ["number"], [["2"], ["1"]]), ordered=False) == []


def test_ordered_comparison_reports_order_problem():
    exp = canon(["id"], ["number"], [["1"], ["2"]])
    act = canon(["id"], ["number"], [["2"], ["1"]])
    assert v.compare(exp, act, ordered=False) == []
    problems = v.compare(exp, act, ordered=True)
    assert problems and "wrong ORDER BY" in problems[0]


def test_column_names_and_types_are_enforced():
    exp = canon(["customer_id", "total"], ["number", "number"], [["1", "2"]])
    assert "Column names" in v.compare(exp, canon(["customer_id", "spend"], ["number", "number"], [["1", "2"]]), False)[0]
    assert "types differ" in v.compare(exp, canon(["customer_id", "total"], ["number", "text"], [["1", "2"]]), False)[0]


def test_empty_result_never_passes():
    exp = canon(["id"], ["number"], [["1"]])
    assert "0 rows" in v.compare(exp, canon(["id"], ["number"], []), False)[0]


def test_python_assertions(tmp_path, monkeypatch):
    ex = Exercise("SQL-900", "sql", "t", "01_foundations", "easy", 5, "query", True)
    yaml_text = """
assertions:
  - {name: has 3 once, present: {customer_id: 3}, count: 1}
  - {name: no 2, absent: {customer_id: 2}}
  - {name: total for 3, row: {customer_id: 3}, expect: {total: 12.5}}
  - {name: no nulls, absent: {customer_id: null}}
"""
    path = tmp_path / "SQL-900.yaml"
    path.write_text(yaml_text)
    monkeypatch.setattr(Exercise, "adversarial_path", property(lambda self: path))
    good = canon(["customer_id", "total"], ["number", "number"],
                 [[v.canon_value(3, "number", 6), v.canon_value(Decimal("12.50"), "number", 6)]])
    assert v.python_assertions(ex, good) == []
    bad = canon(["customer_id", "total"], ["number", "number"],
                [["2.000000", "1.000000"], ["3.000000", "1.000000"], ["3.000000", "1.000000"], [None, "0.000000"]])
    failures = v.python_assertions(ex, bad)
    assert len(failures) == 4


# ---------------------------------------------------------------- database-backed modes
def _exercise(ex_id):
    from lab import exercise_catalog
    try:
        return exercise_catalog.get(ex_id)
    except exercise_catalog.CatalogError:
        pytest.skip(f"{ex_id} not in catalog")


def test_query_mode_end_to_end(seeded_conn, tmp_path):
    ex = _exercise("SQL-021")
    assert v.check(ex, ex.stub_path).status == v.NOT_ATTEMPTED
    assert v.check(ex, ex.solution_path()).status == v.PASSED
    wrong = tmp_path / "wrong.sql"
    wrong.write_text("SELECT customer_id FROM customers WHERE customer_id IN (3, 4)")
    res = v.check(ex, wrong)
    assert res.status == v.FAILED and any("missing" in m for m in res.messages)
    syntax = tmp_path / "syntax.sql"
    syntax.write_text("SELEC 1")
    res = v.check(ex, syntax)
    assert res.status == v.ERROR and "syntax error" in res.messages[0] and "line 1" in res.messages[0]


def test_query_mode_is_read_only(seeded_conn, tmp_path):
    ex = _exercise("SQL-021")
    attempt = tmp_path / "write.sql"
    attempt.write_text("WITH d AS (DELETE FROM transactions RETURNING customer_id) SELECT customer_id FROM d")
    res = v.check(ex, attempt)
    assert res.status == v.ERROR
    assert seeded_conn.execute("SELECT count(*) FROM transactions").fetchone()[0] > 0


def test_mutation_mode_is_sandboxed_and_rolled_back(seeded_conn, tmp_path):
    ex = _exercise("SQL-046")
    before = seeded_conn.execute("SELECT count(*), sum(source_lsn) FROM cdc_transaction_events").fetchone()
    assert v.check(ex, ex.solution_path()).status == v.PASSED
    naive = tmp_path / "naive.sql"
    naive.write_text("INSERT INTO txn_current SELECT * FROM stg_txn_batch ON CONFLICT DO NOTHING")
    assert v.check(ex, naive).status == v.FAILED
    hostile = tmp_path / "hostile.sql"
    hostile.write_text("DELETE FROM public.cdc_transaction_events")
    assert v.check(ex, hostile).status == v.ERROR
    seeded_conn.rollback()
    after = seeded_conn.execute("SELECT count(*), sum(source_lsn) FROM cdc_transaction_events").fetchone()
    leftovers = seeded_conn.execute("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'lab_sb_%'").fetchone()[0]
    assert before == after and leftovers == 0
