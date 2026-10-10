"""PY-005 - Normalise ISO 8601 timestamps to UTC (naive and DST-safe).

Question: python/questions/01_fundamentals/PY-005.md   (python -m lab show PY-005)
Check   : python -m lab check PY-005
"""
from __future__ import annotations

from datetime import datetime

AMBIGUOUS_POLICIES = ("raise", "earlier", "later")


def to_utc(value: str, default_tz: str | None = None, *, ambiguous: str = "raise") -> datetime:
    """Parse an ISO 8601 timestamp and return an aware datetime with tzinfo timezone.utc.

    Naive input requires default_tz (IANA name), else ValueError. Non-existent local times
    raise ValueError; ambiguous ones follow `ambiguous` ("raise" | "earlier" | "later").
    Date-only strings, malformed input, unknown zones and bad policies -> ValueError;
    non-str value -> TypeError. Fractions beyond microseconds are truncated.
    """
    raise NotImplementedError
