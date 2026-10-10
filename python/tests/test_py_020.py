"""Tests for PY-020 (imports your practice file by default; see _loader.py)."""
import ctypes
import random
import threading
import time
from datetime import date, datetime, timedelta, timezone

import pytest

from _loader import load

mod = load("PY-020")

UTC = timezone.utc
D = date
C = "COMPLETED"


def call_with_deadline(fn, seconds=6.0):
    """Run fn(); if it is still running after `seconds`, interrupt it and fail."""
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


def rec(customer, day, status=C, hour=12, minute=0, tz=UTC):
    """Record whose local wall-clock time is `day` at hour:minute in tz."""
    return (customer, datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz), status)


def days(customer, start, n, **kw):
    return [rec(customer, start + timedelta(days=i), **kw) for i in range(n)]


def oracle(records, min_days):
    """Independent brute force: mark ordinals on a number line, then read maximal runs."""
    per = {}
    for cid, ts, status in records:
        if status == "COMPLETED" and cid is not None:
            per.setdefault(cid, set()).add(ts.astimezone(UTC).date().toordinal())
    out = {}
    for cid in sorted(per):
        marked = per[cid]
        lo, hi = min(marked), max(marked)
        runs, run_start = [], None
        for o in range(lo, hi + 2):
            if o in marked:
                if run_start is None:
                    run_start = o
            elif run_start is not None:
                if o - run_start >= min_days:
                    runs.append((D.fromordinal(run_start), D.fromordinal(o - 1), o - run_start))
                run_start = None
        if runs:
            out[cid] = runs
    return out


def test_example_table_from_question():
    records = (
        days(501, D(2025, 3, 1), 5) + [rec(501, D(2025, 3, 2), hour=18)]
        + [rec(502, D(2025, 3, d)) for d in (1, 2, 3, 4, 6, 7)]
        + [rec(503, D(2024, 12, 30)), rec(503, D(2024, 12, 31)), rec(503, D(2025, 1, 1)),
           rec(503, D(2025, 1, 2)), rec(503, D(2025, 1, 3))]
        + days(504, D(2025, 3, 1), 5) + days(504, D(2025, 3, 20), 7)
    )
    assert mod.find_purchase_streaks(records) == {
        501: [(D(2025, 3, 1), D(2025, 3, 5), 5)],
        503: [(D(2024, 12, 30), D(2025, 1, 3), 5)],
        504: [(D(2025, 3, 1), D(2025, 3, 5), 5), (D(2025, 3, 20), D(2025, 3, 26), 7)],
    }


def test_exactly_four_days_is_not_a_streak_and_five_is():
    assert mod.find_purchase_streaks(days(1, D(2025, 5, 10), 4)) == {}
    assert mod.find_purchase_streaks(days(1, D(2025, 5, 10), 5)) == {1: [(D(2025, 5, 10), D(2025, 5, 14), 5)]}


def test_many_purchases_on_one_day_do_not_inflate_the_run():
    records = [rec(7, D(2025, 5, 1), hour=h) for h in range(8, 20)]
    records += days(7, D(2025, 5, 2), 3)                  # 4 distinct days in total
    assert mod.find_purchase_streaks(records) == {}
    records += [rec(7, D(2025, 5, 5), hour=h) for h in range(8, 12)]   # still 5th day only once
    assert mod.find_purchase_streaks(records) == {7: [(D(2025, 5, 1), D(2025, 5, 5), 5)]}


def test_run_across_a_month_end():
    assert mod.find_purchase_streaks(days(2, D(2025, 1, 29), 5)) == {2: [(D(2025, 1, 29), D(2025, 2, 2), 5)]}
    assert mod.find_purchase_streaks(days(2, D(2025, 4, 28), 5)) == {2: [(D(2025, 4, 28), D(2025, 5, 2), 5)]}


def test_run_across_a_year_end():
    assert mod.find_purchase_streaks(days(3, D(2024, 12, 29), 6)) == {3: [(D(2024, 12, 29), D(2025, 1, 3), 6)]}


def test_leap_day_is_a_real_day_but_feb_29_2025_does_not_exist():
    assert mod.find_purchase_streaks(days(4, D(2024, 2, 27), 5)) == {4: [(D(2024, 2, 27), D(2024, 3, 2), 5)]}
    # same calendar dates in a non-leap year: Feb 28 is followed directly by Mar 1
    assert mod.find_purchase_streaks(days(4, D(2025, 2, 27), 4)) == {}
    assert mod.find_purchase_streaks(days(4, D(2025, 2, 27), 5)) == {4: [(D(2025, 2, 27), D(2025, 3, 3), 5)]}
    # skipping Feb 29 in a leap year breaks the run
    gap = [rec(4, d) for d in (D(2024, 2, 26), D(2024, 2, 27), D(2024, 2, 28), D(2024, 3, 1), D(2024, 3, 2))]
    assert mod.find_purchase_streaks(gap) == {}


@pytest.mark.parametrize("status", ["CANCELLED", "PENDING", "completed", "", "REFUNDED"])
def test_only_exact_completed_status_counts_and_other_status_breaks_the_run(status):
    records = days(5, D(2025, 6, 1), 5)
    records[2] = rec(5, D(2025, 6, 3), status=status)          # the middle day is not a purchase day
    assert mod.find_purchase_streaks(records) == {}
    records.append(rec(5, D(2025, 6, 3)))                      # a valid purchase on that day restores it
    assert mod.find_purchase_streaks(records) == {5: [(D(2025, 6, 1), D(2025, 6, 5), 5)]}


def test_cancelled_extra_row_on_a_completed_day_changes_nothing():
    records = days(5, D(2025, 6, 1), 5) + [rec(5, D(2025, 6, 3), status="CANCELLED")]
    assert mod.find_purchase_streaks(records) == {5: [(D(2025, 6, 1), D(2025, 6, 5), 5)]}


def test_two_disjoint_streaks_are_both_reported_in_order():
    records = days(6, D(2025, 8, 20), 6) + days(6, D(2025, 7, 1), 5)      # later run supplied first
    assert mod.find_purchase_streaks(records) == {
        6: [(D(2025, 7, 1), D(2025, 7, 5), 5), (D(2025, 8, 20), D(2025, 8, 25), 6)]}


def test_a_long_run_is_one_maximal_streak():
    assert mod.find_purchase_streaks(days(8, D(2025, 9, 1), 12)) == {8: [(D(2025, 9, 1), D(2025, 9, 12), 12)]}


def test_run_with_a_one_day_gap_splits_into_two_short_runs():
    records = days(9, D(2025, 9, 1), 4) + days(9, D(2025, 9, 6), 4)
    assert mod.find_purchase_streaks(records) == {}
    assert mod.find_purchase_streaks(records, min_days=4) == {
        9: [(D(2025, 9, 1), D(2025, 9, 4), 4), (D(2025, 9, 6), D(2025, 9, 9), 4)]}


@pytest.mark.parametrize("min_days, expected_lengths", [(1, [1, 3]), (2, [3]), (3, [3]), (4, [])])
def test_min_days_parameter(min_days, expected_lengths):
    records = [rec(1, D(2025, 1, 1))] + days(1, D(2025, 1, 10), 3)
    got = mod.find_purchase_streaks(records, min_days=min_days)
    assert [s[2] for s in got.get(1, [])] == expected_lengths


def test_business_date_is_the_utc_date():
    est = timezone(timedelta(hours=-5))
    jst = timezone(timedelta(hours=9))
    # 23:30 at UTC-5 on Mar 1..5 is 04:30 UTC on Mar 2..6; 01:00 at UTC+9 on Mar 3 is 16:00 UTC on Mar 2
    records = [rec(10, D(2025, 3, d), hour=23, minute=30, tz=est) for d in range(1, 6)]
    assert mod.find_purchase_streaks(records) == {10: [(D(2025, 3, 2), D(2025, 3, 6), 5)]}
    # Mar 7 01:00 at UTC+9 is Mar 6 16:00 UTC: the same business date as the Mar 6 purchase, so still 4 days
    records = days(11, D(2025, 3, 3), 4) + [rec(11, D(2025, 3, 7), hour=1, tz=jst)]
    assert mod.find_purchase_streaks(records) == {}
    # Mar 9 01:00 at UTC+9 is Mar 8 16:00 UTC: with Mar 3..7 that makes one run of 6 (3..8)
    records = days(11, D(2025, 3, 3), 5) + [rec(11, D(2025, 3, 9), hour=1, tz=jst)]
    assert mod.find_purchase_streaks(records) == {11: [(D(2025, 3, 3), D(2025, 3, 8), 6)]}


def test_midnight_utc_boundaries():
    records = [(12, datetime(2025, 3, d, 23, 59, 59, tzinfo=UTC), C) for d in (1, 2, 3)]
    records += [(12, datetime(2025, 3, 4, 0, 0, 0, tzinfo=UTC), C), (12, datetime(2025, 3, 5, 0, 0, 1, tzinfo=UTC), C)]
    assert mod.find_purchase_streaks(records) == {12: [(D(2025, 3, 1), D(2025, 3, 5), 5)]}


def test_guests_are_ignored():
    records = days(None, D(2025, 3, 1), 10) + days(13, D(2025, 3, 1), 5)
    assert mod.find_purchase_streaks(records) == {13: [(D(2025, 3, 1), D(2025, 3, 5), 5)]}
    assert mod.find_purchase_streaks(days(None, D(2025, 3, 1), 10)) == {}


def test_empty_input_and_dict_order():
    assert mod.find_purchase_streaks([]) == {}
    records = days(30, D(2025, 3, 1), 5) + days(10, D(2025, 3, 1), 5) + days(20, D(2025, 3, 1), 5)
    assert list(mod.find_purchase_streaks(records)) == [10, 20, 30]


def test_result_types_and_input_is_read_once():
    records = days(1, D(2025, 3, 1), 5)
    result = mod.find_purchase_streaks(r for r in records)
    (start, end, length), = result[1]
    assert type(start) is date and type(end) is date and type(length) is int
    assert type(result[1][0]) is tuple and type(result) is dict


def test_unordered_input():
    records = days(1, D(2025, 3, 1), 7)
    random.Random(20).shuffle(records)
    assert mod.find_purchase_streaks(records) == {1: [(D(2025, 3, 1), D(2025, 3, 7), 7)]}


def test_naive_datetime_raises_value_error():
    with pytest.raises(ValueError):
        mod.find_purchase_streaks([(1, datetime(2025, 3, 1, 12, 0), C)])


@pytest.mark.parametrize("min_days", [0, -1])
def test_min_days_below_one_raises_value_error(min_days):
    with pytest.raises(ValueError):
        mod.find_purchase_streaks([], min_days=min_days)


@pytest.mark.parametrize("min_days", [True, 5.0, "5", None])
def test_non_int_min_days_raises_type_error(min_days):
    with pytest.raises(TypeError):
        mod.find_purchase_streaks([], min_days=min_days)


def test_matches_brute_force_on_random_inputs():
    rng = random.Random(2020)
    zones = [UTC, timezone(timedelta(hours=-8)), timezone(timedelta(hours=9)), timezone(timedelta(hours=5, minutes=30))]
    statuses = [C, C, C, "CANCELLED", "PENDING"]
    base = datetime(2024, 2, 20, tzinfo=UTC)
    for _ in range(300):
        records = []
        for _ in range(rng.randint(0, 60)):
            cid = rng.choice([1, 2, 3, None])
            ts = (base + timedelta(days=rng.randint(0, 20), hours=rng.randint(0, 23))).astimezone(rng.choice(zones))
            records.append((cid, ts, rng.choice(statuses)))
        min_days = rng.choice([1, 2, 3, 5])
        assert mod.find_purchase_streaks(records, min_days=min_days) == oracle(records, min_days), (records, min_days)


def test_large_input_runs_fast():
    rng = random.Random(5)
    base = datetime(2024, 1, 1, tzinfo=UTC)
    records = [(rng.randrange(5_000), base + timedelta(days=rng.randrange(365), seconds=rng.randrange(86_400)),
                C if rng.random() < 0.9 else "CANCELLED") for _ in range(200_000)]
    records += days(99_999, D(2024, 2, 27), 6)                    # a planted streak that spans leap day
    t0 = time.perf_counter()
    result = call_with_deadline(lambda: mod.find_purchase_streaks(records))
    elapsed = time.perf_counter() - t0
    assert result[99_999] == [(D(2024, 2, 27), D(2024, 3, 3), 6)]
    assert result == oracle(records, 5)
    assert elapsed < 2.0, f"took {elapsed:.2f}s"
