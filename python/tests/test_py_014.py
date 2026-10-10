"""Tests for PY-014 (imports your practice file by default; see _loader.py)."""
import random
import time

import pytest

from _loader import load

mod = load("PY-014")

EXAMPLE = ["B-7", "C-3", "A-1", "B-7", "A-1", None, "D-9", "C-3", "B-7"]


def oracle(skus, k):
    """Count by hand, then pick the best remaining SKU k times with an explicit comparison."""
    counts = {}
    for s in skus:
        if s is not None:
            counts[s] = counts.get(s, 0) + 1
    out = []
    for _ in range(min(k, len(counts))):
        best = None
        for sku, c in counts.items():
            if best is None or c > best[1] or (c == best[1] and sku < best[0]):
                best = (sku, c)
        out.append(best)
        del counts[best[0]]
    return out


def exploding_stream():
    raise AssertionError("the stream was read before k was validated")
    yield  # pragma: no cover  (makes this a generator)


@pytest.mark.parametrize("k, expected", [
    (1, [("B-7", 3)]),
    (2, [("B-7", 3), ("A-1", 2)]),
    (3, [("B-7", 3), ("A-1", 2), ("C-3", 2)]),
    (10, [("B-7", 3), ("A-1", 2), ("C-3", 2), ("D-9", 1)]),
    (0, []),
])
def test_examples_from_question(k, expected):
    assert mod.top_k_frequent(EXAMPLE, k) == expected


def test_ties_ignore_first_seen_order():
    # first seen order: z, y, x ... all tied on 2
    skus = ["z", "y", "x", "x", "y", "z", "w"]
    assert mod.top_k_frequent(skus, 2) == [("x", 2), ("y", 2)]
    assert mod.top_k_frequent(list(reversed(skus)), 2) == [("x", 2), ("y", 2)]


def test_tie_at_the_cut_off_is_broken_by_sku():
    skus = ["m"] * 5 + ["q"] * 3 + ["c"] * 3 + ["k"] * 3 + ["a"]
    assert mod.top_k_frequent(skus, 3) == [("m", 5), ("c", 3), ("k", 3)]


def test_none_entries_are_ignored():
    assert mod.top_k_frequent([None, None, "X", None], 5) == [("X", 1)]
    assert mod.top_k_frequent([None, None], 3) == []


def test_empty_stream():
    assert mod.top_k_frequent([], 3) == []
    assert mod.top_k_frequent(iter([]), 0) == []


def test_codes_are_case_sensitive_and_not_trimmed():
    skus = ["sku-1", "SKU-1", "sku-1", "sku-1 ", "SKU-1"]
    assert mod.top_k_frequent(skus, 5) == [("SKU-1", 2), ("sku-1", 2), ("sku-1 ", 1)]


def test_stream_is_read_only_once():
    gen = (s for s in EXAMPLE)
    assert mod.top_k_frequent(gen, 2) == [("B-7", 3), ("A-1", 2)]


def test_returns_tuples_with_int_counts():
    result = mod.top_k_frequent(EXAMPLE, 4)
    assert all(type(t) is tuple and len(t) == 2 and type(t[1]) is int for t in result)


def test_negative_k_raises_value_error_before_reading():
    with pytest.raises(ValueError):
        mod.top_k_frequent(exploding_stream(), -1)
    with pytest.raises(ValueError):
        mod.top_k_frequent([], -3)


@pytest.mark.parametrize("k", [True, False, 2.0, "3", None])
def test_non_int_k_raises_type_error_before_reading(k):
    with pytest.raises(TypeError):
        mod.top_k_frequent(exploding_stream(), k)


def test_matches_oracle_on_random_inputs():
    rng = random.Random(14)
    alphabet = ["A", "B", "C", "D", "E", "F", "G", "a", "b", "AA", None]
    for _ in range(400):
        skus = [rng.choice(alphabet) for _ in range(rng.randint(0, 30))]
        k = rng.randint(0, 12)
        assert mod.top_k_frequent(skus, k) == oracle(skus, k), (skus, k)


def test_large_stream():
    rng = random.Random(4)
    n_skus = 100_000
    names = [f"SKU-{i:06d}" for i in range(n_skus)]
    skus = [names[min(int(rng.paretovariate(1.2)) - 1, n_skus - 1)] if rng.random() < 0.5
            else rng.choice(names) for _ in range(1_000_000)]
    t0 = time.perf_counter()
    result = mod.top_k_frequent(iter(skus), 20)
    elapsed = time.perf_counter() - t0
    counts = {}
    for s in skus:
        counts[s] = counts.get(s, 0) + 1
    expected = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
    assert result == expected
    assert elapsed < 2.0, f"took {elapsed:.2f}s"
