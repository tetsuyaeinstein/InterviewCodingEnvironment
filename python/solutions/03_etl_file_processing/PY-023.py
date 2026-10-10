"""PY-023 reference solution: one small, strict parser per column kind, chosen once from the schema.

Every parser either returns a canonical value or raises _Bad(reason); nothing is guessed.
Grammars are anchored regexes over ASCII digits, so '2025-3-1', '20250301', '12,34' or '١٢'
(Arabic-Indic digits, which int()/Decimal() would accept) are rejected instead of "fixed".
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

DATE = "date"
TIMESTAMP = "timestamp"
DECIMAL = "decimal"
INT = "int"
STR = "str"

NULL_TOKENS = frozenset({"", "null", "n/a"})

NULL_NOT_ALLOWED = "null_not_allowed"
INVALID_DATE = "invalid_date"
INVALID_TIMESTAMP = "invalid_timestamp"
NAIVE_TIMESTAMP = "naive_timestamp"
INVALID_DECIMAL = "invalid_decimal"
INVALID_INT = "invalid_int"


@dataclass(frozen=True)
class Column:
    name: str
    kind: str
    nullable: bool = True


@dataclass(frozen=True)
class FieldError:
    row_index: int
    column: str
    value: str | None
    reason: str


class _Bad(Exception):
    def __init__(self, reason: str):
        self.reason = reason


_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_SLASH_DATE = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})")
_NUM = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"
_DEC = re.compile(rf"(?:(?P<sign>-)?(?P<a>{_NUM}(?:\.[0-9]+)?)|\((?P<p>{_NUM}(?:\.[0-9]+)?)\))")
_INT = re.compile(rf"(?:(?P<sign>-)?(?P<a>{_NUM})|\((?P<p>{_NUM})\))")


def _make_date_parser(order: str) -> Callable[[str], date]:
    def parse(text: str) -> date:
        try:
            if m := _ISO_DATE.fullmatch(text):
                y, mo, d = map(int, m.groups())
            elif m := _SLASH_DATE.fullmatch(text):
                a, b, y = map(int, m.groups())
                mo, d = (a, b) if order == "MDY" else (b, a)
            else:
                raise _Bad(INVALID_DATE)
            return date(y, mo, d)               # rejects 02/30, month 13, ...
        except ValueError:
            raise _Bad(INVALID_DATE) from None
    return parse


def _parse_timestamp(text: str) -> datetime:
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        raise _Bad(INVALID_TIMESTAMP) from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise _Bad(NAIVE_TIMESTAMP)             # never assume a zone
    return dt.astimezone(timezone.utc)


def _number(pattern: re.Pattern, reason: str, text: str) -> str:
    m = pattern.fullmatch(text)
    if not m:
        raise _Bad(reason)
    if m.group("p") is not None:                # accounting negative: (12.00)
        return "-" + m.group("p").replace(",", "")
    return (m.group("sign") or "") + m.group("a").replace(",", "")


def _parse_decimal(text: str) -> Decimal:
    return Decimal(_number(_DEC, INVALID_DECIMAL, text))  # keeps the scale: '1,234.50' -> 1234.50


def _parse_int(text: str) -> int:
    return int(_number(_INT, INVALID_INT, text))


def normalise_rows(rows: Iterable[Mapping[str, str | None]], schema: Sequence[Column], *,
                   slash_date_order: str) -> tuple[list[dict], list[FieldError]]:
    if slash_date_order not in ("MDY", "DMY"):
        raise ValueError(f"slash_date_order must be 'MDY' or 'DMY', not {slash_date_order!r}")
    parsers: dict[str, Callable[[str], object]] = {
        DATE: _make_date_parser(slash_date_order), TIMESTAMP: _parse_timestamp,
        DECIMAL: _parse_decimal, INT: _parse_int, STR: lambda s: s,
    }
    names = [c.name for c in schema]
    if len(set(names)) != len(names):
        raise ValueError("duplicate column names in schema")
    plan = []
    for col in schema:
        if col.kind not in parsers:
            raise ValueError(f"unknown column kind {col.kind!r} for {col.name!r}")
        plan.append((col, parsers[col.kind]))

    out: list[dict] = []
    errors: list[FieldError] = []
    for i, row in enumerate(rows):
        norm: dict = {}
        for col, parse in plan:
            raw = row.get(col.name)
            text = raw.strip() if raw is not None else None
            value = None
            if text is None or text.lower() in NULL_TOKENS:
                if not col.nullable:
                    errors.append(FieldError(i, col.name, raw, NULL_NOT_ALLOWED))
            else:
                try:
                    value = parse(text)
                except _Bad as bad:
                    errors.append(FieldError(i, col.name, raw, bad.reason))
            norm[col.name] = value
        out.append(norm)
    return out, errors
