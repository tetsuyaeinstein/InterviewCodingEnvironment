"""Tests for PY-016 (imports your practice file by default; see _loader.py)."""
import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from _loader import load

mod = load("PY-016")

UTC = timezone.utc


class CountingSeq:
    """Read-only sequence that counts element reads and forbids iteration or slicing."""

    def __init__(self, data):
        self._data = list(data)
        self.reads = 0

    def __len__(self):
        return len(self._data)

    def __getitem__(self, i):
        if not isinstance(i, int):
            raise TypeError("slicing is not allowed")
        if not -len(self._data) <= i < len(self._data):
            raise IndexError(i)
        self.reads += 1
        return self._data[i]

    def __iter__(self):
        raise AssertionError("iterating over the sequence is not allowed")


def oracle(seq, target):
    for i, v in enumerate(seq):
        if v >= target:
            return i
    return len(seq)


@pytest.mark.parametrize("target, expected", [(20, 1), (25, 4), (5, 0), (31, 5), (10, 0), (30, 4), (21, 4)])
def test_examples_from_question(target, expected):
    assert mod.first_at_or_after([10, 20, 20, 20, 30], target) == expected


def test_empty_and_single_element():
    assert mod.first_at_or_after([], 7) == 0
    assert mod.first_at_or_after([5], 5) == 0
    assert mod.first_at_or_after([5], 4) == 0
    assert mod.first_at_or_after([5], 6) == 1


def test_first_of_a_long_run_of_duplicates():
    seq = [1, 2] + [7] * 50 + [9]
    assert mod.first_at_or_after(seq, 7) == 2
    assert mod.first_at_or_after([7] * 10, 7) == 0
    assert mod.first_at_or_after([7] * 10, 8) == 10


def test_all_smaller_returns_len():
    assert mod.first_at_or_after([1, 2, 3, 4], 100) == 4


def test_works_on_strings_and_tuples():
    assert mod.first_at_or_after(["a", "c", "c", "e"], "c") == 1
    assert mod.first_at_or_after(["a", "c", "c", "e"], "d") == 3
    assert mod.first_at_or_after([(1, "a"), (1, "b"), (2, "a")], (1, "b")) == 1


def test_datetimes_with_duplicates_at_the_cutoff():
    t = lambda h, m=0: datetime(2025, 6, 1, h, m, tzinfo=UTC)
    seq = [t(9), t(13, 59), t(14), t(14), t(14, 0) + timedelta(seconds=1), t(18)]
    assert mod.first_at_or_after(seq, t(14)) == 2
    assert mod.first_at_or_after(seq, t(14) + timedelta(microseconds=1)) == 4
    assert mod.first_at_or_after(seq, t(18, 1)) == 6
    assert mod.first_at_or_after(seq, t(0)) == 0


def test_does_not_mutate_and_accepts_tuples_and_ranges():
    data = [1, 3, 3, 5]
    mod.first_at_or_after(data, 3)
    assert data == [1, 3, 3, 5]
    assert mod.first_at_or_after(tuple(data), 4) == 3
    assert mod.first_at_or_after(range(0, 100, 10), 35) == 4


def test_matches_linear_scan_on_random_inputs():
    rng = random.Random(16)
    for _ in range(800):
        seq = sorted(rng.randint(0, 15) for _ in range(rng.randint(0, 20)))
        target = rng.randint(-2, 17)
        assert mod.first_at_or_after(seq, target) == oracle(seq, target), (seq, target)


def test_only_len_and_indexing_are_used():
    seq = CountingSeq([1, 2, 2, 3, 5, 8])
    assert mod.first_at_or_after(seq, 2) == 1
    assert mod.first_at_or_after(seq, 9) == 6


@pytest.mark.parametrize("target", [-5, 0, 333_333, 500_000, 999_999, 2_000_000])
def test_reads_are_logarithmic(target):
    n = 1_000_000
    data = [2 * (i // 2) for i in range(n)]           # sorted, every value twice
    seq = CountingSeq(data)
    result = mod.first_at_or_after(seq, target)
    assert result == oracle_fast(data, target)
    limit = 2 * math.log2(n) + 5
    assert seq.reads <= limit, f"{seq.reads} reads for n={n} (limit {limit:.0f}); expected O(log n)"


def oracle_fast(data, target):
    """Independent O(log n) reference written differently from the solutions (value-halving walk)."""
    step, pos = 1 << (len(data).bit_length()), 0
    while step:
        nxt = pos + step
        if nxt <= len(data) and data[nxt - 1] < target:
            pos = nxt
        step >>= 1
    return pos
