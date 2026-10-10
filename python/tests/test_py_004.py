"""Tests for PY-004 (imports your practice file by default; see _loader.py)."""
import copy
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-004")


def example():
    return {
        "id": "T-1",
        "payment": {"method": "card", "card": {"last4": "4242", "network": "VISA"}},
        "items": [{"sku": "COIN", "qty": 2}, {"sku": "GIFT", "qty": 1}],
        "tags": [],
        "meta": {},
    }


def test_example_from_question_including_key_order():
    result = mod.flatten_record(example())
    assert list(result.items()) == [
        ("id", "T-1"),
        ("payment.method", "card"),
        ("payment.card.last4", "4242"),
        ("payment.card.network", "VISA"),
        ("items.0.sku", "COIN"),
        ("items.0.qty", 2),
        ("items.1.sku", "GIFT"),
        ("items.1.qty", 1),
        ("tags", []),
        ("meta", {}),
    ]


def test_leaves_are_kept_as_is():
    ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    rec = {"a": None, "b": "", "c": "word", "d": Decimal("1.10"), "e": False, "f": b"\x00", "g": ts, "h": 0}
    assert mod.flatten_record(rec) == rec


def test_nested_lists_and_tuples():
    rec = {"grid": [[1, 2], [3]], "pair": ("x", {"y": 1}), "codes": ["A", "B"]}
    assert mod.flatten_record(rec) == {
        "grid.0.0": 1, "grid.0.1": 2, "grid.1.0": 3,
        "pair.0": "x", "pair.1.y": 1,
        "codes.0": "A", "codes.1": "B",
    }


def test_empty_containers_are_preserved_at_any_depth():
    assert mod.flatten_record({}) == {}
    rec = {"a": {"b": {}, "c": []}, "d": [{}], "e": ()}
    assert mod.flatten_record(rec) == {"a.b": {}, "a.c": [], "d.0": {}, "e": []}


def test_separator_inside_a_key_without_collision_is_fine():
    assert mod.flatten_record({"a.b": 1, "a": {"c": 2}}) == {"a.b": 1, "a.c": 2}


@pytest.mark.parametrize("rec", [
    {"a.b": 1, "a": {"b": 2}},
    {"a": {"b": 2}, "a.b": 1},
    {"items": [10], "items.0": 5},
    {"x": {"y.z": 1, "y": {"z": 2}}},
])
def test_colliding_output_keys_raise_value_error(rec):
    original = copy.deepcopy(rec)
    with pytest.raises(ValueError):
        mod.flatten_record(rec)
    assert rec == original


def test_custom_separator_changes_what_collides():
    rec = {"a.b": 1, "a": {"b": 2}}
    assert mod.flatten_record(rec, sep="/") == {"a.b": 1, "a/b": 2}
    assert mod.flatten_record({"a": {"b": [7]}}, sep="__") == {"a__b__0": 7}


@pytest.mark.parametrize("rec", [{1: "x"}, {"a": {2: "y"}}, {"a": [{None: 1}]}])
def test_non_string_keys_raise_type_error(rec):
    with pytest.raises(TypeError):
        mod.flatten_record(rec)


def test_top_level_must_be_a_mapping():
    with pytest.raises(TypeError):
        mod.flatten_record([{"a": 1}])


def test_max_depth_keeps_deeper_containers_as_values():
    result = mod.flatten_record(example(), max_depth=2)
    assert result == {
        "id": "T-1",
        "payment.method": "card",
        "payment.card": {"last4": "4242", "network": "VISA"},
        "items.0": {"sku": "COIN", "qty": 2},
        "items.1": {"sku": "GIFT", "qty": 1},
        "tags": [],
        "meta": {},
    }
    assert mod.flatten_record(example(), max_depth=1)["payment"] == example()["payment"]
    assert mod.flatten_record(example(), max_depth=50) == mod.flatten_record(example())


@pytest.mark.parametrize("kwargs", [{"max_depth": 0}, {"max_depth": -1}, {"max_depth": True},
                                    {"max_depth": 1.5}, {"sep": ""}, {"sep": None}])
def test_invalid_options_raise_value_error(kwargs):
    with pytest.raises(ValueError):
        mod.flatten_record(example(), **kwargs)


def test_input_not_mutated_and_output_does_not_alias_input():
    rec = example()
    original = copy.deepcopy(rec)
    flat = mod.flatten_record(rec, max_depth=2)
    assert rec == original
    flat["payment.card"]["last4"] = "0000"
    flat["items.0"]["qty"] = 99
    flat["tags"].append("mutated")
    flat["meta"]["k"] = "v"
    assert rec == original

    rec2 = {"cut": {"inner": {"deep": [1, 2]}}}
    out = mod.flatten_record(rec2, max_depth=1)
    out["cut"]["inner"]["deep"].append(3)
    assert rec2 == {"cut": {"inner": {"deep": [1, 2]}}}


def test_nesting_deeper_than_the_recursion_limit():
    depth = 5_000
    rec = leaf = {}
    for _ in range(depth - 1):
        leaf["n"] = {}
        leaf = leaf["n"]
    leaf["n"] = "bottom"
    result = mod.flatten_record(rec)
    assert result == {".".join(["n"] * depth): "bottom"}
    assert list(mod.flatten_record(rec, max_depth=depth).items()) == list(result.items())
