"""PY-030 - Incremental load with watermark, overlap window and dedup.

Question: python/questions/03_etl_file_processing/PY-030.md   (python -m lab show PY-030)
Check   : python -m lab check PY-030
"""
from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class WatermarkState:
    watermark: datetime | None = None                                  # None = never run
    processed: frozenset[tuple[Hashable, datetime]] = frozenset()       # (key, updated_at) already done


@dataclass
class BatchResult:
    to_process: list[Mapping[str, object]] = field(default_factory=list)
    late: list[Mapping[str, object]] = field(default_factory=list)
    state: WatermarkState = field(default_factory=WatermarkState)


def select_incremental(records: Iterable[Mapping[str, object]], state: WatermarkState, *,
                       overlap: timedelta, upper_bound: datetime,
                       key_field: str = "id", ts_field: str = "updated_at") -> BatchResult:
    """Select the records to process in this run and compute the next state.

    Window: [watermark - overlap, upper_bound). Already-processed (key, updated_at) pairs are
    skipped; records older than the window are returned as ``late``. ``state`` is not modified.
    """
    raise NotImplementedError
