"""Tests for PY-027 (imports your practice file by default; see _loader.py)."""
from datetime import datetime, timedelta, timezone

import pytest

from _loader import load

mod = load("PY-027")
UTC = timezone.utc


def ev(i, ts):
    return {"id": i, "event_ts": ts}


def ids(result):
    return {k: [r["id"] for r in v] for k, v in result.items()}


def test_basic_utc_partitions():
    recs = [ev(1, datetime(2025, 3, 1, 10, tzinfo=UTC)), ev(2, datetime(2025, 3, 2, 0, tzinfo=UTC)),
            ev(3, datetime(2025, 3, 1, 23, tzinfo=UTC))]
    assert ids(mod.partition_records(recs)) == {
        "year=2025/month=03/day=01": [1, 3],
        "year=2025/month=03/day=02": [2],
    }


def test_offsets_are_converted_before_partitioning():
    recs = [ev(1, datetime(2025, 3, 1, 21, tzinfo=timezone(timedelta(hours=-5)))),   # 02:00 UTC on the 2nd
            ev(2, "2025-03-02T08:30:00+09:00"),                                         # 23:30 UTC on the 1st
            ev(3, "2025-03-01T12:00:00Z")]
    assert ids(mod.partition_records(recs)) == {
        "year=2025/month=03/day=01": [2, 3],
        "year=2025/month=03/day=02": [1],
    }


def test_day_boundaries_are_exact():
    recs = [ev(1, datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)),
            ev(2, datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC))]
    assert ids(mod.partition_records(recs)) == {
        "year=2025/month=12/day=31": [1],
        "year=2026/month=01/day=01": [2],
    }


def test_named_time_zone_with_dst():
    recs = [ev(1, datetime(2025, 3, 9, 4, 59, tzinfo=UTC)),    # 23:59 EST on 3/8
            ev(2, datetime(2025, 3, 9, 5, 0, tzinfo=UTC)),     # 00:00 EST on 3/9
            ev(3, datetime(2025, 3, 10, 3, 59, tzinfo=UTC)),   # 23:59 EDT on 3/9 (after the DST jump)
            ev(4, datetime(2025, 3, 10, 4, 0, tzinfo=UTC))]    # 00:00 EDT on 3/10
    assert ids(mod.partition_records(recs, tz="America/New_York")) == {
        "year=2025/month=03/day=08": [1],
        "year=2025/month=03/day=09": [2, 3],
        "year=2025/month=03/day=10": [4],
    }


def test_tzinfo_object_and_custom_field():
    recs = [{"id": 1, "ts": datetime(2025, 6, 30, 15, tzinfo=UTC)}]
    out = mod.partition_records(recs, ts_field="ts", tz=timezone(timedelta(hours=9)))
    assert ids(out) == {"year=2025/month=07/day=01": [1]}


@pytest.mark.parametrize("bad", [datetime(2025, 3, 1, 10), "2025-03-01T10:00:00", "2025-03-01", None,
                                 "not a date", 1740823200])
def test_naive_missing_or_invalid_timestamps_raise(bad):
    with pytest.raises(ValueError):
        mod.partition_records([ev(1, datetime(2025, 3, 1, tzinfo=UTC)), ev(2, bad)])


def test_missing_field_raises():
    with pytest.raises(ValueError):
        mod.partition_records([{"id": 1}])


@pytest.mark.parametrize("root, expected", [
    ("", "year=2025/month=03/day=01"),
    ("s3://lake/events", "s3://lake/events/year=2025/month=03/day=01"),
    ("s3://lake/events/", "s3://lake/events/year=2025/month=03/day=01"),
    ("events//", "events/year=2025/month=03/day=01"),
])
def test_root_prefix_uses_forward_slashes(root, expected):
    out = mod.partition_records([ev(1, datetime(2025, 3, 1, tzinfo=UTC))], root=root)
    assert list(out) == [expected]
    assert "\\" not in expected


def test_keys_sorted_records_stable_and_identical_objects():
    recs = [ev(i, datetime(2025, 1 + (i % 3) * 4, 1 + i % 2, tzinfo=UTC)) for i in range(10)][::-1]
    out = mod.partition_records(iter(recs))
    assert list(out) == sorted(out)
    for key, group in out.items():
        positions = [recs.index(r) for r in group]
        assert positions == sorted(positions)
        assert all(any(r is x for x in recs) for r in group), "records must be returned as-is"
    assert sum(len(v) for v in out.values()) == 10


def test_zero_padding_for_small_years_and_months():
    out = mod.partition_records([ev(1, datetime(999, 2, 3, tzinfo=UTC))])
    assert list(out) == ["year=0999/month=02/day=03"]


def test_empty_input():
    assert mod.partition_records([]) == {}
