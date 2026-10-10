"""Tests for PY-013 (imports your practice file by default; see _loader.py)."""
import random
from datetime import datetime, timedelta, timezone

import pytest

from _loader import load

mod = load("PY-013")

UTC = timezone.utc


def oracle(intervals):
    """Mark every covered unit cell [t, t+1) on an integer grid, then read off the runs."""
    covered = set()
    for s, e in intervals:
        covered.update(range(s, e))
    out = []
    for t in sorted(covered):
        if out and out[-1][1] == t:
            out[-1] = (out[-1][0], t + 1)
        else:
            out.append((t, t + 1))
    return out


@pytest.mark.parametrize("intervals, expected", [
    ([(1, 3), (2, 6), (8, 10), (15, 18)], [(1, 6), (8, 10), (15, 18)]),
    ([(5, 9), (1, 5)], [(1, 9)]),
    ([(1, 10), (2, 3), (4, 5)], [(1, 10)]),
    ([(1, 4), (6, 6), (6, 9)], [(1, 4), (6, 9)]),
    ([(4, 4)], []),
])
def test_examples_from_question(intervals, expected):
    assert mod.merge_intervals(intervals) == expected


def test_empty_input():
    assert mod.merge_intervals([]) == []


def test_touching_windows_merge_but_a_gap_of_one_keeps_them_apart():
    assert mod.merge_intervals([(1, 5), (5, 9)]) == [(1, 9)]
    assert mod.merge_intervals([(1, 5), (6, 9)]) == [(1, 5), (6, 9)]
    assert mod.merge_intervals([(10, 20), (0, 10), (20, 30)]) == [(0, 30)]


def test_long_window_swallows_several_later_ones():
    intervals = [(0, 100), (10, 20), (30, 40), (99, 100), (50, 60), (100, 101)]
    assert mod.merge_intervals(intervals) == [(0, 101)]
    # a later, shorter window must not shrink the current end
    assert mod.merge_intervals([(0, 50), (1, 2), (60, 70)]) == [(0, 50), (60, 70)]


def test_zero_length_windows_never_bridge_a_gap():
    assert mod.merge_intervals([(1, 5), (6, 6), (7, 9)]) == [(1, 5), (7, 9)]
    assert mod.merge_intervals([(5, 5), (5, 5), (9, 9)]) == []
    assert mod.merge_intervals([(1, 5), (5, 5)]) == [(1, 5)]
    assert mod.merge_intervals([(3, 3), (1, 9)]) == [(1, 9)]


def test_duplicates_and_identical_starts():
    assert mod.merge_intervals([(2, 4), (2, 4), (2, 4)]) == [(2, 4)]
    assert mod.merge_intervals([(2, 8), (2, 3), (2, 5)]) == [(2, 8)]


@pytest.mark.parametrize("bad", [[(3, 1)], [(0, 5), (9, 8)], [(1, 1), (2, 1)]])
def test_start_after_end_raises_value_error(bad):
    with pytest.raises(ValueError):
        mod.merge_intervals(bad)


def test_datetime_windows():
    d = lambda h, m=0: datetime(2025, 3, 30, h, m, tzinfo=UTC)
    midnight = datetime(2025, 3, 31, tzinfo=UTC)
    intervals = [
        (d(23), midnight),                                    # ends exactly at midnight
        (midnight, midnight + timedelta(minutes=15)),         # touches it: one outage
        (d(9, 30), d(10)),
        (d(9), d(9, 30)),
        (d(12), d(12)),                                       # zero-length
        (d(14), d(14, 1)),
    ]
    assert mod.merge_intervals(intervals) == [
        (d(9), d(10)),
        (d(14), d(14, 1)),
        (d(23), midnight + timedelta(minutes=15)),
    ]


def test_accepts_a_generator_and_returns_new_tuples():
    source = [(7, 9), (1, 3), (2, 4)]
    snapshot = list(source)
    result = mod.merge_intervals(w for w in source)
    assert result == [(1, 4), (7, 9)]
    assert all(type(w) is tuple for w in result)
    assert source == snapshot


def test_does_not_mutate_a_list_input():
    source = [(5, 6), (1, 2), (2, 3)]
    snapshot = list(source)
    mod.merge_intervals(source)
    assert source == snapshot


def test_matches_brute_force_on_random_inputs():
    rng = random.Random(13)
    for _ in range(500):
        intervals = []
        for _ in range(rng.randint(0, 12)):
            s = rng.randint(0, 30)
            intervals.append((s, s + rng.choice([0, 0, 1, 1, 2, 3, 5, 8])))
        assert mod.merge_intervals(intervals) == oracle(intervals), intervals
