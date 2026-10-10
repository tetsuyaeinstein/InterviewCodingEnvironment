"""Tests for PY-002 (imports your practice file by default; see _loader.py)."""
import random
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-002")


def txn(customer_id, status, amount):
    return {"customer_id": customer_id, "status": status, "amount": amount}


EXAMPLE = [
    txn(7, "COMPLETED", "10.10"),
    txn(7, "completed", Decimal("0.20")),
    txn(8, "PENDING", "99.99"),
    txn(8, "COMPLETED", 5),
    txn(None, "COMPLETED", "3.00"),
    txn(9, "COMPLETED", "4.00"),
    txn(9, "COMPLETED", "-4.00"),
]


def assert_cents(result):
    for cid, value in result.items():
        assert type(value) is Decimal, f"{cid}: {type(value).__name__} is not Decimal"
        assert value.as_tuple().exponent == -2, f"{cid}: {value!r} does not have exactly 2 decimal places"


def test_example_from_question():
    result = mod.total_spend_by_customer(EXAMPLE)
    assert result == {7: Decimal("10.30"), 8: Decimal("5.00"), 9: Decimal("0.00")}
    assert_cents(result)


def test_guests_included_under_none_when_requested():
    result = mod.total_spend_by_customer(EXAMPLE, include_guests=True)
    assert result[None] == Decimal("3.00")
    assert len(result) == 4
    assert None not in mod.total_spend_by_customer(EXAMPLE)


def test_empty_input_and_nothing_completed():
    assert mod.total_spend_by_customer([]) == {}
    assert mod.total_spend_by_customer([txn(1, "PENDING", "5.00"), txn(2, None, "1.00")]) == {}


def test_status_is_case_and_whitespace_insensitive_but_exact_word():
    rows = [
        txn(1, " Completed\t", "1.00"),
        txn(1, "COMPLETED", "2.00"),
        txn(1, "COMPLETED_PARTIAL", "100.00"),
        txn(1, "REFUNDED", "-50.00"),
        txn(1, "FAILED", "7.00"),
    ]
    assert mod.total_spend_by_customer(rows) == {1: Decimal("3.00")}


def test_bad_amounts_on_uncounted_rows_are_never_parsed():
    rows = [
        txn(1, "PENDING", "not-a-number"),
        txn(1, "FAILED", 1.5),
        txn(None, "COMPLETED", "garbage"),   # guest row excluded by default
        txn(1, "COMPLETED", "2.50"),
    ]
    assert mod.total_spend_by_customer(rows) == {1: Decimal("2.50")}


def test_result_values_always_have_two_decimal_places():
    rows = [txn(1, "COMPLETED", 10), txn(2, "COMPLETED", "3"), txn(3, "COMPLETED", Decimal("1.5")),
            txn(4, "COMPLETED", " 7.25 ")]
    result = mod.total_spend_by_customer(rows)
    assert result == {1: Decimal("10"), 2: Decimal("3"), 3: Decimal("1.5"), 4: Decimal("7.25")}
    assert_cents(result)
    assert str(result[1]) == "10.00"


def test_rounding_happens_once_on_the_exact_total():
    # per-row rounding would give 0.01 + 0.01 = 0.02; the exact total 0.010 stays 0.01
    rows = [txn(5, "COMPLETED", "0.005"), txn(5, "COMPLETED", "0.005")]
    assert mod.total_spend_by_customer(rows) == {5: Decimal("0.01")}
    # half-up on the final total, also for a single sub-cent amount
    assert mod.total_spend_by_customer([txn(6, "COMPLETED", "2.125")]) == {6: Decimal("2.13")}


def test_no_float_round_trip():
    # float("0.015") is 0.01499999..., which would round down to 0.01
    assert mod.total_spend_by_customer([txn(1, "COMPLETED", "0.015")]) == {1: Decimal("0.02")}
    rows = [txn(2, "COMPLETED", "0.10")] * 3 + [txn(2, "COMPLETED", "-0.30")]
    assert mod.total_spend_by_customer(rows) == {2: Decimal("0.00")}


@pytest.mark.parametrize("amount", [1.25, True, None, [1]])
def test_wrong_amount_types_raise_type_error(amount):
    with pytest.raises(TypeError):
        mod.total_spend_by_customer([txn(1, "COMPLETED", amount)])


@pytest.mark.parametrize("amount", ["abc", "", "  ", "1,000.00", "NaN", "Infinity"])
def test_unparsable_amount_strings_raise_value_error(amount):
    with pytest.raises(ValueError):
        mod.total_spend_by_customer([txn(1, "COMPLETED", amount)])


def test_returns_plain_dict_and_does_not_mutate():
    rows = [txn(1, "COMPLETED", "1.00"), txn(2, "PENDING", "1.00")]
    snapshot = [dict(r) for r in rows]
    result = mod.total_spend_by_customer(rows)
    assert type(result) is dict
    assert rows == snapshot
    with pytest.raises(KeyError):
        result[2]


def test_generator_input_and_random_oracle():
    rng = random.Random(2)
    for _ in range(200):
        rows = []
        for _ in range(rng.randint(0, 40)):
            cents = rng.randint(-500, 5_000)
            amount = rng.choice([f"{cents / 100:.2f}", Decimal(cents) / 100, f"{cents * 10 + rng.randint(0, 9)}e-3"])
            rows.append(txn(rng.choice([1, 2, 3, None]), rng.choice(["COMPLETED", "completed ", "PENDING"]), amount))
        expected_raw = {}
        for r in rows:
            if r["status"].strip().upper() == "COMPLETED" and r["customer_id"] is not None:
                expected_raw[r["customer_id"]] = expected_raw.get(r["customer_id"], Decimal(0)) + Decimal(r["amount"])
        expected = {k: v.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP") for k, v in expected_raw.items()}
        assert mod.total_spend_by_customer(r for r in rows) == expected
