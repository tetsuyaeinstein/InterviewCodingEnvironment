"""PY-050 reference solution: parse/validate -> dedupe -> stage (upsert) -> summarise -> reconcile."""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

ALLOWED_STATUSES = frozenset({"COMPLETED", "PENDING", "CANCELLED", "DECLINED"})
REQUIRED = ("transaction_id", "store_id", "transaction_ts", "amount", "status", "sequence")
MAX_AMOUNT = Decimal("9999999999.99")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Rejection:
    line: int
    reason: str


@dataclass
class RunReport:
    rows_read: int = 0
    rejected: list[Rejection] = field(default_factory=list)
    duplicates_dropped: int = 0
    upserted: int = 0
    unchanged: int = 0
    daily_summary: dict[date, Decimal] = field(default_factory=dict)
    reconciliation_ok: bool = True


class ReconciliationError(Exception):
    """Raised in strict mode when the staged totals do not match the Python summary."""


# ----------------------------------------------------------------------------- parsing

def _is_int(v, lo: int, hi: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _parse_amount(v) -> Decimal | None:
    if isinstance(v, bool) or not isinstance(v, (str, int, Decimal)):
        return None
    try:
        amount = Decimal(v.strip() if isinstance(v, str) else v)
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT:
        return None
    if amount.as_tuple().exponent < -2:
        return None
    return amount.quantize(CENT)


def parse_line(text: str) -> tuple[dict | None, str | None]:
    """Return (row, None) for a valid line or (None, reason_code)."""
    try:
        obj = json.loads(text, parse_float=Decimal)
    except ValueError:
        return None, "invalid_json"
    if not isinstance(obj, dict):
        return None, "not_an_object"
    for name in REQUIRED:
        if name not in obj:
            return None, f"missing_field:{name}"
    if not _is_int(obj["transaction_id"], 1, 2**63 - 1):
        return None, "invalid_transaction_id"
    if not _is_int(obj["store_id"], 1, 2**31 - 1):
        return None, "invalid_store_id"
    raw_ts = obj["transaction_ts"]
    if not isinstance(raw_ts, str):
        return None, "invalid_timestamp"
    try:
        ts = datetime.fromisoformat(raw_ts.strip())
    except ValueError:
        return None, "invalid_timestamp"
    if ts.tzinfo is None or ts.utcoffset() is None:
        return None, "naive_timestamp"
    amount = _parse_amount(obj["amount"])
    if amount is None:
        return None, "invalid_amount"
    if obj["status"] not in ALLOWED_STATUSES:
        return None, "invalid_status"
    if not _is_int(obj["sequence"], 0, 2**31 - 1):
        return None, "invalid_sequence"
    return {
        "transaction_id": obj["transaction_id"], "store_id": obj["store_id"],
        "transaction_ts": ts.astimezone(timezone.utc), "amount": amount,
        "status": obj["status"], "sequence": obj["sequence"],
    }, None


# ----------------------------------------------------------------------------- database

DDL = """
CREATE TABLE IF NOT EXISTS stg_txn (
    transaction_id bigint PRIMARY KEY,
    store_id       integer NOT NULL,
    transaction_ts timestamptz NOT NULL,
    amount         numeric(12,2) NOT NULL,
    status         text NOT NULL,
    sequence       integer NOT NULL
)
"""

UPSERT = """
INSERT INTO stg_txn AS t (transaction_id, store_id, transaction_ts, amount, status, sequence)
SELECT * FROM unnest(%s::bigint[], %s::int[], %s::timestamptz[], %s::numeric[], %s::text[], %s::int[])
ON CONFLICT (transaction_id) DO UPDATE
   SET store_id = EXCLUDED.store_id, transaction_ts = EXCLUDED.transaction_ts,
       amount = EXCLUDED.amount, status = EXCLUDED.status, sequence = EXCLUDED.sequence
 WHERE t.sequence < EXCLUDED.sequence
RETURNING t.transaction_id
"""

STAGED_TOTALS = """
SELECT (transaction_ts AT TIME ZONE 'UTC')::date AS day, sum(amount)
FROM stg_txn
WHERE transaction_id = ANY(%s) AND status = 'COMPLETED'
GROUP BY 1
"""


def run_pipeline(conn, lines: Iterable[str], *, batch_size: int = 500, strict: bool = False) -> RunReport:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    report = RunReport()

    # 1 + 2: parse, validate, dedupe (highest sequence wins; later line wins ties)
    winners: dict[int, dict] = {}
    valid = 0
    for lineno, text in enumerate(lines, start=1):
        if not text.strip():
            continue
        report.rows_read += 1
        row, reason = parse_line(text)
        if row is None:
            report.rejected.append(Rejection(lineno, reason))
            continue
        valid += 1
        current = winners.get(row["transaction_id"])
        if current is None or row["sequence"] >= current["sequence"]:
            winners[row["transaction_id"]] = row
    report.duplicates_dropped = valid - len(winners)

    # 4a: Python-side summary
    summary: dict[date, Decimal] = {}
    for row in winners.values():
        if row["status"] == "COMPLETED":
            day = row["transaction_ts"].date()          # already UTC
            summary[day] = summary.get(day, Decimal(0)) + row["amount"]
    report.daily_summary = dict(sorted(summary.items()))

    # 3 + 4b: one transaction for table creation, upserts and the reconciliation read
    ordered = sorted(winners.values(), key=lambda r: r["transaction_id"])   # stable lock order
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(DDL)
            for i in range(0, len(ordered), batch_size):
                chunk = ordered[i:i + batch_size]
                cur.execute(UPSERT, (
                    [r["transaction_id"] for r in chunk], [r["store_id"] for r in chunk],
                    [r["transaction_ts"] for r in chunk], [r["amount"] for r in chunk],
                    [r["status"] for r in chunk], [r["sequence"] for r in chunk],
                ))
                report.upserted += len(cur.fetchall())
            report.unchanged = len(ordered) - report.upserted

            cur.execute(STAGED_TOTALS, ([r["transaction_id"] for r in ordered],))
            staged = {day: total for day, total in cur.fetchall()}
        report.reconciliation_ok = staged == report.daily_summary
        if strict and not report.reconciliation_ok:
            raise ReconciliationError(f"staged totals {staged} != summary {report.daily_summary}")
    return report
