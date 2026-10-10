# Claude Code Build Prompt — Senior Data Engineer Interview Lab

> **How to use this file:** Open a new empty folder in VS Code, open Claude Code in that folder, and say: **"Implement the project described in this Markdown file. Treat it as the full specification. Start by creating a working foundation, then implement the question banks, reference answers, fixtures, tests, and developer workflow. Actually run and verify the project before calling it done."** Attach or reference this file by path.
>
> You are Claude Code, working as a senior engineer and instructor. **Build the runnable repository**, not merely a design document. Work in the current workspace. Do not introduce a cloud deployment, frontend, web service, commercial learning platform, or elaborate UI unless essential. This is a **local, keyboard-first VS Code practice environment**.

---

## 1. My background, learning goal, and success criteria

I am an experienced BI/data engineer preparing for demanding **Senior / Lead Data Engineer** interviews. My main production background is SQL Server, Azure Synapse, ADF, ETL/ELT, dimensional modeling, Python, APIs, Docker, and data warehouse design. I want to develop **fast, reliable muscle memory** for writing SQL and Python from scratch. I will type solutions into empty practice files, run them immediately, see accurate test feedback, revise, and optionally compare with multiple reference solutions.

Design for **daily repeated practice**, not a one-time tutorial. Cover entry-level syntax to genuinely challenging senior-level exercises. Questions should test problem-solving, edge cases, correctness, scalability, and production trade-offs. Favor financial transactions, kiosks, retail products, subscriptions, CDC, late-arriving events, reconciliation, and data warehouse analytics as business scenarios. All generated datasets must be fictitious and contain no company data or personal information.

**Acceptance criteria:**

1. `docker compose up -d` starts a healthy PostgreSQL database locally.
2. A fresh clone can be installed and seeded using documented commands; no manual schema creation.
3. VS Code can connect to PostgreSQL; I can edit and execute individual `.sql` files.
4. I can open a SQL question **without seeing its answer**, type a query in a dedicated `.sql` practice file, and run/check it with one command.
5. I can open a Python question **without seeing its answer**, implement a function in a dedicated `.py` file, and run targeted tests with one command.
6. Reference solutions and explanations are in different folders from practice files. At least 15 SQL and 15 Python questions offer **two genuinely different correct approaches** where useful, with trade-offs.
7. Automated validators check **correctness**, not mere successful execution; they report failures with understandable expected/actual differences and edge cases.
8. There is a browsable, numbered question bank for both languages, tagged by topic, difficulty, and expected interview time.
9. There is a convenient way to reset only my attempts, optionally preserve history, reseed the database, and switch between small and larger datasets.
10. All commands advertised by the README **actually run**, the seed is reproducible, and a representative subset of exercises has been executed successfully by you.

## 2. Technology and boundaries

- **PostgreSQL 17** Docker image (stable, pinned major version), Docker Compose v2, named volume, health check. Expose `5433:5432` by default to avoid colliding with local PostgreSQL.
- Python **3.12+**, virtual environment `.venv`, `pytest`, `psycopg` 3, `python-dotenv` if useful; standard library for most coding exercises. Use `pyproject.toml` for project metadata/dependencies and include lock strategy if applicable.
- Scripts: Python standard library + `psycopg`; avoid requiring `make` on Windows. Since I use VS Code and may be on Windows, create **cross-platform Python commands** (`python -m lab ...`) as the canonical interface. Add a `Makefile` only as optional aliases for macOS/Linux. Explain PowerShell usage.
- VS Code recommendations/settings: Python, Pylance, Docker, a PostgreSQL-capable SQL extension (e.g., SQLTools + PostgreSQL driver), default Python interpreter `.venv`; useful `tasks.json` for common commands. Never assume a VS Code extension is automatically installed.
- No external APIs, paid accounts, hosted databases, or real secrets. `.env.example` should contain clearly marked **local-development-only** credentials; `.env` should be gitignored.
- Use a deterministic timezone (UTC) for stored timestamp data. Define business-day boundaries explicitly for date problems. Seeded timestamps should not depend on `CURRENT_DATE` or runtime wall-clock time.
- Python and SQL tasks must be executable **offline** after setup.
- Keep implementation simple, understandable, and extensible. Avoid a heavyweight custom grader, embedded editor, Jupyter-only approach, or over-engineering.

## 3. Required repository layout

Use the following layout, adapting only where there's a clear technical reason. Preserve the separation of **question / attempt / solution / validation**.

```text
data-engineering-interview-lab/
├── README.md
├── QUICKSTART.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── pyproject.toml
├── Makefile                         # optional aliases; CLI is canonical
├── .vscode/
│   ├── extensions.json
│   ├── settings.json
│   └── tasks.json
├── lab/                             # cross-platform CLI and validation engine
│   ├── __main__.py
│   ├── cli.py
│   ├── db.py
│   ├── sql_runner.py
│   ├── sql_validator.py
│   ├── exercise_catalog.py
│   └── progress.py
├── database/
│   ├── migrations/                  # numbered idempotent local schema changes
│   │   ├── 001_core.sql
│   │   ├── 002_retail.sql
│   │   ├── 003_cdc_and_warehouse.sql
│   │   └── 004_indexes.sql
│   ├── seed/
│   │   ├── seed_small.py
│   │   ├── seed_medium.py
│   │   ├── seed_large.py
│   │   └── fixtures/                 # explicit known edge-case data
│   └── DATA_DICTIONARY.md
├── sql/
│   ├── QUESTION_BANK.md             # ALL SQL questions; NO answers
│   ├── questions/
│   │   ├── 01_foundations/
│   │   ├── 02_aggregates_windows/
│   │   ├── 03_gaps_islands_time/
│   │   ├── 04_dimensional_modeling/
│   │   ├── 05_cdc_data_quality/
│   │   └── 06_postgres_performance/
│   ├── practice/                    # files I EDIT; questions only, no solutions
│   │   └── <same topic folders>/SQL-001.sql ... SQL-060.sql
│   ├── solutions/                   # files I open AFTER I try
│   │   └── <same topic folders>/SQL-001.sql, SQL-001_alt.sql, ...
│   ├── explanations/                # explanations, variations, complexity, pitfalls
│   │   └── <same topic folders>/SQL-001.md ...
│   └── checks/                      # independent expected-result fixtures/rubrics
│       ├── catalog.yaml             # or JSON; metadata & validation mode
│       ├── expected/
│       └── adversarial/
├── python/
│   ├── QUESTION_BANK.md             # ALL Python questions; NO answers
│   ├── questions/
│   │   ├── 01_fundamentals/
│   │   ├── 02_algorithms/
│   │   ├── 03_etl_file_processing/
│   │   ├── 04_streaming_reliability/
│   │   └── 05_database_integrations/
│   ├── practice/
│   │   └── <same topic folders>/PY-001.py ... PY-050.py
│   ├── solutions/
│   │   └── <same topic folders>/PY-001.py, PY-001_alt.py, ...
│   ├── explanations/
│   │   └── <same topic folders>/PY-001.md ...
│   └── tests/
│       ├── conftest.py
│       ├── test_py_001.py ...
│       └── fixtures/
├── study/
│   ├── 8_WEEK_PLAN.md
│   ├── INTERVIEW_PLAYBOOK.md
│   ├── SQL_POSTGRES_VS_SQLSERVER.md
│   ├── COMMON_PITFALLS.md
│   ├── PERFORMANCE_CHECKLIST.md
│   ├── PROGRESS.md
│   └── session_notes/               # gitignored personal notes optionally
└── tests/                           # infrastructure / tool self-tests
    ├── test_seed_integrity.py
    ├── test_cli.py
    └── test_sql_validator.py
```

### File format convention

For every question create:

- `sql/questions/<topic>/SQL-NNN.md`: business scenario, source tables, grain, requirements, expected output column names/types, ordering semantics, sample input/output, pitfalls, constraints, hint levels 1–3 **without the solution**. For practice mode, hints should be accessible separately/on request, not shown by default.
- `sql/practice/<topic>/SQL-NNN.sql`: only comments identifying the question, table names, link to question, and a **clearly empty area** for typing the answer. Do not include working query syntax or reveal the technique. Empty attempt should fail validation as **not attempted**.
- `sql/solutions/<topic>/SQL-NNN.sql`: working PostgreSQL solution; `_alt.sql` when another genuinely useful strategy exists.
- `sql/explanations/<topic>/SQL-NNN.md`: plain-English logic, window/joins explanation, why edge cases matter, rough time/space or query-plan trade-offs, indexes if relevant, production considerations, and optional SQL Server / Azure Synapse dialect notes.
- `python/questions/<topic>/PY-NNN.md`: clear function contract (input/output types), examples, assumptions, corner cases, time/space expectations and constraints, NO reference code.
- `python/practice/<topic>/PY-NNN.py`: a callable stub with the required function signature, docstring and `raise NotImplementedError` only. No embedded implementation or algorithmic hints. For problems requiring a class, include the public interface with unimplemented methods.
- `python/solutions/<topic>/PY-NNN.py` and `_alt.py` as appropriate. **Unit tests must import the practice implementation by default**, not the reference answer.
- `python/explanations/<topic>/PY-NNN.md`: compare approaches and big-O; include scale-up questions (millions of records, streaming, late data, memory constraints).

Question banks are indexes, not substitutes for these individual files. No placeholder questions or repetitive boilerplate passed off as solved exercises.

## 4. Synthetic PostgreSQL database and realistic fixtures

Build a coherent fictional retail/financial transaction domain. Prefer referentially meaningful records that support the entire question bank. Create data dictionary entries that identify primary keys, natural/business keys, foreign keys, date semantics, uniqueness, and whether a table represents current state, immutable history, events, or a snapshot.

### Core tables (adjust names modestly if needed; questions must use actual names)

1. `customers` — customer_id, registration timestamp, segment, home_region, status.
2. `stores` — store_id, region, store type.
3. `products` — product_id, category_id, product name, category, standard price; optionally `product_categories`.
4. `transactions` — transaction_id, customer_id, store_id, transaction_ts (timestamptz), gross_amount, transaction_status, payment_method, ingested_at. Include repeat transactions for a customer on the same date.
5. `transaction_items` — transaction_id, line_number, product_id, quantity, unit_price, discounts; order line grain.
6. `refunds` — refund_id, original transaction_id, refund timestamp, refund amount.
7. `customer_events` — event_id, customer_id, event_ts, event_type, session_id (nullable), payload JSONB.
8. `store_product_availability` — store_id, product_id, valid_from, valid_to (exclusive), available boolean; intentionally include changes throughout the day, but document overlap rules.
9. `product_price_history` — product_id, valid_from, valid_to (exclusive), price.
10. `dim_customer_scd2` — surrogate dimension key, business customer_id, effective_from, effective_to (exclusive), region, segment, is_current.
11. `customer_daily_activity` — customer_id, activity_date, transaction_count, daily_spend (materialized or populated summary).
12. `account_ledger` — account_id, entry_id, transaction_id, posting_ts, signed_amount, entry_type; use a precise money type.
13. `device_status_events` — kiosk/device_id, event_ts, state (up/down), event_id.
14. `source_transactions` and `target_transactions` — deliberately different snapshots for reconciliation.
15. `cdc_transaction_events` — source_system, business_key, operation (I/U/D), sequence/LSN, commit_ts, ingested_at, payload; ties and out-of-order arrival cases.
16. `pipeline_runs` and `pipeline_watermarks` — run_id, source_system, start/end, status, last committed offset/watermark.
17. `employees` — employee_id, manager_id, department, salary, hire_date (for hierarchy, rank, and recursive CTE exercises).
18. `subscriptions` — customer_id, plan, start_date, end_date (exclusive), status; for cohorts and retention.
19. `daily_store_snapshot` — daily store/product counts or other periodic snapshot.
20. `event_ingestion_log` — raw event id, event_ts, ingest_ts, ingestion_status and error reason for quality/lag analysis.

### Deterministic seed profiles

- `small`: roughly **10k–30k transactions**, enough to run quickly and inspect manually. Include hand-curated explicit fixtures as well as seeded pseudo-random generation.
- `medium`: roughly **250k transactions** for query plan and indexing exercises.
- `large`: roughly **1M–2M transactions**, opt-in only and with warning about disk/CPU/time. **DO NOT generate 500 million rows by default**; discuss that scale conceptually in the questions.
- Repeatable seed: the exact same command + seed version gives the same business data, regardless of run date. Use stable timestamps, IDs, RNG seed, and transaction isolation where applicable. Re-seeding should be idempotent or a clearly documented full reset.
- Add indexes as appropriate but allow performance exercises to compare index alternatives in isolated schemas/transactions; ensure no exercise permanently damages shared tables.

### Mandatory adversarial data

Include explicit customers who purchase on exactly 4, exactly 5, 6+, and disjoint 5-day streaks; two purchases on the same day; five days crossing month/year boundary; skipped days; no transactions; leap day and timezone/DST differences (with exact timezone interpretation specified). Include duplicate rows/IDs where raw events permit them, legitimate refunds, cancelled/pending transactions, `NULL` fields, equal timestamps, late-arriving events spanning at least 7 days, multiple CDC revisions and deletes, SCD2 effective-date boundaries, missing and changed source/target rows, out-of-order device status, and product availability changes during a transaction day. Ensure fixtures support **deterministic expected results**, not just plausible random data.

Provide the actual seed counts and fixture descriptions in `database/DATA_DICTIONARY.md`.

## 5. SQL exercise bank: implement ALL 60 questions

Create the full 60-question SQL bank with unique IDs, independent specifications, actual working reference answers and executable checks. Order by difficulty within each topic. The following are **problem requirements**, not vague suggestions. Use actual table/column names from your schema and precise output contracts.

### 01 — Foundations: SQL-001 through SQL-010

| ID | Interview question |
|---|---|
| SQL-001 | Total completed transaction spend per customer, including customers with zero completed transactions. |
| SQL-002 | Daily completed transaction count and gross amount per store for a specified date range. |
| SQL-003 | Customers with no transactions in the last 90 days relative to a **fixed supplied anchor date**. |
| SQL-004 | Find transaction IDs appearing more than once in the raw source or event stream; distinguish business-key duplicates from repeated event deliveries. |
| SQL-005 | Net spend after refunds, correctly handling multiple refunds and preventing fan-out joins. |
| SQL-006 | Conditional aggregation: counts and sums by approved, pending, cancelled status in one row per store. |
| SQL-007 | Detect orphan transaction items referencing missing products or transactions (use a deliberately untrusted staging table if FK constraints block these). |
| SQL-008 | Highest-revenue product categories with correct ties and quantity × unit price accounting. |
| SQL-009 | Average transaction value by customer segment, handling customers with no spend and division-by-zero policy. |
| SQL-010 | Return all customers who bought product A but never product B during a fixed date range. |

### 02 — Aggregates, CTEs, windows: SQL-011 through SQL-020

| ID | Interview question |
|---|---|
| SQL-011 | Latest completed transaction per customer; deterministic tie-breaking. |
| SQL-012 | Second-largest **distinct** transaction amount per store and explicit treatment of ties. |
| SQL-013 | Seven-calendar-day rolling store revenue, including dates with zero transactions. |
| SQL-014 | Running daily spending total per customer, ordered by business date. |
| SQL-015 | Month-over-month revenue growth, showing months with zero sales and safe percentage calculation. |
| SQL-016 | First purchase, latest purchase, and days from registration to first purchase. |
| SQL-017 | Assign customers to spending quartiles, documenting tie behavior. |
| SQL-018 | Top three products in each region by revenue; define how ties are handled. |
| SQL-019 | Each product's percentage of total store revenue over a period without double counting. |
| SQL-020 | Reconstruct ledger account balances using cumulative signed entries and flag negative balances. |

### 03 — Gaps, islands, dates, and time: SQL-021 through SQL-030

| ID | Interview question |
|---|---|
| SQL-021 | Find customers who made at least one **completed purchase on 5 consecutive calendar days** from a 500-million-row conceptual transaction fact; implement correctly on seeded subset, explain scaling. |
| SQL-022 | Return **all** purchase streaks with inclusive start, end, and length (no overlaps). |
| SQL-023 | Find each customer's longest consecutive purchasing streak, including deterministic handling of equal-length streaks. |
| SQL-024 | Five consecutive days where **each day's total completed spend exceeds $100**; aggregate before grouping streaks. |
| SQL-025 | Retention: customers who purchased on day 0 and exactly day 7 after first purchase; explain distinction from any time within first week. |
| SQL-026 | Sessionize customer events into sessions separated by more than 30 minutes of inactivity. |
| SQL-027 | Collapse adjacent/overlapping kiosk downtime intervals and calculate total downtime without double counting. |
| SQL-028 | Point-in-time join a transaction item to the effective product price **at transaction timestamp**, using half-open time intervals. |
| SQL-029 | Identify transactions for which **all** requested products in a selected set were available at that transaction timestamp; add ANY semantics as alternate. |
| SQL-030 | Detect missing scheduled daily events or unusually long reporting gaps per device. |

**For SQL-021, include three separate writeups:** (a) a window-function gaps-and-islands SQL solution, (b) an alternative using `LAG` and cumulative grouping or another genuinely different method, and (c) a performance discussion for **500 million source transactions**, including customer-day deduplication, possible `(customer_id, transaction_ts)` or expression indexes, EXPLAIN, warehouse summaries, partitioning, and handling late-arriving events. Show that duplicate same-day purchases do NOT create false streaks. Use PostgreSQL date arithmetic, not SQL Server `DATEADD` in executable files.

### 04 — Dimensional modeling and analytics: SQL-031 through SQL-040

| ID | Interview question |
|---|---|
| SQL-031 | Point-in-time fact-to-SCD2 customer join without using current dimension attributes for historical records. |
| SQL-032 | Detect overlapping SCD2 validity ranges and duplicate current rows. |
| SQL-033 | Identify facts missing a matching historical dimension version; include effective-date boundary behavior. |
| SQL-034 | Generate a daily account-balance snapshot from a posting ledger; clarify beginning/end-of-day convention. |
| SQL-035 | Weekly active customers based on ISO weeks and a fixed timezone definition. |
| SQL-036 | Produce a factless daily product-availability snapshot from interval history, documenting whether ANY-time or end-of-day status counts. |
| SQL-037 | Products frequently purchased together (unordered item pairs, no self-pair, no double counting). |
| SQL-038 | Monthly first-purchase cohorts and month-1/month-2 repeat purchase retention. |
| SQL-039 | Distinct purchasing customers grouped by historical region using SCD2 and correct transaction grain. |
| SQL-040 | Net recognized sales with returns and partial refunds; explicitly avoid multiplying values through joins. |

### 05 — CDC, incremental processing, reconciliation, data quality: SQL-041 through SQL-050

| ID | Interview question |
|---|---|
| SQL-041 | Choose latest version of each CDC business key using source sequence/LSN rather than ingestion timestamp. |
| SQL-042 | Find rows eligible for watermark-based incremental ingestion with an overlap window; explain how idempotency prevents duplicates. |
| SQL-043 | Identify source transactions arriving after the reporting watermark and quantify late-arriving impact by business date. |
| SQL-044 | Full source/target reconciliation: missing in target, extra in target, same key but differing business values. |
| SQL-045 | Null-safe, unambiguous row fingerprint (avoid naive ambiguous string concatenation); explain hashing risks. |
| SQL-046 | Apply incremental upserts using PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`; run **in an isolated rollback transaction** or ephemeral per-exercise schema. |
| SQL-047 | Apply CDC tombstones/deletes without accidentally resurrecting an older record. |
| SQL-048 | Demonstrate idempotent incremental processing: running the same logical batch twice yields unchanged final state. |
| SQL-049 | Compare source commit order vs ingestion order; identify stale updates and sequence tie policies. |
| SQL-050 | Compute safe committed per-source watermark after mixed successful/failed pipeline batches. |

### 06 — PostgreSQL optimization and advanced syntax: SQL-051 through SQL-060

| ID | Interview question |
|---|---|
| SQL-051 | Use `EXPLAIN (ANALYZE, BUFFERS)` to evaluate a selective customer/date query; interpret scan, sort, rows and buffers. |
| SQL-052 | Rewrite a filter that unnecessarily applies a date cast to indexed timestamp columns into a half-open, sargable range. |
| SQL-053 | Compare composite index column order for equality + range + `ORDER BY` filtering. |
| SQL-054 | Identify extreme customer/partition data skew and explain consequences for parallel warehouse processing. |
| SQL-055 | Compute p50 and p95 ingestion delay using PostgreSQL ordered-set aggregates; define time units. |
| SQL-056 | Extract typed attributes from `jsonb` event payload, including missing keys and invalid values. |
| SQL-057 | Expand JSON arrays into rows with `LATERAL` / JSONB functions and prevent accidental duplicates. |
| SQL-058 | Create a complete calendar using `generate_series` and report missing sales dates. |
| SQL-059 | Explore partition pruning with a partitioned fact table; compare a pruning-friendly predicate to one that blocks pruning. |
| SQL-060 | Implement/demonstrate an appropriate unique constraint or dedup key strategy and test conflict behavior safely in an isolated environment. |

**SQL validation modes:**
- `query`: execute one read-only SQL statement against a fixed seeded fixture and compare exact expected columns/values and unordered row multiset unless `ORDER BY` is required. Do not accept any empty response as a pass.
- `mutation`: evaluate DML in a dedicated transaction or disposable schema, then verify resulting table state and roll back. No mutation of shared fixtures after tests.
- `plan`: make EXPLAIN and reasoning exercises executable, but grade index/plan interpretation through a documented manual checklist; do not claim automated plan quality based solely on elapsed time.
- `modeling`: some tasks may require written design rationale alongside the executable query; include an explicit rubric.

For SQL tasks involving more than just `SELECT`, make sure student files are executable and that execution is safe. Avoid running untrusted SQL with superuser-level permissions. Prefer separate `practice` and `grader` database roles; graders may create isolated schemas and control cleanup. The practice database is disposable, but no drop of databases/schemas without a narrowly targeted safety guard.

## 6. Python exercise bank: implement ALL 50 questions

Use real callable signatures, tests, illustrative examples, at least 3 edge tests per question, and realistic constraints. Prefer pure functions and dependency injection so I can focus on typing and get fast feedback. Do **not** require external network services. Keep Python reference solutions idiomatic and compare straightforward vs optimized approaches where appropriate.

### 01 — Python fundamentals: PY-001 through PY-010

| ID | Interview question |
|---|---|
| PY-001 | Remove duplicate transaction records by `transaction_id` while preserving original input order. |
| PY-002 | Aggregate transaction amounts by customer ID using a dictionary. |
| PY-003 | Find top-K customers by spend with deterministic tie-breaking. |
| PY-004 | Flatten nested JSON-style transaction dictionaries into a documented flat mapping. |
| PY-005 | Parse ISO 8601 timestamps and normalize correctly to UTC; distinguish naive timestamps. |
| PY-006 | Group transactions by date in a chosen business timezone. |
| PY-007 | Validate required fields/types and return structured row errors rather than crash. |
| PY-008 | Perform an inner and left join of two in-memory collections efficiently by key. |
| PY-009 | Count word or event frequencies, normalize case, and sort deterministically. |
| PY-010 | Implement a reusable generator yielding chunks of iterable records. |

### 02 — Algorithms and interview patterns: PY-011 through PY-020

| ID | Interview question |
|---|---|
| PY-011 | Two-sum with duplicate values and a deterministic answer policy. |
| PY-012 | Longest substring with no repeated characters (sliding window). |
| PY-013 | Merge overlapping half-open time intervals. |
| PY-014 | Find top-K frequent elements via heap vs full sorting. |
| PY-015 | Group anagrams using a stable canonical key. |
| PY-016 | Binary search for first element greater than or equal to a target. |
| PY-017 | Merge K already-sorted streams without materializing them all. |
| PY-018 | Design a small LRU cache with O(1) average get/put. |
| PY-019 | Find maximum value in each sliding window of length K. |
| PY-020 | Find customer purchasing streaks of at least five calendar days using pure Python; duplicate-day safe. |

### 03 — ETL and large-file processing: PY-021 through PY-030

| ID | Interview question |
|---|---|
| PY-021 | Stream a CSV and calculate spend per customer without loading all rows. |
| PY-022 | Parse newline-delimited JSON, separate malformed rows into a quarantine result, continue safely. |
| PY-023 | Normalize mixed date, numeric and null inputs to an explicit canonical schema. |
| PY-024 | Detect duplicate business keys; if revisions exist select latest by source sequence. |
| PY-025 | Compute column-level data-quality statistics for a bounded iterable. |
| PY-026 | Build a file-to-file transform using temporary output and atomic rename to avoid partial publish. |
| PY-027 | Partition records to deterministic `year=/month=/day=` logical destinations (simulate locally). |
| PY-028 | Compare two streams by keyed canonical hashes, reporting missing/extra/changed records. |
| PY-029 | Implement bounded-memory external merge sorting of large file records (use temp files). |
| PY-030 | Implement an incremental watermark filter with overlap, idempotent dedup and explicit boundary semantics. |

### 04 — Streaming, correctness, reliability: PY-031 through PY-040

| ID | Interview question |
|---|---|
| PY-031 | Maintain order-aware state from out-of-order business events; sequence wins over ingest time. |
| PY-032 | Implement an idempotent event consumer with stable event IDs and a deterministic state store. |
| PY-033 | Retry transient failures with capped exponential backoff and deterministic injectable clock/sleeper. |
| PY-034 | Simulate checkpointing and crash recovery so reruns do not duplicate committed work. |
| PY-035 | Compute fixed five-minute event-time windows with late events and a clear watermark policy. |
| PY-036 | Apply customer SCD2 updates from ordered source changes, preserving non-overlapping validity intervals. |
| PY-037 | Compute a null-safe canonical record fingerprint; explain ambiguity and schema evolution. |
| PY-038 | Implement backpressure with bounded producer/consumer queues (test with deterministic threads or asyncio). |
| PY-039 | Detect identical duplicate messages versus same-ID conflicting payloads. |
| PY-040 | Incrementally update purchasing streaks, then repair affected history when a late day arrives. |

### 05 — PostgreSQL, APIs, and practical backend patterns: PY-041 through PY-050

| ID | Interview question |
|---|---|
| PY-041 | Query PostgreSQL using parameterized `psycopg` SQL; do not build SQL with user-supplied string interpolation. |
| PY-042 | Iterate a large Postgres result set using server-side cursor/streaming with bounded memory. |
| PY-043 | Batch inserts and upserts in transactions; validate idempotency on duplicate attempts. |
| PY-044 | Paginate SQL records with keyset pagination using a stable composite cursor. |
| PY-045 | Build a small ETL pipeline (extract/transform/load) with testable interfaces and injected dependencies. |
| PY-046 | Consume a paginated REST-style source using a local fake client, including empty and repeated pages. |
| PY-047 | Respect an API rate limit / 429 retry-after using a mocked client and injectable sleeper. |
| PY-048 | Limit asyncio concurrency and aggregate results with predictable error handling. |
| PY-049 | Reconcile Python-computed daily aggregate totals against PostgreSQL aggregate query results. |
| PY-050 | End-to-end mini project: ingest synthetic transactions, validate and dedup, upsert into staging, produce a daily summary, assert reconciliation. |

### Multiple approaches requirement

For at least these Python questions, provide `solution.py` and `solution_alt.py` (or the naming convention above) with real trade-offs: **PY-001, 002, 003, 008, 011, 012, 013, 014, 016, 017, 019, 020, 021, 024, 028, 030**. Avoid artificially different variable names as an "alternative"; use different algorithms/data structures or genuinely meaningful implementation patterns. For Python integration tasks requiring a running DB, clearly tag `requires_postgres` and supply automated setup fixtures.

## 7. Exercise metadata and question quality

Every exercise must have machine-readable metadata, such as:

```yaml
id: SQL-021
title: Five consecutive purchase days
area: gaps_islands_time
difficulty: medium
estimated_minutes: 20
requires_database: true
validation_mode: query
prerequisites: [SQL-011]
tags: [window-functions, deduplication, dates, scale]
```

For Python, include expected function/module location and whether integration dependencies are needed.

Write questions as an actual interviewer would: start with a business requirement, not a prompt revealing the method. Spell out edge conditions (multiple purchases/day; inclusive vs exclusive dates; nulls; ties; input scale). At the end of the *explanations*, add 2–4 tougher follow-ups, including how to scale a 500M-row dataset, but **do not show answer hints in student question/practice files**.

Difficulty target: roughly 20% easy, 50% medium, 30% hard. For every SQL question provide at least one realistic expected-result fixture and for every Python task at least 3 tests, covering tricky cases. `test-all` must include genuinely adversarial cases, not just examples designed to pass the reference solution.

## 8. Required developer commands

Implement all of these as usable, documented commands using `python -m lab` (assuming `.venv` is activated). **Commands below are examples of exact interface desired; make them actually work.**

```bash
# After cloning / opening in VS Code:
python -m venv .venv
python -m pip install -e '.[dev]'
docker compose up -d
python -m lab db status
python -m lab db migrate
python -m lab db seed --size small

# Choose and practice a question:
python -m lab list sql --difficulty medium
python -m lab list python --topic algorithms
python -m lab show SQL-021          # question only, not solution
python -m lab show PY-012           # question only
python -m lab run SQL-021           # execute my sql/practice file
python -m lab check SQL-021         # validate against fixture
python -m lab check PY-012          # run pytest targeting practice stub
python -m lab check-all            # summary by category

# Reference material, explicitly opt in:
python -m lab solution SQL-021      # path/display only when requested
python -m lab solution PY-012 --alt

# Manage local learning and database:
python -m lab db seed --size medium
python -m lab db reset --confirm   # explicit guarded operation; local DB only
python -m lab progress
python -m lab session --minutes 45 --mix sql,python
```

If you choose different CLI arguments, make them completely consistent across the CLI, VS Code tasks, and README; do not document nonexistent commands. `lab run` should be useful even with invalid SQL: print the database error in a readable way and identify which practice file ran. `lab check` should report concise diff/diagnostics and time taken. SQL checks should avoid depending on arbitrary row order unless order was explicitly specified by the question. Validate both column names/types and data values, including duplicate rows where relevant. Use **read-only execution** for query questions, plus statement timeout and sensible row limits; don't permit destructive SQL through the default runner.

**Windows usage:** include PowerShell snippets, e.g. `py -3.12 -m venv .venv`, `.\.venv\Scripts\Activate.ps1`, `python -m pip install -e '.[dev]'`. Include alternatives where Windows execution policy interferes: `.\.venv\Scripts\python.exe -m lab ...`. The system must not depend on `make` being installed.

### Practice workflow

1. From `QUESTION_BANK.md` or `lab list`, choose a numbered task.
2. Read a **question only**, without hints or answer leakage.
3. Open the `practice` file and type a full implementation from scratch.
4. Execute/check via VS Code Task or CLI.
5. Read concise feedback and modify until it passes.
6. Only then inspect canonical and alternate solutions, explanations and performance notes.
7. Record completion date, elapsed time, confidence (1–5), and notes. A missed/slow problem should recur in spaced repetition.

Implement a simple local `study/progress.json` or SQLite progress database. Do not overwrite practice code automatically when resetting metadata. `lab session` can print a recommended sequence of problems; it does not need to track time automatically.

## 9. Interview training curriculum

Write `study/8_WEEK_PLAN.md`, assuming 45–90 minutes most weekdays, 2–3 hours one weekend day. Mix SQL and Python every week and introduce senior-level discussion early. Include a 10-minute speed-typing warmup where I retype syntax without copy/paste. Include checkpoints and at least one timed mock each week.

- **Week 1:** SQL foundations, joins, group by; Python dict/list/set, simple transformations.
- **Week 2:** SQL windows, CTEs, top N, running totals; Python heaps, sliding window, searching.
- **Week 3:** Gaps/islands, calendar logic, timezones, temporal joins; Python iterators and file streaming.
- **Week 4:** Dimensional modeling, SCD2, fact grain, cohort queries; Python clean ETL design and validation.
- **Week 5:** CDC, incremental ingest, late arrivals, idempotency, reconciliation; Python checkpoint/retries.
- **Week 6:** PostgreSQL EXPLAIN, indexing, query plans, data skew; Python bounded memory, concurrency, integration.
- **Week 7:** 500M-row system design follow-ups, partitioning, data correctness, implementation trade-offs; timed mixed problems.
- **Week 8:** Mock interviews (45–60 minutes), error review, explain your trade-offs aloud, focus on weak areas.

`INTERVIEW_PLAYBOOK.md` should teach how to **clarify requirements first**, explain grain and assumptions, handle NULL/ties/duplicates/timezones, verbalize complexity, ask about available indexes, and discuss how to validate production correctness. Add short "What would change at 500 million rows?" follow-ups across exercises. Include PostgreSQL vs T-SQL cheat sheet: `DATEADD` vs interval arithmetic, `DATEDIFF` vs subtraction, `TOP` vs `LIMIT`, `ISNULL` vs `COALESCE`, `STRING_AGG`, `DISTINCT ON`, `FILTER`, timestamp/date operations, CTE/window conventions, `INSERT ... ON CONFLICT`, `EXPLAIN`, and SQL Server-specific features with no exact PostgreSQL equivalent.

## 10. Safety, reliability, and anti-shortcut rules

- Protect me from unintentionally seeing solutions during normal practice. Do not place explanations or revealing "hints" in the practice code, test names, question file, or CLI `show` output. I should have to deliberately open solutions.
- Do not insert complete reference answers into practice stubs. No auto-completing the practice files from reference implementations.
- Python tests should test practice stubs by default and fail clearly with `NotImplementedError`, not silently test the reference file.
- Reference solutions themselves must pass the tests in a separate verification mode; verification must not leave reference code inside practice files.
- For SQL, independently verify expected output against hand-checkable fixtures and cross-validate important problems with alternate strategies. SQL solutions must be runnable **on PostgreSQL 17 as written**, not SQL Server or Synapse syntax.
- Avoid using business secrets, real customer records, or production credentials. Local credentials are for a disposable local database only.
- DML/DDL and performance/index exercises run in clearly scoped, resettable isolation; ordinary query exercises never modify shared fixtures.
- The progress system must not mark an unattempted stub as completed or conflate "executed without exception" with "passed".
- Do not generate fake test success messages. Run actual tests and report which passed and which are incomplete.
- Optimize for beginner-friendly commands but **senior-level problem depth**. The Python question bank should mix interview algorithms with real data engineering coding, not only LeetCode-type puzzles.

## 11. Implementation order and verification

Implement in coherent phases and leave the repository usable after each phase:

1. **Foundation:** Docker Compose, connection, schema/migrations, small deterministic seed, data dictionary, cross-platform Python package/CLI, README, VS Code config.
2. **End-to-end vertical slice:** Fully implement and verify SQL-001, SQL-011, SQL-021, SQL-024, SQL-031, SQL-041 and PY-001, PY-003, PY-012, PY-020, PY-030, PY-041. These include questions, empty practice files, real solutions, checks, edge-case fixtures, and explanations. Prove that the lab truly runs.
3. **Full bank:** Build all remaining SQL-001…060 and PY-001…050 with the same quality bar. No "TODO: add test" placeholder masquerading as completion.
4. **Experience:** question banks, timer/session suggestion, progress tracker, 8-week plan, cheat sheets, VS Code tasks, optional Make aliases.
5. **QA:** Start a clean DB, migrate, seed twice to verify repeatability, run CLI self-tests, verify **all reference solutions**, verify several intentional wrong solutions are rejected, and verify unimplemented practice stubs are not reported as passing. Test both query-mode and mutation-mode SQL tasks. Validate packaging, import paths, and documented commands. If large seed takes too long, at least verify the medium seed and clearly explain what you did/did not run.

### What to show in your final implementation report

When done, provide:

- A concise file-tree summary and counts of **fully implemented / actually verified** SQL and Python exercises.
- Exact copy-pasteable setup commands for **Windows PowerShell** and a macOS/Linux shell.
- 3 very short examples showing how to practice SQL-021, PY-012, and a PostgreSQL integration question.
- One paragraph showing where to edit attempts, where answers live, and how to reset.
- Any genuine limitations, skipped problems, assumptions, dependencies, or failing tests (do not hide partial work).
- A suggestion for the **first 7 days of practice** using the generated exercise IDs.

**Begin implementing immediately.** Ask questions only if there is a truly blocking ambiguity. Prefer reasonable defaults as specified and execute code to verify it. Do not stop at writing a proposal. Continue until the repository works and the requested files are created.
