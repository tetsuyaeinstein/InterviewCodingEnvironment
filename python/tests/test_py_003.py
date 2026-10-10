"""Tests for PY-003 (imports your practice file by default; see _loader.py)."""
import random
import time
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-003")

D = Decimal
EXAMPLE = {501: D("80.00"), 502: D("120.00"), 503: D("80.00"), 504: D("15.00"), 505: D("120.00")}


def oracle(spend, k):
    """Selection by repeated scan: pick the best remaining customer k times."""
    remaining = dict(spend)
    out = []
    for _ in range(min(k, len(remaining))):
        best = None
        for cid, amt in remaining.items():
            if best is None or amt > best[1] or (amt == best[1] and cid < best[0]):
                best = (cid, amt)
        out.append(best)
        del remaining[best[0]]
    return out


def test_example_from_question():
    assert mod.top_k_customers(EXAMPLE, 3) == [(502, D("120.00")), (505, D("120.00")), (501, D("80.00"))]
    assert mod.top_k_customers(EXAMPLE, 4) == [(502, D("120.00")), (505, D("120.00")),
                                               (501, D("80.00")), (503, D("80.00"))]


def test_tie_at_the_cut_off_goes_to_lower_id():
    spend = {9: D("50"), 3: D("50"), 7: D("50"), 1: D("10")}
    assert mod.top_k_customers(spend, 2) == [(3, D("50")), (7, D("50"))]


def test_result_independent_of_insertion_order():
    items = [(cid, D(cid % 3)) for cid in range(1, 40)]
    forward = dict(items)
    backward = dict(reversed(items))
    shuffled = dict(random.Random(3).sample(items, len(items)))
    expected = mod.top_k_customers(forward, 10)
    assert expected == oracle(forward, 10)
    assert mod.top_k_customers(backward, 10) == expected
    assert mod.top_k_customers(shuffled, 10) == expected


def test_k_larger_than_customer_count_returns_everyone_ranked():
    assert mod.top_k_customers(EXAMPLE, 100) == oracle(EXAMPLE, 100)
    assert len(mod.top_k_customers(EXAMPLE, 100)) == 5


def test_k_zero_and_empty_mapping():
    assert mod.top_k_customers(EXAMPLE, 0) == []
    assert mod.top_k_customers({}, 5) == []
    assert mod.top_k_customers({}, 0) == []


def test_negative_k_raises_value_error():
    with pytest.raises(ValueError):
        mod.top_k_customers(EXAMPLE, -1)


@pytest.mark.parametrize("k", [True, 2.0, "3", None])
def test_non_int_k_raises_type_error(k):
    with pytest.raises(TypeError):
        mod.top_k_customers(EXAMPLE, k)


def test_zero_and_negative_spend_rank_last():
    spend = {1: D("-5.00"), 2: D("0.00"), 3: D("0.01"), 4: D("-0.01")}
    assert mod.top_k_customers(spend, 4) == [(3, D("0.01")), (2, D("0.00")), (4, D("-0.01")), (1, D("-5.00"))]


def test_returns_tuples_and_does_not_mutate():
    spend = dict(EXAMPLE)
    result = mod.top_k_customers(spend, 2)
    assert all(type(t) is tuple and len(t) == 2 for t in result)
    assert spend == EXAMPLE


def test_matches_oracle_on_random_inputs():
    rng = random.Random(33)
    for _ in range(300):
        n = rng.randint(0, 25)
        ids = rng.sample(range(1, 1000), n)
        spend = {cid: D(rng.randint(-3, 6)) / 2 for cid in ids}   # many ties
        k = rng.randint(0, 30)
        assert mod.top_k_customers(spend, k) == oracle(spend, k), (spend, k)


def test_large_input():
    rng = random.Random(7)
    spend = {cid: D(rng.randint(0, 100_000)) / 100 for cid in rng.sample(range(10_000_000), 300_000)}
    t0 = time.perf_counter()
    result = mod.top_k_customers(spend, 25)
    elapsed = time.perf_counter() - t0
    expected = sorted(spend.items(), key=lambda kv: (-kv[1], kv[0]))[:25]
    assert result == expected
    assert elapsed < 2.0, f"took {elapsed:.2f}s"
