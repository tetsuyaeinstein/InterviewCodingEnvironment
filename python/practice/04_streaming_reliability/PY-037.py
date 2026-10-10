"""PY-037 - Null-safe canonical record fingerprint that survives schema evolution.

Question: python/questions/04_streaming_reliability/PY-037.md   (python -m lab show PY-037)
Check   : python -m lab check PY-037
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def fingerprint(record: Mapping[str, object], fields: Sequence[str]) -> str:
    """Return the SHA-256 hex digest (64 lowercase hex chars) of the canonical form of
    ``record`` restricted to ``fields``.

    Two (record, fields) pairs get the same digest if and only if their canonical forms are
    equal. See the question for the canonical-form rules.
    """
    raise NotImplementedError
