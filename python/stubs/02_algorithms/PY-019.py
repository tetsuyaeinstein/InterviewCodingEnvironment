"""PY-019 - Peak queue length in every K-minute window.

Question: python/questions/02_algorithms/PY-019.md   (python -m lab show PY-019)
Check   : python -m lab check PY-019
"""
from __future__ import annotations

from collections.abc import Sequence


def sliding_window_max(values: Sequence[int], k: int) -> list[int]:
    """Return the maximum of every window of k consecutive values (len(values) - k + 1 results).

    k > len(values) (or empty values) -> []. k < 1 -> ValueError; non-int k (including bool)
    -> TypeError, checked before anything else. The input is not mutated.
    """
    raise NotImplementedError
