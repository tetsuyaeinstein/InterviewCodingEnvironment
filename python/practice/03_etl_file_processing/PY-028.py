"""PY-028 - Reconcile two extracts with canonical row hashes.

Question: python/questions/03_etl_file_processing/PY-028.md   (python -m lab show PY-028)
Check   : python -m lab check PY-028
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field


@dataclass
class DiffResult:
    missing: list[tuple] = field(default_factory=list)    # keys in source, not in target
    extra: list[tuple] = field(default_factory=list)      # keys in target, not in source
    changed: list[tuple[tuple, tuple[str, ...]]] = field(default_factory=list)  # (key, differing fields)
    unchanged: int = 0


def canonical_row_hash(row: Mapping[str, object], *, exclude: Collection[str] = ()) -> str:
    """Return the SHA-256 hex digest of the row's canonical form (see the question for the rules)."""
    raise NotImplementedError


def diff_streams(source: Iterable[Mapping[str, object]], target: Iterable[Mapping[str, object]],
                 key_fields: Sequence[str], *, exclude: Collection[str] = ()) -> DiffResult:
    """Compare two row streams by business key using canonical row comparison.

    All lists in the result are sorted by key. Duplicate keys within one stream raise ValueError.
    """
    raise NotImplementedError
