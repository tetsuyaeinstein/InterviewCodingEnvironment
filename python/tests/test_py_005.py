"""Tests for PY-005 (imports your practice file by default; see _loader.py)."""
from datetime import datetime, timezone

import pytest

from _loader import load

mod = load("PY-005")

UTC = timezone.utc


def utc(*args):
    return datetime(*args, tzinfo=UTC)


def assert_utc(result, expected):
    assert isinstance(result, datetime)
    assert result.tzinfo is UTC, f"tzinfo must be datetime.timezone.utc, got {result.tzinfo!r}"
    assert result == expected
    assert result.replace(tzinfo=None) == expected.replace(tzinfo=None)


@pytest.mark.parametrize("value, expected", [
    ("2025-06-01T14:03:22Z", utc(2025, 6, 1, 14, 3, 22)),
    ("2025-06-01T14:03:22z", utc(2025, 6, 1, 14, 3, 22)),
    ("2025-06-01t14:03:22Z", utc(2025, 6, 1, 14, 3, 22)),
    ("2025-06-01 14:03Z", utc(2025, 6, 1, 14, 3)),
    ("2025-06-01T19:33:22.5+05:30", utc(2025, 6, 1, 14, 3, 22, 500_000)),
    ("2025-06-01T19:48:22+0545", utc(2025, 6, 1, 14, 3, 22)),
    ("2025-06-01T01:00:00+05:30", utc(2025, 5, 31, 19, 30)),
    ("2025-12-31T21:30:00-03:30", utc(2026, 1, 1, 1, 0)),
    ("2025-06-01T14:03:22+00:00", utc(2025, 6, 1, 14, 3, 22)),
    ("  2025-06-01T14:03:22Z\n", utc(2025, 6, 1, 14, 3, 22)),
])
def test_aware_inputs_are_converted_to_utc(value, expected):
    assert_utc(mod.to_utc(value), expected)


def test_fractional_seconds_are_truncated_to_microseconds():
    assert_utc(mod.to_utc("2025-06-01T14:03:22.123Z"), utc(2025, 6, 1, 14, 3, 22, 123_000))
    assert_utc(mod.to_utc("2025-06-01T14:03:22.123456789Z"), utc(2025, 6, 1, 14, 3, 22, 123_456))
    # rounding would carry into the next second
    assert_utc(mod.to_utc("2025-06-01T14:03:22.9999999Z"), utc(2025, 6, 1, 14, 3, 22, 999_999))


def test_naive_without_default_zone_raises():
    with pytest.raises(ValueError):
        mod.to_utc("2025-06-01T10:03:22")
    with pytest.raises(ValueError):
        mod.to_utc("2025-06-01 10:03:22", None)


@pytest.mark.parametrize("value, tz, expected", [
    ("2025-06-01 10:03:22", "America/New_York", utc(2025, 6, 1, 14, 3, 22)),     # EDT -4
    ("2025-01-15T10:03:22", "America/New_York", utc(2025, 1, 15, 15, 3, 22)),    # EST -5
    ("2025-06-01T00:30:00", "Asia/Kolkata", utc(2025, 5, 31, 19, 0)),            # previous UTC day
    ("2025-06-01T23:30:00", "America/Los_Angeles", utc(2025, 6, 2, 6, 30)),      # next UTC day
    ("2025-06-01T12:00:00", "UTC", utc(2025, 6, 1, 12, 0)),
])
def test_naive_interpreted_in_default_zone(value, tz, expected):
    assert_utc(mod.to_utc(value, tz), expected)


def test_default_zone_does_not_override_an_explicit_offset():
    assert_utc(mod.to_utc("2025-06-01T14:03:22Z", "Asia/Tokyo"), utc(2025, 6, 1, 14, 3, 22))
    assert_utc(mod.to_utc("2025-06-01T14:03:22+02:00", "America/New_York"), utc(2025, 6, 1, 12, 3, 22))


@pytest.mark.parametrize("value, tz", [
    ("2025-03-09T02:30:00", "America/New_York"),     # spring forward: 02:00 -> 03:00
    ("2025-03-09T02:00:00", "America/New_York"),
    ("2025-03-30T01:15:00", "Europe/London"),        # 01:00 -> 02:00
    ("2025-10-05T02:30:00", "Australia/Sydney"),     # southern hemisphere spring forward
])
def test_nonexistent_local_times_always_raise(value, tz):
    for policy in ("raise", "earlier", "later"):
        with pytest.raises(ValueError):
            mod.to_utc(value, tz, ambiguous=policy)


def test_ambiguous_local_time_policies():
    value, tz = "2025-11-02T01:30:00", "America/New_York"     # 01:00-02:00 happens twice
    with pytest.raises(ValueError):
        mod.to_utc(value, tz)
    with pytest.raises(ValueError):
        mod.to_utc(value, tz, ambiguous="raise")
    assert_utc(mod.to_utc(value, tz, ambiguous="earlier"), utc(2025, 11, 2, 5, 30))
    assert_utc(mod.to_utc(value, tz, ambiguous="later"), utc(2025, 11, 2, 6, 30))
    # Sydney falls back in April: 02:30 happens at +11:00 and then at +10:00
    assert_utc(mod.to_utc("2025-04-06T02:30:00", "Australia/Sydney", ambiguous="earlier"), utc(2025, 4, 5, 15, 30))
    assert_utc(mod.to_utc("2025-04-06T02:30:00", "Australia/Sydney", ambiguous="later"), utc(2025, 4, 5, 16, 30))


def test_times_next_to_a_transition_are_not_ambiguous():
    tz = "America/New_York"
    assert_utc(mod.to_utc("2025-11-02T00:59:59", tz), utc(2025, 11, 2, 4, 59, 59))
    assert_utc(mod.to_utc("2025-11-02T02:00:00", tz), utc(2025, 11, 2, 7, 0))
    assert_utc(mod.to_utc("2025-03-09T03:00:00", tz), utc(2025, 3, 9, 7, 0))
    assert_utc(mod.to_utc("2025-03-09T01:59:59", tz), utc(2025, 3, 9, 6, 59, 59))


@pytest.mark.parametrize("value", ["2025-03-09", " 2025-03-09 "])
def test_date_only_is_rejected_even_with_a_zone(value):
    with pytest.raises(ValueError):
        mod.to_utc(value)
    with pytest.raises(ValueError):
        mod.to_utc(value, "America/New_York")


@pytest.mark.parametrize("value", [
    "", "   ", "yesterday", "2025-02-30T10:00:00Z", "2025-13-01T10:00:00Z", "2025-03-09T24:00:00Z",
    "2025-03-09T23:59:60Z", "2025-03-09T10:00:00+24:00", "2025-03-09T10:00:00Z extra", "2025-03-09T10:00:00 +01:00 UTC",
])
def test_malformed_strings_raise_value_error(value):
    with pytest.raises(ValueError):
        mod.to_utc(value, "UTC")


@pytest.mark.parametrize("value", [None, 1717250602, datetime(2025, 6, 1, tzinfo=UTC), b"2025-06-01T10:00:00Z"])
def test_non_string_values_raise_type_error(value):
    with pytest.raises(TypeError):
        mod.to_utc(value)


def test_bad_zone_and_bad_policy_are_rejected():
    for tz in ("Mars/Olympus_Mons", "EST5EDT_not_real", ""):
        with pytest.raises(ValueError):
            mod.to_utc("2025-06-01T10:00:00", tz)
        with pytest.raises(ValueError):
            mod.to_utc("2025-06-01T10:00:00Z", tz)       # validated even when not needed
    with pytest.raises(ValueError):
        mod.to_utc("2025-06-01T10:00:00Z", ambiguous="first")
