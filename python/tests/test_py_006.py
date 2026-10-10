"""Tests for PY-006 (imports your practice file by default; see _loader.py)."""
import copy
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from _loader import load

mod = load("PY-006")

D = Decimal
NY = "America/New_York"


def txn(ts, amount="1.00"):
    return {"transaction_ts": ts, "amount": D(amount) if isinstance(amount, str) else amount}


def as_plain(result):
    return {d: tuple(v) for d, v in result.items()}


def test_example_from_question():
    rows = [txn("2025-06-15T02:30:00Z", "12.00"), txn("2025-06-15T04:00:00Z", "3.50"),
            txn("2025-06-15T16:00:00+02:00", "1.25")]
    result = mod.daily_totals_by_business_date(rows, NY)
    assert as_plain(result) == {date(2025, 6, 14): (1, D("12.00")), date(2025, 6, 15): (2, D("4.75"))}
    assert result[date(2025, 6, 15)] == (2, D("4.75"))


def test_empty_input():
    assert mod.daily_totals_by_business_date([], NY) == {}


def test_spring_forward_day_is_23_hours_long():
    rows = [
        txn("2025-03-09T04:59:59Z"),   # 23:59:59 EST on 8 Mar
        txn("2025-03-09T05:00:00Z"),   # 00:00 EST on 9 Mar
        txn("2025-03-10T03:59:59Z"),   # 23:59:59 EDT on 9 Mar
        txn("2025-03-10T04:00:00Z"),   # 00:00 EDT on 10 Mar (a fixed -5h offset says 9 Mar)
    ]
    result = as_plain(mod.daily_totals_by_business_date(rows, NY))
    assert result == {date(2025, 3, 8): (1, D("1.00")), date(2025, 3, 9): (2, D("2.00")),
                      date(2025, 3, 10): (1, D("1.00"))}


def test_fall_back_day_is_25_hours_long_including_the_repeated_hour():
    rows = [
        txn("2025-11-02T03:59:59Z", "1"),   # 23:59:59 EDT on 1 Nov
        txn("2025-11-02T04:00:00Z", "2"),   # 00:00 EDT on 2 Nov
        txn("2025-11-02T05:30:00Z", "4"),   # 01:30 EDT (first pass through 01:30)
        txn("2025-11-02T06:30:00Z", "8"),   # 01:30 EST (second pass)
        txn("2025-11-03T04:30:00Z", "16"),  # 23:30 EST on 2 Nov (a fixed -4h offset says 3 Nov)
        txn("2025-11-03T05:00:00Z", "32"),  # 00:00 EST on 3 Nov
    ]
    rows = [{"transaction_ts": r["transaction_ts"], "amount": D(int(r["amount"]))} for r in rows]
    result = as_plain(mod.daily_totals_by_business_date(rows, NY))
    assert result == {date(2025, 11, 1): (1, D(1)), date(2025, 11, 2): (4, D(30)), date(2025, 11, 3): (1, D(32))}


def test_zones_east_of_utc_and_half_hour_offsets():
    rows = [txn("2025-06-14T14:59:59Z"), txn("2025-06-14T15:00:00Z"), txn("2025-06-14T23:00:00Z")]
    assert as_plain(mod.daily_totals_by_business_date(rows, "Asia/Tokyo")) == {
        date(2025, 6, 14): (1, D("1.00")), date(2025, 6, 15): (2, D("2.00"))}
    rows = [txn("2025-06-14T18:29:59Z"), txn("2025-06-14T18:30:00Z")]
    assert as_plain(mod.daily_totals_by_business_date(rows, "Asia/Kolkata")) == {
        date(2025, 6, 14): (1, D("1.00")), date(2025, 6, 15): (1, D("1.00"))}


def test_aware_datetimes_in_any_zone_and_mixed_inputs():
    berlin = ZoneInfo("Europe/Berlin")
    rows = [
        txn(datetime(2025, 6, 15, 1, 0, tzinfo=berlin)),                    # 14 Jun 19:00 EDT
        txn(datetime(2025, 6, 15, 4, 0, tzinfo=timezone.utc)),              # 15 Jun 00:00 EDT
        txn(datetime(2025, 6, 14, 23, 0, tzinfo=timezone(timedelta(hours=-4)))),  # 14 Jun 23:00
        txn("2025-06-14T22:30:00-04:00"),
        txn("2025-06-15T03:59:59z"),
    ]
    assert as_plain(mod.daily_totals_by_business_date(rows, NY)) == {
        date(2025, 6, 14): (4, D("4.00")), date(2025, 6, 15): (1, D("1.00"))}


def test_keys_are_in_ascending_date_order():
    rng = random.Random(6)
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = [txn(base + timedelta(hours=rng.randint(0, 24 * 120))) for _ in range(500)]
    rows.sort(key=lambda r: r["transaction_ts"], reverse=True)
    result = mod.daily_totals_by_business_date(rows, NY)
    assert list(result) == sorted(result)
    assert sum(v[0] for v in result.values()) == 500


def test_exact_sums_without_rounding():
    rows = [txn("2025-06-14T12:00:00Z", "0.005"), txn("2025-06-14T13:00:00Z", "0.001"),
            txn("2025-06-14T14:00:00Z", 2), txn("2025-06-14T15:00:00Z", "-0.006")]
    result = mod.daily_totals_by_business_date(rows, "UTC")
    assert result[date(2025, 6, 14)] == (4, D("2.000"))
    assert isinstance(result[date(2025, 6, 14)][1], Decimal)


def test_matches_independent_oracle_on_random_instants():
    rng = random.Random(66)
    base = datetime(2025, 3, 1, tzinfo=timezone.utc)
    for zone in ("America/New_York", "Australia/Sydney", "Europe/London", "Pacific/Auckland"):
        tz = ZoneInfo(zone)
        rows = [txn(base + timedelta(minutes=rng.randint(0, 60 * 24 * 300)), D(rng.randint(1, 999)) / 100)
                for _ in range(400)]
        expected = {}
        for r in rows:
            # oracle: local wall-clock date of the POSIX timestamp
            d = datetime.fromtimestamp(r["transaction_ts"].timestamp(), tz).date()
            c, s = expected.get(d, (0, D(0)))
            expected[d] = (c + 1, s + r["amount"])
        assert as_plain(mod.daily_totals_by_business_date(iter(rows), zone)) == dict(sorted(expected.items()))


@pytest.mark.parametrize("ts", [
    "2025-06-14T22:30:00",                 # naive string
    "2025-06-14",                          # date-only string
    datetime(2025, 6, 14, 22, 30),         # naive datetime
    "not a timestamp",
])
def test_naive_or_unparsable_timestamps_raise_value_error(ts):
    with pytest.raises(ValueError):
        mod.daily_totals_by_business_date([txn("2025-06-14T12:00:00Z"), txn(ts)], NY)


def test_float_amount_raises_type_error():
    with pytest.raises(TypeError):
        mod.daily_totals_by_business_date([txn("2025-06-14T12:00:00Z", 1.5)], NY)


@pytest.mark.parametrize("zone", ["America/Gotham", "", "EST+5"])
def test_unknown_zone_raises_value_error(zone):
    with pytest.raises(ValueError):
        mod.daily_totals_by_business_date([txn("2025-06-14T12:00:00Z")], zone)


def test_input_not_mutated():
    rows = [txn("2025-06-15T02:30:00Z", "12.00"), txn(datetime(2025, 6, 15, 4, tzinfo=timezone.utc))]
    snapshot = copy.deepcopy(rows)
    mod.daily_totals_by_business_date(rows, NY)
    assert rows == snapshot
