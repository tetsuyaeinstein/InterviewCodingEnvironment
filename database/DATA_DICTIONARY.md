# Data dictionary: interview lab database

Fictional retail + stored-value finance company with stores, kiosks and an online flagship. All
data is synthetic and generated deterministically by `python -m lab db seed --size <profile>`. No
real people, companies or personal data appear anywhere. Names are invented word combinations.

## Global conventions (read these first)

| topic | convention |
|---|---|
| Time zone | All timestamps are `timestamptz` and stored in **UTC**. Lab sessions run with `timezone = UTC`. |
| Business date | Unless a question says otherwise, the business date of an event is its **UTC calendar date**: `(ts AT TIME ZONE 'UTC')::date`. Store-local dates use `stores.timezone` (IANA zone), e.g. `(t.transaction_ts AT TIME ZONE s.timezone)::date`. |
| Intervals | Half-open `[from, to)` everywhere. History tables use `valid_to IS NULL` for "still valid". `dim_customer_scd2` uses the sentinel `effective_to = '9999-12-31 00:00:00+00'` instead. |
| Money | `numeric(12,2)` / `numeric(14,2)`; never floats. |
| Purchase | A "purchase" is a `transactions` row with `transaction_status = 'COMPLETED'`. Other statuses: `PENDING`, `CANCELLED`, `DECLINED`. |
| Guests | `transactions.customer_id IS NULL` is a guest checkout. |
| Data window | Generated business data covers 2024-01-01 – 2025-12-31 (UTC). Some ingestion/refund timestamps fall in early 2026. Nothing depends on `now()`. |
| Fixture IDs | Hand-written edge cases use reserved low IDs (customers 1–99, stores 1–5, products 1–10, transactions < 10000). Generated rows start at customer 1001, transaction 100001, etc. Fixtures are identical in every seed profile. |

## Tables

Kind: **CS** = current state, **H** = immutable history / versions, **E** = events (append-only),
**S** = periodic snapshot, **L** = landing/staging (untrusted), **D** = derived summary.

| table | kind | grain / primary key | business keys & FKs | notes |
|---|---|---|---|---|
| `stores` | CS | `store_id` | `store_code` unique | `region` ∈ NORTH/SOUTH/EAST/WEST; `store_type` ∈ KIOSK/CONVENIENCE/SUPERMARKET/ONLINE; `timezone` IANA (ONLINE stores use `UTC`). Store 6 is the high-volume ONLINE flagship (skew). |
| `customers` | CS | `customer_id` | `customer_code` unique | `segment` ∈ CONSUMER/SMALL_BUSINESS/ENTERPRISE/PILOT; `home_region` NULL = unknown; `status` ACTIVE/DORMANT/CLOSED; `loyalty_tier` NULL = not enrolled. Current attributes only; history is in `dim_customer_scd2`. Customer 1001 is a very heavy ENTERPRISE account (skew). |
| `product_categories` | CS | `category_id` | `category_name` unique | 12 fixed categories, each with a `department`. |
| `products` | CS | `product_id` | `sku` unique; FK `category_id` | `standard_price` = current list price. Product 7 "Open-Price Voucher" has **no price history** (its price is set at the till). |
| `product_price_history` | H | (`product_id`, `valid_from`) | FK `product_id` | `[valid_from, valid_to)`, `valid_to NULL` = current; non-overlap enforced by an `EXCLUDE` constraint. Changes happen at midnight or mid-day. |
| `transactions` | E | `transaction_id` | FK `customer_id` (nullable), `store_id` | Header grain. `gross_amount = SUM(quantity*unit_price - discount_amount)` of its lines (exact). `payment_method` may be NULL. `source_system` POS/ECOM. `ingested_at >= transaction_ts`: ~3% arrive 1–3 days late, ~0.5% 4–12 days late. Customers can buy several times a day. |
| `transaction_items` | E | (`transaction_id`, `line_number`) | FK `transaction_id`, `product_id` | Order-line grain. `unit_price` normally equals the effective list price at `transaction_ts`; ~2% are manual price overrides. A product can appear on two lines of one transaction. |
| `refunds` | E | `refund_id` | FK `transaction_id` | Only for COMPLETED transactions. Several partial refunds per transaction are possible; `SUM(refund_amount) <= gross_amount`. `refund_ts` is after the sale (can be in a later month). |
| `customer_events` | E | `event_id` | FK `customer_id` (NULL = anonymous) | Clickstream. `session_id` is client-supplied and unreliable (often NULL). `payload` jsonb with **inconsistent typing**: `amount` as string, number, `"N/A"`, missing or null; `items` as array, empty array, null or even an object; `qty` sometimes a string. |
| `event_ingestion_log` | E | `log_id` | `raw_event_id` (repeats on retry) | One row per ingestion attempt. `ingestion_status` LOADED/REJECTED/DUPLICATE/RETRIED. Delay = `ingest_ts - event_ts`; a few rows have **negative** delay (clock skew). |
| `store_product_availability` | H | (`store_id`, `product_id`, `valid_from`) | FKs | `[valid_from, valid_to)`, `valid_to NULL` = open-ended. Rows never overlap (EXCLUDE). **A timestamp covered by no row means "not stocked" = unavailable.** Changes happen mid-day. Only the first N products are tracked (60 in small). |
| `subscriptions` | H | `subscription_id` | FK `customer_id` | `[start_date, end_date)` dates, `end_date NULL` = running. Upgrades start on the previous end date. A few overlaps exist (data issue). |
| `employees` | CS | `employee_id` | self-FK `manager_id` (NULL = CEO) | 300 people, 5 levels, 6 departments + Executive; salaries in steps, so ties are common; some terminated. Identical in every profile. |
| `accounts` | CS | `account_id` | FK `customer_id` | Stored-value accounts; CREDIT_LINE accounts have a `credit_limit`. |
| `account_ledger` | E | `entry_id` | FK `account_id`; `transaction_id` soft ref (no FK) | Signed postings (+ credit, − debit). Ties on `posting_ts` are ordered by `entry_id`. Balances can go negative. |
| `devices` | CS | `device_id` | FK `store_id` | Kiosks / POS terminals; `decommissioned_on` = first day out of service (NULL = active). |
| `device_status_events` | E | `event_id` | FK `device_id` | One `SCHEDULED` report per UTC day at ~02:00 (some days missing), plus `CHANGE` events on UP/DOWN flips. `received_at` order ≠ `event_ts` order. |
| `device_downtime_incidents` | E | `incident_id` | FK `device_id` | Outages reported independently by MONITORING / TECHNICIAN / VENDOR. `[down_from, down_to)`; intervals overlap, nest, touch or duplicate each other. |
| `customer_daily_activity` | D | (`customer_id`, `activity_date`) | FK `customer_id` | Built by the seed from COMPLETED, non-guest transactions; `activity_date` = UTC date. |
| `daily_store_snapshot` | S | (`snapshot_date`, `store_id`, `product_id`) | FKs | End-of-day stock for 10 stores × 19 products, 2025-10-01 … 2025-12-31. `units_sold` = completed units that UTC day. **Store 3 is missing 2025-11-15** (failed snapshot job). |
| `dim_customer_scd2` | H | `customer_sk` (surrogate) | `customer_id` business key (no FK, no uniqueness) | `[effective_from, effective_to)`, current row `effective_to = 9999-12-31`, `is_current = true`. Generated customers: first version starts at `registered_at`, last version = current `customers` attributes. Deliberate defects only for fixtures 51, 52, 55 (see below). |
| `source_transactions` / `target_transactions` | S | `transaction_id` | – | Source extract vs warehouse load of December 2025 transactions plus fixtures 90001–90020. Rows are deliberately missing, extra or changed (including NULL vs value, `''` vs NULL, and 1-second timestamp drift). |
| `cdc_transaction_events` | E | `cdc_event_id` (= arrival order) | key (`source_system`, `business_key`) | Operation I/U/D. `source_lsn` is the source commit order and the only reliable ordering; `ingested_at` is arrival order. LSN sequences are per source system, and POS and ECOM even share LSN numbers. `payload` is the full after-image for I/U (`amount` as string) and the key only for D. ~1,500 generated keys (Nov–Dec 2025) + `FX-*` fixtures (2025-12-31). Identical in every profile. |
| `pipeline_runs` | E | `run_id` | (`pipeline_name`, `source_system`) | Each run processes `[window_start, window_end)`. Status SUCCEEDED/FAILED/RUNNING; retries re-process failed windows later. |
| `pipeline_watermarks` | CS | (`pipeline_name`, `source_system`) | – | Last committed high-water mark as recorded by the (buggy) job. Includes `daily_sales_report/ALL = 2026-01-01 00:00 UTC`, the reporting cut-off. |
| `raw_transaction_events` | L | `delivery_id` | `message_id` (repeats on redelivery), `transaction_id` business key | At-least-once message deliveries of December 2025 transactions: redeliveries (same `message_id`), legitimate STATUS_CHANGED events (new `message_id`), and double-posted CREATED events (different `message_id`, same `transaction_id`). |
| `stg_transaction_items` | L | none | none (no constraints) | Untrusted landing copy of lines: batch 2 = December 2025 lines; batch 1 = orphans, NULL keys and duplicates. |
| `fact_sales_partitioned` | D | (`sale_date`, `transaction_id`, `line_number`) | – | Line-grain COMPLETED sales, `PARTITION BY RANGE (sale_date)`, monthly partitions `fact_sales_pYYYY_MM` for 2024–2025, plus a default partition. |
| `lab_meta`, `schema_migrations` | – | – | – | Lab bookkeeping (seed profile, counts, checksum; applied migrations). |

Baseline indexes (`004_indexes.sql`):

- `transactions(customer_id)`, `(transaction_ts)`, `(store_id, transaction_ts)`
- `transaction_items(product_id)`, `refunds(transaction_id)`, `customer_events(customer_id, event_ts)`
- `account_ledger(account_id, posting_ts, entry_id)`, `device_status_events(device_id, event_ts)`
- `dim_customer_scd2(customer_id, effective_from)`, `cdc_transaction_events(source_system, business_key, source_lsn)`
- `event_ingestion_log(raw_event_id)`, `raw_transaction_events(transaction_id)`
- `subscriptions(customer_id, start_date)`, `employees(manager_id)`

There is deliberately **no** `(customer_id, transaction_ts)` composite index. The performance
exercises build candidates in sandbox schemas.

## Seed profiles and actual row counts

| table | small | medium | large |
|---|---:|---:|---:|
| `stores` | 40 | 120 | 300 |
| `customers` | 2,056 | 20,056 | 100,056 |
| `products` | 200 | 600 | 1,500 |
| `product_categories` | 12 | 12 | 12 |
| `product_price_history` | 375 | 1,171 | 2,882 |
| `transactions` | 21,257 | 263,512 | 1,581,206 |
| `transaction_items` | 46,589 | 579,733 | 3,479,385 |
| `refunds` | 1,420 | 17,697 | 106,499 |
| `customer_events` | 30,154 | 200,373 | 599,644 |
| `event_ingestion_log` | 30,590 | 202,981 | 607,432 |
| `store_product_availability` | 48,080 | 241,891 | 913,648 |
| `subscriptions` | 1,422 | 14,393 | 71,432 |
| `employees` | 300 | 300 | 300 |
| `accounts` | 505 | 3,005 | 10,005 |
| `account_ledger` | 40,603 | 177,617 | 499,439 |
| `devices` | 63 | 153 | 303 |
| `device_status_events` | 27,988 | 70,419 | 140,742 |
| `device_downtime_incidents` | 1,177 | 3,021 | 6,099 |
| `customer_daily_activity` | 17,091 | 207,497 | 1,230,292 |
| `daily_store_snapshot` | 17,461 | 17,461 | 17,461 |
| `dim_customer_scd2` | 3,068 | 29,922 | 149,735 |
| `source_transactions` | 2,032 | 24,900 | 151,257 |
| `target_transactions` | 2,020 | 24,769 | 150,460 |
| `cdc_transaction_events` | 3,797 | 3,797 | 3,797 |
| `pipeline_runs` | 51 | 51 | 51 |
| `pipeline_watermarks` | 6 | 6 | 6 |
| `raw_transaction_events` | 2,224 | 27,177 | 164,990 |
| `stg_transaction_items` | 4,436 | 54,642 | 332,986 |
| `fact_sales_partitioned` | 41,987 | 521,290 | 3,132,481 |
| **all tables** | **347,004** | **2,708,566** | **13,454,400** |

Checksums (seed version 1; `python -m lab db status` prints the live one): small `c5f7bde53a61d19fa891a461b2f61171`, medium `031ade0e7fa2437d7b66cbff0e10c5a4`, large `df3314b38eef0cb657cbd5379e09b89d`. Re-seeding any profile reproduces its checksum exactly. Timings measured on a Windows laptop with Docker Desktop: small about 8 s, medium about 75 s, large about 250 s (a few GB of disk). The exact counts for the live profile are in `lab_meta` (`SELECT meta_value->'row_counts' FROM lab_meta`).

## Fixture catalogue (hand-checkable edge cases)

All fixture transactions are at store 1 (America/New_York), 15:00 UTC, COMPLETED, unless noted.
Store 1 15:00 UTC is the same calendar date locally.

### Purchase streaks, calendars and time zones

| customer | data | demonstrates |
|---|---|---|
| 1 | no transactions at all | zero rows / LEFT JOIN, inactivity |
| 2 | 2025-03-03 … 03-06 (4 days) + 03-10 | exactly 4 consecutive days → not a 5-streak |
| 3 | 2025-03-03 … 03-07 | exactly 5 consecutive days |
| 4 | 2025-04-01 … 04-07 | 7-day streak (6+) |
| 5 | 2025-05-01 … 05-05 and 05-10 … 05-14 | two disjoint 5-day streaks of equal length (tie) |
| 6 | 06-02 ×2, 06-03 ×2, 06-04, 06-05, 06-07 | many rows, only 4 consecutive distinct days |
| 7 | 06-10 ×2, 06-11, 06-12 ×3, 06-13, 06-14 | 5-day streak with same-day duplicates |
| 8 | 2025-01-29 … 02-02 | month boundary |
| 9 | 2024-12-29 … 2025-01-02 | year boundary; 2024-12-30 starts ISO week 2025-W01 |
| 10 | 2024-02-26 … 03-01 | leap day 2024-02-29 |
| 11 | 2025-07-01 … 07-04, 07-06 … 07-08 | skipped day (4 + 3) |
| 12 | 2025-07-10 … 07-14; 07-12 only CANCELLED; extra PENDING on 07-11 | non-completed day breaks a streak |
| 13 | store 3 (Los Angeles): UTC 08-01 12:00, 08-02 12:00, **08-03 02:30**, 08-04 12:00, 08-05 12:00 | 5 consecutive **UTC** dates, but in local time 08-03 02:30 UTC is 08-02 19:30 PDT → not a local streak |
| 14 | 2025-03-10 03:30 UTC (Sun 03-09 23:30 EDT), 2025-11-02 05:30 UTC (01:30 EDT), 2025-11-02 06:30 UTC (01:30 EST), 2025-11-03 04:30 UTC (Sun 11-02 23:30 EST); 10.00 each | DST transitions; ISO week differs between UTC and New York |

### Daily spend thresholds (each day's total of COMPLETED `gross_amount`)

| customer | daily totals | demonstrates |
|---|---|---|
| 15 | 2025-09-01 … 05: 120.00, 110.00 (60+50), 101.00, 150.00, 100.01 | qualifies for "> 100 every day" |
| 16 | 2025-09-01 … 05: 120, 130, **100.00**, 140, 150 | exactly 100.00 is not > 100 |
| 17 | 2025-09-01 … 05: 150 each, but 09-03 = 150 CANCELLED + 50 completed | cancelled spend does not count |
| 18 | 2025-09-10 … 15: 55.00 + 50.00 per day (6 days) | each purchase < 100, daily sum > 100: aggregate before filtering |

### Retention, first purchase and inactivity (anchor 2025-12-31)

| customer | data | demonstrates |
|---|---|---|
| 19 | 2025-02-01, 2025-02-08 | purchase exactly on day 7 |
| 20 | 2025-02-01, 02-04, 02-09 | within the first week but not on day 7 |
| 21 | 2025-02-01 23:50, 2025-02-08 00:10 | day 7 by calendar date, only 6d 0h20m elapsed |
| 22 | 2025-01-31 PENDING, 2025-02-01, 2025-02-08 | first *completed* purchase is 02-01 |
| 34 | 2025-05-01, **2025-10-03 00:00:00** | last purchase on the first day of a 90-day window ending 2025-12-31 (10-03 … 12-31 inclusive) |
| 35 | **2025-10-02 23:59:59** (status DORMANT) | one second before that window |
| 36 | 2025-06-01 completed, 2025-12-20 PENDING | recent activity is not a completed purchase |
| 32, 33 | segment PILOT: 32 none; 33 one CANCELLED 45.00 (store 4) | segment with zero completed spend (division by zero, NULL vs 0 policy) |

### Refunds, ties, NULLs, A-not-B

| entity | data | demonstrates |
|---|---|---|
| customer 23 | txn 2301 (2025-10-10) = two lines 60 + 40 = 100.00, refunds 20.00 (10-12) + 30.00 (10-20); txn 2302 (10-15) 40.00 | multiple partial refunds; lines × refunds join fan-out; net = 90.00 |
| customer 24 | txn 2401 80.00 fully refunded 2025-10-13 | net zero |
| customer 25 | txn 2501 (2025-10-30) 70 + 50 = 120.00; refunds 45.00 (2025-11-05) + 15.00 (11-06) | refunds land in the following month |
| customer 26 | 2601 (09-01, 30.00); **2602 and 2603 both at 2025-10-05 18:00:00** (10.00, 20.00); 2604 (10-06, PENDING 99.00) | latest-transaction ties (tie-break on `transaction_id`); a later non-completed row |
| customer 27 / guests | 2701 with `payment_method` NULL; guest txns 9801 and 9802 (customer NULL, store 1, same timestamp 2025-08-10 16:00, both 8.00 CASH) | NULL handling; duplicate-looking but distinct rows |
| customers 28–31 | product 1 = A, product 2 = B, window [2025-01-01, 2025-07-01): 28 bought A, and B only in a CANCELLED txn; 29 bought A and B in the same txn; 30 bought A, and B only on 2025-08-01; 31 bought A only in a CANCELLED txn | "bought A but never B" (28 and 30 qualify) |

### Fixture-only stores 4 and 5 (no generated transactions)

| store | data | demonstrates |
|---|---|---|
| 4 (America/Phoenix) | customers 62/63, all 25.00 vouchers. COMPLETED: Jan 5, 12, 20; Feb 3, 14; Mar 1, 2, 3, 15; May 2, 20 (2025). Also PENDING 02-14 and 06-01, DECLINED 03-16, CANCELLED 03-15 and 04-10, and customer 33's CANCELLED 05-05 | status mix (11 completed, 2 pending, 3 cancelled, 1 declined); zero-sales months (Apr, Jun–Dec 2025); only one distinct amount → no "second largest" |
| 5 (America/New_York) | Nov 2025 COMPLETED: 6001 = 4 × p1 @19.50 = 78.00; 6101 = 2 × p5 @9 + 2 × p6 @30 = 78.00; 6002 = 3 × p2 @24 − 6.00 discount = 66.00; 6102 = p8 ×10 + p8 ×12 @3 (two lines, same product) = 66.00; 6003 = 5 × p3 @12 = 60.00; CANCELLED 6103 = 50 × p4 = 300.00; Dec: 6004 = p1 + p5 + p6 = 58.50 | Category revenue Nov 2025 (net of discounts): Coffee 78 = Electronics 78 > Kitchenware 66 = Stationery 66 > Snacks 60, i.e. ties for 1st and 3rd. Two transactions with equal max amount (78), second distinct amount 66. Self-pair (p8, p8) and pair (p5, p6) for market-basket questions |

### Point-in-time, availability and ingestion

| entity | data | demonstrates |
|---|---|---|
| customer 50 | SCD2: EAST `[2023-12-01, 2025-06-15 10:00)`, WEST `[2025-06-15 10:00, 9999)`; txns 2025-06-01, **06-15 09:59:59**, **06-15 10:00:00**, 06-20 | half-open effective-date boundary; current region (WEST) ≠ historical region |
| customer 53 | SCD2 versions `[2023-12-01, 2025-03-01)` and `[2025-04-01, 9999)` (gap in March); txns 02-28 23:59:59, **03-01 00:00:00**, 03-10, **04-01 00:00:00** | facts with no matching dimension version (03-01 and 03-10) |
| customer 54 | first SCD2 version starts 2025-01-01; txns 2024-12-31 23:59:59 (no version) and 2025-01-01 00:00:00 (matches) | dimension row arrives later than the first fact |
| customers 51, 52, 55, 56 (no transactions) | 51: overlapping versions (`[2024-01-01, 2025-02-01)` vs `[2025-01-15, ∞)`); 52: two `is_current` rows, both open-ended; 55: open-ended row with `is_current = false`; 56: adjacent versions touching at 2024-07-01 (valid, **not** an overlap) | SCD2 data-quality checks |
| customer 64 | six txns at 2025-12-15 05:00 ingested at 05:49:59, 05:50:00, 05:59:59, 06:00:00, 06:30:00, 07:00:00; late: 6411 (12-20, ingested 12-30, 10 days), 6412 (12-28 → 2026-01-05), 6413 (12-31 23:00 → exactly 2026-01-01 00:00:00), 6414 (12-24 → 2026-01-02) | watermark `transactions_incremental/POS` = 2025-12-15 06:00 with an overlap window; late arrivals vs the reporting watermark 2026-01-01 00:00 |
| customer 65 / store 2 | products 4, 5, 6 on 2025-05-10 (UTC): p4 unavailable `[13:00, 15:00)`; p5 always available; p6 unavailable `[09:00, 12:00)` and **uncovered** (not stocked) `[20:00, next day 08:00)`. Baskets with p4 + p5 + p6 at 10:00, 13:00:00, 14:59:59, 15:00:00, 21:00, 05-11 09:00 | ALL vs ANY availability at a timestamp; half-open boundaries; gaps |
| customer 66 | p3 price 10.00 → 12.00 at 2025-03-01 12:00: lines at 11:59:59 (10.00) and 12:00:00 (12.00); 03-02 line at 11.00 (override); p9 4.25 → 4.50 at 2025-06-15 08:30 with lines at 08:29:59 and 08:30:00 | point-in-time price lookup; charged vs list price |
| customer 40 events | 2025-07-01 10:00, 10:10, **10:40 (gap exactly 30m)**, **11:10:01 (gap 30m01s)**, 11:10:01 (same ts), 11:20; 23:50 and 07-02 00:05 (over midnight); 07-03 09:00 | sessionization with a "> 30 minutes" rule → 4 sessions; unreliable client `session_id` |
| customer 67 events | event_ids 101–111 on 2025-08-15 | JSON edge cases: string, number, `"N/A"`, missing, null, `"1e3"`, `" 42.10 "` (padded) and negative amounts; `qty` `"two"` / `"3"`; `items` empty, null, an object, duplicate entries, null sku; `is_member` `"yes"` |
| ingestion `evt-fx-*` | source_system FIXTURE, event_ts 2025-12-01 12:00: 20 LOADED with delays 0, 30, …, 570 s; 021 negative (−45 s); 022 RETRIED then LOADED at +620 s; 023 REJECTED; 024 LOADED + DUPLICATE; 025 LOADED after 2 days | percentile definitions; which attempt counts; negative delays |

### Ledger accounts 1–5 (owner customer 37)

| account | entries (entry_id: posting_ts, amount) | demonstrates |
|---|---|---|
| 1 | 1: 01-01 10:00 +100; 2: 01-02 09:00 −30; 3: 01-02 09:00 −80 (same ts) → −10; 4: 01-03 +50; 5: **01-05 00:00:00** −5 | negative balance mid-day; same-timestamp ordering by entry_id; posting exactly at midnight |
| 2 | 6: 01-01 +200; 7: 01-04 −45.50 | days without postings (carry balance forward) |
| 3 (CREDIT_LINE, limit 500) | 8: 01-02 11:00 −20; 9: 01-02 23:59:59 +20 → 0.00 | negative from the first entry; zero is not negative |
| 4 | none | account without postings |
| 5 | 11: 01-02 09:00 +40; 10: 01-03 09:00 −12; 12: 01-03 09:00 −28 | entry_id order ≠ time order; balance reaches exactly 0 |

(all dates January 2025)

### Kiosk devices (store 2, January 2025)

| device | data | demonstrates |
|---|---|---|
| KIOSK-F01 | `decommissioned_on` 2025-02-01; daily 02:00 reports except **01-10, 01-11, 01-20**. CHANGE events on 01-15: DOWN 08:00 (received 09:45, out of order), UP 09:30, DOWN 09:30, UP 10:00; and 01-16 12:00–12:30. Incidents: `[08:00, 09:30)` MONITORING, `[09:00, 10:00)` TECHNICIAN (overlap), `[10:00, 10:15)` VENDOR (touching), `[08:30, 08:45)` (nested), `[01-16 12:00, 12:30)` | missing scheduled reports; merging overlapping/touching intervals → 08:00–10:15 + 12:00–12:30 = **165 minutes** |
| KIOSK-F02 | `decommissioned_on` 2025-02-01; reports every day; the 01-15 report is received on 01-16; 01-22 has two reports. DOWN 01-20 23:30, DOWN again 23:45, UP 01-21 00:30. Two identical incidents `[01-20 23:30, 01-21 00:30)` | duplicate reports; outage across midnight; duplicate incidents (60 minutes total) |
| KIOSK-F03 | reports 01-01 … 01-31, `decommissioned_on` 2025-03-01, silent all of February | long reporting gap while still in service |

### CDC (`cdc_transaction_events`, source POS unless noted, commits 2025-12-31)

| key | events | demonstrates |
|---|---|---|
| FX-0001 | I 9000010 (50.00) → U 9000020 (55.00, **ingested last**) → U 9000030 (60.00 COMPLETED) | latest by LSN ≠ latest by ingestion |
| FX-0002 | I 9000110 → D 9000120 → stale U 9000115 ingested after the delete | tombstone must not be resurrected |
| FX-0003 | I 9000210 → D 9000220 → I 9000230 (35.00 COMPLETED) | legitimate re-insert after delete |
| FX-0004 | I 9000310 → U 9000320 delivered **twice** (identical) | duplicate delivery |
| FX-0005 | U 9000420 and U 9000430 with the **same commit_ts**, arriving in reverse | commit-time tie; LSN decides |
| FX-0006 | two different U events sharing LSN 9000520 (75.00 vs 80.00) | conflicting tie: flag it, don't silently pick one |
| FX-0007 | only a D (key never inserted) | tombstone for an unknown key |
| FX-0008 | U 9000720 arrives **before** its I 9000710 | out-of-order arrival |
| FX-0010 | I + 3 U in order | control case |
| ECOM FX-0001 | I 9000010 (500.00), U 9000020 (510.00) | same business_key text **and** same LSN numbers in another source system |

### Pipelines (`transactions_incremental`, hourly windows on 2025-12-15)

| source | runs | safe watermark | recorded watermark |
|---|---|---|---|
| POS | 00–01 ✓, 01–02 ✓ (and a re-run ✓), 02–03 ✓, 03–04 ✗ then retried ✓ later, 04–05 ✓, 05–06 ✓ | 06:00 | 06:00 |
| ECOM | 00–01 ✓, 01–02 ✗ (never retried), 02–03 ✓, 03–04 ✓ | **01:00** | 04:00 (unsafe) |
| KIOSK | 00–01 ✓, 01–02 ✓, 02–03 RUNNING, 03–04 ✓ | 02:00 | 02:00 |
| MOBILE | 00–01 ✗ twice | none (stays at 00:00) | 00:00 |

`customer_events_load/APP` has daily December runs, with failures on 12-10 and 12-20 that are
retried successfully.

### Reconciliation rows (`source_transactions` vs `target_transactions`)

| id | difference |
|---|---|
| 90001–90005 | identical |
| 90006 | missing in target |
| 90007 | extra in target |
| 90008 | amount 10.00 vs 10.01 |
| 90009 | status COMPLETED vs CANCELLED |
| 90010 | customer_id NULL vs 1001 |
| 90011, 90012 | NULL in both → **not** a difference |
| 90013 | note `''` vs NULL → a difference |
| 90014 | transaction_ts differs by 1 second |
| 90015 / 90016 | identical in both systems; `('AB','C')` vs `('A','BC')` collide under naive concatenation |
| 90017 / 90018 | `('X|Y', NULL)` vs `('X','Y')` collide under `'|'` concatenation with NULL → '' |
| 90019 / 90020 | `note = 'NULL'` (string) vs NULL with otherwise equal business values |

Generated December rows add hash-selected differences: about 1% missing, amount +0.01,
PENDING→COMPLETED, payment_method nulled, and late-November extras in the target.

### Raw deliveries and staging

| entity | data |
|---|---|
| `raw_transaction_events` delivery 1–10 | 2301 delivered 3× (same message_id, redelivery); 2302 CREATED + STATUS_CHANGED; 2401 CREATED twice with different message_ids (double-posting); 2501 once; 2601 CREATED twice with **different amounts** (conflict) |
| `stg_transaction_items` batch 1 | missing transaction (99999999), missing product (999999), both missing, NULL product_id, NULL transaction_id, a valid line loaded twice, a valid line |
