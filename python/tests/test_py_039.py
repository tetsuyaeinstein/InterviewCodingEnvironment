"""Tests for PY-039 (imports your practice file by default; see _loader.py)."""
import random
import time
from datetime import datetime
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-039")

D = Decimal


def classify(msgs):
    return mod.classify_messages(msgs)


def ids(items):
    return [x.message_id for x in items]


def test_example_from_question():
    res = classify([("m1", {"amount": D("10.0"), "ccy": "EUR"}), ("m2", {"qty": 1}),
                    ("m1", {"ccy": "EUR", "amount": 10}), ("m3", {"qty": 5}), ("m3", {"qty": 6})])
    assert res.unique == [mod.Delivered("m2", {"qty": 1}, 1)]
    assert res.exact_duplicates == [mod.Delivered("m1", {"amount": D("10.0"), "ccy": "EUR"}, 2)]
    assert res.conflicts == [mod.Conflict("m3", ({"qty": 5}, {"qty": 6}), 2)]


def test_empty_and_one_shot_iterator():
    res = classify([])
    assert (res.unique, res.exact_duplicates, res.conflicts) == ([], [], [])
    res = classify(iter([("a", {"x": 1}), ("a", {"x": 1})]))
    assert ids(res.exact_duplicates) == ["a"] and res.exact_duplicates[0].deliveries == 2


def test_key_order_is_irrelevant_at_any_depth_but_list_order_is_not():
    res = classify([("a", {"x": 1, "y": {"p": 1, "q": [1, 2]}}), ("a", {"y": {"q": [1, 2], "p": 1}, "x": 1}),
                    ("b", {"l": [1, 2, 3]}), ("b", {"l": [3, 2, 1]})])
    assert ids(res.exact_duplicates) == ["a"]
    assert ids(res.conflicts) == ["b"]


def test_numbers_compare_by_value_across_int_float_decimal():
    same = [1, 1.0, D("1"), D("1.00"), D("0.1E+1")]
    res = classify([("a", {"v": v}) for v in same])
    assert ids(res.exact_duplicates) == ["a"] and res.exact_duplicates[0].deliveries == 5
    res = classify([("a", {"v": v}) for v in [0.1, D("0.1"), D("0.10")]])
    assert ids(res.exact_duplicates) == ["a"]
    res = classify([("a", {"v": v}) for v in [0, 0.0, -0.0, D("-0"), D("0.00")]])
    assert ids(res.exact_duplicates) == ["a"]
    res = classify([("a", {"v": D("1.10")}), ("a", {"v": D("1.1")}), ("b", {"v": 2}), ("b", {"v": 2.5})])
    assert ids(res.exact_duplicates) == ["a"] and ids(res.conflicts) == ["b"]


def test_large_integers_are_not_confused():
    res = classify([("a", {"v": 10**30}), ("a", {"v": 10**30 + 1})])
    assert ids(res.conflicts) == ["a"]
    res = classify([("a", {"v": 10**30}), ("a", {"v": D(10**30)})])
    assert ids(res.exact_duplicates) == ["a"]


def test_nan_equals_nan_and_infinities_compare_by_sign():
    res = classify([("a", {"v": float("nan")}), ("a", {"v": D("NaN")}), ("b", {"v": float("inf")}), ("b", {"v": float("-inf")})])
    assert ids(res.exact_duplicates) == ["a"] and ids(res.conflicts) == ["b"]


def test_types_that_python_equality_would_merge_are_conflicts():
    for left, right in [(True, 1), (False, 0), (1, "1"), (None, 0), (None, ""), ("", 0), ([], {}), ([1], 1)]:
        res = classify([("a", {"v": left}), ("a", {"v": right})])
        assert ids(res.conflicts) == ["a"], (left, right)
        assert res.exact_duplicates == [] and res.unique == []


def test_none_value_and_missing_key_are_different():
    res = classify([("a", {"x": 1, "y": None}), ("a", {"x": 1})])
    assert ids(res.conflicts) == ["a"]
    res = classify([("a", {"x": None}), ("a", {"x": None})])
    assert ids(res.exact_duplicates) == ["a"]


def test_tuples_are_treated_like_lists():
    res = classify([("a", {"v": (1, 2)}), ("a", {"v": [1, 2]})])
    assert ids(res.exact_duplicates) == ["a"]


def test_strings_are_exact():
    res = classify([("a", {"n": "Ida"}), ("a", {"n": "ida"}), ("b", {"n": "x"}), ("b", {"n": "x "})])
    assert ids(res.conflicts) == ["a", "b"]


def test_conflict_with_three_deliveries_counts_all_and_orders_by_first_arrival():
    res = classify([("a", {"v": "B"}), ("a", {"v": "A"}), ("a", {"v": "B"})])
    (c,) = res.conflicts
    assert c.payloads == ({"v": "B"}, {"v": "A"}) and c.deliveries == 3
    res = classify([("a", {"v": "A"}), ("a", {"v": "B"}), ("a", {"v": "A"}), ("a", {"v": "C"})])
    assert res.conflicts[0].payloads == ({"v": "A"}, {"v": "B"}, {"v": "C"}) and res.conflicts[0].deliveries == 4


def test_each_id_appears_in_exactly_one_group_and_all_lists_are_sorted():
    rng = random.Random(39)
    msgs = [(f"m{rng.randint(0, 40):02d}", {"v": rng.choice([1, 2, D("1.0"), "x"]), "w": rng.choice([None, 0])})
            for _ in range(300)]
    res = classify(msgs)
    all_ids = ids(res.unique) + ids(res.exact_duplicates) + ids(res.conflicts)
    assert len(all_ids) == len(set(all_ids)) == len({m for m, _ in msgs})
    for group in (res.unique, res.exact_duplicates, res.conflicts):
        assert ids(group) == sorted(ids(group))
    assert sum(x.deliveries for x in res.unique + res.exact_duplicates + res.conflicts) == len(msgs)


def test_shuffling_input_does_not_change_the_classification_of_ids():
    rng = random.Random(3939)
    msgs = [(f"m{rng.randint(0, 25)}", {"v": rng.randint(0, 2)}) for _ in range(200)]
    base = classify(msgs)
    for _ in range(5):
        shuffled = msgs[:]
        rng.shuffle(shuffled)
        res = classify(shuffled)
        assert ids(res.unique) == ids(base.unique)
        assert ids(res.exact_duplicates) == ids(base.exact_duplicates)
        assert [(c.message_id, c.deliveries, len(c.payloads)) for c in res.conflicts] == \
               [(c.message_id, c.deliveries, len(c.payloads)) for c in base.conflicts]


def test_result_payloads_are_copies_of_the_first_arrival():
    original = {"v": [1, 2]}
    res = classify([("a", original), ("a", {"v": [1, 2]})])
    assert res.exact_duplicates[0].payload == original
    res.exact_duplicates[0].payload["extra"] = 1
    assert "extra" not in original


@pytest.mark.parametrize("bad, exc", [
    ([("", {"a": 1})], ValueError), ([(None, {"a": 1})], ValueError), ([(5, {"a": 1})], ValueError),
    ([("a", [1])], TypeError), ([("a", None)], TypeError),
    ([("a", {1: "x"})], TypeError), ([("a", {"v": {1, 2}})], TypeError),
    ([("a", {"v": b"x"})], TypeError), ([("a", {"v": datetime(2025, 1, 1)})], TypeError),
    ([("a", {"v": {"deep": [object()]}})], TypeError),
])
def test_invalid_input_raises(bad, exc):
    with pytest.raises(exc):
        classify(bad)


def test_large_input_is_linear_time():
    msgs = []
    for i in range(100_000):
        mid = f"id{i // 2}"
        msgs.append((mid, {"a": i // 2, "tags": ["x", (i // 2) % 7], "meta": {"amt": D("1.50")}}))
    t0 = time.perf_counter()
    res = classify(msgs)
    elapsed = time.perf_counter() - t0
    assert len(res.exact_duplicates) == 50_000 and res.unique == [] and res.conflicts == []
    assert elapsed < 6.0, f"took {elapsed:.2f}s"
