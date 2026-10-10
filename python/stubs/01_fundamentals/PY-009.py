"""PY-009 - Event-type frequency report with normalisation.

Question: python/questions/01_fundamentals/PY-009.md   (python -m lab show PY-009)
Check   : python -m lab check PY-009
"""
from __future__ import annotations

from collections.abc import Iterable


def event_type_counts(events: Iterable[str | None]) -> list[tuple[str, int]]:
    """Count normalised event types (trimmed, whitespace runs -> one space, lowercased).

    None and blank strings are ignored; other non-str values -> TypeError.
    Returns (name, count) tuples sorted by count descending, then name ascending.
    """
    raise NotImplementedError
