"""PY-002 alternative: sort by customer, then itertools.groupby + sum per group.

groupby only merges *adjacent* equal keys, so the input must be sorted (or already clustered)
by customer. Sorting here makes it O(n log n) and materialises the filtered rows, which is worse
than the dict approach for in-memory data. The pattern pays off when the input is *already*
ordered by customer (``ORDER BY customer_id`` from the database, files partitioned by customer,
a merge of sorted runs): then the sort disappears, memory is O(1) per group, and each customer's
total can be emitted the moment its group ends. Requires customer ids to be mutually orderable.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from itertools import groupby
from operator import itemgetter
from typing import Any

CENT = Decimal("0.01")


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, (bool, float)):
        raise TypeError(f"amount must not be {type(value).__name__}: {value!r}")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except InvalidOperation:
            raise ValueError(f"invalid decimal amount: {value!r}") from None
    else:
        raise TypeError(f"unsupported amount type {type(value).__name__}: {value!r}")
    if not result.is_finite():
        raise ValueError(f"amount must be finite: {value!r}")
    return result


def _counted(transactions: Iterable[Mapping[str, Any]], include_guests: bool) -> Iterator[tuple[Any, Decimal]]:
    for txn in transactions:
        status = txn.get("status")
        if not (isinstance(status, str) and status.strip().upper() == "COMPLETED"):
            continue
        customer = txn.get("customer_id")
        if customer is None and not include_guests:
            continue
        yield customer, _to_decimal(txn.get("amount"))


def total_spend_by_customer(transactions: Iterable[Mapping[str, Any]],
                            include_guests: bool = False) -> dict[Any, Decimal]:
    # None (guests) sorts last; ids themselves are compared only among non-None values.
    rows = sorted(_counted(transactions, include_guests), key=lambda r: (r[0] is None, r[0]))
    return {
        customer: sum(map(itemgetter(1), group), Decimal(0)).quantize(CENT, rounding=ROUND_HALF_UP)
        for customer, group in groupby(rows, key=itemgetter(0))
    }
