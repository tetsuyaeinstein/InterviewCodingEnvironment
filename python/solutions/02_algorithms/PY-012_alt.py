"""PY-012 alternative: sliding window with a membership set (left pointer walks forward).

Each character enters and leaves the set at most once, so this is still O(n) amortised, but it
does up to 2n set operations instead of n dict lookups, and the left pointer advances one step at a time.
"""
from __future__ import annotations


def longest_unique_substring(s: str) -> str:
    window: set[str] = set()
    left = 0
    best_start, best_len = 0, 0
    for right, ch in enumerate(s):
        while ch in window:          # shrink until the incoming char is unique again
            window.remove(s[left])
            left += 1
        window.add(ch)
        if right - left + 1 > best_len:
            best_start, best_len = left, right - left + 1
    return s[best_start:best_start + best_len]
