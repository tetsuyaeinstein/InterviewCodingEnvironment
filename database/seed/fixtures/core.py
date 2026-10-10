"""Hand-curated core fixtures: stores, catalogue, customers, transactions, refunds,
SCD2 history, accounts/ledger and subscriptions.

Every row here is identical in every seed profile (small/medium/large). Reserved ID ranges:
  stores 1-5, products 1-10, customers 1-99, transactions 1-9999 (customer N uses N*100+k),
  refunds 1-999, accounts 1-5, ledger entries 1-999, subscriptions 1-99, SCD2 keys 1-9999.
Generated (pseudo-random) data never uses these customers, and never transacts in stores 4-5.
See database/DATA_DICTIONARY.md for what each fixture demonstrates.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ..common import SCD2_OPEN_END, Txn, money, ts

# ---------------------------------------------------------------------------
# Reference data (fixed in every profile)
# ---------------------------------------------------------------------------
CATEGORIES = [
    (1, "Coffee & Tea", "GROCERY"),
    (2, "Snacks", "GROCERY"),
    (3, "Beverages", "GROCERY"),
    (4, "Fresh Produce", "GROCERY"),
    (5, "Household", "HOME"),
    (6, "Personal Care", "HEALTH"),
    (7, "Electronics Accessories", "ELECTRONICS"),
    (8, "Mobile Top-Up", "SERVICES"),
    (9, "Gift Cards & Vouchers", "SERVICES"),
    (10, "Toys", "LEISURE"),
    (11, "Stationery", "LEISURE"),
    (12, "Kitchenware", "HOME"),
]

STORES = [
    # store_id, code, name, region, type, timezone, opened_on, closed_on
    (1, "ST-0001", "Harbor Point Supermarket", "EAST", "SUPERMARKET", "America/New_York", date(2022, 3, 1), None),
    (2, "ST-0002", "Maple Row Kiosk Hub", "NORTH", "KIOSK", "America/Chicago", date(2022, 5, 1), None),
    (3, "ST-0003", "Sunset Strand Convenience", "WEST", "CONVENIENCE", "America/Los_Angeles", date(2022, 7, 1), None),
    (4, "ST-0004", "Pilot Lab Kiosk A", "SOUTH", "KIOSK", "America/Phoenix", date(2024, 11, 1), None),
    (5, "ST-0005", "Pilot Lab Kiosk B", "EAST", "KIOSK", "America/New_York", date(2024, 11, 1), None),
]

PRODUCTS = [
    # product_id, sku, name, category_id, standard_price (current), is_active, launched_on
    (1, "SKU-00001", "Arabica Espresso Beans 1kg", 1, "19.50", True, date(2022, 1, 1)),
    (2, "SKU-00002", "Milk Frother Wand", 12, "24.00", True, date(2022, 1, 1)),
    (3, "SKU-00003", "Oat Granola Bar 6-pack", 2, "12.00", True, date(2022, 1, 1)),
    (4, "SKU-00004", "Sparkling Water 12x330ml", 3, "6.00", True, date(2022, 1, 1)),
    (5, "SKU-00005", "USB-C Cable 1m", 7, "9.00", True, date(2022, 1, 1)),
    (6, "SKU-00006", "Phone Charger 20W", 7, "30.00", True, date(2022, 1, 1)),
    (7, "SKU-00007", "Open-Price Voucher", 9, "0.00", True, date(2022, 1, 1)),
    (8, "SKU-00008", "Notebook A5", 11, "3.00", True, date(2022, 1, 1)),
    (9, "SKU-00009", "Dish Soap 500ml", 5, "4.50", True, date(2022, 1, 1)),
    (10, "SKU-00010", "Building Blocks Set", 10, "30.00", True, date(2022, 1, 1)),
]

# [valid_from, valid_to) ; valid_to None = open-ended. Product 7 intentionally has NO history.
PRICE_HISTORY = [
    (1, ts(2023, 1, 1, 0), ts(2025, 4, 1, 0), "18.00"),
    (1, ts(2025, 4, 1, 0), None, "19.50"),
    (2, ts(2023, 1, 1, 0), None, "24.00"),
    (3, ts(2023, 1, 1, 0), ts(2025, 3, 1, 12), "10.00"),
    (3, ts(2025, 3, 1, 12), None, "12.00"),
    (4, ts(2023, 1, 1, 0), None, "6.00"),
    (5, ts(2023, 1, 1, 0), ts(2024, 7, 1, 0), "8.00"),
    (5, ts(2024, 7, 1, 0), None, "9.00"),
    (6, ts(2023, 1, 1, 0), None, "30.00"),
    (8, ts(2023, 1, 1, 0), None, "3.00"),
    (9, ts(2023, 1, 1, 0), ts(2025, 6, 15, 8, 30), "4.25"),
    (9, ts(2025, 6, 15, 8, 30), None, "4.50"),
    (10, ts(2023, 1, 1, 0), ts(2025, 11, 24, 0), "30.00"),
    (10, ts(2025, 11, 24, 0), ts(2025, 12, 1, 0), "25.00"),
    (10, ts(2025, 12, 1, 0), None, "30.00"),
]

# ---------------------------------------------------------------------------
# Customers 1-99
# ---------------------------------------------------------------------------
REG = ts(2023, 12, 1, 0)

# customer_id -> (segment, home_region, status, loyalty_tier, purpose)
CUSTOMERS = {
    1: ("CONSUMER", "EAST", "ACTIVE", None, "never transacted"),
    2: ("CONSUMER", "EAST", "ACTIVE", "BRONZE", "exactly 4 consecutive days (+ isolated day)"),
    3: ("CONSUMER", "EAST", "ACTIVE", "BRONZE", "exactly 5 consecutive days"),
    4: ("CONSUMER", "EAST", "ACTIVE", "SILVER", "7 consecutive days"),
    5: ("CONSUMER", "EAST", "ACTIVE", "SILVER", "two disjoint 5-day streaks of equal length"),
    6: ("CONSUMER", "EAST", "ACTIVE", None, "6 purchases on only 4 consecutive days, then a skipped day"),
    7: ("CONSUMER", "EAST", "ACTIVE", None, "5-day streak containing same-day duplicate purchases"),
    8: ("CONSUMER", "EAST", "ACTIVE", None, "5-day streak across a month boundary"),
    9: ("CONSUMER", "EAST", "ACTIVE", "GOLD", "5-day streak across a year boundary (ISO-week edge)"),
    10: ("CONSUMER", "EAST", "ACTIVE", None, "5-day streak across leap day 2024-02-29"),
    11: ("CONSUMER", "EAST", "ACTIVE", None, "7 purchase days with one skipped day (4 + 3)"),
    12: ("CONSUMER", "EAST", "ACTIVE", None, "5 days but the middle day is only CANCELLED"),
    13: ("CONSUMER", "WEST", "ACTIVE", None, "5-day UTC streak that is NOT a streak in store-local time"),
    14: ("CONSUMER", "EAST", "ACTIVE", None, "DST / ISO-week timezone edge purchases (New York store)"),
    15: ("SMALL_BUSINESS", "EAST", "ACTIVE", "GOLD", "5 days each with completed daily spend > 100"),
    16: ("SMALL_BUSINESS", "EAST", "ACTIVE", None, "5 days but one day totals exactly 100.00"),
    17: ("SMALL_BUSINESS", "EAST", "ACTIVE", None, "5 days but one day's big purchase was CANCELLED"),
    18: ("SMALL_BUSINESS", "EAST", "ACTIVE", None, "6 days of two small purchases that sum to > 100"),
    19: ("CONSUMER", "EAST", "ACTIVE", None, "first purchase + purchase exactly on day 7"),
    20: ("CONSUMER", "EAST", "ACTIVE", None, "purchases on day 3 and day 8, not day 7"),
    21: ("CONSUMER", "EAST", "ACTIVE", None, "day-7 by calendar date but < 7x24h elapsed"),
    22: ("CONSUMER", "EAST", "ACTIVE", None, "first transaction PENDING, first completed the next day"),
    23: ("CONSUMER", "EAST", "ACTIVE", None, "multi-line transaction with two partial refunds"),
    24: ("CONSUMER", "EAST", "ACTIVE", None, "fully refunded transaction"),
    25: ("CONSUMER", "EAST", "ACTIVE", None, "refunds booked in the month after the sale"),
    26: ("CONSUMER", "EAST", "ACTIVE", None, "two completed transactions at the identical latest timestamp"),
    27: ("CONSUMER", "EAST", "ACTIVE", None, "transaction with NULL payment_method"),
    28: ("CONSUMER", "EAST", "ACTIVE", None, "bought product 1; product 2 only in a CANCELLED txn"),
    29: ("CONSUMER", "EAST", "ACTIVE", None, "bought products 1 and 2 in the same transaction"),
    30: ("CONSUMER", "EAST", "ACTIVE", None, "bought product 1 in H1-2025, product 2 only after"),
    31: ("CONSUMER", "EAST", "ACTIVE", None, "product 1 only in a CANCELLED transaction"),
    32: ("PILOT", "SOUTH", "ACTIVE", None, "PILOT segment, no transactions"),
    33: ("PILOT", "SOUTH", "ACTIVE", None, "PILOT segment, only a CANCELLED transaction"),
    34: ("CONSUMER", "EAST", "ACTIVE", None, "last completed purchase 2025-10-03 00:00:00 UTC"),
    35: ("CONSUMER", "EAST", "DORMANT", None, "last completed purchase 2025-10-02 23:59:59 UTC"),
    36: ("CONSUMER", "EAST", "ACTIVE", None, "only a PENDING transaction recently"),
    37: ("SMALL_BUSINESS", "EAST", "ACTIVE", None, "owns fixture ledger accounts 1-5"),
    40: ("CONSUMER", "NORTH", "ACTIVE", None, "sessionization events with exact 30-minute gaps"),
    50: ("CONSUMER", "WEST", "ACTIVE", None, "SCD2 region change EAST->WEST at 2025-06-15 10:00 UTC"),
    51: ("CONSUMER", "NORTH", "ACTIVE", None, "SCD2 defect: overlapping versions (no transactions)"),
    52: ("CONSUMER", "NORTH", "ACTIVE", None, "SCD2 defect: two current rows (no transactions)"),
    53: ("CONSUMER", "EAST", "ACTIVE", None, "SCD2 gap in March 2025 with transactions in the gap"),
    54: ("CONSUMER", "EAST", "ACTIVE", None, "SCD2 first version starts after the first transaction"),
    55: ("CONSUMER", "NORTH", "ACTIVE", None, "SCD2 defect: open-ended row not flagged current"),
    56: ("CONSUMER", "NORTH", "ACTIVE", None, "SCD2 adjacent (touching) versions - NOT an overlap"),
    60: ("SMALL_BUSINESS", "EAST", "ACTIVE", None, "store 5 shopper (category/product ties)"),
    61: ("SMALL_BUSINESS", "EAST", "ACTIVE", None, "store 5 shopper (category/product ties)"),
    62: ("ENTERPRISE", "SOUTH", "ACTIVE", None, "store 4 shopper (status mix, zero-sales months)"),
    63: ("ENTERPRISE", "SOUTH", "ACTIVE", None, "store 4 shopper (status mix, zero-sales months)"),
    64: ("CONSUMER", "EAST", "ACTIVE", None, "ingestion-watermark boundary and late-arriving transactions"),
    65: ("CONSUMER", "NORTH", "ACTIVE", None, "purchases while store 2 availability changes intra-day"),
    66: ("CONSUMER", "EAST", "ACTIVE", None, "purchases exactly at a product price-change instant"),
    67: ("CONSUMER", "EAST", "ACTIVE", None, "JSON payload edge cases in customer_events"),
    68: ("CONSUMER", "EAST", "ACTIVE", None, "subscription upgrade (end_date = next start_date)"),
    69: ("CONSUMER", "EAST", "ACTIVE", None, "overlapping subscriptions (data issue)"),
    70: ("CONSUMER", "EAST", "ACTIVE", None, "trial subscription only"),
}


def customer_rows():
    rows = []
    for cid, (segment, region, status, tier, _purpose) in sorted(CUSTOMERS.items()):
        rows.append((cid, f"CUST-{cid:06d}", REG, segment, region, status, tier))
    return rows


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------
def _seq(cid):
    """Transaction-id generator for fixture customer `cid`: cid*100+1, +2, ..."""
    n = cid * 100
    while True:
        n += 1
        yield n


def _daily(cid, store, days, amount="20.00", hour=15):
    nxt = _seq(cid)
    return [Txn(next(nxt), cid, store, ts(d.year, d.month, d.day, hour), amount) for d in days]


def _days(start: date, n: int):
    return [start + timedelta(days=i) for i in range(n)]


def build_transactions() -> list[Txn]:
    T: list[Txn] = []

    # --- streak fixtures (store 1, 15:00 UTC = 10:00/11:00 New York, same calendar date) -----
    T += _daily(2, 1, _days(date(2025, 3, 3), 4) + [date(2025, 3, 10)])
    T += _daily(3, 1, _days(date(2025, 3, 3), 5))
    T += _daily(4, 1, _days(date(2025, 4, 1), 7))
    T += _daily(5, 1, _days(date(2025, 5, 1), 5) + _days(date(2025, 5, 10), 5))

    s = _seq(6)  # 6 purchases, 4 consecutive distinct days, skip 06-06, then 06-07
    for d, h in [((2025, 6, 2), 9), ((2025, 6, 2), 18), ((2025, 6, 3), 9), ((2025, 6, 3), 18),
                 ((2025, 6, 4), 15), ((2025, 6, 5), 15), ((2025, 6, 7), 15)]:
        T.append(Txn(next(s), 6, 1, ts(*d, h), "20.00"))

    s = _seq(7)  # 5 distinct days, 8 purchases
    for d, h in [((2025, 6, 10), 9), ((2025, 6, 10), 18), ((2025, 6, 11), 15), ((2025, 6, 12), 8),
                 ((2025, 6, 12), 12), ((2025, 6, 12), 19), ((2025, 6, 13), 15), ((2025, 6, 14), 15)]:
        T.append(Txn(next(s), 7, 1, ts(*d, h), "20.00"))

    T += _daily(8, 1, _days(date(2025, 1, 29), 5))      # 01-29 .. 02-02
    T += _daily(9, 1, _days(date(2024, 12, 29), 5))     # 2024-12-29 .. 2025-01-02
    T += _daily(10, 1, _days(date(2024, 2, 26), 5))     # 02-26 .. 03-01 incl. 02-29
    T += _daily(11, 1, [date(2025, 7, d) for d in (1, 2, 3, 4, 6, 7, 8)])

    s = _seq(12)  # 07-12 has only a CANCELLED transaction; 07-11 has an extra PENDING one
    for d in _days(date(2025, 7, 10), 5):
        T.append(Txn(next(s), 12, 1, ts(d.year, d.month, d.day), "20.00",
                     status="CANCELLED" if d.day == 12 else "COMPLETED"))
    T.append(Txn(next(s), 12, 1, ts(2025, 7, 11, 18), "35.00", status="PENDING"))

    # Store 3 = America/Los_Angeles (PDT = UTC-7 in August). 08-03 02:30 UTC is 08-02 19:30 local.
    s = _seq(13)
    for t in [ts(2025, 8, 1, 12), ts(2025, 8, 2, 12), ts(2025, 8, 3, 2, 30), ts(2025, 8, 4, 12), ts(2025, 8, 5, 12)]:
        T.append(Txn(next(s), 13, 3, t, "20.00"))

    # Store 1 = America/New_York. DST starts 2025-03-09 07:00 UTC, ends 2025-11-02 06:00 UTC.
    s = _seq(14)
    for t in [ts(2025, 3, 10, 3, 30),   # Sun 2025-03-09 23:30 EDT; Mon in UTC (ISO week 10 vs 11)
              ts(2025, 11, 2, 5, 30),   # 01:30 EDT (first 01:30 of the day)
              ts(2025, 11, 2, 6, 30),   # 01:30 EST (second 01:30 of the day)
              ts(2025, 11, 3, 4, 30)]:  # Sun 2025-11-02 23:30 EST; Mon in UTC (ISO week 44 vs 45)
        T.append(Txn(next(s), 14, 1, t, "10.00"))

    # --- daily-spend streaks (SQL-024 style) ---------------------------------------------------
    s = _seq(15)
    for d, amounts in zip(_days(date(2025, 9, 1), 5), [["120.00"], ["60.00", "50.00"], ["101.00"], ["150.00"], ["100.01"]]):
        for i, a in enumerate(amounts):
            T.append(Txn(next(s), 15, 1, ts(d.year, d.month, d.day, 12 + 3 * i), a))
    s = _seq(16)
    for d, a in zip(_days(date(2025, 9, 1), 5), ["120.00", "130.00", "100.00", "140.00", "150.00"]):
        T.append(Txn(next(s), 16, 1, ts(d.year, d.month, d.day), a))
    s = _seq(17)
    for d in _days(date(2025, 9, 1), 5):
        if d.day == 3:
            T.append(Txn(next(s), 17, 1, ts(2025, 9, 3, 12), "150.00", status="CANCELLED"))
            T.append(Txn(next(s), 17, 1, ts(2025, 9, 3, 16), "50.00"))
        else:
            T.append(Txn(next(s), 17, 1, ts(d.year, d.month, d.day), "150.00"))
    s = _seq(18)
    for d in _days(date(2025, 9, 10), 6):
        T.append(Txn(next(s), 18, 1, ts(d.year, d.month, d.day, 11), "55.00"))
        T.append(Txn(next(s), 18, 1, ts(d.year, d.month, d.day, 17), "50.00"))

    # --- retention fixtures ----------------------------------------------------------------
    T += _daily(19, 1, [date(2025, 2, 1), date(2025, 2, 8)], "25.00")
    T += _daily(20, 1, [date(2025, 2, 1), date(2025, 2, 4), date(2025, 2, 9)], "25.00")
    s = _seq(21)
    T.append(Txn(next(s), 21, 1, ts(2025, 2, 1, 23, 50), "25.00"))
    T.append(Txn(next(s), 21, 1, ts(2025, 2, 8, 0, 10), "25.00"))
    s = _seq(22)
    T.append(Txn(next(s), 22, 1, ts(2025, 1, 31), "25.00", status="PENDING"))
    T.append(Txn(next(s), 22, 1, ts(2025, 2, 1), "25.00"))
    T.append(Txn(next(s), 22, 1, ts(2025, 2, 8), "25.00"))

    # --- refunds / fan-out fixtures (refund rows defined in REFUNDS below) ------------------
    V = Txn.VOUCHER_PRODUCT_ID
    T.append(Txn(2301, 23, 1, ts(2025, 10, 10), lines=[(V, 1, "60.00", "0"), (V, 1, "40.00", "0")]))
    T.append(Txn(2302, 23, 1, ts(2025, 10, 15), "40.00"))
    T.append(Txn(2401, 24, 1, ts(2025, 10, 11), "80.00"))
    T.append(Txn(2501, 25, 1, ts(2025, 10, 30), lines=[(V, 1, "70.00", "0"), (V, 1, "50.00", "0")]))

    # --- latest-transaction tie ------------------------------------------------------------
    T.append(Txn(2601, 26, 1, ts(2025, 9, 1), "30.00"))
    T.append(Txn(2602, 26, 1, ts(2025, 10, 5, 18), "10.00"))
    T.append(Txn(2603, 26, 1, ts(2025, 10, 5, 18), "20.00"))
    T.append(Txn(2604, 26, 1, ts(2025, 10, 6, 12), "99.00", status="PENDING"))

    T.append(Txn(2701, 27, 1, ts(2025, 8, 10), "12.34", payment=None))
    # guest checkouts (customer_id NULL) at store 1
    T.append(Txn(9801, None, 1, ts(2025, 8, 10, 16), "8.00", payment="CASH"))
    T.append(Txn(9802, None, 1, ts(2025, 8, 10, 16), "8.00", payment="CASH"))

    # --- product A (1) but never product B (2) in [2025-01-01, 2025-07-01) ---------------
    T.append(Txn(2801, 28, 1, ts(2025, 2, 10), lines=[(1, 1, "18.00", "0")]))
    T.append(Txn(2802, 28, 1, ts(2025, 3, 1), lines=[(2, 1, "24.00", "0")], status="CANCELLED"))
    T.append(Txn(2901, 29, 1, ts(2025, 2, 11), lines=[(1, 1, "18.00", "0"), (2, 1, "24.00", "0")]))
    T.append(Txn(3001, 30, 1, ts(2025, 3, 15), lines=[(1, 2, "18.00", "0")]))
    T.append(Txn(3002, 30, 1, ts(2025, 8, 1), lines=[(2, 1, "24.00", "0")]))
    T.append(Txn(3101, 31, 1, ts(2025, 4, 2), lines=[(1, 1, "19.50", "0")], status="CANCELLED"))

    # --- PILOT segment ------------------------------------------------------------------------
    T.append(Txn(3301, 33, 4, ts(2025, 5, 5), "45.00", status="CANCELLED"))

    # --- inactivity anchor 2025-12-31: window of business dates 2025-10-03 .. 2025-12-31 ------
    T.append(Txn(3401, 34, 1, ts(2025, 5, 1), "15.00"))
    T.append(Txn(3402, 34, 1, ts(2025, 10, 3, 0, 0, 0), "15.00"))
    T.append(Txn(3501, 35, 1, ts(2025, 10, 2, 23, 59, 59), "15.00"))
    T.append(Txn(3601, 36, 1, ts(2025, 6, 1), "15.00"))
    T.append(Txn(3602, 36, 1, ts(2025, 12, 20), "15.00", status="PENDING"))

    # --- SCD2 point-in-time fixtures (store 1) ---------------------------------------------
    for i, t in enumerate([ts(2025, 6, 1), ts(2025, 6, 15, 9, 59, 59), ts(2025, 6, 15, 10, 0, 0), ts(2025, 6, 20)]):
        T.append(Txn(5001 + i, 50, 1, t, "40.00"))
    for i, t in enumerate([ts(2025, 2, 28, 23, 59, 59), ts(2025, 3, 1, 0, 0, 0), ts(2025, 3, 10), ts(2025, 4, 1, 0, 0, 0)]):
        T.append(Txn(5301 + i, 53, 1, t, "40.00"))
    T.append(Txn(5401, 54, 1, ts(2024, 12, 31, 23, 59, 59), "40.00"))
    T.append(Txn(5402, 54, 1, ts(2025, 1, 1, 0, 0, 0), "40.00"))

    # --- store 5 (fixture-only store): November 2025 category/product ties -----------------
    T.append(Txn(6001, 60, 5, ts(2025, 11, 3, 16), lines=[(1, 4, "19.50", "0")]))                      # 78.00
    T.append(Txn(6101, 61, 5, ts(2025, 11, 5, 17), lines=[(5, 2, "9.00", "0"), (6, 2, "30.00", "0")]))  # 78.00
    T.append(Txn(6002, 60, 5, ts(2025, 11, 10), lines=[(2, 3, "24.00", "6.00")]))                      # 66.00
    T.append(Txn(6102, 61, 5, ts(2025, 11, 12), lines=[(8, 10, "3.00", "0"), (8, 12, "3.00", "0")]))   # 66.00
    T.append(Txn(6003, 60, 5, ts(2025, 11, 20), lines=[(3, 5, "12.00", "0")]))                         # 60.00
    T.append(Txn(6103, 61, 5, ts(2025, 11, 21), lines=[(4, 50, "6.00", "0")], status="CANCELLED"))     # 300.00
    T.append(Txn(6004, 60, 5, ts(2025, 12, 2), lines=[(1, 1, "19.50", "0"), (5, 1, "9.00", "0"), (6, 1, "30.00", "0")]))  # 58.50

    # --- store 4 (fixture-only store): status mix, zero-sales months, one distinct amount ---
    s62, s63 = _seq(62), _seq(63)
    for d in [(2025, 1, 5), (2025, 1, 12), (2025, 2, 3), (2025, 3, 1), (2025, 3, 2), (2025, 5, 2)]:
        T.append(Txn(next(s62), 62, 4, ts(*d), "25.00", payment="CASH" if d == (2025, 3, 2) else "CARD"))
    T.append(Txn(next(s62), 62, 4, ts(2025, 2, 14, 18), "25.00", status="PENDING"))
    T.append(Txn(next(s62), 62, 4, ts(2025, 3, 16), "25.00", status="DECLINED"))
    T.append(Txn(next(s62), 62, 4, ts(2025, 6, 1), "25.00", status="PENDING"))
    for d in [(2025, 1, 20), (2025, 2, 14), (2025, 3, 3), (2025, 3, 15), (2025, 5, 20)]:
        T.append(Txn(next(s63), 63, 4, ts(*d), "25.00", payment=None if d == (2025, 5, 20) else "MOBILE"))
    T.append(Txn(next(s63), 63, 4, ts(2025, 3, 15, 18), "25.00", status="CANCELLED"))
    T.append(Txn(next(s63), 63, 4, ts(2025, 4, 10), "25.00", status="CANCELLED"))

    # --- ingestion watermark boundary (pipeline 'transactions_incremental'/POS watermark is
    #     2025-12-15 06:00:00 UTC) and late arrivals vs reporting watermark 2026-01-01 00:00 --
    for i, ing in enumerate([ts(2025, 12, 15, 5, 49, 59), ts(2025, 12, 15, 5, 50, 0), ts(2025, 12, 15, 5, 59, 59),
                             ts(2025, 12, 15, 6, 0, 0), ts(2025, 12, 15, 6, 30, 0), ts(2025, 12, 15, 7, 0, 0)]):
        T.append(Txn(6401 + i, 64, 1, ts(2025, 12, 15, 5, 0, 0), "11.00", ingested_at=ing))
    T.append(Txn(6411, 64, 1, ts(2025, 12, 20, 10), "70.00", ingested_at=ts(2025, 12, 30, 10)))       # 10 days late
    T.append(Txn(6412, 64, 1, ts(2025, 12, 28, 9), "80.00", ingested_at=ts(2026, 1, 5, 9)))           # 8 days late, after report
    T.append(Txn(6413, 64, 1, ts(2025, 12, 31, 23), "90.00", ingested_at=ts(2026, 1, 1, 0, 0, 0)))    # exactly at report watermark
    T.append(Txn(6414, 64, 1, ts(2025, 12, 24, 8), "60.00", ingested_at=ts(2026, 1, 2, 8)))           # 9 days late, after report

    # --- store 2 availability day 2025-05-10 (products 4, 5, 6 in every basket) ----------
    basket = [(4, 1, "6.00", "0"), (5, 1, "9.00", "0"), (6, 1, "30.00", "0")]
    for i, t in enumerate([ts(2025, 5, 10, 10), ts(2025, 5, 10, 13, 0, 0), ts(2025, 5, 10, 14, 59, 59),
                           ts(2025, 5, 10, 15, 0, 0), ts(2025, 5, 10, 21), ts(2025, 5, 11, 9)]):
        T.append(Txn(6501 + i, 65, 2, t, lines=basket))

    # --- price-change instants (product 3 changes 2025-03-01 12:00, product 9 2025-06-15 08:30) --
    T.append(Txn(6601, 66, 1, ts(2025, 3, 1, 11, 59, 59), lines=[(3, 1, "10.00", "0")]))
    T.append(Txn(6602, 66, 1, ts(2025, 3, 1, 12, 0, 0), lines=[(3, 2, "12.00", "0")]))
    T.append(Txn(6603, 66, 1, ts(2025, 3, 2), lines=[(3, 1, "11.00", "0")]))          # price-match override
    T.append(Txn(6604, 66, 1, ts(2025, 6, 15, 8, 30, 0), lines=[(9, 2, "4.50", "0")]))
    T.append(Txn(6605, 66, 1, ts(2025, 6, 15, 8, 29, 59), lines=[(9, 1, "4.25", "0")]))

    return T


# refund_id, transaction_id, refund_ts, amount, reason
REFUNDS = [
    (1, 2301, ts(2025, 10, 12), "20.00", "DAMAGED"),
    (2, 2301, ts(2025, 10, 20), "30.00", "CHANGED_MIND"),
    (3, 2401, ts(2025, 10, 13), "80.00", "DUPLICATE_CHARGE"),
    (4, 2501, ts(2025, 11, 5), "45.00", "PRICE_ADJUSTMENT"),
    (5, 2501, ts(2025, 11, 6), "15.00", "DAMAGED"),
]


def refund_rows():
    return [(rid, tid, rts, money(a), reason) for rid, tid, rts, a, reason in REFUNDS]


# ---------------------------------------------------------------------------
# SCD2 history for fixture customers
# ---------------------------------------------------------------------------
def scd2_rows():
    """customer_sk = customer_id * 10 + version for fixtures."""
    rows = []
    special = {50, 51, 52, 53, 54, 55, 56}
    for cid, (segment, region, status, _tier, _p) in sorted(CUSTOMERS.items()):
        if cid not in special:
            rows.append((cid * 10 + 1, cid, segment, region, status, REG, SCD2_OPEN_END, True))
    rows += [
        (501, 50, "CONSUMER", "EAST", "ACTIVE", REG, ts(2025, 6, 15, 10, 0, 0), False),
        (502, 50, "CONSUMER", "WEST", "ACTIVE", ts(2025, 6, 15, 10, 0, 0), SCD2_OPEN_END, True),
        (511, 51, "CONSUMER", "EAST", "ACTIVE", ts(2024, 1, 1, 0), ts(2025, 2, 1, 0), False),
        (512, 51, "CONSUMER", "NORTH", "ACTIVE", ts(2025, 1, 15, 0), SCD2_OPEN_END, True),
        (521, 52, "CONSUMER", "EAST", "ACTIVE", ts(2024, 1, 1, 0), SCD2_OPEN_END, True),
        (522, 52, "CONSUMER", "NORTH", "ACTIVE", ts(2024, 6, 1, 0), SCD2_OPEN_END, True),
        (531, 53, "CONSUMER", "EAST", "ACTIVE", REG, ts(2025, 3, 1, 0), False),
        (532, 53, "CONSUMER", "EAST", "ACTIVE", ts(2025, 4, 1, 0), SCD2_OPEN_END, True),
        (541, 54, "CONSUMER", "EAST", "ACTIVE", ts(2025, 1, 1, 0), SCD2_OPEN_END, True),
        (551, 55, "CONSUMER", "NORTH", "ACTIVE", REG, SCD2_OPEN_END, False),
        (561, 56, "CONSUMER", "EAST", "ACTIVE", ts(2024, 1, 1, 0), ts(2024, 7, 1, 0), False),
        (562, 56, "CONSUMER", "NORTH", "ACTIVE", ts(2024, 7, 1, 0), SCD2_OPEN_END, True),
    ]
    return rows


# ---------------------------------------------------------------------------
# Accounts + ledger (all owned by customer 37)
# ---------------------------------------------------------------------------
ACCOUNTS = [
    (1, 37, "WALLET", ts(2024, 12, 15, 0), "0.00"),
    (2, 37, "WALLET", ts(2024, 12, 15, 0), "0.00"),
    (3, 37, "CREDIT_LINE", ts(2024, 12, 15, 0), "500.00"),
    (4, 37, "PREPAID", ts(2024, 12, 15, 0), "0.00"),      # no ledger entries at all
    (5, 37, "WALLET", ts(2024, 12, 15, 0), "0.00"),
]

# entry_id, account_id, transaction_id, posting_ts, signed_amount, entry_type
LEDGER = [
    (1, 1, None, ts(2025, 1, 1, 10), "100.00", "DEPOSIT"),
    (2, 1, None, ts(2025, 1, 2, 9), "-30.00", "PURCHASE"),
    (3, 1, None, ts(2025, 1, 2, 9), "-80.00", "PURCHASE"),         # same posting_ts -> balance -10.00
    (4, 1, None, ts(2025, 1, 3, 12), "50.00", "DEPOSIT"),
    (5, 1, None, ts(2025, 1, 5, 0, 0, 0), "-5.00", "FEE"),         # exactly midnight
    (6, 2, None, ts(2025, 1, 1, 8), "200.00", "DEPOSIT"),
    (7, 2, None, ts(2025, 1, 4, 20), "-45.50", "PURCHASE"),
    (8, 3, None, ts(2025, 1, 2, 11), "-20.00", "PURCHASE"),        # negative from the very first entry
    (9, 3, None, ts(2025, 1, 2, 23, 59, 59), "20.00", "DEPOSIT"),  # back to exactly 0.00
    (10, 5, None, ts(2025, 1, 3, 9), "-12.00", "ADJUSTMENT"),      # lower entry_id, later posting_ts
    (11, 5, None, ts(2025, 1, 2, 9), "40.00", "DEPOSIT"),
    (12, 5, None, ts(2025, 1, 3, 9), "-28.00", "PURCHASE"),        # same posting_ts as entry 10
]


def account_rows():
    return [(a, c, t, o, money(l)) for a, c, t, o, l in ACCOUNTS]


def ledger_rows():
    return [(e, a, tx, p, money(amt), et) for e, a, tx, p, amt, et in LEDGER]


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------
SUBSCRIPTIONS = [
    (1, 68, "BASIC", date(2024, 1, 1), date(2024, 6, 1), "EXPIRED", "9.99"),
    (2, 68, "PLUS", date(2024, 6, 1), None, "ACTIVE", "19.99"),
    (3, 69, "BASIC", date(2024, 3, 1), date(2024, 9, 1), "CANCELLED", "9.99"),
    (4, 69, "PREMIUM", date(2024, 8, 15), None, "ACTIVE", "39.99"),
    (5, 70, "BASIC", date(2025, 12, 1), date(2025, 12, 15), "TRIAL", "0.00"),
]


def subscription_rows():
    return [(i, c, p, s, e, st, Decimal(f)) for i, c, p, s, e, st, f in SUBSCRIPTIONS]
