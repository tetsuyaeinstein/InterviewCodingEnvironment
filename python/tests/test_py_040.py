"""Tests for PY-040 (imports your practice file by default; see _loader.py)."""
import random
import time
from datetime import date, datetime, timedelta

import pytest

from _loader import load

mod = load("PY-040")

ONE = timedelta(days=1)


def jan(day):
    return date(2025, 1, day)


def oracle_runs(days):
    """From-scratch recomputation: sort the set of days and split at gaps."""
    runs = []
    for d in sorted(days):
        if runs and runs[-1][1] + ONE == d:
            runs[-1][1] = d
        else:
            runs.append([d, d])
    return [(a, b) for a, b in runs]


def oracle_current(days, as_of):
    eligible = sorted(d for d in days if d <= as_of)
    if not eligible:
        return 0
    last = eligible[-1]
    if last < as_of - ONE:
        return 0
    n = 1
    i = len(eligible) - 1
    while i > 0 and eligible[i - 1] == eligible[i] - ONE:
        n += 1
        i -= 1
    return n


def length(run):
    return (run[1] - run[0]).days + 1


def test_example_from_question():
    t = mod.StreakTracker()
    steps = [(5, "new", (), (5, 5)), (7, "new", (), (7, 7)), (6, "bridge", ((5, 5), (7, 7)), (5, 7)),
             (6, "duplicate", ((5, 7),), (5, 7)), (8, "extend", ((5, 7),), (5, 8)), (3, "new", (), (3, 3)),
             (4, "bridge", ((3, 3), (5, 8)), (3, 8))]
    for day, kind, before, after in steps:
        ch = t.add_purchase("c", jan(day))
        assert ch == mod.StreakChange(kind, tuple((jan(a), jan(b)) for a, b in before), (jan(after[0]), jan(after[1])))
    assert t.streaks("c") == [(jan(3), jan(8))]
    assert t.longest_streak("c") == 6
    assert [t.current_streak("c", jan(d)) for d in (8, 9, 10, 5, 2, 3)] == [6, 6, 0, 3, 0, 1]


def test_unknown_customer_and_queries_do_not_create_state():
    t = mod.StreakTracker()
    assert t.streaks("nobody") == [] and t.longest_streak("nobody") == 0 and t.current_streak("nobody", jan(1)) == 0
    t.add_purchase("a", jan(1))
    assert t.streaks("nobody") == []


def test_customers_are_independent():
    t = mod.StreakTracker()
    for d in (1, 2, 3):
        t.add_purchase("a", jan(d))
    t.add_purchase("b", jan(2))
    assert t.streaks("a") == [(jan(1), jan(3))] and t.streaks("b") == [(jan(2), jan(2))]
    assert (t.longest_streak("a"), t.longest_streak("b")) == (3, 1)
    assert t.add_purchase("b", jan(3)).kind == "extend" and t.longest_streak("a") == 3


def test_extend_on_either_side_and_new_run_between():
    t = mod.StreakTracker()
    t.add_purchase("c", jan(10))
    assert t.add_purchase("c", jan(11)).kind == "extend"      # after the end
    ch = t.add_purchase("c", jan(9))                          # before the start
    assert ch == mod.StreakChange("extend", ((jan(10), jan(11)),), (jan(9), jan(11)))
    assert t.add_purchase("c", jan(20)).kind == "new"
    assert t.add_purchase("c", jan(13)).kind == "new"         # gap of one day on the left
    assert t.streaks("c") == [(jan(9), jan(11)), (jan(13), jan(13)), (jan(20), jan(20))]


def test_duplicates_change_nothing_anywhere_in_a_run():
    t = mod.StreakTracker()
    for d in (1, 2, 3, 4):
        t.add_purchase("c", jan(d))
    for d in (1, 2, 3, 4, 2):
        ch = t.add_purchase("c", jan(d))
        assert ch == mod.StreakChange("duplicate", ((jan(1), jan(4)),), (jan(1), jan(4)))
    assert t.streaks("c") == [(jan(1), jan(4))] and t.longest_streak("c") == 4


def test_late_day_far_in_the_past_and_the_same_day_twice_in_a_row():
    t = mod.StreakTracker()
    t.add_purchase("c", jan(20))
    assert t.add_purchase("c", date(2020, 1, 1)).kind == "new"
    assert t.add_purchase("c", date(2020, 1, 1)).kind == "duplicate"
    assert t.streaks("c") == [(date(2020, 1, 1), date(2020, 1, 1)), (jan(20), jan(20))]


def test_longest_streak_survives_a_shorter_current_run_and_jumps_on_a_bridge():
    t = mod.StreakTracker()
    for d in (1, 2, 3, 4):
        t.add_purchase("c", jan(d))
    for d in (10, 11):
        t.add_purchase("c", jan(d))
    assert t.longest_streak("c") == 4
    for d in (5, 6, 7, 8):
        t.add_purchase("c", jan(d))
    assert t.longest_streak("c") == 8                          # 1..8 (10..11 is separate)
    t.add_purchase("c", jan(9))
    assert t.longest_streak("c") == 11


def test_leap_day_month_and_year_boundaries():
    t = mod.StreakTracker()
    t.add_purchase("c", date(2024, 2, 28))
    t.add_purchase("c", date(2024, 3, 1))
    ch = t.add_purchase("c", date(2024, 2, 29))
    assert ch.kind == "bridge" and ch.after == (date(2024, 2, 28), date(2024, 3, 1))
    t.add_purchase("c", date(2024, 12, 31))
    assert t.add_purchase("c", date(2025, 1, 1)).kind == "extend"
    assert t.add_purchase("c", date(2023, 2, 28)).kind == "new"
    assert t.add_purchase("c", date(2023, 3, 1)).kind == "extend"      # 2023 has no Feb 29: 28th and 1st are adjacent
    assert t.add_purchase("c", date(2023, 3, 3)).kind == "new"
    assert len(t.streaks("c")) == 4


def test_calendar_limits_do_not_overflow():
    t = mod.StreakTracker()
    assert t.add_purchase("c", date.max).kind == "new"
    assert t.add_purchase("c", date.max - ONE).kind == "extend"
    assert t.add_purchase("c", date.min).kind == "new"
    assert t.add_purchase("c", date.min + ONE).kind == "extend"
    assert t.streaks("c") == [(date.min, date.min + ONE), (date.max - ONE, date.max)]
    assert t.current_streak("c", date.max) == 2 and t.current_streak("c", date.min) == 1


def test_current_streak_alive_broken_and_truncated_at_as_of():
    t = mod.StreakTracker()
    for d in (1, 2, 3, 5, 6):
        t.add_purchase("c", jan(d))
    assert [t.current_streak("c", date(2024, 12, 31))] == [0]       # before every purchase
    assert [t.current_streak("c", jan(d)) for d in range(1, 10)] == [1, 2, 3, 3, 1, 2, 2, 0, 0]
    assert t.current_streak("c", jan(7)) == 2                       # run 5..6 ended yesterday: alive
    assert t.current_streak("c", jan(8)) == 0


def test_current_streak_ignores_purchases_after_as_of_even_when_they_arrive_later():
    t = mod.StreakTracker()
    t.add_purchase("c", jan(1))
    t.add_purchase("c", jan(10))
    assert t.current_streak("c", jan(2)) == 1
    t.add_purchase("c", jan(2))
    assert t.current_streak("c", jan(2)) == 2 and t.current_streak("c", jan(3)) == 2


@pytest.mark.parametrize("call", [
    lambda t: t.add_purchase("c", datetime(2025, 1, 1, 12)),
    lambda t: t.add_purchase("c", "2025-01-01"),
    lambda t: t.add_purchase("c", None),
    lambda t: t.current_streak("c", datetime(2025, 1, 1)),
    lambda t: t.current_streak("c", 20250101),
])
def test_only_plain_dates_are_accepted(call):
    t = mod.StreakTracker()
    t.add_purchase("c", jan(1))
    with pytest.raises(TypeError):
        call(t)
    assert t.streaks("c") == [(jan(1), jan(1))]


def test_matches_from_scratch_recomputation_and_every_change_agrees_with_the_oracle():
    rng = random.Random(40)
    base = date(2025, 1, 1)
    for _ in range(300):
        t = mod.StreakTracker()
        days = {"a": set(), "b": set()}
        for _ in range(rng.randint(1, 60)):
            cust = rng.choice("ab")
            d = base + timedelta(days=rng.randint(0, 30))
            before_runs = oracle_runs(days[cust])
            already = d in days[cust]
            days[cust].add(d)
            after_runs = oracle_runs(days[cust])
            ch = t.add_purchase(cust, d)
            removed = [r for r in before_runs if r not in after_runs]
            added = [r for r in after_runs if r not in before_runs]
            if already:
                assert ch.kind == "duplicate" and removed == [] and added == []
                assert len(ch.before) == 1 and ch.before[0] == ch.after and ch.after[0] <= d <= ch.after[1]
            else:
                assert len(added) == 1 and ch.after == added[0]
                assert list(ch.before) == removed
                assert ch.kind == {0: "new", 1: "extend", 2: "bridge"}[len(removed)]
            assert t.streaks(cust) == after_runs
            assert t.longest_streak(cust) == max(length(r) for r in after_runs)
        for cust in "ab":
            for off in range(-2, 34):
                as_of = base + timedelta(days=off)
                assert t.current_streak(cust, as_of) == oracle_current(days[cust], as_of), (cust, as_of)


def test_arrival_order_never_matters():
    rng = random.Random(4040)
    days = [date(2025, 1, 1) + timedelta(days=rng.randint(0, 80)) for _ in range(120)]
    expected = oracle_runs(set(days))
    for _ in range(10):
        rng.shuffle(days)
        t = mod.StreakTracker()
        for d in days:
            t.add_purchase("c", d)
        assert t.streaks("c") == expected and t.longest_streak("c") == max(length(r) for r in expected)


def test_large_history_with_late_days_does_not_recompute_everything():
    rng = random.Random(1)
    t = mod.StreakTracker()
    start = date(2000, 1, 1).toordinal()
    consecutive = list(range(start, start + 100_000))
    isolated = [start + 1_000_000 + 2 * i for i in range(30_000)]      # every other day: 30k separate runs
    stream = consecutive + isolated
    rng.shuffle(stream)
    t0 = time.perf_counter()
    for n, o in enumerate(stream):
        t.add_purchase("big", date.fromordinal(o))
        if n % 1000 == 0:
            t.current_streak("big", date.fromordinal(start + 5))
            t.longest_streak("big")
            assert time.perf_counter() - t0 < 8.0, "too slow: are you re-scanning the history?"
    elapsed = time.perf_counter() - t0
    runs = t.streaks("big")
    assert runs[0] == (date.fromordinal(start), date.fromordinal(start + 99_999))
    assert len(runs) == 1 + 30_000 and t.longest_streak("big") == 100_000
    assert elapsed < 8.0, f"took {elapsed:.2f}s: are you re-scanning the history?"
