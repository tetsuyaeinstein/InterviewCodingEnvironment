"""Hand-curated temporal fixtures: clickstream sessions, JSON payload edge cases,
ingestion delays, intra-day availability changes, kiosk status streams and downtime incidents.
Reserved IDs: customer_events 1-9999, event_ingestion_log 1-9999, devices KIOSK-F01..F03,
device_status_events 1-9999, device_downtime_incidents 1-99.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..common import ts

# ---------------------------------------------------------------------------
# customer_events
# ---------------------------------------------------------------------------
# Customer 40 on 2025-07-01: gaps of exactly 30:00 (same session) and 30:01 (new session),
# duplicate timestamps, a session spanning midnight, and unreliable client session_ids.
_C40 = [
    # event_id, ts, type, session_id
    (1, ts(2025, 7, 1, 10, 0, 0), "app_open", "S-A"),
    (2, ts(2025, 7, 1, 10, 10, 0), "page_view", "S-A"),
    (3, ts(2025, 7, 1, 10, 40, 0), "search", None),            # gap exactly 30m -> same session
    (4, ts(2025, 7, 1, 11, 10, 1), "page_view", "S-A"),        # gap 30m01s -> NEW session (client reused id)
    (5, ts(2025, 7, 1, 11, 10, 1), "add_to_cart", "S-B"),      # identical timestamp
    (6, ts(2025, 7, 1, 11, 20, 0), "checkout", "S-B"),
    (7, ts(2025, 7, 1, 23, 50, 0), "app_open", None),
    (8, ts(2025, 7, 2, 0, 5, 0), "page_view", None),            # crosses midnight, same session
    (9, ts(2025, 7, 3, 9, 0, 0), "app_open", "S-C"),            # single-event session
]

_C40_PAYLOAD = {
    "app_open": {"device": "ios", "app_version": "4.2.0"},
    "page_view": {"device": "ios", "page": "/home"},
    "search": {"device": "ios", "query_length": 7},
    "add_to_cart": {"sku": "SKU-00004", "qty": 1},
    "checkout": {"amount": "6.00", "currency": "USD", "device": "ios", "is_member": True,
                 "items": [{"sku": "SKU-00004", "qty": 1}]},
}

# Customer 67: JSON payload edge cases (all on 2025-08-15).
_C67 = [
    (101, ts(2025, 8, 15, 9, 0), "checkout", {"amount": "12.50", "currency": "USD", "device": "ios", "is_member": True,
                                              "items": [{"sku": "SKU-00001", "qty": 2}, {"sku": "SKU-00003", "qty": 1}]}),
    (102, ts(2025, 8, 15, 9, 5), "checkout", {"amount": 7.25, "currency": "USD", "device": "android", "is_member": False,
                                              "items": []}),                                   # numeric amount, empty array
    (103, ts(2025, 8, 15, 9, 10), "checkout", {"amount": "N/A", "currency": "USD", "device": "web",
                                               "items": [{"sku": "SKU-00001", "qty": "two"}]}),  # invalid amount + qty
    (104, ts(2025, 8, 15, 9, 15), "checkout", {"currency": "USD", "device": "web", "items": None}),  # missing amount, null items
    (105, ts(2025, 8, 15, 9, 20), "checkout", {"amount": None, "currency": "USD", "device": "ios",
                                               "items": [{"sku": "SKU-00001", "qty": 1}, {"sku": "SKU-00001", "qty": 1}]}),  # dup items
    (106, ts(2025, 8, 15, 9, 25), "page_view", {"page": "/home", "device": "ios"}),          # no amount, no items
    (107, ts(2025, 8, 15, 9, 30), "checkout", {"amount": "1e3", "currency": "USD", "is_member": "yes",
                                               "items": [{"sku": "SKU-00005", "qty": 3}]}),  # sci-notation, string bool, no device
    (108, ts(2025, 8, 15, 9, 35), "add_to_cart", {"sku": "SKU-00004", "qty": "3"}),         # qty as string
    (109, ts(2025, 8, 15, 9, 40), "promo_click", {"coupon": "SAVE10", "amount": "-5.00"}),   # negative amount
    (110, ts(2025, 8, 15, 9, 45), "checkout", {"amount": "19.99", "currency": "USD", "device": "web",
                                               "items": {"sku": "SKU-00006", "qty": 1}}),     # items is an OBJECT, not array
    (111, ts(2025, 8, 15, 9, 50), "checkout", {"amount": " 42.10 ", "currency": "USD", "device": "android",
                                               "items": [{"sku": "SKU-00008", "qty": 10}, {"sku": None, "qty": 1}]}),  # padded, null sku
]


def event_rows():
    rows = [(eid, 40, t, typ, sid, _C40_PAYLOAD[typ]) for eid, t, typ, sid in _C40]
    rows += [(eid, 67, t, typ, None, payload) for eid, t, typ, payload in _C67]
    return rows


# ---------------------------------------------------------------------------
# event_ingestion_log fixtures (source_system 'FIXTURE'); delays in seconds are exact.
# ---------------------------------------------------------------------------
def ingestion_rows():
    base = ts(2025, 12, 1, 12, 0, 0)
    rows = []
    log_id = 0
    # 20 cleanly loaded events with delays 0, 30, 60, ..., 570 seconds
    for i in range(20):
        log_id += 1
        rows.append((log_id, f"evt-fx-{i + 1:03d}", "FIXTURE", base, base + timedelta(seconds=30 * i), "LOADED", None, 512))
    # clock skew: ingest_ts BEFORE event_ts
    log_id += 1
    rows.append((log_id, "evt-fx-021", "FIXTURE", base, base - timedelta(seconds=45), "LOADED", None, 512))
    # retried, then loaded 10 minutes after the first attempt
    log_id += 1
    rows.append((log_id, "evt-fx-022", "FIXTURE", base, base + timedelta(seconds=20), "RETRIED", "TIMEOUT", 512))
    log_id += 1
    rows.append((log_id, "evt-fx-022", "FIXTURE", base, base + timedelta(seconds=620), "LOADED", None, 512))
    # rejected and never loaded
    log_id += 1
    rows.append((log_id, "evt-fx-023", "FIXTURE", base, base + timedelta(seconds=5), "REJECTED", "SCHEMA_MISMATCH", 0))
    # loaded, then a duplicate delivery recognised by the loader
    log_id += 1
    rows.append((log_id, "evt-fx-024", "FIXTURE", base, base + timedelta(seconds=15), "LOADED", None, 512))
    log_id += 1
    rows.append((log_id, "evt-fx-024", "FIXTURE", base, base + timedelta(seconds=75), "DUPLICATE", None, 512))
    # extreme late arrival: 2 days
    log_id += 1
    rows.append((log_id, "evt-fx-025", "FIXTURE", base, base + timedelta(days=2), "LOADED", None, 512))
    return rows


# ---------------------------------------------------------------------------
# store_product_availability for store 2, products 4/5/6 (store-local tz America/Chicago)
# ---------------------------------------------------------------------------
AVAILABILITY = [
    # store_id, product_id, valid_from, valid_to, available
    (2, 4, ts(2024, 1, 1, 0), ts(2025, 5, 10, 13, 0, 0), True),
    (2, 4, ts(2025, 5, 10, 13, 0, 0), ts(2025, 5, 10, 15, 0, 0), False),
    (2, 4, ts(2025, 5, 10, 15, 0, 0), None, True),
    (2, 5, ts(2024, 1, 1, 0), None, True),
    (2, 6, ts(2024, 1, 1, 0), ts(2025, 5, 10, 9, 0, 0), True),
    (2, 6, ts(2025, 5, 10, 9, 0, 0), ts(2025, 5, 10, 12, 0, 0), False),
    (2, 6, ts(2025, 5, 10, 12, 0, 0), ts(2025, 5, 10, 20, 0, 0), True),
    # 2025-05-10 20:00 -> 2025-05-11 08:00 is NOT covered by any row (= not stocked)
    (2, 6, ts(2025, 5, 11, 8, 0, 0), None, True),
]
FIXTURE_AVAILABILITY_PAIRS = {(2, 4), (2, 5), (2, 6)}


# ---------------------------------------------------------------------------
# Devices, status events, downtime incidents (January 2025, store 2)
# ---------------------------------------------------------------------------
DEVICES = [
    ("KIOSK-F01", 2, "KIOSK", date(2025, 1, 1), date(2025, 2, 1)),
    ("KIOSK-F02", 2, "KIOSK", date(2025, 1, 1), date(2025, 2, 1)),
    ("KIOSK-F03", 2, "KIOSK", date(2025, 1, 1), date(2025, 3, 1)),   # silent from 2025-02-01 while in service
]


def device_status_rows():
    rows = []
    eid = 0

    def add(dev, t, state, kind, received=None):
        nonlocal eid
        eid += 1
        rows.append((eid, dev, t, received or (t + timedelta(seconds=30)), state, kind))

    jan = [date(2025, 1, 1) + timedelta(days=i) for i in range(31)]
    for d in jan:
        # F01 misses its scheduled report on 01-10, 01-11 and 01-20
        if d.day not in (10, 11, 20):
            add("KIOSK-F01", ts(d.year, d.month, d.day, 2, 0, 0), "UP", "SCHEDULED")
        # F02 reports every day; 01-15 report arrives a day late; 01-22 has two reports
        if d.day == 15:
            add("KIOSK-F02", ts(2025, 1, 15, 2, 0, 0), "UP", "SCHEDULED", received=ts(2025, 1, 16, 3, 0, 0))
        else:
            add("KIOSK-F02", ts(d.year, d.month, d.day, 2, 0, 0), "UP", "SCHEDULED")
        if d.day == 22:
            add("KIOSK-F02", ts(2025, 1, 22, 2, 5, 0), "UP", "SCHEDULED")
        # F03 reports every day in January, then goes silent until decommissioning on 03-01
        add("KIOSK-F03", ts(d.year, d.month, d.day, 2, 0, 0), "UP", "SCHEDULED")

    # F01 state changes on 2025-01-15, delivered out of order (received_at not monotonic)
    add("KIOSK-F01", ts(2025, 1, 15, 8, 0, 0), "DOWN", "CHANGE", received=ts(2025, 1, 15, 9, 45, 0))
    add("KIOSK-F01", ts(2025, 1, 15, 9, 30, 0), "UP", "CHANGE", received=ts(2025, 1, 15, 9, 30, 20))
    add("KIOSK-F01", ts(2025, 1, 15, 9, 30, 0), "DOWN", "CHANGE", received=ts(2025, 1, 15, 9, 31, 0))
    add("KIOSK-F01", ts(2025, 1, 15, 10, 0, 0), "UP", "CHANGE", received=ts(2025, 1, 15, 10, 0, 10))
    add("KIOSK-F01", ts(2025, 1, 16, 12, 0, 0), "DOWN", "CHANGE")
    add("KIOSK-F01", ts(2025, 1, 16, 12, 30, 0), "UP", "CHANGE")
    # F02: duplicate DOWN (two consecutive DOWN events) then UP
    add("KIOSK-F02", ts(2025, 1, 20, 23, 30, 0), "DOWN", "CHANGE")
    add("KIOSK-F02", ts(2025, 1, 20, 23, 45, 0), "DOWN", "CHANGE")
    add("KIOSK-F02", ts(2025, 1, 21, 0, 30, 0), "UP", "CHANGE")
    return rows


# incident_id, device_id, reported_by, down_from, down_to   -- [down_from, down_to)
INCIDENTS = [
    (1, "KIOSK-F01", "MONITORING", ts(2025, 1, 15, 8, 0), ts(2025, 1, 15, 9, 30)),
    (2, "KIOSK-F01", "TECHNICIAN", ts(2025, 1, 15, 9, 0), ts(2025, 1, 15, 10, 0)),    # overlaps #1
    (3, "KIOSK-F01", "VENDOR", ts(2025, 1, 15, 10, 0), ts(2025, 1, 15, 10, 15)),      # touches #2
    (4, "KIOSK-F01", "MONITORING", ts(2025, 1, 15, 8, 30), ts(2025, 1, 15, 8, 45)),   # nested in #1
    (5, "KIOSK-F01", "MONITORING", ts(2025, 1, 16, 12, 0), ts(2025, 1, 16, 12, 30)),  # separate
    (6, "KIOSK-F02", "MONITORING", ts(2025, 1, 20, 23, 30), ts(2025, 1, 21, 0, 30)),  # crosses midnight
    (7, "KIOSK-F02", "VENDOR", ts(2025, 1, 20, 23, 30), ts(2025, 1, 21, 0, 30)),      # exact duplicate of #6
    (8, "KIOSK-F03", "TECHNICIAN", ts(2025, 1, 25, 14, 0), ts(2025, 1, 25, 14, 20)),
]
