"""PY-029 reference solution: classic two-phase external merge sort.

Phase 1 (run generation): read at most M rows, stable-sort them, write a CSV run file to the work
dir, repeat. Phase 2 (merge): heapq.merge over one lazy reader per run. heapq.merge is stable
across its inputs (ties go to the earlier iterable), runs are created in input order and each run
is stably sorted, so equal keys keep their original order end to end.

Memory: M rows during phase 1; one row + one file buffer per run during phase 2.
I/O: every row is read twice and written twice (sequentially).
"""
from __future__ import annotations

import csv
import heapq
import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _key_func(index: int, numeric: bool) -> Callable[[list[str]], object]:
    if not numeric:
        return lambda row: row[index]

    def key(row: list[str]) -> Decimal:
        try:
            value = Decimal(row[index].strip())
        except InvalidOperation:
            raise ValueError(f"non-numeric sort key {row[index]!r}") from None
        if not value.is_finite():
            raise ValueError(f"non-finite sort key {row[index]!r}")
        return value
    return key


def _write_run(rows: list[list[str]], key, work_dir: str, runs: list[str]) -> str:
    rows.sort(key=key)                                  # list.sort is stable
    fd, path = tempfile.mkstemp(dir=work_dir, prefix="run-", suffix=".csv")
    runs.append(path)                                   # registered before writing: always cleaned up
    with open(fd, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    return path


def _read_run(path: str, stack: ExitStack) -> Iterator[list[str]]:
    f = stack.enter_context(open(path, encoding="utf-8", newline=""))
    return csv.reader(f)


def external_sort_csv(src: str | os.PathLike[str], dest: str | os.PathLike[str], key_column: str, *,
                      max_records_in_memory: int, work_dir: str | os.PathLike[str],
                      numeric: bool = False,
                      on_run_written: Callable[[Path], None] | None = None) -> int:
    if max_records_in_memory < 1:
        raise ValueError("max_records_in_memory must be >= 1")
    work = os.fspath(work_dir)
    dest_path = os.path.abspath(os.fspath(dest))
    runs: list[str] = []
    try:
        # ---- phase 1: sorted runs ------------------------------------------------------
        with open(src, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                raise ValueError("empty input: no header row")
            if header.count(key_column) != 1:
                raise ValueError(f"key column {key_column!r} must appear exactly once in {header}")
            key = _key_func(header.index(key_column), numeric)
            buffer: list[list[str]] = []
            total = 0
            for row in reader:
                if not row:
                    continue                            # blank line
                if len(row) != len(header):
                    raise ValueError(f"line {reader.line_num}: expected {len(header)} fields, got {len(row)}")
                key(row)                                # validate early (numeric keys)
                buffer.append(row)
                total += 1
                if len(buffer) == max_records_in_memory:
                    run = _write_run(buffer, key, work, runs)
                    buffer = []
                    if on_run_written:
                        on_run_written(Path(run))
            if buffer:
                run = _write_run(buffer, key, work, runs)
                buffer = []
                if on_run_written:
                    on_run_written(Path(run))

        # ---- phase 2: k-way merge into a temp file next to dest, then atomic replace ----
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dest_path), prefix=".sort-", suffix=".tmp")
        try:
            with ExitStack() as stack, open(fd, "w", encoding="utf-8", newline="") as out:
                writer = csv.writer(out)
                writer.writerow(header)
                writer.writerows(heapq.merge(*(_read_run(p, stack) for p in runs), key=key))
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, dest_path)
        except BaseException:
            os.unlink(tmp)
            raise
        return total
    finally:
        for p in runs:                                  # files are closed by now (Windows!)
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
