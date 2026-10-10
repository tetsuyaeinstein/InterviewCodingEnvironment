# Interview playbook: senior / lead data engineer coding rounds

Interviewers at this level grade four things at once:

1. **Correctness:** right answer, including edge cases.
2. **Communication:** clarify, state assumptions, narrate the plan.
3. **Engineering judgement:** grain, scale, idempotency, data quality.
4. **Fluency:** you type working SQL/Python without fumbling syntax.

This lab trains all four. Use the routine below on every exercise, out loud, even when practising alone.

---

## 1. The 6-step routine (45-minute round)

| step | time | what you do | what to say |
|---|---|---|---|
| 1. Clarify | 3–5 min | Restate the problem; ask about grain, filters, time zone, ties, NULLs, duplicates, output shape and order | "Before I write anything, let me confirm what one output row means…" |
| 2. Examples | 2–3 min | Build a 4–6 row example that includes a nasty case (duplicate, tie, boundary) | "Here's a tricky input; I expect this output because…" |
| 3. Plan | 3–5 min | Name the approach and its complexity; mention alternatives in one sentence | "I'll de-duplicate to customer-day first, then gaps-and-islands with ROW_NUMBER. O(n log n) for the sort." |
| 4. Code | 15–20 min | Write top-down: CTE names or function skeleton first, then fill in | Narrate the *why* of each CTE / step, not the syntax |
| 5. Test | 5 min | Walk your example through the code; run it; check the edge cases | "Customer with two purchases on one day: the DISTINCT collapses them…" |
| 6. Scale & production | 5 min | 500M rows, late data, idempotency, monitoring, validation | "In production I'd pre-aggregate daily, partition by date, reconcile counts…" |

If you get stuck, say what you are trying, fall back to a simpler correct version, then optimise.
A correct O(n log n) solution beats an unfinished clever one.

---

## 2. Clarifying questions checklist

**Grain and keys**

- What is one row of the output? One per customer, per customer-day, or per streak?
- What is the grain of each input table? Is `transaction_id` unique? Is there a header/line split?
- Which key identifies an entity across systems: business key or surrogate key? Does the key
  include the source system? (In this lab, `FX-0001` exists in both POS and ECOM.)

**Filters and semantics**

- Which statuses count (COMPLETED only? pending? refunds?), and is the amount gross or net of
  discounts and refunds?
- Inclusive or exclusive date bounds? *Always* propose half-open `[start, end)`.
- Which time zone defines "a day"? UTC, store-local, or customer-local? What about DST?
  (Fixtures 13 and 14.)
- Is "7 days later" a calendar date or 168 hours? (Fixture 21.)

**NULLs, ties and duplicates**

- NULL keys: guests, unknown region. Excluded, grouped as "unknown", or an error?
- Ties: should the output be deterministic? Which tie-breaker: latest id, alphabetical, or
  return all tied rows?
- Duplicates: exact duplicate deliveries vs legitimate repeats vs conflicting versions. Do we
  de-duplicate, and on what key?

**Output**

- Column names and types, rounding, how to show zero vs NULL, and whether order matters.

**Scale and environment**

- How big are the tables? Which indexes, partitions or distribution keys exist?
- How often does this run? Incremental or full refresh? How late can data arrive?

---

## 3. Explaining grain and assumptions (templates)

- "The fact table is at transaction grain; the question is at customer-day grain. I'll collapse
  to customer-day **before** any window function, otherwise duplicates break the island logic."
- "Refunds are one-to-many with transactions, and so are lines. Joining both to the header
  multiplies rows. I'll aggregate each child table to transaction grain first, then join."
- "I'm assuming business dates are UTC calendar dates. If the business wants store-local dates,
  I'd convert with `AT TIME ZONE stores.timezone`, which changes the result for late-evening
  purchases."
- "Tie policy: when two transactions share the latest timestamp I'll pick the higher
  `transaction_id`. I'd confirm that with the business, but the output must be deterministic
  either way."

---

## 4. Handling the classic traps

| trap | what goes wrong | the habit |
|---|---|---|
| NULL | `NOT IN (subquery with NULL)` returns nothing; `=` never matches NULL; `COUNT(col)` skips NULLs | `NOT EXISTS`; `IS DISTINCT FROM`; `COALESCE` only in the output layer |
| Ties | `ROW_NUMBER` picks arbitrarily; `LIMIT 3` cuts a tie in half | add a tie-breaker to every `ORDER BY` in windows; choose RANK/DENSE_RANK consciously |
| Duplicates | fan-out joins inflate SUMs; repeated deliveries double-count | aggregate before joining; de-duplicate on an explicit key; compare `count(*)` vs `count(DISTINCT key)` |
| Time zones | `ts::date` depends on session time zone; DST days have 23/25 hours | `(ts AT TIME ZONE 'UTC')::date`; never cast the indexed column in WHERE; half-open timestamp ranges |
| Boundaries | `BETWEEN` includes the end; `valid_to` inclusive double-matches at a change instant | half-open everywhere; test the exact boundary instant |
| Empty input | division by zero; `MAX` over nothing is NULL; Python `max([])` raises | `NULLIF(x, 0)`; explicit defaults; tests for empty input |
| Order of events | ingestion time ≠ business time ≠ commit order | order CDC by source sequence/LSN; use event time for business logic and ingestion time for watermarks |

---

## 5. Verbalising complexity

**SQL** (talk in terms of the plan, not big-O alone):

- "This is one scan of transactions, a hash aggregate to customer-day, then a sort per customer
  for the window: roughly O(n log n), dominated by the sort. With an index on
  `(customer_id, transaction_ts)` the rows arrive pre-sorted."
- "The anti-join is a hash anti-join: linear in both sides if the hash table fits in `work_mem`."
- "The correlated subquery runs once per outer row. With an index it's a nested loop of index
  lookups, which is fine for 1,000 rows and terrible for 100 million."

**Python:** state time and **space**, and whether it streams:

- "Single pass, O(n) time, O(k) memory for k distinct customers. It works on a generator, so a
  50 GB file is fine as long as the number of customers fits in memory."
- "Heap of size k: O(n log k) instead of sorting everything in O(n log n)."

---

## 6. Ask about indexes and physical design

Ask: "What indexes exist on `transactions`? Is it partitioned? Distributed on which key?" Then:

- Equality columns first, then range, then ORDER BY columns in a composite index (SQL-053).
- Sargable predicates: `ts >= '2025-03-01' AND ts < '2025-03-02'`, not `ts::date = '2025-03-01'` (SQL-052).
- Partition pruning needs predicates on the partition key, in the same type, without functions
  around the column (SQL-059).
- Warehouses (Synapse/Snowflake/BigQuery): distribution/cluster keys, skew (SQL-054), and
  pre-aggregated summary tables.

---

## 7. Validating production correctness (always mention at least two)

- **Reconciliation:** row counts and sums source vs target per day/partition (SQL-044, PY-049).
- **Invariants:** header total = sum of lines, refunds ≤ sale, no overlapping SCD2 ranges
  (SQL-032), one current row per key.
- **Uniqueness:** `count(*) = count(DISTINCT business_key)` in the current-state table; unique
  constraints where possible (SQL-060).
- **Freshness and lateness:** watermark lag, p95 ingestion delay (SQL-055), late-arriving impact
  per day (SQL-043).
- **Idempotency test:** run the same batch twice and assert an identical final state (SQL-048, PY-032).
- **Golden fixtures:** a handful of hand-built cases (like this lab's fixture customers 1–99)
  checked on every deploy.

---

## 8. "What would change at 500 million rows?" (ready-made answers)

| exercise family | answer outline |
|---|---|
| Aggregations (SQL-001…010) | Pre-aggregate incrementally into daily summaries; partition by date; hash-distribute on the grouping key; beware skewed keys (guest NULL, enterprise account). |
| Windows / top-N (SQL-011…020) | Window sorts spill to disk: reduce rows first, give `work_mem`, use indexes that provide order; DISTINCT ON / LATERAL top-N with an index beats a full ROW_NUMBER. |
| Gaps & islands (SQL-021…030) | Work at customer-day grain from a summary table; recompute only affected customers with a lookback window for late days; partition-local windows in distributed engines. |
| SCD2 / modelling (SQL-031…040) | Range joins are expensive: use surrogate keys assigned at load time (fact stores `customer_sk`), or sort-merge on business key + effective_from; validate non-overlap with exclusion constraints. |
| CDC / incremental (SQL-041…050) | Never full-scan the change log: watermark + overlap, idempotent MERGE/upsert, compaction of the change log, partition-wise processing, exactly-once via checkpoints + idempotent sinks. |
| Performance (SQL-051…060) | Read the plan (`EXPLAIN (ANALYZE, BUFFERS)`); fix estimates (ANALYZE, extended statistics); partition pruning; covering indexes; avoid functions on indexed columns. |
| Python ETL (PY-021…030) | Stream, don't load: generators, chunked I/O, external sort, bounded dicts; parallelise by partition; checkpoint progress; atomic publish. |
| Streaming (PY-031…040) | Keyed state, watermarks, allowed lateness, idempotent sinks, replay from offsets, backpressure. |
| DB integration (PY-041…050) | Server-side cursors, `COPY` for bulk loads, batch upserts, keyset pagination, connection pools, statement timeouts, retries with idempotency keys. |

---

## 9. Language fluency: things to type without thinking

- SQL: CTE chains; `ROW_NUMBER() OVER (PARTITION BY … ORDER BY … , tie_breaker)`; `LAG/LEAD`;
  `SUM(...) OVER (... ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`; `FILTER (WHERE …)`;
  `DISTINCT ON`; `generate_series`; `LEFT JOIN … IS NULL` anti-join; `NOT EXISTS`;
  `INSERT … ON CONFLICT … DO UPDATE … WHERE`; `percentile_cont(0.95) WITHIN GROUP (ORDER BY …)`;
  `jsonb_array_elements`; `tstzrange` and `&&`.
- Python: `collections.defaultdict/Counter/deque/OrderedDict`, `heapq.nlargest/merge`,
  `itertools.islice/groupby/chain`, `bisect`, `csv.DictReader`, `json.loads` with try/except,
  `decimal.Decimal`, `datetime.fromisoformat` + `zoneinfo.ZoneInfo`, `dataclasses`, context
  managers, generators, `tempfile` + `os.replace`, `asyncio.Semaphore`, psycopg `cursor.execute(query, params)`.

The 8-week plan starts every session with a 10-minute typing warm-up of exactly these patterns.
