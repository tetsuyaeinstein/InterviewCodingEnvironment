"""PY-016 - First transaction at or after a cutoff.

Question: python/questions/02_algorithms/PY-016.md   (python -m lab show PY-016)
Check   : python -m lab check PY-016
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def first_at_or_after(seq: Sequence[Any], target: Any) -> int:
    """Return the smallest index i with seq[i] >= target, or len(seq) if there is none.

    seq is sorted ascending (duplicates allowed) and must only be accessed through
    len() and indexing, in O(log n) reads. It is not mutated.
    """
    raise NotImplementedError
