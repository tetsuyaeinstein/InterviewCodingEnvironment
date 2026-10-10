"""Tests for PY-021 (imports your practice file by default; see _loader.py)."""
import tracemalloc
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-021")

EXPECTED = {"C001": Decimal("4.70"), "C002": Decimal("8.00"), "C003": Decimal("1.000")}


def lines(*rows: str):
    """A one-shot iterator of CSV lines (like a file object, but no read()/readlines())."""
    return iter([r + "\n" for r in rows])


def test_fixture_file_by_path(fixtures_dir):
    # BOM, CRLF, quoted commas / quotes / embedded newline, blank and whitespace-only lines,
    # columns in a different order plus extra columns.
    result = mod.spend_per_customer(fixtures_dir / "PY-021" / "transactions.csv")
    assert result == EXPECTED
    assert all(isinstance(v, Decimal) for v in result.values())


def test_fixture_file_by_str_path_with_guest_key(fixtures_dir):
    result = mod.spend_per_customer(str(fixtures_dir / "PY-021" / "transactions.csv"), guest_key="__guest__")
    assert result == {**EXPECTED, "__guest__": Decimal("7.00")}


def test_open_file_object_is_streamed_and_not_closed(fixtures_dir):
    # opened WITHOUT utf-8-sig: the BOM is still on the first header name
    with open(fixtures_dir / "PY-021" / "transactions.csv", encoding="utf-8", newline="") as f:
        result = mod.spend_per_customer(f)
        assert not f.closed, "the caller's file object must not be closed"
    assert result == EXPECTED


def test_decimal_precision_is_exact_and_scale_is_kept():
    src = lines("customer_id,amount,status", *["A,0.10,COMPLETED"] * 3, "B,1.005,COMPLETED", "B,2,COMPLETED")
    result = mod.spend_per_customer(src)
    assert result["A"] == Decimal("0.30") and str(result["A"]) == "0.30"
    assert str(result["B"]) == "3.005"


@pytest.mark.parametrize("header", ["amount,status", "customer_id,status", "customer_id,amount",
                                    "customer,amount,status", "Customer_ID,amount,status"])
def test_missing_required_column_raises(header):
    with pytest.raises(ValueError):
        mod.spend_per_customer(lines(header, "x,1,COMPLETED"))


def test_duplicated_required_column_is_ambiguous():
    with pytest.raises(ValueError):
        mod.spend_per_customer(lines("customer_id,amount,status,amount", "A,1,COMPLETED,2"))


def test_empty_input_raises_but_header_only_is_empty_result():
    with pytest.raises(ValueError):
        mod.spend_per_customer(iter([]))
    assert mod.spend_per_customer(lines(" customer_id , amount , status ")) == {}


def test_only_completed_rows_count_and_others_are_not_parsed():
    src = lines("customer_id,amount,status",
                "A,10.00,COMPLETED",
                "A,oops,PENDING",            # never parsed: not COMPLETED
                "A,,FAILED",
                "A,5.00,COMPLETED_REVERSED",
                "A,1.00, Completed ",
                "B,3.00,CANCELLED")
    assert mod.spend_per_customer(src) == {"A": Decimal("11.00")}


@pytest.mark.parametrize("bad", ["abc", "", "NaN", "Infinity", "1.2.3"])
def test_invalid_amount_on_completed_row_raises(bad):
    with pytest.raises(ValueError):
        mod.spend_per_customer(lines("customer_id,amount,status", "A,1.00,COMPLETED", f"A,{bad},COMPLETED"))


def test_wrong_field_count_raises():
    with pytest.raises(ValueError):
        mod.spend_per_customer(lines("customer_id,amount,status", "A,1.00,COMPLETED", "A,2.00"))
    with pytest.raises(ValueError):
        mod.spend_per_customer(lines("customer_id,amount,status", "A,1,000.00,COMPLETED"))


def test_ids_are_strings_and_zero_totals_are_kept():
    src = lines("customer_id,amount,status", "007,1.00,COMPLETED", "7,2.00,COMPLETED",
                "Z,5.00,COMPLETED", "Z,-5.00,COMPLETED", ",9.99,COMPLETED", "  ,1.00,COMPLETED")
    assert mod.spend_per_customer(src) == {"007": Decimal("1.00"), "7": Decimal("2.00"), "Z": Decimal("0.00")}


def test_quoted_newline_inside_a_field_is_one_record():
    src = iter(['customer_id,note,amount,status\n', 'A,"line one\n', 'line two, COMPLETED",1.50,COMPLETED\n',
                'B,"x",2.00,PENDING\n'])
    assert mod.spend_per_customer(src) == {"A": Decimal("1.50")}


def test_large_stream_uses_bounded_memory():
    n = 200_000

    def gen():
        yield "customer_id,amount,status,comment\n"
        for i in range(n):
            yield f"C{i % 50:03d},{i % 100}.25,{'COMPLETED' if i % 4 else 'PENDING'},row number {i} padding text\n"

    tracemalloc.start()
    try:
        result = mod.spend_per_customer(gen())
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(result) == 50
    assert sum(result.values()) == sum(Decimal(f"{i % 100}.25") for i in range(n) if i % 4)
    assert peak < 8_000_000, f"peak traced memory {peak / 1e6:.1f} MB - rows must be streamed, not collected"
