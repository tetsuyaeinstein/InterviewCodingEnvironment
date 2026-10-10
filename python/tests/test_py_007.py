"""Tests for PY-007 (imports your practice file by default; see _loader.py)."""
import copy
from datetime import date, datetime
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-007")

D = Decimal


def schema():
    F = mod.FieldSpec
    return [
        F("refund_id", "int"),
        F("amount", "decimal"),
        F("reason", "str", allowed=frozenset({"DAMAGED", "DUPLICATE", "OTHER"})),
        F("approved", "bool", required=False),
        F("refund_date", "date", nullable=True),
    ]


def codes(errors):
    return [(e.row_index, e.field, e.error_code) for e in errors]


def good_row(**overrides):
    row = {"refund_id": "7", "amount": "12.50", "reason": "OTHER", "refund_date": "2025-06-01"}
    row.update(overrides)
    return row


def check_one_field(spec, value):
    """Validate a single-field row; return (valid_rows, error codes)."""
    valid, errors = mod.validate_rows([{spec.name: value}], [spec])
    return valid, [e.error_code for e in errors]


def test_example_from_question():
    rows = [
        good_row(),
        {"refund_id": "x", "amount": 1.5, "reason": "LOST", "refund_date": "", "note": "hi"},
        ["7", "12.50"],
    ]
    valid, errors = mod.validate_rows(rows, schema())
    assert valid == [{"refund_id": 7, "amount": D("12.50"), "reason": "OTHER", "refund_date": date(2025, 6, 1)}]
    assert codes(errors) == [
        (1, "refund_id", "invalid_format"),
        (1, "amount", "invalid_type"),
        (1, "reason", "not_allowed"),
        (1, "note", "unknown_field"),
        (2, None, "not_a_mapping"),
    ]
    assert all(isinstance(e, mod.RowError) for e in errors)
    assert all(isinstance(e.message, str) and e.message.strip() for e in errors)


def test_valid_rows_are_coerced_in_schema_order():
    row = {"refund_date": date(2025, 1, 2), "approved": " TRUE ", "reason": "DAMAGED",
           "amount": 3, "refund_id": 11}
    valid, errors = mod.validate_rows([row], schema())
    assert errors == []
    assert list(valid[0].items()) == [("refund_id", 11), ("amount", D(3)), ("reason", "DAMAGED"),
                                      ("approved", True), ("refund_date", date(2025, 1, 2))]
    assert type(valid[0]["amount"]) is Decimal


def test_all_errors_in_a_row_are_collected_in_schema_order():
    row = {"zeta": 1, "approved": "yes", "amount": "NaN", "alpha": 2, "reason": None}
    valid, errors = mod.validate_rows([row], schema())
    assert valid == []
    assert codes(errors) == [
        (0, "refund_id", "missing_required"),
        (0, "amount", "invalid_format"),
        (0, "reason", "null_not_allowed"),
        (0, "approved", "invalid_format"),
        (0, "refund_date", "missing_required"),
        (0, "alpha", "unknown_field"),
        (0, "zeta", "unknown_field"),
    ]


def test_absent_optional_field_is_omitted_and_nullable_blank_is_none():
    valid, errors = mod.validate_rows([good_row(refund_date="   ")], schema())
    assert errors == []
    assert valid == [{"refund_id": 7, "amount": D("12.50"), "reason": "OTHER", "refund_date": None}]
    assert "approved" not in valid[0]


def test_empty_string_is_a_value_for_str_fields_but_null_for_typed_fields():
    F = mod.FieldSpec
    assert check_one_field(F("note", "str"), "") == ([{"note": ""}], [])
    assert check_one_field(F("note", "str"), "  x ") == ([{"note": "  x "}], [])
    assert check_one_field(F("qty", "int"), "") == ([], ["null_not_allowed"])
    assert check_one_field(F("qty", "int", nullable=True), " ") == ([{"qty": None}], [])
    assert check_one_field(F("note", "str"), None) == ([], ["null_not_allowed"])


@pytest.mark.parametrize("ftype, value, expected", [
    ("int", " -42 ", -42), ("int", "+5", 5), ("int", 9, 9),
    ("decimal", " 0.10 ", D("0.10")), ("decimal", "1e3", D("1e3")), ("decimal", D("-2.5"), D("-2.5")), ("decimal", 4, D(4)),
    ("bool", "False", False), ("bool", True, True),
    ("date", "2024-02-29", date(2024, 2, 29)), ("date", date(2025, 1, 1), date(2025, 1, 1)),
])
def test_accepted_values_and_coercion(ftype, value, expected):
    valid, errs = check_one_field(mod.FieldSpec("f", ftype), value)
    assert errs == []
    assert valid[0]["f"] == expected
    assert type(valid[0]["f"]) is type(expected)


@pytest.mark.parametrize("ftype, value, code", [
    ("str", 5, "invalid_type"),
    ("int", True, "invalid_type"), ("int", 3.0, "invalid_type"), ("int", D("3"), "invalid_type"),
    ("int", "3.0", "invalid_format"), ("int", "1,000", "invalid_format"),
    ("decimal", 1.5, "invalid_type"), ("decimal", False, "invalid_type"), ("decimal", [1], "invalid_type"),
    ("decimal", "NaN", "invalid_format"), ("decimal", "Infinity", "invalid_format"),
    ("decimal", D("NaN"), "invalid_format"), ("decimal", "12,50", "invalid_format"),
    ("bool", 1, "invalid_type"), ("bool", "yes", "invalid_format"),
    ("date", datetime(2025, 1, 1, 10, 0), "invalid_type"), ("date", 20250101, "invalid_type"),
    ("date", "2025-02-30", "invalid_format"), ("date", "01/02/2025", "invalid_format"),
    ("date", "2025-06-01T10:00:00", "invalid_format"),
])
def test_rejected_values_get_the_right_code(ftype, value, code):
    assert check_one_field(mod.FieldSpec("f", ftype), value) == ([], [code])


def test_allowed_values_apply_after_coercion():
    F = mod.FieldSpec
    spec = F("tier", "int", allowed=(1, 2, 3))
    assert check_one_field(spec, " 2 ") == ([{"tier": 2}], [])
    assert check_one_field(spec, "4") == ([], ["not_allowed"])
    spec = F("fee", "decimal", allowed=[D("0.50"), D("1.00")])
    assert check_one_field(spec, "1.0") == ([{"fee": D("1.00")}], [])
    assert check_one_field(F("r", "str", nullable=True, allowed={"A"}), None) == ([{"r": None}], [])


def test_unknown_field_policies():
    row = good_row(zz=1, aa=2)
    _, errors = mod.validate_rows([row], schema())
    assert codes(errors) == [(0, "aa", "unknown_field"), (0, "zz", "unknown_field")]
    valid, errors = mod.validate_rows([row], schema(), unknown_fields="ignore")
    assert errors == [] and set(valid[0]) == {"refund_id", "amount", "reason", "refund_date"}
    valid, errors = mod.validate_rows([row], schema(), unknown_fields="keep")
    assert errors == []
    assert list(valid[0])[-2:] == ["zz", "aa"] and valid[0]["zz"] == 1
    with pytest.raises(ValueError):
        mod.validate_rows([row], schema(), unknown_fields="drop")


def test_never_raises_on_hostile_rows():
    rows = [None, "a,b,c", 42, {"refund_id": object(), "amount": {"x": 1}, "reason": ["OTHER"],
                                "refund_date": b"2025-01-01", 7: "int key"}, good_row()]
    valid, errors = mod.validate_rows(iter(rows), schema())
    assert len(valid) == 1
    assert codes(errors) == [
        (0, None, "not_a_mapping"), (1, None, "not_a_mapping"), (2, None, "not_a_mapping"),
        (3, "refund_id", "invalid_type"), (3, "amount", "invalid_type"), (3, "reason", "invalid_type"),
        (3, "refund_date", "invalid_type"), (3, "7", "unknown_field"),
    ]


def test_inputs_not_mutated_and_output_rows_are_new_dicts():
    rows = [good_row(), good_row(refund_id="oops")]
    snapshot = copy.deepcopy(rows)
    valid, _ = mod.validate_rows(rows, schema(), unknown_fields="keep")
    assert rows == snapshot
    valid[0]["refund_id"] = -1
    assert rows[0]["refund_id"] == "7"


@pytest.mark.parametrize("bad_schema", [
    [("refund_id", "int")],
    ["refund_id"],
    "refund_id:int",
])
def test_schema_entries_must_be_field_specs(bad_schema):
    with pytest.raises(mod.SchemaError):
        mod.validate_rows([], bad_schema)


@pytest.mark.parametrize("make", [
    lambda F: [F("a", "int"), F("a", "str")],                      # duplicate name
    lambda F: [F("", "int")],                                      # empty name
    lambda F: [F("a", "float")],                                   # unknown type
    lambda F: [F("a", "int", required="yes")],                     # non-bool flag
    lambda F: [F("a", "int", allowed=[])],                         # empty allowed
    lambda F: [F("a", "str", allowed="ABC")],                      # string as collection
    lambda F: [F("a", "int", allowed=[1, "2"])],                   # wrong type in allowed
    lambda F: [F("a", "int", allowed=[True])],                     # bool is not an int here
    lambda F: [F("a", "decimal", allowed=[1.5])],                  # float is not Decimal
    lambda F: [F("a", "date", allowed=[datetime(2025, 1, 1)])],    # datetime is not a date
])
def test_bad_schema_raises_schema_error_before_reading_rows(make):
    def rows():
        raise AssertionError("rows must not be read when the schema is invalid")
        yield  # pragma: no cover

    with pytest.raises(mod.SchemaError):
        mod.validate_rows(rows(), make(mod.FieldSpec))
    assert issubclass(mod.SchemaError, ValueError)


def test_empty_inputs():
    assert mod.validate_rows([], schema()) == ([], [])
    valid, errors = mod.validate_rows([{}, {"x": 1}], [], unknown_fields="error")
    assert valid == [{}] and codes(errors) == [(1, "x", "unknown_field")]
