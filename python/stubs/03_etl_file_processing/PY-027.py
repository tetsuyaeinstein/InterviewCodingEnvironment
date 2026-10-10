"""PY-027 - Hive-style date partition paths for events.

Question: python/questions/03_etl_file_processing/PY-027.md   (python -m lab show PY-027)
Check   : python -m lab check PY-027
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import tzinfo


def partition_records(records: Iterable[Mapping[str, object]], *, ts_field: str = "event_ts",
                      tz: str | tzinfo = "UTC", root: str = "") -> dict[str, list[Mapping[str, object]]]:
    """Group records by 'year=YYYY/month=MM/day=DD' of their timestamp in ``tz``.

    Keys are sorted ascending (optionally prefixed by ``root``); records keep input order.
    Naive or missing timestamps raise ValueError.
    """
    raise NotImplementedError
