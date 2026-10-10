"""PY-043 alternative: executemany(..., returning=True) with psycopg's pipelined batching.

Simpler to read (row-shaped parameters, no column arrays) at the cost of one protocol message
per row inside the pipeline. For very large loads, COPY into a temp table + one MERGE/INSERT SELECT is faster.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from psycopg import sql


@dataclass(frozen=True)
class LoadResult:
    inserted: int
    updated: int
    skipped: int


def load_batch(conn, rows: Iterable[dict], *, table: str = "txn_load", batch_size: int = 500) -> LoadResult:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    best: dict[str, dict] = {}
    total = 0
    for row in rows:
        for key in ("business_key", "amount", "status", "seq"):
            if key not in row:
                raise ValueError(f"missing {key}")
        total += 1
        prev = best.get(row["business_key"])
        if prev is None or row["seq"] >= prev["seq"]:
            best[row["business_key"]] = row
    if not best:
        return LoadResult(0, 0, 0)

    stmt = sql.SQL(
        "INSERT INTO {t} AS t (business_key, amount, status, seq) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (business_key) DO UPDATE "
        "SET amount = EXCLUDED.amount, status = EXCLUDED.status, seq = EXCLUDED.seq "
        "WHERE t.seq < EXCLUDED.seq RETURNING (xmax = 0)"
    ).format(t=sql.Identifier(table))

    winners = list(best.values())
    inserted = updated = 0
    with conn.transaction():
        with conn.cursor() as cur:
            for i in range(0, len(winners), batch_size):
                params = [(r["business_key"], r["amount"], r["status"], r["seq"])
                          for r in winners[i:i + batch_size]]
                cur.executemany(stmt, params, returning=True)
                while True:  # one result set per parameter tuple; empty when the WHERE skipped the row
                    for (was_inserted,) in cur.fetchall():
                        inserted += bool(was_inserted)
                        updated += not was_inserted
                    if not cur.nextset():
                        break
    return LoadResult(inserted, updated, total - inserted - updated)
