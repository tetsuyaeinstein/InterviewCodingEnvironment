"""Tests for PY-022 (imports your practice file by default; see _loader.py)."""
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-022")


def run(lines, required=("id",)):
    q = []
    records = list(mod.read_ndjson(lines, required, q))
    return records, q


def reasons(q):
    return [(r.line_number, r.reason) for r in q]


def test_fixture_file_crlf_bom_and_every_reject_reason(fixtures_dir):
    q = []
    with open(fixtures_dir / "PY-022" / "events.ndjson", encoding="utf-8", newline="") as f:
        records = list(mod.read_ndjson(f, ["event_id", "type"], q))
    assert [r["event_id"] for r in records] == ["e1", "e2", "e7", "e9"]
    assert records[0]["amount"] == Decimal("1.10")
    assert reasons(q) == [(4, "invalid_json"), (5, "not_an_object"), (7, "missing_keys"),
                          (8, "duplicate_key"), (10, "invalid_json")]
    assert q[0].raw == '{"event_id": "e3", "type": "click", "amount": 2.5'
    assert all(not r.raw.endswith(("\r", "\n")) for r in q)
    assert all(isinstance(r, mod.Rejected) for r in q)


def test_valid_records_in_order_and_unchanged():
    records, q = run(['{"id": 1, "x": "a"}\n', '{"id": 2, "nested": {"k": [1, 2, {"z": null}]}}\n'])
    assert records == [{"id": 1, "x": "a"}, {"id": 2, "nested": {"k": [1, 2, {"z": None}]}}]
    assert q == []


@pytest.mark.parametrize("bad", ['{"id": 1', '{"id": 1,}', "{'id': 1}", '{"id": 1} {"id": 2}',
                                 '{"id": 1} trailing', '{id: 1}', 'not json at all'])
def test_malformed_json_is_quarantined_and_processing_continues(bad):
    records, q = run(['{"id": "a"}', bad, '{"id": "b"}'])
    assert [r["id"] for r in records] == ["a", "b"]
    assert reasons(q) == [(2, "invalid_json")]
    assert q[0].raw == bad


@pytest.mark.parametrize("value", ["[1, 2]", "42", '"just a string"', "null", "true", "[]"])
def test_valid_json_that_is_not_an_object(value):
    records, q = run([value + "\n", '{"id": 9}\n'])
    assert records == [{"id": 9}]
    assert reasons(q) == [(1, "not_an_object")]


def test_missing_required_keys_lists_them_and_null_counts_as_present():
    records, q = run(['{"id": 1, "amount": null}', '{"other": 1}', '{"id": 2}'], required=["id", "amount"])
    assert records == [{"id": 1, "amount": None}]
    assert reasons(q) == [(2, "missing_keys"), (3, "missing_keys")]
    assert "amount" in q[0].detail and "id" in q[0].detail
    assert "amount" in q[1].detail and "id" not in q[1].detail


def test_duplicate_keys_anywhere_are_rejected():
    records, q = run(['{"id": 1, "id": 2}', '{"id": 3, "meta": {"a": 1, "a": 1}}', '{"id": 4}'])
    assert records == [{"id": 4}]
    assert reasons(q) == [(1, "duplicate_key"), (2, "duplicate_key")]


def test_line_numbers_count_blank_lines_and_raw_keeps_inner_whitespace():
    lines = ["\n", "   \n", '{"id": 1}\r\n', "\t\n", '  {"id": oops}  \r\n', "\n"]
    records, q = run(lines)
    assert records == [{"id": 1}]
    assert reasons(q) == [(5, "invalid_json")]
    assert q[0].raw == '  {"id": oops}  '


def test_bom_only_tolerated_on_the_first_line():
    records, q = run(['﻿{"id": 1}\n', '{"id": 2}\n', '﻿{"id": 3}\n'])
    assert records == [{"id": 1}, {"id": 2}]
    assert reasons(q) == [(3, "invalid_json")]


def test_numbers_keep_precision_and_non_standard_constants_are_invalid():
    records, q = run(['{"id": 1, "a": 0.1, "b": 1e400, "c": 10, "d": -0.000001}',
                      '{"id": 2, "a": NaN}', '{"id": 3, "a": Infinity}', '{"id": 4, "a": -Infinity}'])
    rec = records[0]
    assert rec["a"] == Decimal("0.1") and isinstance(rec["a"], Decimal)
    assert rec["b"] == Decimal("1e400")
    assert rec["c"] == 10 and isinstance(rec["c"], int)
    assert rec["d"] == Decimal("-0.000001")
    assert reasons(q) == [(2, "invalid_json"), (3, "invalid_json"), (4, "invalid_json")]


def test_last_line_without_terminator_and_trailing_whitespace():
    records, q = run(['{"id": 1}   \n', '{"id": 2}'])
    assert records == [{"id": 1}, {"id": 2}] and q == []


def test_very_long_line():
    payload = "x" * 3_000_000
    records, q = run(['{"id": 1, "blob": "' + payload + '"}\n', '{"id": 2}\n'])
    assert len(records) == 2 and len(records[0]["blob"]) == 3_000_000 and q == []


def test_pathologically_deep_nesting_is_quarantined_not_fatal():
    deep = '{"id": 1, "x": ' + "[" * 100_000 + "]" * 100_000 + "}"
    records, q = run([deep, '{"id": 2}'])
    assert records == [{"id": 2}]
    assert reasons(q) == [(1, "invalid_json")]


def test_records_are_produced_lazily():
    consumed = []

    def source():
        for i in range(1, 100_001):
            consumed.append(i)
            yield '{"id": %d}\n' % i if i != 2 else "garbage\n"

    q = []
    it = mod.read_ndjson(source(), ["id"], q)
    assert next(it) == {"id": 1}
    assert len(consumed) <= 2, "the input must be consumed lazily, one line at a time"
    assert next(it) == {"id": 3}
    assert reasons(q) == [(2, "invalid_json")], "rejects must be recorded as they are encountered"
    assert len(consumed) <= 4
