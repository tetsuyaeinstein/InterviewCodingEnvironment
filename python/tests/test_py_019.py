"""Tests for PY-019 (imports your practice file by default; see _loader.py)."""
import ctypes
import random
import threading
import time

import pytest

from _loader import load

mod = load("PY-019")


def call_with_deadline(fn, seconds=6.0):
    """Run fn(); if it is still running after `seconds`, interrupt it and fail (guards against O(n*k) runs)."""
    tid = threading.get_ident()

    def interrupt():
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), ctypes.py_object(TimeoutError))

    timer = threading.Timer(seconds, interrupt)
    timer.start()
    try:
        return fn()
    except TimeoutError:
        pytest.fail(f"still running after {seconds:.0f}s - expected an O(n) or O(n log n) algorithm")
    finally:
        timer.cancel()


def oracle(values, k):
    """Brute force: slice and take the max of every window."""
    return [max(values[i:i + k]) for i in range(len(values) - k + 1)]


@pytest.mark.parametrize("values, k, expected", [
    ([1, 3, -1, -3, 5, 3, 6, 7], 3, [3, 3, 5, 5, 6, 7]),
    ([4, 2, 12, 3], 1, [4, 2, 12, 3]),
    ([4, 2, 12, 3], 4, [12]),
    ([4, 2, 12, 3], 5, []),
    ([-5, -2, -9], 2, [-2, -2]),
    ([7, 7, 7], 2, [7, 7]),
    ([], 3, []),
])
def test_examples_from_question(values, k, expected):
    assert mod.sliding_window_max(values, k) == expected


@pytest.mark.parametrize("k", [0, -1, -7])
def test_k_below_one_raises_value_error(k):
    with pytest.raises(ValueError):
        mod.sliding_window_max([1, 2, 3], k)
    with pytest.raises(ValueError):
        mod.sliding_window_max([], k)


@pytest.mark.parametrize("k", [True, 2.0, "2", None])
def test_non_int_k_raises_type_error(k):
    with pytest.raises(TypeError):
        mod.sliding_window_max([1, 2, 3], k)
    with pytest.raises(TypeError):
        mod.sliding_window_max([], k)


def test_k_larger_than_data_returns_empty_list():
    assert mod.sliding_window_max([1, 2], 3) == []
    assert mod.sliding_window_max([5], 2) == []
    assert mod.sliding_window_max([], 1) == []


def test_window_covering_all_data_and_single_element():
    assert mod.sliding_window_max([5], 1) == [5]
    assert mod.sliding_window_max([2, 9, 4], 3) == [9]


def test_duplicate_maximum_survives_when_the_first_copy_expires():
    assert mod.sliding_window_max([5, 1, 5, 1, 1], 3) == [5, 5, 5]
    assert mod.sliding_window_max([9, 9, 1, 1], 2) == [9, 9, 1]
    assert mod.sliding_window_max([3, 3, 3, 3], 3) == [3, 3]
    assert mod.sliding_window_max([4, 1, 4, 0, 0, 0], 4) == [4, 4, 4]


def test_monotonic_inputs():
    up = list(range(10))
    down = list(range(10, 0, -1))
    assert mod.sliding_window_max(up, 4) == [3, 4, 5, 6, 7, 8, 9]
    assert mod.sliding_window_max(down, 4) == [10, 9, 8, 7, 6, 5, 4]


def test_negative_and_mixed_values():
    assert mod.sliding_window_max([-8, -3, -5, -1, -9], 3) == [-3, -1, -1]
    assert mod.sliding_window_max([0, -1, 0, -2], 2) == [0, 0, 0]


def test_returns_a_new_list_and_does_not_mutate():
    values = [2, 1, 4, 3]
    snapshot = list(values)
    result = mod.sliding_window_max(values, 2)
    assert result == [2, 4, 4] and type(result) is list
    assert values == snapshot
    assert mod.sliding_window_max(tuple(values), 2) == [2, 4, 4]


def test_matches_brute_force_on_random_inputs():
    rng = random.Random(19)
    for _ in range(600):
        n = rng.randint(0, 25)
        values = [rng.randint(-6, 6) for _ in range(n)]
        k = rng.randint(1, 30)
        expected = oracle(values, k) if k <= n else []
        assert mod.sliding_window_max(values, k) == expected, (values, k)


@pytest.mark.parametrize("shape", ["random", "increasing", "decreasing", "constant"])
def test_large_input_runs_fast(shape):
    rng = random.Random(2)
    n, k = 300_000, 2_000
    if shape == "random":
        values = [rng.randint(-10**6, 10**6) for _ in range(n)]
    elif shape == "increasing":
        values = list(range(n))
    elif shape == "decreasing":
        values = list(range(n, 0, -1))
    else:
        values = [7] * n
    t0 = time.perf_counter()
    result = call_with_deadline(lambda: mod.sliding_window_max(values, k))
    elapsed = time.perf_counter() - t0
    assert len(result) == n - k + 1
    # spot checks against direct slicing at a few positions (cheap, independent of the method)
    for i in (0, 1, 1_999, 2_000, 54_321, n - k):
        assert result[i] == max(values[i:i + k]), i
    assert elapsed < 2.0, f"took {elapsed:.2f}s - cost per window must not grow with k"
