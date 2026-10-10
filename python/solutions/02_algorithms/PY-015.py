"""PY-015 reference solution: canonical key = sorted normalised characters; dict of groups -> O(n L log L).

Normalise for comparison only (casefold + drop whitespace), sort the characters to get a key that is
identical for every rearrangement, and append the ORIGINAL label to that key's group. dicts keep
insertion order, so groups come out in order of first appearance and members in input order.
"""
from __future__ import annotations

from collections.abc import Iterable


def _canonical(label: str) -> str:
    folded = "".join(ch for ch in label.casefold() if not ch.isspace())
    return "".join(sorted(folded))


def group_anagram_labels(labels: Iterable[str]) -> list[list[str]]:
    groups: dict[str, list[str]] = {}
    for label in labels:
        groups.setdefault(_canonical(label), []).append(label)
    return list(groups.values())
