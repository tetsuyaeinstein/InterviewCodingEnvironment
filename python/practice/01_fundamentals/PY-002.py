"""PY-002 - Completed spend per customer with exact cents.

Question: python/questions/01_fundamentals/PY-002.md   (python -m lab show PY-002)
Check   : python -m lab check PY-002
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, ROUND_UP
from typing import Any

def total_spend_by_customer(transactions: Iterable[Mapping[str, Any]],
                            include_guests: bool = False) -> dict[Any, Decimal]:
    """Return net COMPLETED spend per customer_id as Decimal with exactly 2 decimal places.

    Status match is case/whitespace-insensitive. Amounts: Decimal, int or decimal string;
    float/bool/None -> TypeError, unparsable or non-finite string -> ValueError.
    Guests (customer_id None) are excluded unless include_guests=True (key None).
    Totals are summed exactly and rounded once, half-up.
    """
    # raise NotImplementedError
