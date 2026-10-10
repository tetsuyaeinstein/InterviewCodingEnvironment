"""PY-015 - Group scrambled product labels.

Question: python/questions/02_algorithms/PY-015.md   (python -m lab show PY-015)
Check   : python -m lab check PY-015
"""
from __future__ import annotations

from collections.abc import Iterable


def group_anagram_labels(labels: Iterable[str]) -> list[list[str]]:
    """Group labels that are rearrangements of each other (case-folded, whitespace ignored).

    Groups in order of first appearance; members in input order with original spelling;
    duplicates kept. The input is read once and not mutated.
    """
    raise NotImplementedError
