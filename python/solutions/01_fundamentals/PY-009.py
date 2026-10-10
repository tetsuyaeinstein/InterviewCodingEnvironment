"""PY-009 reference solution: Counter over normalised names + an explicit total-order sort."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable


def _normalise(event: object) -> str | None:
    if event is None:
        return None
    if not isinstance(event, str):
        raise TypeError(f"event type must be str or None, got {type(event).__name__}: {event!r}")
    name = " ".join(event.split()).lower()      # split() trims and collapses any whitespace run
    return name or None


def event_type_counts(events: Iterable[str | None]) -> list[tuple[str, int]]:
    counts = Counter(name for name in map(_normalise, events) if name is not None)
    # most_common() orders ties by first occurrence; the report needs a total order instead.
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))
