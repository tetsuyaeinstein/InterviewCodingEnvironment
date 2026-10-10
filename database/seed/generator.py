"""Deterministic data generator + loader for the interview lab.

Flow:
  1. build rows (hand-written fixtures first, then pseudo-random data) into COPY-format
     temp files under .lab_tmp/seed_<profile>/;
  2. in ONE database transaction: TRUNCATE every lab table, COPY the files in FK order,
     derive summary/landing tables with INSERT ... SELECT, record lab_meta;
  3. VACUUM ANALYZE.

The same profile + SEED_VERSION always yields byte-identical business data (verified by the
checksum stored in lab_meta and by tests/test_seed_integrity.py).
"""
from __future__ import annotations

import bisect
import hashlib
import json
import shutil
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .common import END, SCD2_OPEN_END, SEED_VERSION, START, UTC, daterange, money, rand_ts, rng_for, ts
from .fixtures import core, temporal, warehouse
from .profiles import PROFILES, Profile

ROOT = Path(__file__).resolve().parents[2]

COLUMNS: dict[str, list[str]] = {
    "stores": ["store_id", "store_code", "store_name", "region", "store_type", "timezone", "opened_on", "closed_on"],
    "product_categories": ["category_id", "category_name", "department"],
    "products": ["product_id", "sku", "product_name", "category_id", "standard_price", "is_active", "launched_on"],
    "product_price_history": ["product_id", "valid_from", "valid_to", "price"],
    "customers": ["customer_id", "customer_code", "registered_at", "segment", "home_region", "status", "loyalty_tier"],
    "dim_customer_scd2": ["customer_sk", "customer_id", "segment", "region", "status", "effective_from", "effective_to", "is_current"],
    "transactions": ["transaction_id", "customer_id", "store_id", "transaction_ts", "gross_amount", "currency",
                     "transaction_status", "payment_method", "source_system", "ingested_at"],
    "transaction_items": ["transaction_id", "line_number", "product_id", "quantity", "unit_price", "discount_amount"],
    "refunds": ["refund_id", "transaction_id", "refund_ts", "refund_amount", "reason"],
    "customer_events": ["event_id", "customer_id", "event_ts", "event_type", "session_id", "payload"],
    "event_ingestion_log": ["log_id", "raw_event_id", "source_system", "event_ts", "ingest_ts", "ingestion_status",
                            "error_reason", "payload_bytes"],
    "store_product_availability": ["store_id", "product_id", "valid_from", "valid_to", "available"],
    "subscriptions": ["subscription_id", "customer_id", "plan", "start_date", "end_date", "status", "monthly_fee"],
    "employees": ["employee_id", "manager_id", "employee_name", "department", "job_title", "salary", "hire_date",
                  "termination_date"],
    "accounts": ["account_id", "customer_id", "account_type", "opened_at", "credit_limit"],
    "account_ledger": ["entry_id", "account_id", "transaction_id", "posting_ts", "signed_amount", "entry_type"],
    "devices": ["device_id", "store_id", "device_type", "installed_on", "decommissioned_on"],
    "device_status_events": ["event_id", "device_id", "event_ts", "received_at", "state", "event_kind"],
    "device_downtime_incidents": ["incident_id", "device_id", "reported_by", "down_from", "down_to"],
    "daily_store_snapshot": ["snapshot_date", "store_id", "product_id", "on_hand_qty", "units_sold"],
    "cdc_transaction_events": ["cdc_event_id", "source_system", "business_key", "operation", "source_lsn", "commit_ts",
                               "ingested_at", "payload"],
    "pipeline_runs": ["run_id", "pipeline_name", "source_system", "started_at", "ended_at", "status", "window_start",
                      "window_end", "rows_read", "rows_written", "error_message"],
    "pipeline_watermarks": ["pipeline_name", "source_system", "watermark_ts", "committed_offset", "updated_at"],
    "source_transactions": ["transaction_id", "customer_id", "store_id", "transaction_ts", "amount", "status",
                            "payment_method", "merchant_ref", "note", "extracted_at"],
    "target_transactions": ["transaction_id", "customer_id", "store_id", "transaction_ts", "amount", "status",
                            "payment_method", "merchant_ref", "note", "loaded_at"],
    "raw_transaction_events": ["delivery_id", "message_id", "transaction_id", "event_type", "delivered_at", "payload"],
    "stg_transaction_items": ["load_batch_id", "transaction_id", "line_number", "product_id", "quantity", "unit_price",
                              "discount_amount"],
}
LOAD_ORDER = list(COLUMNS)  # dict order above is FK-safe
DERIVED_TABLES = ["customer_daily_activity", "fact_sales_partitioned"]
ALL_TABLES = LOAD_ORDER + DERIVED_TABLES

REGIONS = ["NORTH", "SOUTH", "EAST", "WEST"]
REGION_TZ = {"NORTH": "America/Chicago", "SOUTH": "America/Phoenix", "EAST": "America/New_York",
             "WEST": "America/Los_Angeles"}


# ---------------------------------------------------------------------------
# COPY text-format writer
# ---------------------------------------------------------------------------
def _fmt(v) -> str:
    if v is None:
        return r"\N"
    if v is True:
        return "t"
    if v is False:
        return "f"
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (date, Decimal, int)):
        return str(v)
    if isinstance(v, (dict, list)):
        v = json.dumps(v, separators=(",", ":"))
    s = str(v)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


class Writers:
    def __init__(self, directory: Path):
        self.dir = directory
        self.files: dict[str, object] = {}
        self.counts: dict[str, int] = defaultdict(int)

    def row(self, table: str, values) -> None:
        f = self.files.get(table)
        if f is None:
            f = open(self.dir / f"{table}.copy", "w", encoding="utf-8", newline="\n")
            self.files[table] = f
        if len(values) != len(COLUMNS[table]):
            raise ValueError(f"{table}: expected {len(COLUMNS[table])} values, got {len(values)}: {values!r}")
        f.write("\t".join(_fmt(v) for v in values) + "\n")
        self.counts[table] += 1

    def rows(self, table: str, many) -> None:
        for r in many:
            self.row(table, r)

    def close(self) -> None:
        for f in self.files.values():
            f.close()


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
_STORE_WORDS = ["Cedar", "Harbor", "Granite", "Willow", "Juniper", "Copper", "Lantern", "Meadow", "Summit", "Riverside",
                "Orchard", "Beacon", "Foxglove", "Ironbridge", "Moss", "Pebble", "Quarry", "Saffron", "Thistle", "Larch"]
_STORE_SUFFIX = {"KIOSK": "Kiosk", "CONVENIENCE": "Corner Shop", "SUPERMARKET": "Market", "ONLINE": "Online"}
_PRODUCT_WORDS = {
    1: ["Roast Coffee", "Green Tea", "Cold Brew Pack", "Chai Blend"], 2: ["Pretzel Bites", "Trail Mix", "Rice Crackers", "Choc Wafer"],
    3: ["Orange Juice", "Iced Tea", "Energy Drink", "Coconut Water"], 4: ["Apples 1kg", "Banana Bunch", "Salad Mix", "Cherry Tomatoes"],
    5: ["Paper Towels", "Laundry Pods", "Sponge Pack", "Bin Bags"], 6: ["Toothpaste", "Hand Cream", "Shampoo", "Lip Balm"],
    7: ["Earbuds", "Power Bank", "Phone Case", "HDMI Cable"], 8: ["Top-Up 10", "Top-Up 20", "Data Pack", "Roaming Pack"],
    9: ["Gift Card 25", "Gift Card 50", "Store Voucher", "Cinema Voucher"], 10: ["Puzzle Cube", "Toy Car", "Plush Bear", "Card Game"],
    11: ["Gel Pens", "Sticky Notes", "Sketchbook", "Planner"], 12: ["Chef Knife", "Cutting Board", "Mixing Bowl", "Spatula Set"],
}
_PRICE_RANGE = {1: (6, 25), 2: (1, 6), 3: (1, 5), 4: (1, 8), 5: (2, 15), 6: (2, 12), 7: (8, 60), 8: (10, 30), 9: (25, 50),
                10: (8, 45), 11: (1, 15), 12: (6, 70)}
_ADJ = ["Classic", "Premium", "Value", "Organic", "Family", "Mini", "Deluxe", "Everyday", "Eco", "Signature"]


class StoreInfo:
    __slots__ = ("region", "type", "tz")

    def __init__(self, region, type_, tz):
        self.region, self.type, self.tz = region, type_, ZoneInfo(tz)


def gen_stores(p: Profile, w: Writers) -> dict[int, StoreInfo]:
    rng = rng_for(p.name, "stores")
    info: dict[int, StoreInfo] = {}
    for row in core.STORES:
        w.row("stores", row)
        info[row[0]] = StoreInfo(row[3], row[4], row[5])
    for sid in range(6, p.n_stores + 1):
        if sid == 6:
            region, stype = "EAST", "ONLINE"
        else:
            region = REGIONS[rng.randrange(4)]
            r = rng.random()
            stype = "KIOSK" if r < 0.40 else "CONVENIENCE" if r < 0.70 else "SUPERMARKET" if r < 0.96 else "ONLINE"
        tz = "UTC" if stype == "ONLINE" else REGION_TZ[region]
        name = f"{_STORE_WORDS[rng.randrange(len(_STORE_WORDS))]} {_STORE_WORDS[rng.randrange(len(_STORE_WORDS))]} {_STORE_SUFFIX[stype]}"
        if sid == 6:
            name = "Online Flagship Store"
        opened = date(2021, 1, 1) + timedelta(days=rng.randrange(1000))
        w.row("stores", (sid, f"ST-{sid:04d}", name, region, stype, tz, opened, None))
        info[sid] = StoreInfo(region, stype, tz)
    for row in core.CATEGORIES:
        w.row("product_categories", row)
    return info


def gen_products(p: Profile, w: Writers):
    """Returns prices: product_id -> (sorted valid_from list, price list)."""
    rng = rng_for(p.name, "products")
    prices: dict[int, tuple[list[datetime], list[Decimal]]] = {}
    for pid, sku, name, cat, std, active, launched in core.PRODUCTS:
        w.row("products", (pid, sku, name, cat, Decimal(std), active, launched))
    for pid, vf, vt, price in core.PRICE_HISTORY:
        w.row("product_price_history", (pid, vf, vt, Decimal(price)))
        froms, ps = prices.setdefault(pid, ([], []))
        froms.append(vf)
        ps.append(Decimal(price))
    for pid in range(11, p.n_products + 1):
        cat = (pid % 12) + 1
        lo, hi = _PRICE_RANGE[cat]
        price = money(lo + rng.random() * (hi - lo))
        n_changes = (rng.random() < 0.5) + (rng.random() < 0.3) + (rng.random() < 0.15)
        changes = sorted(rand_ts(rng, ts(2024, 1, 15, 0), ts(2025, 12, 15, 0)) for _ in range(n_changes))
        changes = [c.replace(hour=0, minute=0, second=0) if rng.random() < 0.3 else c for c in changes]
        changes = sorted(set(changes))
        froms = [ts(2023, 1, 1, 0)] + changes
        ps = [price]
        for _ in changes:
            ps.append(max(money(ps[-1] * Decimal(repr(0.9 + rng.random() * 0.25))), Decimal("0.50")))
        for i, vf in enumerate(froms):
            vt = froms[i + 1] if i + 1 < len(froms) else None
            w.row("product_price_history", (pid, vf, vt, ps[i]))
        words = _PRODUCT_WORDS[cat]
        name = f"{_ADJ[rng.randrange(len(_ADJ))]} {words[rng.randrange(len(words))]}"
        active = rng.random() < 0.96
        launched = date(2021, 1, 1) + timedelta(days=rng.randrange(700))
        w.row("products", (pid, f"SKU-{pid:05d}", name, cat, ps[-1], active, launched))
        prices[pid] = (froms, ps)
    return prices


class CustInfo:
    __slots__ = ("cid", "reg", "region", "segment")

    def __init__(self, cid, reg, region, segment):
        self.cid, self.reg, self.region, self.segment = cid, reg, region, segment


def gen_customers(p: Profile, w: Writers) -> list[CustInfo]:
    rng = rng_for(p.name, "customers")
    w.rows("customers", core.customer_rows())
    w.rows("dim_customer_scd2", core.scd2_rows())
    gen: list[CustInfo] = []
    sk = 100000
    for i in range(p.n_customers):
        cid = 1001 + i
        if cid == 1001:
            reg, segment, region, status, tier = ts(2023, 6, 1, 0), "ENTERPRISE", "EAST", "ACTIVE", "GOLD"
        else:
            reg = rand_ts(rng, ts(2023, 6, 1, 0), ts(2025, 11, 1, 0))
            r = rng.random()
            segment = "CONSUMER" if r < 0.75 else "SMALL_BUSINESS" if r < 0.93 else "ENTERPRISE"
            region = None if rng.random() < 0.02 else REGIONS[rng.randrange(4)]
            r = rng.random()
            status = "ACTIVE" if r < 0.85 else "DORMANT" if r < 0.95 else "CLOSED"
            r = rng.random()
            tier = None if r < 0.40 else "BRONZE" if r < 0.70 else "SILVER" if r < 0.91 else "GOLD"
        w.row("customers", (cid, f"CUST-{cid:06d}", reg, segment, region, status, tier))
        gen.append(CustInfo(cid, reg, region, segment))

        # SCD2 history ending in the current attributes
        r = rng.random()
        n_changes = 0 if r < 0.60 else 1 if r < 0.90 else 2
        lo = reg + timedelta(days=1)
        changes = sorted({rand_ts(rng, lo, ts(2025, 12, 31, 0)) for _ in range(n_changes)}) if lo < ts(2025, 12, 31, 0) else []
        versions = [(segment, region, status)]
        for _ in changes:  # build older versions backwards
            seg0, reg0, st0 = versions[0]
            if rng.random() < 0.6:
                choices = [x for x in REGIONS if x != reg0]
                reg0 = choices[rng.randrange(len(choices))]
            else:
                seg0 = "CONSUMER" if seg0 != "CONSUMER" else "SMALL_BUSINESS"
            versions.insert(0, (seg0, reg0, "ACTIVE"))
        bounds = [reg] + changes + [SCD2_OPEN_END]
        for vi, (seg_v, reg_v, st_v) in enumerate(versions):
            sk += 1
            w.row("dim_customer_scd2", (sk, cid, seg_v, reg_v, st_v, bounds[vi], bounds[vi + 1], vi == len(versions) - 1))
    return gen


def _price_at(prices, pid, t):
    froms, ps = prices[pid]
    i = bisect.bisect_right(froms, t) - 1
    return ps[i]


def gen_transactions(p: Profile, w: Writers, stores: dict[int, StoreInfo], customers: list[CustInfo], prices,
                     snap_acc: dict, snap_stores: set, snap_products: set) -> None:
    rng = rng_for(p.name, "transactions")
    eligible = [sid for sid in sorted(stores) if sid not in (4, 5)]
    online = [sid for sid in eligible if stores[sid].type == "ONLINE"]
    physical = [sid for sid in eligible if stores[sid].type != "ONLINE"]
    by_region = {r: [sid for sid in physical if stores[sid].region == r] for r in REGIONS}

    def emit_status():
        r = rng.random()
        return "COMPLETED" if r < 0.90 else "PENDING" if r < 0.94 else "CANCELLED" if r < 0.99 else "DECLINED"

    def emit_payment(stype):
        r = rng.random()
        if r < 0.01:
            return None
        if r < 0.56:
            return "CARD"
        if r < 0.81:
            return "MOBILE"
        if r < 0.96 and stype != "ONLINE":
            return "CASH"
        return "GIFT_CARD" if r >= 0.96 else "CARD"

    def emit_delay():
        r = rng.random()
        if r < 0.965:
            return 60 + rng.randrange(1740)
        if r < 0.995:
            return 86400 + rng.randrange(2 * 86400)
        return 4 * 86400 + rng.randrange(8 * 86400)

    headers: list[tuple] = []

    def emit(day: date, cid, home, not_before=START):
        r = rng.random()
        if r < 0.20:  # online; store 6 is the deliberately "hot" flagship partition
            sid = 6 if rng.random() < 0.75 else online[rng.randrange(len(online))]
        else:
            sid = home if r < 0.85 else eligible[rng.randrange(len(eligible))]
        info = stores[sid]
        local = datetime(day.year, day.month, day.day, 7 + rng.randrange(15), rng.randrange(60), rng.randrange(60), tzinfo=info.tz)
        t = local.astimezone(UTC)
        if not (not_before <= t < END):
            return
        headers.append((t, cid, sid, emit_status(), emit_payment(info.type), emit_delay()))

    # weights: heavy 5% (8.0), regular 30% (2.0), occasional 65% (0.5); whale 1001 + guests fixed shares
    weights = {}
    for c in customers:
        if c.cid == 1001:
            continue
        r = rng.random()
        weights[c.cid] = 8.0 if r < 0.05 else 2.0 if r < 0.35 else 0.5
    whale_n = p.n_transactions * 2 // 100
    guest_n = p.n_transactions * 15 // 1000
    remaining = p.n_transactions - whale_n - guest_n
    total_w = sum(weights.values())

    for c in customers:
        lo = max(c.reg, START)
        window = (END.date() - lo.date()).days
        if window <= 0:
            continue
        pool = by_region.get(c.region) or physical
        home = pool[rng.randrange(len(pool))]
        if c.cid == 1001:
            k, heavy = whale_n, False
        else:
            k = int(remaining * weights[c.cid] / total_w + rng.random())
            heavy = weights[c.cid] == 8.0
        if k <= 0:
            continue
        days: list[int] = []
        while len(days) < k:
            d0 = rng.randrange(window)
            if heavy and rng.random() < 0.5:
                days.extend(d0 + j for j in range(3 + rng.randrange(6)) if d0 + j < window)
            else:
                days.append(d0)
        extra_p = 0.30 if c.cid == 1001 else 0.10 if heavy else 0.03
        for dd in days[:k]:
            day = lo.date() + timedelta(days=dd)
            emit(day, c.cid, home, lo)
            if rng.random() < extra_p:
                emit(day, c.cid, home, lo)
    total_days = (END - START).days
    for _ in range(guest_n):
        day = START.date() + timedelta(days=rng.randrange(total_days))
        emit(day, None, physical[rng.randrange(len(physical))])

    headers.sort(key=lambda h: (h[0], h[1] or 0, h[2]))

    # fixtures first
    for t in core.build_transactions():
        w.row("transactions", t.header_row())
        w.rows("transaction_items", t.item_rows())
        if t.status == "COMPLETED":
            _accumulate(snap_acc, snap_stores, snap_products, t.transaction_ts, t.store_id,
                        [(pid, q) for (pid, q, _u, _d) in t.lines])
    w.rows("refunds", core.refund_rows())

    # product popularity (arithmetic-only weights), product 7 is never generated
    rng_i = rng_for(p.name, "items")
    pids = [pid for pid in range(1, p.n_products + 1) if pid != 7]
    order = pids[:]
    rng_i.shuffle(order)
    cum, acc = [], 0.0
    for rank, _pid in enumerate(order):
        acc += 1.0 / (1.0 + rank * 0.05)
        cum.append(acc)
    rng_r = rng_for(p.name, "refunds")
    refund_id = 100000
    reasons = ["DAMAGED", "CHANGED_MIND", "PRICE_ADJUSTMENT", "DUPLICATE_CHARGE"]

    for idx, (t, cid, sid, status, payment, delay) in enumerate(headers):
        tid = 100001 + idx
        r = rng_i.random()
        n_lines = 1 if r < 0.35 else 2 if r < 0.65 else 3 if r < 0.85 else 4 if r < 0.95 else 5
        lines = []
        gross = Decimal("0.00")
        for ln in range(1, n_lines + 1):
            pid = order[bisect.bisect_left(cum, rng_i.random() * acc)]
            price = _price_at(prices, pid, t)
            r = rng_i.random()
            qty = 1 if r < 0.70 else 2 if r < 0.90 else 3 + rng_i.randrange(4)
            unit = price if rng_i.random() >= 0.02 else money(price * Decimal(repr(0.85 + rng_i.random() * 0.2)))
            disc = Decimal("0.00")
            if rng_i.random() < 0.15:
                disc = money(qty * unit * Decimal(repr(0.05 + rng_i.random() * 0.15)))
            lines.append((tid, ln, pid, qty, unit, disc))
            gross += qty * unit - disc
        w.row("transactions", (tid, cid, sid, t, gross, "USD", status, payment,
                               "ECOM" if stores[sid].type == "ONLINE" else "POS", t + timedelta(seconds=delay)))
        w.rows("transaction_items", lines)
        if status == "COMPLETED":
            _accumulate(snap_acc, snap_stores, snap_products, t, sid, [(l[2], l[3]) for l in lines])
            if gross > 0 and rng_r.random() < 0.06:
                rr = rng_r.random()
                if rr < 0.40:
                    amounts = [gross]
                elif rr < 0.75:
                    amounts = [max(money(gross * Decimal(repr(0.1 + 0.8 * rng_r.random()))), Decimal("0.01"))]
                else:
                    amounts = [max(money(gross * Decimal(repr(0.05 + 0.25 * rng_r.random()))), Decimal("0.01"))
                               for _ in range(2)]
                rts = t
                for a in amounts:
                    rts = rts + timedelta(days=1 + rng_r.randrange(20), seconds=rng_r.randrange(86400))
                    refund_id += 1
                    w.row("refunds", (refund_id, tid, rts, a, reasons[rng_r.randrange(4)]))


def _accumulate(acc, snap_stores, snap_products, t, sid, items):
    if sid not in snap_stores:
        return
    d = t.astimezone(UTC).date()
    if not (date(2025, 10, 1) <= d < date(2026, 1, 1)):
        return
    for pid, q in items:
        if pid in snap_products:
            acc[(d, sid, pid)] += q


def gen_daily_snapshot(w: Writers, acc: dict, snap_stores: set, snap_products: set) -> None:
    for sid in sorted(snap_stores):
        for pid in sorted(snap_products):
            on_hand = 60 + (sid * 7 + pid * 13) % 80
            for d in daterange(date(2025, 10, 1), date(2026, 1, 1)):
                sold = acc.get((d, sid, pid), 0)
                if on_hand < sold + 10:
                    on_hand += 100  # delivery arrives before opening
                on_hand -= sold
                if sid == 3 and d == date(2025, 11, 15):
                    continue  # known gap: store 3 snapshot job failed that day
                w.row("daily_store_snapshot", (d, sid, pid, on_hand, sold))


_DEVICES_OS = ["ios", "android", "web"]


def gen_events(p: Profile, w: Writers, customers: list[CustInfo], n_products: int) -> None:
    rng = rng_for(p.name, "events")
    rng_l = rng_for(p.name, "ingestion")
    w.rows("customer_events", temporal.event_rows())
    w.rows("event_ingestion_log", temporal.ingestion_rows())
    n_sessions = max(1, p.n_events * 2 // 11)
    sessions = []
    for _ in range(n_sessions):
        if rng.random() < 0.10:
            cid, lo = None, START
        else:
            c = customers[rng.randrange(len(customers))]
            cid, lo = c.cid, max(c.reg, START)
        sessions.append((rand_ts(rng, lo, END - timedelta(hours=6)), cid))
    sessions.sort(key=lambda s: (s[0], s[1] or 0))
    event_id, log_id = 100000, 100000
    middle_types = ["page_view", "page_view", "search", "add_to_cart", "promo_click"]
    for start, cid in sessions:
        n = 1 + rng.randrange(10)
        sid = f"S-{rng.getrandbits(32):08x}" if rng.random() < 0.70 else None
        device = _DEVICES_OS[rng.randrange(3)]
        t = start
        for k in range(n):
            if k:
                t = t + timedelta(seconds=5 + rng.randrange(1495))
            if k == 0:
                etype = "app_open" if rng.random() < 0.6 else "page_view"
            elif k == n - 1 and rng.random() < 0.35:
                etype = "checkout"
            else:
                etype = middle_types[rng.randrange(len(middle_types))]
            payload = _payload(rng, etype, device, n_products)
            event_id += 1
            w.row("customer_events", (event_id, cid, t, etype, sid if rng.random() >= 0.05 else None, payload))
            # ingestion attempts
            raw_id = f"evt-{event_id}"
            r = rng_l.random()
            delay = (1 + rng_l.randrange(30) if r < 0.60 else 31 + rng_l.randrange(270) if r < 0.90
                     else 301 + rng_l.randrange(3300) if r < 0.99 else 3601 + rng_l.randrange(172800))
            nbytes = 200 + rng_l.randrange(3800)
            r = rng_l.random()
            if r < 0.003:
                log_id += 1
                w.row("event_ingestion_log", (log_id, raw_id, "APP", t, t - timedelta(seconds=1 + rng_l.randrange(60)), "LOADED", None, nbytes))
                continue
            if r < 0.013:
                log_id += 1
                w.row("event_ingestion_log", (log_id, raw_id, "APP", t, t + timedelta(seconds=delay), "RETRIED", "TIMEOUT", nbytes))
                delay += 60 + rng_l.randrange(540)
            elif r < 0.018:
                log_id += 1
                reason = ["SCHEMA_MISMATCH", "INVALID_JSON", "MISSING_CUSTOMER"][rng_l.randrange(3)]
                w.row("event_ingestion_log", (log_id, raw_id, "APP", t, t + timedelta(seconds=delay), "REJECTED", reason, 0))
                continue
            log_id += 1
            w.row("event_ingestion_log", (log_id, raw_id, "APP", t, t + timedelta(seconds=delay), "LOADED", None, nbytes))
            if rng_l.random() < 0.003:
                log_id += 1
                w.row("event_ingestion_log", (log_id, raw_id, "APP", t, t + timedelta(seconds=delay + 1 + rng_l.randrange(120)), "DUPLICATE", None, nbytes))


def _payload(rng, etype: str, device: str, n_products: int) -> dict:
    sku = lambda: f"SKU-{1 + rng.randrange(n_products):05d}"  # noqa: E731
    if etype == "app_open":
        return {"device": device, "app_version": f"4.{rng.randrange(6)}.{rng.randrange(10)}"}
    if etype == "page_view":
        return {"device": device, "page": f"/category/{1 + rng.randrange(12)}"}
    if etype == "search":
        return {"device": device, "query_length": 1 + rng.randrange(30)}
    if etype == "add_to_cart":
        q = 1 + rng.randrange(3)
        return {"sku": sku(), "qty": str(q) if rng.random() < 0.02 else q}
    if etype == "promo_click":
        return {"coupon": ["SAVE5", "SAVE10", "FREESHIP", "BOGO"][rng.randrange(4)], "amount": f"-{1 + rng.randrange(10)}.00"}
    # checkout
    payload: dict = {"currency": "USD", "device": device, "is_member": rng.random() < 0.4}
    amount = money(2 + rng.random() * 150)
    r = rng.random()
    if r < 0.90:
        payload["amount"] = str(amount)
    elif r < 0.95:
        payload["amount"] = float(amount)
    elif r < 0.97:
        payload["amount"] = "N/A"
    elif r < 0.99:
        pass  # missing key
    else:
        payload["amount"] = None
    if rng.random() < 0.05:
        payload["is_member"] = "yes"
    r = rng.random()
    if r < 0.01:
        payload["items"] = []
    elif r < 0.015:
        payload["items"] = {"sku": sku(), "qty": 1}
    else:
        items = [{"sku": sku(), "qty": 1 + rng.randrange(3)} for _ in range(1 + rng.randrange(4))]
        if rng.random() < 0.02:
            items.append(dict(items[0]))
        payload["items"] = items
    if rng.random() < 0.01:
        del payload["device"]
    return payload


def gen_availability(p: Profile, w: Writers, stores: dict[int, StoreInfo]) -> None:
    rng = rng_for(p.name, "availability")
    w.rows("store_product_availability", temporal.AVAILABILITY)
    tracked = [pid for pid in range(1, p.availability_products + 1) if pid != 7]
    for sid in sorted(stores):
        for pid in tracked:
            if (sid, pid) in temporal.FIXTURE_AVAILABILITY_PAIRS:
                continue
            t = ts(2024, 1, 1, 0)
            avail = rng.random() < 0.9
            while True:
                span = (20 + rng.randrange(100)) * 86400 + rng.randrange(86400) if avail else 2 * 3600 + rng.randrange(3 * 86400)
                nxt = t + timedelta(seconds=span)
                if nxt >= END:
                    w.row("store_product_availability", (sid, pid, t, None, avail))
                    break
                w.row("store_product_availability", (sid, pid, t, nxt, avail))
                t = nxt
                if rng.random() < 0.03:
                    t = t + timedelta(seconds=3600 + rng.randrange(11 * 3600))  # uncovered gap = not stocked
                    avail = True
                else:
                    avail = not avail


def gen_subscriptions(p: Profile, w: Writers, customers: list[CustInfo]) -> None:
    rng = rng_for(p.name, "subscriptions")
    w.rows("subscriptions", core.subscription_rows())
    fees = {"BASIC": Decimal("9.99"), "PLUS": Decimal("19.99"), "PREMIUM": Decimal("39.99")}
    plans = list(fees)
    sub_id = 1000
    for c in customers:
        if rng.random() >= 0.5:
            continue
        start = max(c.reg, START).date() + timedelta(days=rng.randrange(120))
        for k in range(1 + rng.randrange(3)):
            if start >= date(2025, 12, 31):
                break
            sub_id += 1
            if k == 0 and rng.random() < 0.10:
                end = start + timedelta(days=14)
                w.row("subscriptions", (sub_id, c.cid, "BASIC", start, end, "TRIAL", Decimal("0.00")))
                start = end
                continue
            plan = plans[rng.randrange(3)]
            months = 1 + rng.randrange(12)
            end = start + timedelta(days=30 * months)
            if end >= date(2026, 1, 1) or rng.random() < 0.35:
                w.row("subscriptions", (sub_id, c.cid, plan, start, None, "ACTIVE", fees[plan]))
                break
            w.row("subscriptions", (sub_id, c.cid, plan, start, end, "CANCELLED" if rng.random() < 0.5 else "EXPIRED", fees[plan]))
            start = end + timedelta(days=0 if rng.random() < 0.6 else rng.randrange(60))


_FIRST = ["Arlo", "Brisa", "Corin", "Dalia", "Emrys", "Fenna", "Galen", "Halia", "Ivo", "Juno", "Kaius", "Liora", "Mael",
          "Nera", "Orin", "Pella", "Quill", "Riven", "Sela", "Tamsin", "Ulric", "Vesna", "Wren", "Xyla", "Yorick", "Zephyr"]
_LAST = ["Ashdown", "Brightwater", "Copperfield", "Duskmoor", "Emberly", "Fairhollow", "Glenmere", "Hawthorne", "Ironwood",
         "Juniperra", "Kestrelton", "Larkspur", "Marblehead", "Northcott", "Oakridge", "Pinecrest", "Quarryman", "Ravensworth",
         "Stonebridge", "Thistledown", "Underhill", "Valewood", "Westbrook", "Yarrowby"]


def gen_employees(w: Writers) -> None:
    """Fixed 300-person hierarchy, identical in every profile."""
    rng = rng_for("fixed", "employees")
    depts = ["Engineering", "Data", "Finance", "Operations", "Sales", "People"]

    def name():
        return f"{_FIRST[rng.randrange(len(_FIRST))]} {_LAST[rng.randrange(len(_LAST))]}"

    def hired(lo_year=2015):
        return date(lo_year, 1, 1) + timedelta(days=rng.randrange((date(2025, 9, 30) - date(lo_year, 1, 1)).days))

    rows = [(1, None, name(), "Executive", "Chief Executive Officer", Decimal("350000.00"), date(2015, 3, 2), None)]
    vps = {}
    for i, d in enumerate(depts):
        eid = 2 + i
        vps[d] = eid
        rows.append((eid, 1, name(), d, f"VP {d}", Decimal(220000 + 5000 * rng.randrange(9)), hired(2015), None))
    managers = defaultdict(list)
    for eid in range(8, 38):
        d = depts[(eid - 8) % 6]
        managers[d].append(eid)
        rows.append((eid, vps[d], name(), d, f"{d} Manager", Decimal(140000 + 5000 * rng.randrange(9)), hired(2016), None))
    leads = defaultdict(list)
    for eid in range(38, 108):
        d = depts[(eid - 38) % 6]
        leads[d].append(eid)
        mgr = managers[d][rng.randrange(len(managers[d]))]
        rows.append((eid, mgr, name(), d, f"{d} Lead", Decimal(110000 + 2500 * rng.randrange(13)), hired(2017), None))
    for eid in range(108, 301):
        d = depts[rng.randrange(6)]
        mgr = leads[d][rng.randrange(len(leads[d]))]
        h = hired(2018)
        term = None
        if rng.random() < 0.05:
            term = min(h + timedelta(days=90 + rng.randrange(900)), date(2025, 12, 31))
        rows.append((eid, mgr, name(), d, ["Analyst", "Engineer", "Specialist", "Associate"][rng.randrange(4)],
                     Decimal(60000 + 2500 * rng.randrange(21)), h, term))
    w.rows("employees", rows)


def gen_accounts(p: Profile, w: Writers, customers: list[CustInfo]) -> None:
    rng = rng_for(p.name, "accounts")
    w.rows("accounts", core.account_rows())
    w.rows("account_ledger", core.ledger_rows())
    entry_id = 100000
    for i in range(p.n_accounts):
        aid = 1001 + i
        c = customers[rng.randrange(len(customers))]
        r = rng.random()
        atype = "WALLET" if r < 0.60 else "PREPAID" if r < 0.85 else "CREDIT_LINE"
        limit = Decimal(["500.00", "1000.00"][rng.randrange(2)]) if atype == "CREDIT_LINE" else Decimal("0.00")
        opened = max(c.reg, START) + timedelta(seconds=rng.randrange(300 * 86400))
        if opened >= END - timedelta(days=5):
            opened = END - timedelta(days=5)
        w.row("accounts", (aid, c.cid, atype, opened, limit))
        n = max(1, int(p.ledger_per_account * (0.5 + rng.random())))
        times = sorted(rand_ts(rng, opened, END) for _ in range(n))
        prev = None
        for k, t in enumerate(times):
            if prev is not None and rng.random() < 0.02:
                t = prev  # tie on posting_ts
            prev = t
            if k == 0:
                et, amt = "DEPOSIT", money(20 + rng.random() * 480)
            else:
                r = rng.random()
                if r < 0.50:
                    et, amt = "PURCHASE", -money(5 + rng.random() * 195)
                elif r < 0.70:
                    et, amt = "DEPOSIT", money(20 + rng.random() * 480)
                elif r < 0.78:
                    et, amt = "REFUND", money(2 + rng.random() * 60)
                elif r < 0.85:
                    et, amt = "FEE", -money(1 + rng.random() * 14)
                elif r < 0.90:
                    et, amt = "WITHDRAWAL", -money(10 + rng.random() * 190)
                else:
                    et, amt = "ADJUSTMENT", money(-25 + rng.random() * 50)
            if amt == 0:
                amt = Decimal("0.01")
            entry_id += 1
            w.row("account_ledger", (entry_id, aid, None, t, amt, et))


def gen_devices(p: Profile, w: Writers, stores: dict[int, StoreInfo]) -> None:
    rng = rng_for(p.name, "devices")
    w.rows("devices", temporal.DEVICES)
    w.rows("device_status_events", temporal.device_status_rows())
    w.rows("device_downtime_incidents", temporal.INCIDENTS)
    eligible = [sid for sid in sorted(stores) if sid not in (4, 5) and stores[sid].type != "ONLINE"]
    event_id, incident_id = 100000, 1000
    for i in range(p.n_devices):
        sid = eligible[rng.randrange(len(eligible))]
        kiosk = stores[sid].type == "KIOSK" or rng.random() < 0.5
        dev = f"KIOSK-{i + 1:04d}" if kiosk else f"POS-{i + 1:04d}"
        installed = date(2024, 1, 1) + timedelta(days=rng.randrange(545))
        decom = None
        if rng.random() < 0.08:
            cand = installed + timedelta(days=120 + rng.randrange(300))
            decom = cand if cand < date(2026, 1, 1) else None
        w.row("devices", (dev, sid, "KIOSK" if kiosk else "POS_TERMINAL", installed, decom))
        last_day = decom or date(2026, 1, 1)
        outages = []
        for d in daterange(installed, last_day):
            if rng.random() < 0.03:
                down = datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(seconds=rng.randrange(86400))
                if outages and down <= outages[-1][1]:
                    continue
                up = down + timedelta(seconds=300 + rng.randrange(28500))
                outages.append((down, up))
        events = []
        oi = 0
        for d in daterange(installed, last_day):
            if rng.random() < 0.015:
                continue  # missed scheduled report
            t = datetime(d.year, d.month, d.day, 2, tzinfo=UTC) + timedelta(seconds=rng.randrange(300))
            while oi < len(outages) and outages[oi][1] <= t:
                oi += 1
            state = "DOWN" if oi < len(outages) and outages[oi][0] <= t < outages[oi][1] else "UP"
            events.append((t, state, "SCHEDULED"))
        for down, up in outages:
            events.append((down, "DOWN", "CHANGE"))
            if up < END:
                events.append((up, "UP", "CHANGE"))
        events.sort(key=lambda e: (e[0], e[2]))
        for t, state, kind in events:
            delay = rng.randrange(600) if rng.random() >= 0.03 else 3600 + rng.randrange(18000)
            event_id += 1
            w.row("device_status_events", (event_id, dev, t, t + timedelta(seconds=delay), state, kind))
        for down, up in outages:
            incident_id += 1
            w.row("device_downtime_incidents", (incident_id, dev, "MONITORING", down, up))
            if rng.random() < 0.40:
                f = down + timedelta(seconds=rng.randrange(2400) - 600)
                to = up + timedelta(seconds=rng.randrange(4200) - 600)
                if to > f:
                    incident_id += 1
                    w.row("device_downtime_incidents", (incident_id, dev, "TECHNICIAN", f, to))
            if rng.random() < 0.10:
                incident_id += 1
                w.row("device_downtime_incidents", (incident_id, dev, "VENDOR", up, up + timedelta(seconds=300 + rng.randrange(1500))))


def gen_cdc(w: Writers) -> None:
    """Profile-independent CDC feed (generated keys + FX fixtures)."""
    rng = rng_for("fixed", "cdc")
    by_source: dict[str, list] = defaultdict(list)
    cutoff = ts(2025, 12, 31, 0)
    for src, nkeys in (("POS", 1200), ("ECOM", 300)):
        for k in range(1, nkeys + 1):
            key = f"{src}-{k:06d}"
            t = rand_ts(rng, ts(2025, 11, 1, 0), ts(2025, 12, 30, 0))
            state = {"business_key": key, "amount": str(money(5 + rng.random() * 200)), "status": "PENDING",
                     "customer_id": 1001 + rng.randrange(2000), "store_id": 6 if src == "ECOM" else 1 + rng.randrange(3)}
            seq = 0
            by_source[src].append((t, key, seq, "I", dict(state)))
            for _ in range(rng.randrange(4)):
                t = t + timedelta(seconds=60 + rng.randrange(3 * 86400))
                if t >= cutoff:
                    break
                if rng.random() < 0.5:
                    state["status"] = "COMPLETED" if rng.random() < 0.8 else "CANCELLED"
                else:
                    state["amount"] = str(money(Decimal(state["amount"]) + Decimal(repr(rng.random() * 20 - 10))).copy_abs())
                seq += 1
                by_source[src].append((t, key, seq, "U", dict(state)))
            if rng.random() < 0.05:
                t = t + timedelta(seconds=60 + rng.randrange(86400))
                if t < cutoff:
                    seq += 1
                    by_source[src].append((t, key, seq, "D", {"business_key": key}))
    events = []
    for src, evs in by_source.items():
        evs.sort(key=lambda e: (e[0], e[1], e[2]))
        for i, (t, key, _seq, op, payload) in enumerate(evs):
            lsn = 1_000_000 + 10 * i
            delay = 1 + rng.randrange(120) if rng.random() >= 0.04 else 300 + rng.randrange(6900)
            events.append((src, key, op, lsn, t, t + timedelta(seconds=delay), payload))
    events += warehouse.cdc_rows()
    events.sort(key=lambda e: (e[5], e[0], e[1], e[3]))
    for i, e in enumerate(events, start=1):
        w.row("cdc_transaction_events", (i,) + e)


def gen_pipeline(w: Writers) -> None:
    w.rows("pipeline_runs", warehouse.pipeline_run_rows())
    run_id = 100
    for d in daterange(date(2025, 12, 1), date(2026, 1, 1)):
        w0 = datetime(d.year, d.month, d.day, tzinfo=UTC)
        w1 = w0 + timedelta(days=1)
        started = w1 + timedelta(minutes=15)
        run_id += 1
        failed = d.day in (10, 20)
        w.row("pipeline_runs", (run_id, "customer_events_load", "APP", started, started + timedelta(minutes=12),
                                "FAILED" if failed else "SUCCEEDED", w0, w1, None if failed else 900 + d.day,
                                None if failed else 900 + d.day, "disk quota exceeded" if failed else None))
        if failed:
            run_id += 1
            retry = started + timedelta(hours=3)
            w.row("pipeline_runs", (run_id, "customer_events_load", "APP", retry, retry + timedelta(minutes=14),
                                    "SUCCEEDED", w0, w1, 900 + d.day, 900 + d.day, None))
    w.rows("pipeline_watermarks", warehouse.pipeline_watermark_rows())
    w.row("pipeline_watermarks", ("customer_events_load", "APP", ts(2026, 1, 1, 0), 31, ts(2026, 1, 1, 0, 30)))


def gen_landing_fixtures(w: Writers) -> None:
    src, tgt = warehouse.recon_rows()
    w.rows("source_transactions", src)
    w.rows("target_transactions", tgt)
    w.rows("raw_transaction_events", warehouse.raw_event_rows())
    w.rows("stg_transaction_items", warehouse.stg_item_rows())


def generate(p: Profile, directory: Path, log=print) -> dict[str, int]:
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    w = Writers(directory)
    try:
        t0 = time.perf_counter()
        stores = gen_stores(p, w)
        prices = gen_products(p, w)
        customers = gen_customers(p, w)
        log(f"  stores/products/customers ............ {time.perf_counter() - t0:6.1f}s")
        snap_stores = {1, 2, 3} | {sid for sid in sorted(stores) if sid >= 6 and stores[sid].type != "ONLINE"}
        snap_stores = set(sorted(snap_stores)[:10])
        snap_products = {pid for pid in range(1, 21) if pid != 7}
        snap_acc: dict = defaultdict(int)
        gen_transactions(p, w, stores, customers, prices, snap_acc, snap_stores, snap_products)
        log(f"  transactions/items/refunds ........... {time.perf_counter() - t0:6.1f}s")
        gen_daily_snapshot(w, snap_acc, snap_stores, snap_products)
        gen_events(p, w, customers, p.n_products)
        log(f"  events/ingestion log ................. {time.perf_counter() - t0:6.1f}s")
        gen_availability(p, w, stores)
        gen_subscriptions(p, w, customers)
        gen_employees(w)
        gen_accounts(p, w, customers)
        gen_devices(p, w, stores)
        gen_cdc(w)
        gen_pipeline(w)
        gen_landing_fixtures(w)
        log(f"  remaining tables ..................... {time.perf_counter() - t0:6.1f}s")
    finally:
        w.close()
    return dict(w.counts)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
DERIVED_SQL = [
    # Summary: one row per customer per UTC business date with COMPLETED spend.
    """
    INSERT INTO customer_daily_activity (customer_id, activity_date, transaction_count, daily_spend)
    SELECT customer_id, (transaction_ts AT TIME ZONE 'UTC')::date, count(*), sum(gross_amount)
    FROM transactions
    WHERE transaction_status = 'COMPLETED' AND customer_id IS NOT NULL
    GROUP BY 1, 2
    """,
    # Partitioned line-grain fact (COMPLETED only).
    """
    INSERT INTO fact_sales_partitioned (sale_date, transaction_id, line_number, store_id, customer_id, product_id, quantity, net_amount)
    SELECT (t.transaction_ts AT TIME ZONE 'UTC')::date, i.transaction_id, i.line_number, t.store_id, t.customer_id,
           i.product_id, i.quantity, i.quantity * i.unit_price - i.discount_amount
    FROM transaction_items i
    JOIN transactions t ON t.transaction_id = i.transaction_id
    WHERE t.transaction_status = 'COMPLETED'
    """,
    # Reconciliation snapshots: generated December-2025 transactions (fixtures 90001+ already loaded).
    """
    INSERT INTO source_transactions
    SELECT transaction_id, customer_id, store_id, transaction_ts, gross_amount, transaction_status, payment_method,
           'MR-' || lpad((transaction_id % 1000)::text, 3, '0'), NULL, TIMESTAMPTZ '2026-01-01 01:00:00+00'
    FROM transactions
    WHERE transaction_id >= 100001 AND transaction_ts >= '2025-12-01 00:00:00+00' AND transaction_ts < '2026-01-01 00:00:00+00'
    """,
    """
    INSERT INTO target_transactions
    SELECT s.transaction_id, s.customer_id, s.store_id, s.transaction_ts,
           CASE WHEN s.transaction_id % 103 = 5 THEN s.amount + 0.01 ELSE s.amount END,
           CASE WHEN s.transaction_id % 107 = 11 AND s.status = 'PENDING' THEN 'COMPLETED' ELSE s.status END,
           CASE WHEN s.transaction_id % 109 = 13 THEN NULL ELSE s.payment_method END,
           s.merchant_ref, s.note, TIMESTAMPTZ '2026-01-01 01:30:00+00'
    FROM source_transactions s
    WHERE s.transaction_id >= 100001 AND s.transaction_id % 101 <> 3
    """,
    """
    INSERT INTO target_transactions
    SELECT transaction_id, customer_id, store_id, transaction_ts, gross_amount, transaction_status, payment_method,
           'MR-' || lpad((transaction_id % 1000)::text, 3, '0'), NULL, TIMESTAMPTZ '2026-01-01 01:30:00+00'
    FROM transactions
    WHERE transaction_id >= 100001 AND transaction_id % 7 = 0
      AND transaction_ts >= '2025-11-30 00:00:00+00' AND transaction_ts < '2025-12-01 00:00:00+00'
    """,
    # Raw at-least-once message deliveries for generated December-2025 transactions.
    """
    INSERT INTO raw_transaction_events (delivery_id, message_id, transaction_id, event_type, delivered_at, payload)
    SELECT 1000 + row_number() OVER (ORDER BY delivered_at, message_id, k), message_id, transaction_id, event_type, delivered_at, payload
    FROM (
        SELECT 'msg-' || t.transaction_id || '-c' AS message_id, t.transaction_id, 'CREATED' AS event_type,
               t.ingested_at AS delivered_at, 1 AS k,
               jsonb_build_object('transaction_id', t.transaction_id, 'amount', t.gross_amount::text,
                                  'status', CASE WHEN t.transaction_status = 'COMPLETED' THEN 'COMPLETED' ELSE 'PENDING' END,
                                  'store_id', t.store_id) AS payload
        FROM transactions t
        WHERE t.transaction_id >= 100001 AND t.transaction_ts >= '2025-12-01 00:00:00+00' AND t.transaction_ts < '2026-01-01 00:00:00+00'
        UNION ALL
        SELECT 'msg-' || t.transaction_id || '-c', t.transaction_id, 'CREATED', t.ingested_at + interval '45 seconds', 2,
               jsonb_build_object('transaction_id', t.transaction_id, 'amount', t.gross_amount::text,
                                  'status', CASE WHEN t.transaction_status = 'COMPLETED' THEN 'COMPLETED' ELSE 'PENDING' END,
                                  'store_id', t.store_id)
        FROM transactions t
        WHERE t.transaction_id >= 100001 AND t.transaction_id % 37 = 0
          AND t.transaction_ts >= '2025-12-01 00:00:00+00' AND t.transaction_ts < '2026-01-01 00:00:00+00'
        UNION ALL
        SELECT 'msg-' || t.transaction_id || '-s1', t.transaction_id, 'STATUS_CHANGED', t.ingested_at + interval '10 minutes', 3,
               jsonb_build_object('transaction_id', t.transaction_id, 'amount', t.gross_amount::text,
                                  'status', t.transaction_status, 'store_id', t.store_id)
        FROM transactions t
        WHERE t.transaction_id >= 100001 AND t.transaction_status IN ('CANCELLED', 'DECLINED')
          AND t.transaction_ts >= '2025-12-01 00:00:00+00' AND t.transaction_ts < '2026-01-01 00:00:00+00'
        UNION ALL
        SELECT 'msg-' || t.transaction_id || '-c2', t.transaction_id, 'CREATED', t.ingested_at + interval '2 minutes', 4,
               jsonb_build_object('transaction_id', t.transaction_id, 'amount', t.gross_amount::text,
                                  'status', CASE WHEN t.transaction_status = 'COMPLETED' THEN 'COMPLETED' ELSE 'PENDING' END,
                                  'store_id', t.store_id)
        FROM transactions t
        WHERE t.transaction_id >= 100001 AND t.transaction_id % 199 = 0
          AND t.transaction_ts >= '2025-12-01 00:00:00+00' AND t.transaction_ts < '2026-01-01 00:00:00+00'
    ) s
    """,
    # Untrusted staging batch 2: a straight copy of December-2025 generated lines.
    """
    INSERT INTO stg_transaction_items (load_batch_id, transaction_id, line_number, product_id, quantity, unit_price, discount_amount)
    SELECT 2, i.transaction_id, i.line_number, i.product_id, i.quantity, i.unit_price, i.discount_amount
    FROM transaction_items i
    JOIN transactions t ON t.transaction_id = i.transaction_id
    WHERE t.transaction_id >= 100001 AND t.transaction_ts >= '2025-12-01 00:00:00+00' AND t.transaction_ts < '2026-01-01 00:00:00+00'
    """,
]


def checksum_sql(table: str) -> str:
    return f"SELECT md5(coalesce(string_agg(h, '' ORDER BY h), '')) FROM (SELECT md5(t::text) AS h FROM {table} t) s"


def load(conn, p: Profile, directory: Path, log=print) -> dict:
    """Full reset + load in a single transaction. Returns lab_meta seed info."""
    t0 = time.perf_counter()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SET LOCAL timezone = 'UTC'")
            cur.execute("TRUNCATE " + ", ".join(ALL_TABLES + ["lab_meta"]) + " RESTART IDENTITY CASCADE")
            for table in LOAD_ORDER:
                path = directory / f"{table}.copy"
                if not path.exists():
                    continue
                cols = ", ".join(COLUMNS[table])
                with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as cp, open(path, "r", encoding="utf-8", newline="\n") as f:
                    while chunk := f.read(1 << 20):
                        cp.write(chunk)
            log(f"  COPY into {len(LOAD_ORDER)} tables ............. {time.perf_counter() - t0:6.1f}s")
            for sql in DERIVED_SQL:
                cur.execute(sql)
            log(f"  derived tables ....................... {time.perf_counter() - t0:6.1f}s")
            counts, checksums = {}, {}
            for table in ALL_TABLES:
                cur.execute(f"SELECT count(*) FROM {table}")
                counts[table] = cur.fetchone()[0]
                cur.execute(checksum_sql(table))
                checksums[table] = cur.fetchone()[0]
            overall = hashlib.md5("".join(checksums[t] for t in ALL_TABLES).encode()).hexdigest()
            info = {"profile": p.name, "seed_version": SEED_VERSION, "row_counts": counts,
                    "table_checksums": checksums, "checksum": overall}
            cur.execute("INSERT INTO lab_meta (meta_key, meta_value) VALUES ('seed', %s)",
                        (json.dumps(info),))
            log(f"  counts + checksum .................... {time.perf_counter() - t0:6.1f}s")
    return info


def run(conn_factory, profile_name: str, log=print) -> dict:
    """Generate + load a profile. ``conn_factory()`` must return an admin psycopg connection."""
    p = PROFILES[profile_name]
    directory = ROOT / ".lab_tmp" / f"seed_{p.name}"
    log(f"Generating '{p.name}' profile (seed version {SEED_VERSION}) ...")
    generate(p, directory, log)
    with conn_factory() as conn:
        info = load(conn, p, directory, log)
    with conn_factory(autocommit=True) as conn:
        t0 = time.perf_counter()
        conn.execute("VACUUM ANALYZE")
        log(f"  VACUUM ANALYZE ....................... {time.perf_counter() - t0:6.1f}s")
    shutil.rmtree(directory, ignore_errors=True)
    return info


def main(profile_name: str) -> None:  # used by seed_small.py / seed_medium.py / seed_large.py
    import sys
    sys.path.insert(0, str(ROOT))
    from lab import db  # noqa: WPS433
    db.seed(profile_name, assume_yes="--yes" in sys.argv)
