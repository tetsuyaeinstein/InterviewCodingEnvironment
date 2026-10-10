# Common pitfalls (and the exercises that catch them)

Each pitfall below is caught by at least one exercise's adversarial checks. When `lab check`
fails with an "edge-case check" message, find it here.

## SQL

| # | pitfall | example of the bug | fix | exercises |
|---|---|---|---|---|
| 1 | **Join fan-out** | `transactions JOIN transaction_items JOIN refunds` then `SUM(gross_amount)` | aggregate each child to the parent grain first, then join; or use correlated/LATERAL aggregates | SQL-005, SQL-019, SQL-040 |
| 2 | **Inner join drops zero rows** | customers without purchases disappear | `LEFT JOIN` + `COALESCE(sum, 0)`; put child filters in the `ON` clause, not `WHERE` | SQL-001, SQL-009 |
| 3 | **WHERE turns a LEFT JOIN into an INNER JOIN** | `LEFT JOIN t ... WHERE t.status = 'COMPLETED'` | move the predicate into `ON`, or pre-filter in a CTE | SQL-001, SQL-016 |
| 4 | **`NOT IN` with NULLs** | `WHERE id NOT IN (SELECT customer_id ...)` returns nothing if any NULL | `NOT EXISTS` or a LEFT JOIN anti-join | SQL-003, SQL-010 |
| 5 | **Counting rows instead of days** | `COUNT(*) >= 5` over transactions | `DISTINCT customer_id, day` first | SQL-021…024 |
| 6 | **Casting the indexed column** | `WHERE transaction_ts::date = '2025-03-01'` | `transaction_ts >= '2025-03-01' AND transaction_ts < '2025-03-02'` | SQL-052, PY-041 |
| 7 | **`BETWEEN` on timestamps** | `BETWEEN '2025-03-01' AND '2025-03-31'` misses the last day after 00:00 | half-open `>= start AND < next_start` | SQL-002, SQL-028 |
| 8 | **Session time-zone dependence** | `ts::date` changes with `SET TimeZone` | `(ts AT TIME ZONE 'UTC')::date` explicitly | SQL-021, SQL-035 |
| 9 | **ISO week vs calendar year** | `EXTRACT(year)` + `EXTRACT(week)` mislabels 2024-12-30 | `EXTRACT(isoyear)` with `EXTRACT(week)`, or `to_char(d, 'IYYY-"W"IW')` | SQL-035 |
| 10 | **Non-deterministic ties** | `ROW_NUMBER() OVER (ORDER BY ts DESC)` with equal timestamps | add a unique tie-breaker (`, transaction_id DESC`) | SQL-011, SQL-023 |
| 11 | **RANK vs DENSE_RANK vs ROW_NUMBER** | "top 3" cuts ties or skips ranks unexpectedly | decide the tie semantics first, then pick the function | SQL-008, SQL-018 |
| 12 | **Second-largest not distinct** | `OFFSET 1` returns a duplicate of the max | `DENSE_RANK() = 2`, or `MAX(x) WHERE x < MAX(x)` | SQL-012 |
| 13 | **Rolling window by rows, not dates** | `ROWS 6 PRECEDING` skips missing days | build a calendar with `generate_series`, then window, or `RANGE interval '6 days'` | SQL-013 |
| 14 | **Division by zero / percentage of NULL** | `(cur - prev) / prev` when `prev = 0` | `NULLIF(prev, 0)`, and document whether the result is NULL or 0 | SQL-009, SQL-015 |
| 15 | **Closed intervals double-match** | `ts BETWEEN valid_from AND valid_to` matches two versions at the change instant | `ts >= valid_from AND (valid_to IS NULL OR ts < valid_to)` | SQL-028, SQL-031 |
| 16 | **Using current dimension attributes for history** | joining facts to `customers.home_region` | point-in-time join to `dim_customer_scd2` | SQL-031, SQL-039 |
| 17 | **Ingestion order as truth** | latest CDC version by `ingested_at` | order by `source_lsn` within the source system | SQL-041, SQL-049 |
| 18 | **Resurrecting deletes** | applying a late stale UPDATE after a DELETE | keep tombstones / compare LSNs before applying | SQL-047 |
| 19 | **`=` instead of `IS DISTINCT FROM`** | NULL vs NULL "differs", NULL vs value "equal" | `a IS DISTINCT FROM b` | SQL-044 |
| 20 | **Ambiguous concatenated hashes** | `md5(a || b)` collides for ('AB','C') vs ('A','BC'); `coalesce(x,'')` hides NULL vs '' | length-prefix or delimiter + escaping + NULL marker, or hash a row-to-JSON | SQL-045, PY-037 |
| 21 | **Non-idempotent incremental loads** | plain `INSERT` of a re-delivered batch doubles totals | upsert on the natural key / delete-insert by partition | SQL-048 |
| 22 | **Unsafe watermark** | `MAX(window_end)` of successful runs skips a failed gap | require contiguity of successful windows | SQL-050 |
| 23 | **jsonb array assumptions** | `jsonb_array_elements(payload->'items')` errors on an object | guard with `jsonb_typeof(...) = 'array'` | SQL-056, SQL-057 |
| 24 | **Partition pruning blocked** | `WHERE date_trunc('month', sale_date) = ...` | plain range predicates on the partition key | SQL-059 |

## Python

| # | pitfall | fix | exercises |
|---|---|---|---|
| 1 | float money | `Decimal(str_value)`, never `Decimal(float)`; quantize at the edges | PY-002, PY-021 |
| 2 | naive datetimes silently treated as local | reject or require an explicit zone; `datetime.fromisoformat` + `astimezone(UTC)` | PY-005, PY-006 |
| 3 | DST arithmetic on local times | do arithmetic in UTC; convert for display/grouping only | PY-006, PY-035 |
| 4 | unstable sort for ties | sort key tuples with an explicit tie-breaker | PY-003, PY-009, PY-014 |
| 5 | loading whole files | iterate lines/rows; generators; `csv` with `newline=''` | PY-021, PY-022, PY-029 |
| 6 | mutable default arguments / shared state | `None` default + create inside | PY-032, PY-045 |
| 7 | swallowing exceptions | catch narrow exceptions; quarantine with reason + line number | PY-022, PY-007 |
| 8 | partial file publish | temp file in the same directory, `fsync`, `os.replace` | PY-026 |
| 9 | retry storms / non-deterministic tests | capped exponential backoff with an injected clock/sleeper and jitter source | PY-033, PY-047 |
| 10 | at-least-once without idempotency | stable event IDs + processed-set / version check | PY-032, PY-039 |
| 11 | SQL string building | parameters (`%s`, `%(name)s`), `psycopg.sql.Identifier` for identifiers | PY-041, PY-043 |
| 12 | OFFSET pagination drift | keyset pagination on a unique composite key | PY-044, PY-046 |
| 13 | unbounded concurrency | `asyncio.Semaphore` / bounded queues | PY-038, PY-048 |
