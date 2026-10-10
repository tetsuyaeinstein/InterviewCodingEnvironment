# 8-week plan: senior / lead data engineer coding interviews

**Time budget:** 45–90 minutes on most weekdays, plus one 2–3 hour weekend block.

Every week mixes SQL and Python. Senior-level discussion (scale, correctness, trade-offs) starts
in week 1, not at the end.

## How every session works

1. **10-minute typing warm-up (no copy/paste, no autocomplete crutches).** Open a scratch
   file (`study/session_notes/warmup.sql` / `.py`) and retype the week's warm-up patterns from
   memory. Speed comes from not having to think about syntax.
2. **Exercises:** `python -m lab show <ID>` → type into the practice file → `python -m lab check <ID>`
   (Ctrl+Shift+B in VS Code checks the current file). Time yourself against the "Time" column of
   `python -m lab list`.
3. **Only after it passes,** run `python -m lab solution <ID> --explain` (and `--alt`). Read the
   follow-up questions and answer one aloud.
4. **Log it:** `python -m lab progress log <ID> --minutes <m> --confidence <1-5> --notes "..."`.
5. **Start each later session** with `python -m lab session --minutes 45 --mix sql,python` to pull
   due reviews before new work.

Weekend blocks contain a **timed mock**: 45 minutes, closed notes, talking aloud (record yourself
if you can). Follow it with 30 minutes of error review.

Checkpoint rule: at the end of each week, at least 80% of that week's exercises should be
`passed` in `python -m lab progress`. If not, the first two days of the next week are review days
(use `lab session`).

---

## Week 1: SQL foundations, joins, GROUP BY · Python dict/list/set basics

**Warm-up:**

- `LEFT JOIN` + `GROUP BY` + `COALESCE(SUM(...), 0)`
- `NOT EXISTS` anti-join
- `COUNT(*) FILTER (WHERE ...)`
- Python: `defaultdict(Decimal)`, `dict.setdefault`, set-based dedup loop, `sorted(..., key=lambda r: (-r[1], r[0]))`

| day | SQL | Python | senior discussion |
|---|---|---|---|
| Mon | SQL-001, SQL-002 | PY-001 | "Why does an inner join lose customers? What is the grain of each table?" |
| Tue | SQL-003, SQL-006 | PY-002 | NULL semantics of `NOT IN`; Decimal vs float money |
| Wed | SQL-005 | PY-003, PY-009 | fan-out joins; deterministic tie-breaking |
| Thu | SQL-008, SQL-009 | PY-004 | RANK vs DENSE_RANK; division-by-zero policy |
| Fri | SQL-010, SQL-007 | PY-008 | anti-join strategies; hash join vs sort-merge join |
| Weekend | SQL-004 | PY-005, PY-006, PY-007, PY-010 | **Mock 1 (45 min):** SQL-005 + PY-003 cold; then review the PostgreSQL/T-SQL date rows in `SQL_POSTGRES_VS_SQLSERVER.md` |

**Checkpoint:** SQL-001…010 and PY-001…010 passed. Explain aloud the difference between
WHERE-filtering and ON-filtering a LEFT JOIN.

## Week 2: SQL windows, CTEs, top-N, running totals · Python heaps, sliding windows, searching

**Warm-up:**

- `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ..., id DESC)` and the filter
- `DISTINCT ON`
- `SUM() OVER (... ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`
- `LAG`
- Python: `heapq.nlargest`, a two-pointer window skeleton, `bisect_left`

| day | SQL | Python | senior discussion |
|---|---|---|---|
| Mon | SQL-011, SQL-012 | PY-011 | top-1 per group: ROW_NUMBER vs DISTINCT ON vs LATERAL |
| Tue | SQL-013 | PY-012, PY-016 | rolling windows over *dates* vs *rows*; binary search invariants |
| Wed | SQL-014, SQL-015 | PY-013 | running totals at scale; safe percentages |
| Thu | SQL-016, SQL-017 | PY-014, PY-015 | NTILE tie behaviour; heap vs sort complexity |
| Fri | SQL-018, SQL-019 | PY-017, PY-018 | top-N with ties; k-way merge of sorted streams; LRU design |
| Weekend | SQL-020 | PY-019 | **Mock 2:** SQL-011 + SQL-018 + PY-014 in 45 min; review all failed checks from weeks 1–2 |

**Checkpoint:** you can write ROW_NUMBER/LAG/running SUM without looking anything up.

## Week 3: gaps & islands, calendars, time zones, temporal joins · Python iterators and file streaming

**Warm-up:**

- `day - ROW_NUMBER()::int` island key
- `generate_series` calendar
- `(ts AT TIME ZONE 'UTC')::date`
- half-open range join
- Python: generator with `yield`, `itertools.islice`, `csv.DictReader` over a file object, `zoneinfo`

| day | SQL | Python | senior discussion |
|---|---|---|---|
| Mon | SQL-021 | PY-020 | 500M-row version of streaks (read the SQL-021 explanation, part c) |
| Tue | SQL-022, SQL-023 | PY-021 | streaming CSV without loading; deterministic longest-streak ties |
| Wed | SQL-024, SQL-025 | PY-022 | aggregate before islands; retention definitions (date vs 168h) |
| Thu | SQL-026, SQL-027 | PY-023 | sessionization; interval merging without double counting |
| Fri | SQL-028, SQL-029 | PY-027 | point-in-time joins; ALL vs ANY semantics; partition paths |
| Weekend | SQL-030 | PY-029 | **Mock 3:** SQL-024 + PY-022 + explain DST handling for SQL-035/PY-006 aloud |

**Checkpoint:** explain why fixture customer 13 is a UTC streak but not a store-local one.

## Week 4: dimensional modelling, SCD2, fact grain, cohorts · Python clean ETL design and validation

**Warm-up:**

- SCD2 point-in-time join `ts >= effective_from AND ts < effective_to`
- overlap self-join `a.from < b.to AND b.from < a.to`
- cohort `date_trunc('month', first_purchase)`
- Python: dataclass for errors, validation loop collecting errors, `tempfile` + `os.replace`

| day | SQL | Python | senior discussion |
|---|---|---|---|
| Mon | SQL-031 | PY-007 (review), PY-025 | historical vs current attributes; data-quality metrics |
| Tue | SQL-032, SQL-033 | PY-026 | SCD2 integrity checks; atomic publish |
| Wed | SQL-034, SQL-035 | PY-024 | snapshot conventions (end of day); ISO weeks in a fixed zone |
| Thu | SQL-036, SQL-037 | PY-028 | factless facts; market-basket pairs at scale |
| Fri | SQL-038, SQL-039 | PY-045 | cohort retention; injected dependencies in ETL |
| Weekend | SQL-040 | PY-036 | **Mock 4:** SQL-031 + SQL-038 + PY-036 (SCD2 in Python), then whiteboard a star schema for kiosk sales |

**Checkpoint:** explain the grain of `fact_sales_partitioned`, `customer_daily_activity` and
`daily_store_snapshot`, and which kind of fact each is.

## Week 5: CDC, incremental ingest, late arrivals, idempotency, reconciliation · Python checkpoints and retries

**Warm-up:**

- `INSERT ... ON CONFLICT (...) DO UPDATE SET ... WHERE EXCLUDED.lsn > t.lsn`
- `DISTINCT ON (key) ORDER BY key, lsn DESC`
- `FULL OUTER JOIN ... IS DISTINCT FROM`
- Python: retry loop with backoff and an injected sleeper; a checkpoint file

| day | SQL | Python | senior discussion |
|---|---|---|---|
| Mon | SQL-041, SQL-042 | PY-030 | LSN vs ingestion order; overlap windows |
| Tue | SQL-043, SQL-044 | PY-031 | late-arriving impact; reconciliation reports |
| Wed | SQL-045, SQL-046 | PY-032, PY-033 | hash fingerprints; idempotent consumers; backoff |
| Thu | SQL-047, SQL-048 | PY-034 | tombstones; exactly-once = at-least-once + idempotency |
| Fri | SQL-049, SQL-050 | PY-035, PY-037 | sequence anomalies; safe watermarks; event-time windows |
| Weekend | review | PY-039, PY-040 | **Mock 5:** design + code an incremental CDC load (SQL-046/047) in 45 min, then answer "a batch was processed twice; prove nothing changed" |

**Checkpoint:** explain idempotency at three levels: record, batch, job.

## Week 6: PostgreSQL EXPLAIN, indexes, plans, skew · Python bounded memory, concurrency, integration

**Warm-up:**

- `EXPLAIN (ANALYZE, BUFFERS)`
- `CREATE INDEX ... (a, b) INCLUDE (c) WHERE ...`
- `percentile_cont(0.95) WITHIN GROUP (ORDER BY x)`
- `jsonb_array_elements`
- Python: `asyncio.Semaphore`, `queue.Queue(maxsize=...)`, a psycopg server-side cursor

| day | SQL | Python | senior discussion |
|---|---|---|---|
| Mon | SQL-051, SQL-052 | PY-041, PY-042 | reading plans; sargability; streaming result sets |
| Tue | SQL-053 | PY-043, PY-044 | composite index order; batch upserts; keyset pagination |
| Wed | SQL-054, SQL-055 | PY-038 | skew and parallelism; percentiles; backpressure |
| Thu | SQL-056, SQL-057, SQL-058 | PY-046, PY-047 | jsonb typing; API pagination; rate limits |
| Fri | SQL-059, SQL-060 | PY-048 | partition pruning; unique constraints as dedup; asyncio limits |
| Weekend | review | PY-049, PY-050 | **Mock 6:** PY-050 end-to-end (60 min), then present its trade-offs for 10 minutes |

**Checkpoint:** given any plan from SQL-051/053/059, name the costliest node and say why.

## Week 7: 500M-row system-design follow-ups, partitioning, correctness · timed mixed problems

Each day: two timed problems (≤ 25 min each), with no hints. Then 20 minutes answering that
exercise's "at 500M rows" follow-up aloud.

| day | timed set | design prompt (10 min, talk aloud) |
|---|---|---|
| Mon | SQL-021, PY-020 | streaks over 500M transactions with 10-day late data |
| Tue | SQL-027, PY-013 | kiosk uptime SLA reporting for 1M devices |
| Wed | SQL-044, PY-028 | nightly reconciliation of a 2B-row warehouse table |
| Thu | SQL-047, PY-040 | CDC pipeline with deletes, replays and backfills |
| Fri | SQL-059, PY-029 | partitioning + retention for 5 years of sales; sorting a 200 GB file |
| Weekend | **Mock 7:** 2 × 45 min back to back (SQL-038 + PY-024; SQL-050 + PY-034) | write a one-page design: "daily customer activity summary, incremental, idempotent, monitored" |

**Checkpoint:** every timed problem passes within its listed interview time.

## Week 8: mock interviews, error review, explaining trade-offs aloud

| day | activity |
|---|---|
| Mon | **Mock A (60 min):** SQL-023 + SQL-040 + follow-ups. Review: re-solve anything you missed tomorrow. |
| Tue | `lab session --minutes 60` (due reviews only); re-explain three explanations from memory |
| Wed | **Mock B (60 min):** PY-031 + PY-047 + design discussion (retries, idempotency keys) |
| Thu | weak-area day: filter `lab list --tag <tag>` for your lowest-confidence tags; redo two |
| Fri | **Mock C (45 min):** a random hard SQL (`lab list sql --difficulty hard`) + a random hard Python |
| Weekend | **Final mock (90 min):** two coding rounds plus one system-design conversation; then `lab check-all` and a final progress review |

Interview-day checklist: read `INTERVIEW_PLAYBOOK.md` §1–§4 once, warm up for 10 minutes with
SQL-011 and PY-012 typed from memory, and remember: clarify → example → plan → code → test →
scale.
