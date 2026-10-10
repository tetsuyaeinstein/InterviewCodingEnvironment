"""PY-021 - Streaming customer spend from a CSV export.

Question: python/questions/03_etl_file_processing/PY-021.md   (python -m lab show PY-021)
Check   : python -m lab check PY-021
"""
from __future__ import annotations

import os
from collections.abc import Iterable
from decimal import Decimal

REQUIRED_COLUMNS = ("customer_id", "amount", "status")


def spend_per_customer(source: str | os.PathLike[str] | Iterable[str], *,
                       guest_key: str | None = None) -> dict[str, Decimal]:
    """Return total COMPLETED spend per customer_id from a CSV export, streaming the input.

    ``source`` is a path (str / PathLike) or an iterable of text lines (e.g. a file opened with
    newline=''). Missing/duplicated required columns or bad rows raise ValueError.
    Guest rows (blank customer_id) go under ``guest_key``, or are excluded when it is None.
    """
    raise NotImplementedError
