"""PY-043 reference solution: dedupe in Python, one INSERT ... SELECT unnest(...) ON CONFLICT per batch."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from psycopg import sql

REQUIRED = ("business_key", "amount", "status", "seq")


@dataclass(frozen=True)
class LoadResult:
    inserted: int
    updated: int
    skipped: int


def _dedupe(rows: Iterable[dict]) -> tuple[list[dict], int, int]:
    """Return (winning rows, total rows read, rows dropped as duplicates)."""
    best: dict[str, dict] = {}
    total = 0
    for row in rows:
        missing = [k for k in REQUIRED if k not in row]
        if missing:
            raise KeyError(f"row is missing {missing}")
        total += 1
        cur = best.get(row["business_key"])
        # `>=` so that, on a seq tie, the later row wins.
        if cur is None or row["seq"] >= cur["seq"]:
            best[row["business_key"]] = row
    return list(best.values()), total, total - len(best)


def _statement(table: str) -> sql.Composed:
    return sql.SQL(
        """
        INSERT INTO {t} AS t (business_key, amount, status, seq)
        SELECT * FROM unnest(%s::text[], %s::numeric[], %s::text[], %s::int[])
        ON CONFLICT (business_key) DO UPDATE
           SET amount = EXCLUDED.amount, status = EXCLUDED.status, seq = EXCLUDED.seq
         WHERE t.seq < EXCLUDED.seq
        RETURNING (xmax = 0) AS inserted
        """
    ).format(t=sql.Identifier(table))


def load_batch(conn, rows: Iterable[dict], *, table: str = "txn_load", batch_size: int = 500) -> LoadResult:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    winners, total, dropped = _dedupe(rows)
    if not winners:
        return LoadResult(0, 0, 0)
    stmt = _statement(table)
    inserted = updated = 0
    with conn.transaction():  # all batches commit together, or none does
        with conn.cursor() as cur:
            for i in range(0, len(winners), batch_size):
                chunk = winners[i:i + batch_size]
                cur.execute(stmt, (
                    [r["business_key"] for r in chunk],
                    [r["amount"] for r in chunk],
                    [r["status"] for r in chunk],
                    [r["seq"] for r in chunk],
                ))
                for (was_inserted,) in cur.fetchall():
                    if was_inserted:
                        inserted += 1
                    else:
                        updated += 1
    return LoadResult(inserted, updated, total - inserted - updated)
