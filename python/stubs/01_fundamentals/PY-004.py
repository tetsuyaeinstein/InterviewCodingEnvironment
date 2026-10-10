"""PY-004 - Flatten nested transaction payloads into dotted keys.

Question: python/questions/01_fundamentals/PY-004.md   (python -m lab show PY-004)
Check   : python -m lab check PY-004
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def flatten_record(record: Mapping[str, Any], *, sep: str = ".",
                   max_depth: int | None = None) -> dict[str, Any]:
    """Flatten nested mappings/lists into a single-level dict keyed by joined path segments.

    Lists/tuples use their indices as segments; empty containers are kept as {} / [];
    max_depth limits the number of segments per key; container values in the output are deep
    copies. Non-str keys -> TypeError; bad sep/max_depth or colliding output keys -> ValueError.
    Must handle nesting deeper than the recursion limit. The input is never mutated.
    """
    raise NotImplementedError
