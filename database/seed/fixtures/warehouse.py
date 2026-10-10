"""Hand-curated warehouse fixtures: CDC edge cases, pipeline control tables,
source/target reconciliation rows, raw message deliveries and untrusted staging rows.

Reserved: CDC business keys 'FX-xxxx' (LSNs >= 9,000,000), pipeline run_ids 1-99,
reconciliation transaction_ids 90001-90020 (exist ONLY in source/target_transactions),
raw_transaction_events delivery_ids 1-99, stg_transaction_items load_batch_id 1.
"""
from __future__ import annotations

from datetime import timedelta

from ..common import money, ts

# ---------------------------------------------------------------------------
# CDC: (source_system, business_key, op, source_lsn, commit_ts, ingested_at, payload)
# cdc_event_id is assigned later in arrival (ingested_at) order together with generated events.
# ---------------------------------------------------------------------------
def _p(key, amount, status, customer_id=23, store_id=1):
    return {"business_key": key, "amount": amount, "status": status, "customer_id": customer_id, "store_id": store_id}


def _d(key):
    return {"business_key": key}


D = 31  # all fixture CDC commits happen on 2025-12-31


def cdc_rows():
    t = lambda h, m=0, s=0: ts(2025, 12, D, h, m, s)  # noqa: E731
    return [
        # FX-0001: update arrives out of order; latest by ingested_at is NOT latest by LSN
        ("POS", "FX-0001", "I", 9000010, t(10, 0), t(10, 0, 5), _p("FX-0001", "50.00", "PENDING")),
        ("POS", "FX-0001", "U", 9000020, t(10, 5), t(10, 20, 0), _p("FX-0001", "55.00", "PENDING")),
        ("POS", "FX-0001", "U", 9000030, t(10, 10), t(10, 11, 0), _p("FX-0001", "60.00", "COMPLETED")),
        # FX-0002: stale update (older LSN) arrives AFTER the delete -> must not resurrect
        ("POS", "FX-0002", "I", 9000110, t(11, 0), t(11, 0, 5), _p("FX-0002", "20.00", "PENDING")),
        ("POS", "FX-0002", "D", 9000120, t(11, 5), t(11, 5, 5), _d("FX-0002")),
        ("POS", "FX-0002", "U", 9000115, t(11, 2), t(11, 30, 0), _p("FX-0002", "25.00", "COMPLETED")),
        # FX-0003: delete followed by a legitimate re-insert with a higher LSN
        ("POS", "FX-0003", "I", 9000210, t(12, 0), t(12, 0, 5), _p("FX-0003", "30.00", "PENDING")),
        ("POS", "FX-0003", "D", 9000220, t(12, 5), t(12, 5, 5), _d("FX-0003")),
        ("POS", "FX-0003", "I", 9000230, t(12, 10), t(12, 10, 5), _p("FX-0003", "35.00", "COMPLETED")),
        # FX-0004: the same change event delivered twice (identical LSN + payload)
        ("POS", "FX-0004", "I", 9000310, t(13, 0), t(13, 0, 5), _p("FX-0004", "40.00", "PENDING")),
        ("POS", "FX-0004", "U", 9000320, t(13, 5), t(13, 5, 5), _p("FX-0004", "40.00", "COMPLETED")),
        ("POS", "FX-0004", "U", 9000320, t(13, 5), t(13, 7, 5), _p("FX-0004", "40.00", "COMPLETED")),
        # FX-0005: two updates with the SAME commit_ts; LSN decides; arrival reversed
        ("POS", "FX-0005", "I", 9000410, t(14, 0), t(14, 0, 5), _p("FX-0005", "10.00", "PENDING")),
        ("POS", "FX-0005", "U", 9000420, t(14, 5), t(14, 5, 20), _p("FX-0005", "12.00", "PENDING")),
        ("POS", "FX-0005", "U", 9000430, t(14, 5), t(14, 5, 10), _p("FX-0005", "15.00", "COMPLETED")),
        # FX-0006: conflicting events sharing one LSN (anomaly to flag, not silently pick)
        ("POS", "FX-0006", "I", 9000510, t(15, 0), t(15, 0, 5), _p("FX-0006", "70.00", "PENDING")),
        ("POS", "FX-0006", "U", 9000520, t(15, 5), t(15, 5, 5), _p("FX-0006", "75.00", "COMPLETED")),
        ("POS", "FX-0006", "U", 9000520, t(15, 5), t(15, 5, 6), _p("FX-0006", "80.00", "COMPLETED")),
        # FX-0007: tombstone for a key never inserted
        ("POS", "FX-0007", "D", 9000610, t(16, 0), t(16, 0, 5), _d("FX-0007")),
        # FX-0008: insert arrives after its own update
        ("POS", "FX-0008", "I", 9000710, t(17, 0), t(17, 30, 0), _p("FX-0008", "90.00", "PENDING")),
        ("POS", "FX-0008", "U", 9000720, t(17, 1), t(17, 1, 5), _p("FX-0008", "95.00", "COMPLETED")),
        # FX-0010: ordinary well-behaved history
        ("POS", "FX-0010", "I", 9000910, t(19, 0), t(19, 0, 5), _p("FX-0010", "5.00", "PENDING")),
        ("POS", "FX-0010", "U", 9000920, t(19, 5), t(19, 5, 5), _p("FX-0010", "6.00", "PENDING")),
        ("POS", "FX-0010", "U", 9000930, t(19, 10), t(19, 10, 5), _p("FX-0010", "7.00", "PENDING")),
        ("POS", "FX-0010", "U", 9000940, t(19, 15), t(19, 15, 5), _p("FX-0010", "7.00", "COMPLETED")),
        # Same business_key text and SAME LSN numbers in a different source system
        ("ECOM", "FX-0001", "I", 9000010, t(10, 0), t(10, 0, 9), _p("FX-0001", "500.00", "PENDING", store_id=6)),
        ("ECOM", "FX-0001", "U", 9000020, t(10, 30), t(10, 30, 9), _p("FX-0001", "510.00", "COMPLETED", store_id=6)),
    ]


# ---------------------------------------------------------------------------
# Pipeline runs: pipeline 'transactions_incremental', hourly windows on 2025-12-15
# ---------------------------------------------------------------------------
def _run(run_id, source, h0, h1, status, started_after_h=None, error=None):
    w0, w1 = ts(2025, 12, 15, h0), ts(2025, 12, 15, h1)
    started = (ts(2025, 12, 15, started_after_h) if started_after_h is not None else w1) + timedelta(minutes=2)
    ended = None if status == "RUNNING" else started + timedelta(minutes=3)
    rows = None if status != "SUCCEEDED" else 100 + run_id
    return (run_id, "transactions_incremental", source, started, ended, status, w0, w1,
            rows, rows, error)


def pipeline_run_rows():
    return [
        _run(1, "POS", 0, 1, "SUCCEEDED"),
        _run(2, "POS", 1, 2, "SUCCEEDED"),
        _run(3, "POS", 1, 2, "SUCCEEDED", started_after_h=2),          # harmless re-run of the same window
        _run(4, "POS", 2, 3, "SUCCEEDED"),
        _run(5, "POS", 3, 4, "FAILED", error="connection reset by peer"),
        _run(6, "POS", 4, 5, "SUCCEEDED"),
        _run(7, "POS", 3, 4, "SUCCEEDED", started_after_h=5),          # retry fills the gap later
        _run(8, "POS", 5, 6, "SUCCEEDED"),
        _run(9, "ECOM", 0, 1, "SUCCEEDED"),
        _run(10, "ECOM", 1, 2, "FAILED", error="HTTP 503 from source API"),
        _run(11, "ECOM", 2, 3, "SUCCEEDED"),
        _run(12, "ECOM", 3, 4, "SUCCEEDED"),
        _run(13, "KIOSK", 0, 1, "SUCCEEDED"),
        _run(14, "KIOSK", 1, 2, "SUCCEEDED"),
        _run(15, "KIOSK", 2, 3, "RUNNING"),
        _run(16, "KIOSK", 3, 4, "SUCCEEDED", started_after_h=4),
        _run(17, "MOBILE", 0, 1, "FAILED", error="schema validation failed"),
        _run(18, "MOBILE", 0, 1, "FAILED", started_after_h=2, error="schema validation failed"),
    ]


def pipeline_watermark_rows():
    return [
        # pipeline_name, source_system, watermark_ts, committed_offset, updated_at
        ("transactions_incremental", "POS", ts(2025, 12, 15, 6), 600, ts(2025, 12, 15, 6, 10)),
        ("transactions_incremental", "ECOM", ts(2025, 12, 15, 4), 400, ts(2025, 12, 15, 4, 10)),   # naive max -> unsafe
        ("transactions_incremental", "KIOSK", ts(2025, 12, 15, 2), 200, ts(2025, 12, 15, 2, 10)),
        ("transactions_incremental", "MOBILE", ts(2025, 12, 15, 0), 0, ts(2025, 12, 15, 0, 0)),
        ("daily_sales_report", "ALL", ts(2026, 1, 1, 0), None, ts(2026, 1, 1, 0, 30)),
    ]


# ---------------------------------------------------------------------------
# Reconciliation rows 90001-90020 (source vs target)
# ---------------------------------------------------------------------------
_EXTRACTED = ts(2026, 1, 1, 1, 0)
_LOADED = ts(2026, 1, 1, 1, 30)


def _recon(i, **over):
    row = {
        "transaction_id": 90000 + i, "customer_id": 23, "store_id": 1,
        "transaction_ts": ts(2025, 12, 10, 12, i), "amount": money(f"{10 + i}.00"),
        "status": "COMPLETED", "payment_method": "CARD", "merchant_ref": f"MR-{i:03d}", "note": None,
    }
    row.update(over)
    return row


def _tuple(r, stamp):
    return (r["transaction_id"], r["customer_id"], r["store_id"], r["transaction_ts"], r["amount"],
            r["status"], r["payment_method"], r["merchant_ref"], r["note"], stamp)


def recon_rows():
    src, tgt = [], []
    for i in range(1, 6):                                       # 90001-90005 identical
        src.append(_recon(i)); tgt.append(_recon(i))
    src.append(_recon(6))                                       # 90006 missing in target
    tgt.append(_recon(7))                                       # 90007 extra in target
    src.append(_recon(8, amount=money("10.00"))); tgt.append(_recon(8, amount=money("10.01")))
    src.append(_recon(9, status="COMPLETED")); tgt.append(_recon(9, status="CANCELLED"))
    src.append(_recon(10, customer_id=None)); tgt.append(_recon(10, customer_id=1001))   # NULL vs value
    src.append(_recon(11, customer_id=None)); tgt.append(_recon(11, customer_id=None))   # NULL = NULL -> same
    src.append(_recon(12, payment_method=None)); tgt.append(_recon(12, payment_method=None))
    src.append(_recon(13, note="")); tgt.append(_recon(13, note=None))                   # '' vs NULL -> differ
    src.append(_recon(14)); tgt.append(_recon(14, transaction_ts=ts(2025, 12, 10, 12, 14, 1)))
    # concatenation-ambiguity pairs (identical in source and target)
    for i, (mr, note) in {15: ("AB", "C"), 16: ("A", "BC"), 17: ("X|Y", None), 18: ("X", "Y")}.items():
        src.append(_recon(i, merchant_ref=mr, note=note)); tgt.append(_recon(i, merchant_ref=mr, note=note))
    # literal string 'NULL' vs real NULL (identical across systems, but must fingerprint differently)
    src.append(_recon(19, merchant_ref="MR-019", note="NULL")); tgt.append(_recon(19, merchant_ref="MR-019", note="NULL"))
    src.append(_recon(20, merchant_ref="MR-019", note=None, transaction_ts=ts(2025, 12, 10, 12, 19), amount=money("29.00")))
    tgt.append(_recon(20, merchant_ref="MR-019", note=None, transaction_ts=ts(2025, 12, 10, 12, 19), amount=money("29.00")))
    return [_tuple(r, _EXTRACTED) for r in src], [_tuple(r, _LOADED) for r in tgt]


# ---------------------------------------------------------------------------
# raw_transaction_events (delivery_id 1-99)
# ---------------------------------------------------------------------------
def _msg(tid, amount, status="COMPLETED"):
    return {"transaction_id": tid, "amount": amount, "status": status, "store_id": 1}


def raw_event_rows():
    base = ts(2025, 10, 20, 10)
    return [
        # delivery_id, message_id, transaction_id, event_type, delivered_at, payload
        (1, "msg-fx-2301-c", 2301, "CREATED", base + timedelta(seconds=5), _msg(2301, "100.00")),
        (2, "msg-fx-2301-c", 2301, "CREATED", base + timedelta(seconds=35), _msg(2301, "100.00")),   # redelivery
        (3, "msg-fx-2301-c", 2301, "CREATED", base + timedelta(minutes=5), _msg(2301, "100.00")),    # redelivery
        (4, "msg-fx-2302-c", 2302, "CREATED", base + timedelta(minutes=6), _msg(2302, "40.00", "PENDING")),
        (5, "msg-fx-2302-s1", 2302, "STATUS_CHANGED", base + timedelta(minutes=7), _msg(2302, "40.00")),
        (6, "msg-fx-2401-c", 2401, "CREATED", base + timedelta(minutes=8), _msg(2401, "80.00")),
        (7, "msg-fx-2401-c2", 2401, "CREATED", base + timedelta(minutes=9), _msg(2401, "80.00")),   # double-posted
        (8, "msg-fx-2501-c", 2501, "CREATED", base + timedelta(minutes=10), _msg(2501, "120.00")),
        (9, "msg-fx-2601-c", 2601, "CREATED", base + timedelta(minutes=11), _msg(2601, "30.00")),
        (10, "msg-fx-2601-c2", 2601, "CREATED", base + timedelta(minutes=12), _msg(2601, "33.00")),  # conflicting dup
    ]


# ---------------------------------------------------------------------------
# stg_transaction_items, load_batch_id 1: orphans / NULLs / duplicates
# ---------------------------------------------------------------------------
def stg_item_rows():
    return [
        # load_batch_id, transaction_id, line_number, product_id, quantity, unit_price, discount_amount
        (1, 99999999, 1, 1, 1, money("18.00"), money("0")),        # transaction missing
        (1, 2301, 3, 999999, 1, money("5.00"), money("0")),        # product missing
        (1, 88888888, 1, 777777, 2, money("1.00"), money("0")),    # both missing
        (1, 2302, 2, None, 1, money("3.00"), money("0")),          # NULL product_id
        (1, None, None, 4, 1, money("6.00"), money("0")),          # NULL transaction_id
        (1, 2401, 1, 7, 1, money("80.00"), money("0")),            # valid line ...
        (1, 2401, 1, 7, 1, money("80.00"), money("0")),            # ... loaded twice (dup, not orphan)
        (1, 2302, 1, 7, 1, money("40.00"), money("0")),            # valid
    ]
