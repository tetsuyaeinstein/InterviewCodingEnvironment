"""PY-015 alternative: canonical key = character-count signature (frozenset of Counter items) -> O(n L).

Counting is O(L) per label instead of O(L log L) for sorting, and the key size depends on the
number of DISTINCT characters, not the label length. In CPython the sorted-string key is usually
faster for short labels (sorting a few characters runs in C), so this mainly pays off for long
labels with few distinct characters.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable


def group_anagram_labels(labels: Iterable[str]) -> list[list[str]]:
    groups: dict[frozenset[tuple[str, int]], list[str]] = {}
    for label in labels:
        counts = Counter(ch for ch in label.casefold() if not ch.isspace())
        groups.setdefault(frozenset(counts.items()), []).append(label)
    return list(groups.values())
