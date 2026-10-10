"""PY-002 reference solution: one pass, dict of exact running sums, round once at the end."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

CENT = Decimal("0.01")


def _to_decimal(value: Any) -> Decimal:
    # bool must be rejected before int: isinstance(True, int) is True.
    if isinstance(value, bool) or isinstance(value, float):
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
    if not result.is_finite():                      # Decimal("NaN") / Decimal("Infinity") parse fine
        raise ValueError(f"amount must be finite: {value!r}")
    return result


def _is_completed(status: Any) -> bool:
    return isinstance(status, str) and status.strip().upper() == "COMPLETED"


def total_spend_by_customer(transactions: Iterable[Mapping[str, Any]],
                            include_guests: bool = False) -> dict[Any, Decimal]:
    sums: dict[Any, Decimal] = {}
    for txn in transactions:
        if not _is_completed(txn.get("status")):
            continue                                # never parse amounts we don't count
        customer = txn.get("customer_id")
        if customer is None and not include_guests:
            continue
        amount = _to_decimal(txn.get("amount"))
        sums[customer] = sums.get(customer, Decimal(0)) + amount   # exact: no rounding yet
    # Round once per customer; quantize also normalises the exponent ("10" -> "10.00").
    return {cid: total.quantize(CENT, rounding=ROUND_HALF_UP) for cid, total in sums.items()}
