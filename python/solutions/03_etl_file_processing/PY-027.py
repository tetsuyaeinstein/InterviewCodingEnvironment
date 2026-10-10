"""PY-027 reference solution: convert to the target zone, format a zero-padded key, group, sort keys."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, tzinfo
from zoneinfo import ZoneInfo


def _aware(value: object) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"unparseable timestamp {value!r}") from None
    if not isinstance(value, datetime):
        raise ValueError(f"timestamp must be a datetime or ISO-8601 string, got {value!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"naive timestamp {value!r}: refusing to guess its time zone")
    return value


def partition_records(records: Iterable[Mapping[str, object]], *, ts_field: str = "event_ts",
                      tz: str | tzinfo = "UTC", root: str = "") -> dict[str, list[Mapping[str, object]]]:
    zone = ZoneInfo(tz) if isinstance(tz, str) else tz
    prefix = root.rstrip("/") + "/" if root else ""
    groups: dict[str, list[Mapping[str, object]]] = {}
    for rec in records:
        if rec.get(ts_field) is None:
            raise ValueError(f"record has no {ts_field!r}: {rec!r}")
        local = _aware(rec[ts_field]).astimezone(zone)
        # f-string formatting, not strftime: '%Y' is not zero-padded for years < 1000 on all platforms
        key = f"{prefix}year={local.year:04d}/month={local.month:02d}/day={local.day:02d}"
        groups.setdefault(key, []).append(rec)
    return {k: groups[k] for k in sorted(groups)}
