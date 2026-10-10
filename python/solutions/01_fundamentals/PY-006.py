"""PY-006 reference solution: parse to aware instants, convert with zoneinfo, aggregate per date."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class DayTotal(NamedTuple):
    transaction_count: int
    gross_amount: Decimal


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError(f"unknown business time zone {name!r}") from exc


def _instant(value: Any) -> datetime:
    if isinstance(value, str):
        text = value.strip()
        if text[-1:] in ("z", "Z"):
            text = text[:-1] + "+00:00"
        try:
            value = datetime.fromisoformat(text)   # date-only strings come back naive -> rejected below
        except ValueError:
            raise ValueError(f"unparsable timestamp {value!r}") from None
    if not isinstance(value, datetime):
        raise ValueError(f"transaction_ts must be an aware datetime or ISO string, got {value!r}")
    if value.utcoffset() is None:
        raise ValueError(f"naive timestamp {value!r}: the instant is unknown without a zone")
    return value


def _amount(value: Any) -> Decimal:
    if isinstance(value, (float, bool)) or not isinstance(value, (Decimal, int)):
        raise TypeError(f"amount must be Decimal or int, got {type(value).__name__}")
    return Decimal(value)


def daily_totals_by_business_date(transactions: Iterable[Mapping[str, Any]],
                                  business_tz: str) -> dict[date, DayTotal]:
    tz = _zone(business_tz)                         # validate before touching the data
    counts: dict[date, int] = {}
    sums: dict[date, Decimal] = {}
    for txn in transactions:
        # astimezone() applies the zone's offset *for that instant*, so 23h/25h days just work.
        business_date = _instant(txn["transaction_ts"]).astimezone(tz).date()
        amount = _amount(txn["amount"])
        counts[business_date] = counts.get(business_date, 0) + 1
        sums[business_date] = sums.get(business_date, Decimal(0)) + amount
    return {d: DayTotal(counts[d], sums[d]) for d in sorted(counts)}
