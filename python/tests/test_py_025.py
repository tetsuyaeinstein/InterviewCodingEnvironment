"""Tests for PY-025 (imports your practice file by default; see _loader.py)."""
import time
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-025")


class OneShot:
    """Iterable that can be iterated only once (like a DB cursor or a file stream)."""

    def __init__(self, rows):
        self._rows, self._used = rows, False

    def __iter__(self):
        if self._used:
            raise AssertionError("rows were iterated twice - the profile must be computed in one pass")
        self._used = True
        return iter(self._rows)


def test_basic_profile():
    rows = [{"id": 1, "city": "Oslo", "amount": Decimal("10.50")},
            {"id": 2, "city": "Bergen", "amount": None},
            {"id": 3, "city": "Oslo", "amount": Decimal("2.25")},
            {"id": 4, "city": None, "amount": Decimal("10.50")}]
    p = mod.profile_columns(rows)
    assert list(p) == ["id", "city", "amount"]
    city = p["city"]
    assert (city.name, city.count, city.null_count, city.distinct_count) == ("city", 4, 1, 2)
    assert (city.min, city.max, city.mean, city.inferred_type) == ("Bergen", "Oslo", None, "str")
    assert city.top_values == [("Oslo", 2), ("Bergen", 1)]
    amount = p["amount"]
    assert (amount.null_count, amount.distinct_count, amount.min, amount.max) == (1, 2, Decimal("2.25"), Decimal("10.50"))
    assert amount.mean == Decimal("7.75") and isinstance(amount.mean, Decimal)
    assert amount.inferred_type == "decimal" and amount.types_seen == ("decimal",)
    assert p["id"].mean == Decimal("2.5") and p["id"].inferred_type == "int"


def test_missing_keys_count_as_null_and_late_columns_count_all_rows():
    rows = [{"a": 1}, {"a": 2}, {"a": 3, "b": "x"}, {"b": "y"}]
    p = mod.profile_columns(rows)
    assert list(p) == ["a", "b"]
    assert (p["a"].count, p["a"].null_count) == (4, 1)
    assert (p["b"].count, p["b"].null_count, p["b"].distinct_count) == (4, 2, 2)


def test_empty_string_is_a_value_not_null():
    p = mod.profile_columns([{"s": ""}, {"s": None}, {"s": "a"}, {"s": ""}])["s"]
    assert (p.null_count, p.distinct_count, p.min, p.max) == (1, 2, "", "a")
    assert p.top_values == [("", 2), ("a", 1)]


def test_bool_is_not_an_int():
    flags = mod.profile_columns([{"f": True}, {"f": False}, {"f": True}])["f"]
    assert (flags.inferred_type, flags.min, flags.max, flags.mean) == ("bool", False, True, None)
    mixed = mod.profile_columns([{"f": True}, {"f": 1}, {"f": 1}])["f"]
    assert mixed.inferred_type == "mixed" and mixed.types_seen == ("bool", "int")
    assert mixed.distinct_count == 2
    assert mixed.top_values == [(1, 2), (True, 1)]
    assert (mixed.min, mixed.max, mixed.mean) == (None, None, None)


def test_int_and_decimal_widen_to_decimal():
    p = mod.profile_columns([{"x": 1}, {"x": Decimal("2.5")}, {"x": 0.5}, {"x": -3}])["x"]
    assert p.inferred_type == "decimal" and p.types_seen == ("decimal", "int")
    assert (p.min, p.max) == (-3, Decimal("2.5"))
    assert p.mean == Decimal("0.25")


def test_mixed_types_are_flagged_without_crashing():
    p = mod.profile_columns([{"v": 10}, {"v": "10"}, {"v": date(2025, 1, 1)}, {"v": 9}])["v"]
    assert p.inferred_type == "mixed"
    assert p.types_seen == ("date", "int", "str")
    assert (p.min, p.max, p.mean) == (None, None, None)
    assert p.distinct_count == 4


def test_numeric_distinct_uses_value_equality_and_keeps_first_seen_representative():
    p = mod.profile_columns([{"v": Decimal("1.0")}, {"v": 1}, {"v": Decimal("1.00")}, {"v": 2}])["v"]
    assert p.distinct_count == 2
    first, count = p.top_values[0]
    assert count == 3 and str(first) == "1.0"


def test_top3_ties_broken_by_first_occurrence():
    seq = ["b", "a", "c", "d", "d", "c", "a", "b", "e", "e", "e"]
    p = mod.profile_columns([{"k": v} for v in seq])["k"]
    assert p.top_values == [("e", 3), ("b", 2), ("a", 2)]
    assert p.distinct_count == 5


def test_mean_is_exact_decimal():
    p = mod.profile_columns([{"v": Decimal("0.1")}] * 3)["v"]
    assert p.mean == Decimal("0.1")
    q = mod.profile_columns([{"v": 1}, {"v": 2}, {"v": 2}])["v"]
    assert q.mean == Decimal(5) / Decimal(3)
    big = mod.profile_columns([{"v": 10**20 + 1}, {"v": 10**20 + 2}])["v"]
    assert big.mean == Decimal("100000000000000000001.5")


def test_dates_and_datetimes_are_distinct_types():
    d = mod.profile_columns([{"d": date(2025, 3, 1)}, {"d": date(2024, 12, 31)}])["d"]
    assert (d.inferred_type, d.min, d.max) == ("date", date(2024, 12, 31), date(2025, 3, 1))
    ts = [datetime(2025, 1, 1, h, tzinfo=timezone.utc) for h in (5, 1, 9)]
    t = mod.profile_columns([{"t": x} for x in ts])["t"]
    assert (t.inferred_type, t.min, t.max, t.mean) == ("datetime", ts[1], ts[2], None)
    m = mod.profile_columns([{"x": date(2025, 1, 1)}, {"x": datetime(2025, 1, 1, tzinfo=timezone.utc)}])["x"]
    assert m.inferred_type == "mixed" and m.distinct_count == 2


def test_all_null_column_and_empty_input():
    p = mod.profile_columns([{"n": None}, {"n": None}])["n"]
    assert (p.count, p.null_count, p.distinct_count, p.min, p.max, p.mean) == (2, 2, 0, None, None, None)
    assert (p.top_values, p.inferred_type, p.types_seen) == ([], "null", ())
    assert mod.profile_columns([]) == {}


def test_single_pass_over_a_one_shot_iterable():
    rows = OneShot([{"a": i % 7, "b": str(i % 3)} for i in range(1000)])
    p = mod.profile_columns(rows)
    assert p["a"].distinct_count == 7 and p["b"].distinct_count == 3


def test_large_input_runs_quickly():
    n = 150_000
    rows = ({"id": i, "grp": f"g{i % 100}", "amt": Decimal(i % 1000) / 100, "opt": None if i % 10 else i}
            for i in range(n))
    t0 = time.perf_counter()
    p = mod.profile_columns(rows)
    elapsed = time.perf_counter() - t0
    assert p["id"].distinct_count == n and p["grp"].distinct_count == 100
    assert p["opt"].null_count == n - n // 10
    assert p["id"].mean == Decimal(n - 1) / 2
    assert elapsed < 4.0, f"took {elapsed:.2f}s"
