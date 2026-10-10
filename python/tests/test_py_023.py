"""Tests for PY-023 (imports your practice file by default; see _loader.py)."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-023")
C = mod.Column


def one(kind, value, order="MDY", nullable=True):
    """Normalise a single value; return (value, reason_or_None)."""
    rows, errors = mod.normalise_rows([{"v": value}], [C("v", kind, nullable)], slash_date_order=order)
    assert len(rows) == 1 and list(rows[0]) == ["v"]
    assert len(errors) <= 1
    return rows[0]["v"], (errors[0].reason if errors else None)


def test_mixed_row_example():
    schema = [C("order_id", "int", nullable=False), C("order_date", "date"), C("paid_at", "timestamp"),
              C("amount", "decimal", nullable=False), C("note", "str")]
    rows, errors = mod.normalise_rows(
        [{"order_id": " 1,042 ", "order_date": "03/01/2025", "paid_at": "2025-03-01T21:15:00-05:00",
          "amount": "(1,234.50)", "note": "  NA  ", "ignored": "x"}],
        schema, slash_date_order="MDY")
    assert errors == []
    assert rows == [{"order_id": 1042, "order_date": date(2025, 3, 1),
                     "paid_at": datetime(2025, 3, 2, 2, 15, tzinfo=timezone.utc),
                     "amount": Decimal("-1234.50"), "note": "NA"}]
    assert list(rows[0]) == ["order_id", "order_date", "paid_at", "amount", "note"]


def test_slash_dates_follow_the_declared_order_and_are_never_swapped():
    assert one("date", "03/01/2025", "MDY") == (date(2025, 3, 1), None)
    assert one("date", "03/01/2025", "DMY") == (date(2025, 1, 3), None)
    assert one("date", "3/1/2025", "DMY") == (date(2025, 1, 3), None)
    # day > 12 does NOT make the parser silently switch to the other order
    assert one("date", "13/01/2025", "MDY") == (None, "invalid_date")
    assert one("date", "01/13/2025", "DMY") == (None, "invalid_date")
    assert one("date", "13/01/2025", "DMY") == (date(2025, 1, 13), None)


@pytest.mark.parametrize("value", ["2025-3-1", "20250301", "2025/03/01", "03/01/25", "2025-02-30",
                                   "02/30/2025", "2025-13-01", "2025-W09-6", "1 March 2025",
                                   "2025-03-01T00:00:00", "x"])
def test_dates_outside_the_allowed_formats_are_errors(value):
    v, reason = one("date", value)
    assert (v, reason) == (None, "invalid_date"), value


def test_iso_dates_and_leap_day():
    assert one("date", "2024-02-29") == (date(2024, 2, 29), None)
    assert one("date", "  2025-12-31 ") == (date(2025, 12, 31), None)
    assert one("date", "2025-02-29") == (None, "invalid_date")


def test_bad_slash_date_order_is_rejected():
    with pytest.raises(ValueError):
        mod.normalise_rows([{"v": "1/2/2025"}], [C("v", "date")], slash_date_order="YMD")


@pytest.mark.parametrize("value, expected", [
    ("2025-03-01T10:00:00Z", datetime(2025, 3, 1, 10, tzinfo=timezone.utc)),
    ("2025-03-01T10:00:00+00:00", datetime(2025, 3, 1, 10, tzinfo=timezone.utc)),
    ("2025-03-01T23:30:00-05:00", datetime(2025, 3, 2, 4, 30, tzinfo=timezone.utc)),
    ("2025-03-01T04:00:00+05:30", datetime(2025, 2, 28, 22, 30, tzinfo=timezone.utc)),
    ("2025-03-01 10:00:00.123456+01:00", datetime(2025, 3, 1, 9, 0, 0, 123456, tzinfo=timezone.utc)),
])
def test_timestamps_with_offsets_become_utc(value, expected):
    v, reason = one("timestamp", value)
    assert reason is None and v == expected
    assert v.utcoffset() == timedelta(0) and v.tzinfo == timezone.utc


@pytest.mark.parametrize("value, reason", [
    ("2025-03-01T10:00:00", "naive_timestamp"),
    ("2025-03-01", "naive_timestamp"),
    ("2025-03-01T25:00:00Z", "invalid_timestamp"),
    ("03/01/2025 10:00", "invalid_timestamp"),
    ("yesterday", "invalid_timestamp"),
])
def test_naive_or_malformed_timestamps_are_errors(value, reason):
    assert one("timestamp", value) == (None, reason)


@pytest.mark.parametrize("value, expected", [
    ("1,234.50", "1234.50"), ("(12.00)", "-12.00"), ("-0.5", "-0.5"), ("0", "0"),
    (" 42 ", "42"), ("1,234,567.891", "1234567.891"), ("(1,000)", "-1000"), ("007.10", "7.10"),
])
def test_decimal_grammar_keeps_exact_value_and_scale(value, expected):
    v, reason = one("decimal", value)
    assert reason is None and isinstance(v, Decimal)
    assert v == Decimal(expected) and str(v) == expected


@pytest.mark.parametrize("value", ["12,34", "1,2345.00", ",123", "1,234,", ".5", "1.", "1e3", "NaN",
                                   "Infinity", "$12.00", "- 12", "-(12)", "(-12)", "12-", "+12",
                                   "1 234", "١٢", "12.3.4", "(12"])
def test_invalid_decimals(value):
    assert one("decimal", value) == (None, "invalid_decimal")


def test_int_grammar():
    assert one("int", "1,000") == (1000, None)
    assert one("int", "(5)") == (-5, None)
    assert one("int", "-0") == (0, None)
    assert one("int", "12.0") == (None, "invalid_int")
    assert one("int", "1e2") == (None, "invalid_int")
    assert one("int", "none") == (None, "invalid_int")


@pytest.mark.parametrize("value", ["", "   ", "NULL", "null", "Null", "N/A", "n/a", " n/a ", None])
@pytest.mark.parametrize("kind", ["date", "timestamp", "decimal", "int", "str"])
def test_null_tokens_for_every_kind(kind, value):
    assert one(kind, value, nullable=True) == (None, None)
    assert one(kind, value, nullable=False) == (None, "null_not_allowed")


def test_values_that_only_look_null_are_kept_for_strings():
    assert one("str", "NA") == ("NA", None)          # Namibia, sodium, ...
    assert one("str", " None ") == ("None", None)
    assert one("str", "nullable") == ("nullable", None)


def test_missing_keys_errors_order_and_original_values():
    schema = [C("a", "int", nullable=False), C("b", "decimal"), C("c", "date", nullable=False)]
    rows = iter([{"a": "1", "b": "2.50", "c": "2025-01-01"},
                 {"b": " bad ", "c": "31/12/2025"},
                 {"a": "x", "b": None, "c": "12/31/2025", "zzz": "dropped"}])
    out, errors = mod.normalise_rows(rows, schema, slash_date_order="MDY")
    assert out == [{"a": 1, "b": Decimal("2.50"), "c": date(2025, 1, 1)},
                   {"a": None, "b": None, "c": None},
                   {"a": None, "b": None, "c": date(2025, 12, 31)}]
    assert errors == [mod.FieldError(1, "a", None, "null_not_allowed"),
                      mod.FieldError(1, "b", " bad ", "invalid_decimal"),
                      mod.FieldError(1, "c", "31/12/2025", "invalid_date"),
                      mod.FieldError(2, "a", "x", "invalid_int")]


def test_schema_problems_raise():
    with pytest.raises(ValueError):
        mod.normalise_rows([{"a": "1"}], [C("a", "float")], slash_date_order="MDY")
    with pytest.raises(ValueError):
        mod.normalise_rows([{"a": "1"}], [C("a", "int"), C("a", "str")], slash_date_order="MDY")


def test_empty_input():
    assert mod.normalise_rows([], [C("a", "int")], slash_date_order="DMY") == ([], [])
