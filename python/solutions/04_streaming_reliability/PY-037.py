"""PY-037 reference solution.

Canonical form = sorted list of [field, type_tag, text] for every selected field whose value is
not None. json.dumps escapes quotes/backslashes/control characters, so the encoding is injective:
no value can imitate a separator or a neighbouring field. Omitting None entries makes "absent"
and None identical, which is exactly what makes adding a nullable column a non-event.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from decimal import Decimal


def _canonical(value: object) -> list[str]:
    if isinstance(value, bool):                      # before int: True is not 1
        return ["bool", "1" if value else "0"]
    if isinstance(value, (int, Decimal)):
        d = Decimal(value)
        if not d.is_finite():
            raise ValueError(f"non-finite number {value!r}")
        if d == 0:
            return ["num", "0"]                      # 0, 0.00, -0 and 0E+5 all collapse
        # strip trailing zeros WITHOUT Decimal.normalize(): that rounds to the context precision
        # (28 digits) and would make 10**30 and 10**30 + 1 identical
        sign, digits, exp = d.as_tuple()
        digits = list(digits)
        while len(digits) > 1 and digits[-1] == 0:
            digits.pop()
            exp += 1
        return ["num", format(Decimal((sign, tuple(digits), exp)), "f")]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    if isinstance(value, datetime):                  # before date: datetime is a date subclass
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"naive datetime {value!r}: attach a timezone upstream")
        return ["ts", value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")]
    if isinstance(value, date):
        return ["date", value.isoformat()]
    raise TypeError(f"unsupported type {type(value).__name__}")


def fingerprint(record: Mapping[str, object], fields: Sequence[str]) -> str:
    names = list(fields)
    if len(set(names)) != len(names):
        raise ValueError("duplicate field names")
    items = []
    for name in sorted(names):
        value = record.get(name)
        if value is not None:
            items.append([name, *_canonical(value)])
    payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
