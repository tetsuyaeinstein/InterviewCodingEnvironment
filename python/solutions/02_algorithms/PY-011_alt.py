"""PY-011 alternative: sort the distinct amounts + two pointers -> O(n log n), then apply the policy.

Plain "sort and walk two pointers inward" returns *some* matching pair of VALUES, not the pair the
policy asks for, and it loses the original positions. So:

1. Record, per distinct amount, its first two positions (O(n)).
2. Sort the distinct amounts and walk two pointers inward to enumerate every value pair
   (a, b), a <= b, with a + b == target (O(d log d) for d distinct amounts).
3. For a value pair the best positions are fixed:
   - a != b: the first occurrences fa, fb -> (min, max). Any other choice has a larger max.
   - a == b: the first two occurrences of a (needs at least two).
4. Keep the candidate with the smallest (j, i).

Same answers as the hash map, but every value pair must be inspected (no early exit), and it
uses O(d) extra memory for the position table plus the sorted copy.
"""
from __future__ import annotations

from collections.abc import Sequence


def find_refund_pair(amounts_cents: Sequence[int], target_cents: int) -> tuple[int, int] | None:
    if isinstance(target_cents, bool) or not isinstance(target_cents, int):
        raise TypeError(f"target_cents must be an int, got {type(target_cents).__name__}")
    first_two: dict[int, list[int]] = {}
    for pos, amount in enumerate(amounts_cents):
        seen = first_two.setdefault(amount, [])
        if len(seen) < 2:
            seen.append(pos)

    values = sorted(first_two)
    lo, hi = 0, len(values) - 1
    best: tuple[int, int] | None = None          # stored as (j, i) so min() applies the policy
    while lo <= hi:
        total = values[lo] + values[hi]
        if total < target_cents:
            lo += 1
        elif total > target_cents:
            hi -= 1
        else:
            if lo == hi:                          # a + a == target: needs two occurrences
                pos = first_two[values[lo]]
                cand = (pos[1], pos[0]) if len(pos) == 2 else None
            else:
                fa, fb = first_two[values[lo]][0], first_two[values[hi]][0]
                cand = (max(fa, fb), min(fa, fb))
            if cand is not None and (best is None or cand < best):
                best = cand
            lo += 1
            hi -= 1
    return None if best is None else (best[1], best[0])
