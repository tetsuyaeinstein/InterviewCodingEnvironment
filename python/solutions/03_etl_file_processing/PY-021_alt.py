"""PY-021 alternative: chunked map/merge (map-reduce shape).

The row stream is cut into fixed-size chunks with itertools.islice. Each chunk is reduced to a
small partial aggregate (customer -> subtotal) by a pure "map" function, and partials are merged
into the running total. Nothing here needs more than one chunk of rows plus the totals in memory.

Why bother when a single dict is simpler?
  * the map step is pure and independent per chunk, so it can be farmed out to a process pool,
    to Spark tasks, or to one worker per file / byte range, and the merge is associative and
    commutative (Counter-like addition), so partials can be combined in any order;
  * the cost is a little more code and one extra dict per chunk; in a single process it is no
    faster than the reference solution.
Header validation, blank-line handling and amount parsing follow the same contract.
"""
from __future__ import annotations

import csv
import os
from collections.abc import Iterable, Iterator
from decimal import Decimal, InvalidOperation
from itertools import islice

REQUIRED_COLUMNS = ("customer_id", "amount", "status")
CHUNK_ROWS = 5_000


def _open_lines(source) -> tuple[Iterable[str], object | None]:
    if isinstance(source, (str, os.PathLike)):
        f = open(source, encoding="utf-8-sig", newline="")
        return f, f
    return source, None


def _resolve_header(header: list[str]) -> tuple[int, int, int, int]:
    names = [h.strip().lstrip("﻿") if i == 0 else h.strip() for i, h in enumerate(header)]
    idx = []
    for col in REQUIRED_COLUMNS:
        hits = [i for i, n in enumerate(names) if n == col]
        if len(hits) != 1:
            raise ValueError(f"column {col!r} must appear exactly once in the header (found {len(hits)})")
        idx.append(hits[0])
    return idx[0], idx[1], idx[2], len(names)


def _map_chunk(rows: list[tuple[int, list[str]]], cols: tuple[int, int, int, int],
               guest_key: str | None) -> dict[str, Decimal]:
    """Pure function: chunk of (line_no, fields) -> partial totals."""
    i_cust, i_amt, i_status, width = cols
    partial: dict[str, Decimal] = {}
    for line_no, row in rows:
        if len(row) != width:
            raise ValueError(f"line {line_no}: expected {width} fields, got {len(row)}")
        if row[i_status].strip().upper() != "COMPLETED":
            continue
        try:
            amount = Decimal(row[i_amt].strip())
        except InvalidOperation:
            raise ValueError(f"line {line_no}: invalid amount {row[i_amt]!r}") from None
        if not amount.is_finite():
            raise ValueError(f"line {line_no}: non-finite amount {row[i_amt]!r}")
        cust = row[i_cust].strip() or guest_key
        if cust is None:
            continue
        partial[cust] = partial.get(cust, Decimal(0)) + amount
    return partial


def _merge(into: dict[str, Decimal], partial: dict[str, Decimal]) -> None:
    for k, v in partial.items():
        into[k] = into.get(k, Decimal(0)) + v


def spend_per_customer(source: str | os.PathLike[str] | Iterable[str], *,
                       guest_key: str | None = None) -> dict[str, Decimal]:
    lines, owned = _open_lines(source)
    try:
        reader = csv.reader(lines)
        header = next(reader, None)
        if header is None:
            raise ValueError("empty input: no header row")
        cols = _resolve_header(header)

        def numbered() -> Iterator[tuple[int, list[str]]]:
            for row in reader:
                if row and not (len(row) == 1 and not row[0].strip()):
                    yield reader.line_num, row

        stream = numbered()
        totals: dict[str, Decimal] = {}
        while chunk := list(islice(stream, CHUNK_ROWS)):
            _merge(totals, _map_chunk(chunk, cols, guest_key))
        return totals
    finally:
        if owned is not None:
            owned.close()
