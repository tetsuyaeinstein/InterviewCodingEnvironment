"""PY-012 reference solution: sliding window with a last-seen index map (left pointer jumps)."""
from __future__ import annotations


def longest_unique_substring(s: str) -> str:
    last_seen: dict[str, int] = {}
    left = 0
    best_start, best_len = 0, 0
    for right, ch in enumerate(s):
        prev = last_seen.get(ch)
        if prev is not None and prev >= left:   # repeat inside the current window
            left = prev + 1                     # jump past it (never move left backwards)
        last_seen[ch] = right
        if right - left + 1 > best_len:         # strict '>' keeps the earliest window on ties
            best_start, best_len = left, right - left + 1
    return s[best_start:best_start + best_len]
