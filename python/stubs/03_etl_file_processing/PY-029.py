"""PY-029 - Bounded-memory external merge sort of a CSV file.

Question: python/questions/03_etl_file_processing/PY-029.md   (python -m lab show PY-029)
Check   : python -m lab check PY-029
"""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path


def external_sort_csv(src: str | os.PathLike[str], dest: str | os.PathLike[str], key_column: str, *,
                      max_records_in_memory: int, work_dir: str | os.PathLike[str],
                      numeric: bool = False,
                      on_run_written: Callable[[Path], None] | None = None) -> int:
    """Sort the CSV ``src`` by ``key_column`` into ``dest`` holding at most
    ``max_records_in_memory`` data rows in memory at a time.

    Sorted runs are written as temporary files in ``work_dir`` (``on_run_written(path)`` is called
    after each run file is complete), then merged. The sort is stable. All run files are removed,
    on success and on failure. Returns the number of data rows written.
    """
    raise NotImplementedError
