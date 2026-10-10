"""PY-005 reference solution: strict regex for the accepted shape, explicit DST resolution.

datetime.fromisoformat is not used for validation: since Python 3.11 it accepts date-only
strings (returning midnight), week dates, basic format, etc. A pipeline contract should say
exactly what it accepts, so the shape is checked with a regex and the fields are built by hand.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

AMBIGUOUS_POLICIES = ("raise", "earlier", "later")

_ISO = re.compile(
    r"""
    (?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})
    [Tt\ ]
    (?P<hour>\d{2}):(?P<minute>\d{2})
    (?::(?P<second>\d{2})(?:\.(?P<fraction>\d+))?)?
    (?P<tz>[Zz]|(?P<sign>[+-])(?P<oh>\d{2}):?(?P<om>\d{2}))?
    """,
    re.VERBOSE | re.ASCII,
)


def _zone(name: str) -> ZoneInfo:
    if not isinstance(name, str) or not name:
        raise ValueError(f"default_tz must be a non-empty IANA zone name, got {name!r}")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:   # unknown name / malformed path
        raise ValueError(f"unknown time zone {name!r}") from exc


def _localize(naive: datetime, tz: ZoneInfo, ambiguous: str) -> datetime:
    first = naive.replace(tzinfo=tz, fold=0)
    second = naive.replace(tzinfo=tz, fold=1)
    if first.utcoffset() == second.utcoffset():
        return first                                    # the normal case: exactly one instant
    # Offsets differ: either a gap (time skipped) or an overlap (time repeated).
    round_trip = first.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
    if round_trip != naive:
        raise ValueError(f"{naive.isoformat()} does not exist in {tz.key} (DST gap)")
    if ambiguous == "raise":
        raise ValueError(f"{naive.isoformat()} is ambiguous in {tz.key} (DST overlap)")
    return first if ambiguous == "earlier" else second  # fold=0 is the first occurrence


def to_utc(value: str, default_tz: str | None = None, *, ambiguous: str = "raise") -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"value must be str, got {type(value).__name__}")
    if ambiguous not in AMBIGUOUS_POLICIES:
        raise ValueError(f"ambiguous must be one of {AMBIGUOUS_POLICIES}, got {ambiguous!r}")
    zone = _zone(default_tz) if default_tz is not None else None   # fail fast on bad config

    m = _ISO.fullmatch(value.strip())
    if m is None:
        raise ValueError(f"not a supported ISO 8601 timestamp: {value!r}")
    fraction = (m["fraction"] or "")[:6].ljust(6, "0")             # truncate, never round
    # datetime() itself rejects month 13, Feb 30, hour 24, second 60, ...
    naive = datetime(int(m["year"]), int(m["month"]), int(m["day"]),
                     int(m["hour"]), int(m["minute"]), int(m["second"] or 0), int(fraction))

    if m["tz"] is not None:
        if m["tz"] in "Zz":
            return naive.replace(tzinfo=timezone.utc)
        oh, om = int(m["oh"]), int(m["om"])
        if om > 59:
            raise ValueError(f"invalid offset minutes in {value!r}")
        offset = timedelta(hours=oh, minutes=om) * (-1 if m["sign"] == "-" else 1)
        if abs(offset) >= timedelta(hours=24):
            raise ValueError(f"offset out of range in {value!r}")
        return naive.replace(tzinfo=timezone(offset)).astimezone(timezone.utc)

    if zone is None:
        raise ValueError(f"naive timestamp {value!r} and no default_tz given")
    return _localize(naive, zone, ambiguous).astimezone(timezone.utc)
