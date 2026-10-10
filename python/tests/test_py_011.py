"""Tests for PY-011 (imports your practice file by default; see _loader.py)."""
import ctypes
import random
import threading
import time
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-011")


def call_with_deadline(fn, seconds=6.0):
    """Run fn(); if it is still running after `seconds`, interrupt it and fail (guards against quadratic runs)."""
    tid = threading.get_ident()

    def interrupt():
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), ctypes.py_object(TimeoutError))

    timer = threading.Timer(seconds, interrupt)
    timer.start()
    try:
        return fn()
    except TimeoutError:
        pytest.fail(f"still running after {seconds:.0f}s - expected a much faster algorithm")
    finally:
        timer.cancel()


def oracle(amounts, target):
    """Brute force over every pair, ordered by the policy key (j, i)."""
    for j in range(len(amounts)):
        for i in range(j):
            if amounts[i] + amounts[j] == target:
                return (i, j)
    return None


@pytest.mark.parametrize("amounts, target, expected", [
    ([1250, 400, 850, 2100], 1250, (1, 2)),
    ([500, 300, 500], 1000, (0, 2)),
    ([500, 300], 1000, None),
    ([300, 700, 600, 400], 1000, (0, 1)),
    ([200, 200, 800], 1000, (0, 2)),
    ([-150, 900, 750], 600, (0, 2)),
])
def test_examples_from_question(amounts, target, expected):
    assert mod.find_refund_pair(amounts, target) == expected


@pytest.mark.parametrize("amounts", [[], [1000], [500]])
def test_empty_and_single_element_return_none(amounts):
    assert mod.find_refund_pair(amounts, 1000) is None


def test_an_index_is_never_used_twice():
    assert mod.find_refund_pair([500], 1000) is None
    assert mod.find_refund_pair([500, 1, 2, 3], 1000) is None
    assert mod.find_refund_pair([0], 0) is None
    assert mod.find_refund_pair([0, 0], 0) == (0, 1)


def test_smallest_second_position_wins_over_earlier_first_position():
    # (0, 4) has the smaller i, but (2, 3) completes at j = 3 < 4.
    assert mod.find_refund_pair([100, 1, 450, 550, 900], 1000) == (2, 3)


def test_smallest_first_position_wins_for_the_same_second_position():
    # Every 250 pairs with the 750 at j = 4; the earliest 250 is i = 0.
    assert mod.find_refund_pair([250, 250, 10, 250, 750], 1000) == (0, 4)
    # Many copies of half the target: the first two copies.
    assert mod.find_refund_pair([7, 500, 3, 500, 500, 500], 1000) == (1, 3)


def test_zero_and_negative_amounts():
    assert mod.find_refund_pair([0, 5, -5], 0) == (1, 2)
    assert mod.find_refund_pair([-300, -700, 50], -1000) == (0, 1)
    assert mod.find_refund_pair([0, 999, 0], 0) == (0, 2)


def test_returns_a_tuple_and_does_not_mutate():
    amounts = [900, 100, 300, 700]
    snapshot = list(amounts)
    result = mod.find_refund_pair(amounts, 1000)
    assert type(result) is tuple and result == (0, 1)
    assert amounts == snapshot
    assert mod.find_refund_pair(tuple(amounts), 1000) == (0, 1)


@pytest.mark.parametrize("target", [True, 10.0, Decimal("10"), "10", None])
def test_non_int_target_raises_type_error(target):
    with pytest.raises(TypeError):
        mod.find_refund_pair([3, 7], target)


def test_matches_brute_force_on_random_inputs():
    rng = random.Random(11)
    for _ in range(600):
        n = rng.randint(0, 20)
        amounts = [rng.randint(-5, 12) for _ in range(n)]     # small range: many duplicates and ties
        target = rng.randint(-6, 20)
        assert mod.find_refund_pair(amounts, target) == oracle(amounts, target), (amounts, target)


def test_large_input_with_match_near_the_end():
    rng = random.Random(5)
    n = 200_000
    amounts = [rng.randrange(0, 10**9) * 2 for _ in range(n)]   # all even
    target = 2 * 10**9 + 1                                      # odd: no even pair can match
    amounts[-3] = 1
    amounts[-1] = target - 1
    t0 = time.perf_counter()
    result = call_with_deadline(lambda: mod.find_refund_pair(amounts, target))
    elapsed = time.perf_counter() - t0
    assert result == (n - 3, n - 1)
    assert elapsed < 2.0, f"took {elapsed:.2f}s - expected better than checking every pair"
