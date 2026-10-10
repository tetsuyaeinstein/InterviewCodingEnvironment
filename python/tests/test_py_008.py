"""Tests for PY-008 (imports your practice file by default; see _loader.py)."""
import copy
import random
import time

import pytest

from _loader import load

mod = load("PY-008")

_MISSING = object()


def example():
    left = [
        {"transaction_id": 1, "customer_id": 10, "status": "COMPLETED"},
        {"transaction_id": 2, "customer_id": 11, "status": "COMPLETED"},
        {"transaction_id": 3, "customer_id": None, "status": "COMPLETED"},
        {"transaction_id": 4, "customer_id": 10, "status": "PENDING"},
    ]
    right = [
        {"customer_id": 10, "status": "ACTIVE", "region": "EU"},
        {"customer_id": 12, "status": "ACTIVE", "region": "US"},
        {"customer_id": 10, "status": "CLOSED", "region": "EU"},
        {"customer_id": None, "status": "ACTIVE", "region": "??"},
    ]
    return left, right


def oracle(left, right, on, how, suffix="_right"):
    out = []
    for lrow in left:
        lk = lrow.get(on)
        hits = []
        for rrow in right:
            rk = rrow.get(on)
            if lk is not None and rk is not None and type(lk) is type(rk) and lk == rk:
                merged = dict(lrow)
                for name, value in rrow.items():
                    if name != on:
                        merged[name + suffix if name in lrow else name] = value
                hits.append(merged)
        out.extend(hits if hits else ([dict(lrow)] if how == "left" else []))
    return out


def test_example_left_join():
    left, right = example()
    result = mod.join_records(left, right, "customer_id", how="left")
    assert result == [
        {"transaction_id": 1, "customer_id": 10, "status": "COMPLETED", "status_right": "ACTIVE", "region": "EU"},
        {"transaction_id": 1, "customer_id": 10, "status": "COMPLETED", "status_right": "CLOSED", "region": "EU"},
        {"transaction_id": 2, "customer_id": 11, "status": "COMPLETED"},
        {"transaction_id": 3, "customer_id": None, "status": "COMPLETED"},
        {"transaction_id": 4, "customer_id": 10, "status": "PENDING", "status_right": "ACTIVE", "region": "EU"},
        {"transaction_id": 4, "customer_id": 10, "status": "PENDING", "status_right": "CLOSED", "region": "EU"},
    ]


def test_example_inner_join_is_the_default():
    left, right = example()
    result = mod.join_records(left, right, "customer_id")
    assert [(r["transaction_id"], r["status_right"]) for r in result] == [
        (1, "ACTIVE"), (1, "CLOSED"), (4, "ACTIVE"), (4, "CLOSED")]


def test_none_and_missing_keys_never_match_each_other():
    left = [{"k": None, "a": 1}, {"a": 2}, {"k": 5, "a": 3}]
    right = [{"k": None, "b": 1}, {"b": 2}, {"k": 5, "b": 3}]
    assert mod.join_records(left, right, "k") == [{"k": 5, "a": 3, "b": 3}]
    assert mod.join_records(left, right, "k", how="left") == [
        {"k": None, "a": 1}, {"a": 2}, {"k": 5, "a": 3, "b": 3}]


def test_many_to_many_fans_out_in_left_then_right_order():
    left = [{"k": "x", "l": i} for i in range(3)]
    right = [{"k": "x", "r": j} for j in range(4)] + [{"k": "y", "r": 99}]
    result = mod.join_records(left, right, "k")
    assert [(row["l"], row["r"]) for row in result] == [(i, j) for i in range(3) for j in range(4)]


def test_keys_are_not_coerced():
    left = [{"id": 1, "v": "int"}, {"id": "1", "v": "str"}]
    right = [{"id": "1", "w": "str"}]
    assert mod.join_records(left, right, "id") == [{"id": "1", "v": "str", "w": "str"}]


def test_suffix_applies_only_to_names_present_in_the_left_row():
    left = [{"k": 1, "amount": 5}, {"k": 2}]
    right = [{"k": 1, "amount": 7}, {"k": 2, "amount": 8}]
    assert mod.join_records(left, right, "k", right_suffix="__c") == [
        {"k": 1, "amount": 5, "amount__c": 7}, {"k": 2, "amount": 8}]


def test_suffixed_name_clash_raises():
    left = [{"k": 1, "status": "A", "status_right": "B"}]
    right = [{"k": 1, "status": "C"}]
    with pytest.raises(ValueError):
        mod.join_records(left, right, "k")
    left = [{"k": 1, "status": "A"}]
    right = [{"k": 1, "status": "C", "status_right": "D"}]
    with pytest.raises(ValueError):
        mod.join_records(left, right, "k")


@pytest.mark.parametrize("kwargs", [{"how": "outer"}, {"how": "LEFT"}, {"how": "right"},
                                    {"right_suffix": ""}, {"right_suffix": None}])
def test_invalid_options_raise_value_error(kwargs):
    left, right = example()
    with pytest.raises(ValueError):
        mod.join_records(left, right, "customer_id", **kwargs)


def test_empty_sides():
    left, right = example()
    assert mod.join_records([], right, "customer_id", how="left") == []
    assert mod.join_records(left, [], "customer_id") == []
    assert mod.join_records(left, [], "customer_id", how="left") == left


def test_one_pass_iterators_new_dicts_and_no_mutation():
    left, right = example()
    snap_l, snap_r = copy.deepcopy(left), copy.deepcopy(right)
    result = mod.join_records(iter(left), (r for r in right), "customer_id", how="left")
    assert len(result) == 6
    assert left == snap_l and right == snap_r
    assert all(all(out is not src for src in left + right) for out in result)
    result[2]["status"] = "CHANGED"
    assert left[1]["status"] == "COMPLETED"


def test_matches_nested_loop_oracle_on_random_inputs():
    rng = random.Random(8)
    keys = [1, 2, 3, "1", "2", None, _MISSING]
    for _ in range(300):
        def rows(n, tag):
            out = []
            for i in range(n):
                k = rng.choice(keys)
                row = {} if k is _MISSING else {"k": k}
                row[tag] = i
                if rng.random() < 0.3:
                    row["shared"] = f"{tag}{i}"
                out.append(row)
            return out
        left, right = rows(rng.randint(0, 12), "l"), rows(rng.randint(0, 12), "r")
        for how in ("inner", "left"):
            assert mod.join_records(left, right, "k", how=how) == oracle(left, right, "k", how)


def test_large_join_is_not_quadratic():
    n = 20_000
    left = [{"transaction_id": i, "customer_id": i % 15_000} for i in range(n)]
    right = [{"customer_id": c, "segment": c % 7} for c in range(n)]
    t0 = time.perf_counter()
    result = mod.join_records(left, right, "customer_id", how="left")
    elapsed = time.perf_counter() - t0
    assert len(result) == n
    assert result[-1] == {"transaction_id": n - 1, "customer_id": (n - 1) % 15_000, "segment": ((n - 1) % 15_000) % 7}
    assert elapsed < 2.0, f"took {elapsed:.2f}s - expected a near-linear join"
