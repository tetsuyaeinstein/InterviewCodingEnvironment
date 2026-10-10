"""PY-021 reference solution: one streaming pass with csv.DictReader-style name lookup and a dict of totals.

Memory is O(number of distinct customers); rows are never materialised.
"""
from __future__ import annotations

import csv
import os
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ("customer_id", "amount", "status")


@contextmanager
def _lines(source: str | os.PathLike[str] | Iterable[str]) -> Iterator[Iterable[str]]:
    if isinstance(source, (str, os.PathLike)):
        # utf-8-sig drops a BOM; newline='' lets the csv module see quoted embedded newlines.
        with open(source, encoding="utf-8-sig", newline="") as f:
            yield f
    else:
        yield source          # caller owns the file object: do not close it


def _parse_amount(text: str, line_no: int) -> Decimal:
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise ValueError(f"line {line_no}: invalid amount {text!r}") from None
    if not value.is_finite():                       # Decimal accepts 'NaN' and 'Infinity'
        raise ValueError(f"line {line_no}: non-finite amount {text!r}")
    return value


def spend_per_customer(source: str | os.PathLike[str] | Iterable[str], *,
                       guest_key: str | None = None) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    with _lines(source) as lines:
        reader = csv.reader(lines)
        header = next(reader, None)
        if header is None:
            raise ValueError("empty input: no header row")
        names = [h.strip() for h in header]
        if names and names[0].startswith("﻿"):  # BOM left by a non-sig decoder
            names[0] = names[0].lstrip("﻿")
        index: dict[str, int] = {}
        for col in REQUIRED_COLUMNS:
            positions = [i for i, n in enumerate(names) if n == col]
            if not positions:
                raise ValueError(f"missing required column {col!r}; header was {names}")
            if len(positions) > 1:
                raise ValueError(f"column {col!r} appears {len(positions)} times in the header")
            index[col] = positions[0]
        i_cust, i_amt, i_status = (index[c] for c in REQUIRED_COLUMNS)

        for row in reader:
            if not row or (len(row) == 1 and not row[0].strip()):
                continue                                         # blank / whitespace-only line
            if len(row) != len(names):
                raise ValueError(f"line {reader.line_num}: expected {len(names)} fields, got {len(row)}")
            if row[i_status].strip().upper() != "COMPLETED":
                continue                                         # amount not even parsed
            amount = _parse_amount(row[i_amt], reader.line_num)
            customer = row[i_cust].strip()
            if not customer:
                if guest_key is None:
                    continue
                customer = guest_key
            totals[customer] = totals.get(customer, Decimal(0)) + amount
    return totals
