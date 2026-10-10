# PostgreSQL vs T-SQL (SQL Server / Azure Synapse) cheat sheet

This sheet assumes you already think in T-SQL. Every PostgreSQL line here is valid PostgreSQL 17.

## Dates and times

| task | T-SQL | PostgreSQL |
|---|---|---|
| add days | `DATEADD(day, 7, d)` | `d + 7` (date) · `ts + interval '7 days'` · `d + make_interval(days => n)` |
| add months | `DATEADD(month, 1, d)` | `d + interval '1 month'` (result is a timestamp; cast `::date` if needed) |
| difference in days | `DATEDIFF(day, a, b)` | `b - a` (date − date = integer days) |
| difference in seconds | `DATEDIFF(second, a, b)` | `EXTRACT(EPOCH FROM (b - a))` (timestamps; returns numeric) |
| truncate | `DATETRUNC(month, ts)` (2022+) / `DATEFROMPARTS(...)` | `date_trunc('month', ts)` |
| date part | `DATEPART(week, d)`, `DATEPART(iso_week, d)` | `EXTRACT(week FROM d)` (ISO week), `EXTRACT(isoyear FROM d)`, `EXTRACT(isodow FROM d)` |
| today / now | `CAST(GETDATE() AS date)`, `SYSUTCDATETIME()` | `CURRENT_DATE`, `now()` / `clock_timestamp()` (avoid in reproducible queries) |
| convert time zone | `ts AT TIME ZONE 'UTC' AT TIME ZONE 'Eastern Standard Time'` | `ts AT TIME ZONE 'America/New_York'` (timestamptz → local timestamp) |
| business date in UTC | `CAST(SWITCHOFFSET(ts, '+00:00') AS date)` | `(ts AT TIME ZONE 'UTC')::date` |
| build a date | `DATEFROMPARTS(2025, 3, 1)` | `make_date(2025, 3, 1)` or `DATE '2025-03-01'` |
| calendar table | recursive CTE or a numbers table | `generate_series(DATE '2025-01-01', DATE '2025-12-31', interval '1 day')::date` |
| ranges | (none built in) | `tstzrange(a, b, '[)')`, `&&` (overlap), `@>` (contains), `range_agg()`, multiranges |

> `timestamptz` stores an instant (displayed in the session `TimeZone`). `timestamp` has no
> zone. In SQL Server, `AT TIME ZONE` on `datetime2` *assigns* an offset, while on
> `datetimeoffset` it *converts*. PostgreSQL behaves the same way with `timestamp` vs
> `timestamptz`.

## Row limiting, top-N and "latest per group"

| task | T-SQL | PostgreSQL |
|---|---|---|
| first N rows | `SELECT TOP (10) ...` | `... ORDER BY x LIMIT 10` or `FETCH FIRST 10 ROWS ONLY` |
| with ties | `TOP (3) WITH TIES` | `FETCH FIRST 3 ROWS WITH TIES` |
| paging | `OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY` | same, or `LIMIT 10 OFFSET 20` (prefer keyset pagination) |
| latest row per key | `ROW_NUMBER()` + filter, or `CROSS APPLY (SELECT TOP 1 ...)` | `DISTINCT ON (key) ... ORDER BY key, ts DESC, id DESC`, or `LATERAL (... LIMIT 1)` |
| apply | `CROSS APPLY` / `OUTER APPLY` | `CROSS JOIN LATERAL` / `LEFT JOIN LATERAL ... ON true` |

## NULLs, strings and conditionals

| task | T-SQL | PostgreSQL |
|---|---|---|
| null replacement | `ISNULL(a, b)` (2 args, type of a) | `COALESCE(a, b, ...)` (standard; also works in T-SQL) |
| null-safe compare | `EXISTS (SELECT a INTERSECT SELECT b)` / `IS [NOT] DISTINCT FROM` (2022+) | `a IS [NOT] DISTINCT FROM b` |
| conditional aggregate | `SUM(CASE WHEN ... THEN x END)` | `SUM(x) FILTER (WHERE ...)` (or the CASE form) |
| IIF | `IIF(c, a, b)` | `CASE WHEN c THEN a ELSE b END` |
| string concat | `a + b` (NULL-propagating), `CONCAT()` | `a || b` (NULL-propagating), `concat()` / `concat_ws()` (ignore NULLs) |
| string aggregate | `STRING_AGG(x, ',') WITHIN GROUP (ORDER BY x)` | `string_agg(x, ',' ORDER BY x)` |
| array aggregate | (none) | `array_agg(x ORDER BY x)`, `unnest()`, `= ANY(array)` |
| case-insensitive match | collation-dependent `LIKE` | `ILIKE`, `lower(a) = lower(b)`, or `citext` |
| regex | (limited) | `~`, `~*`, `regexp_replace`, `regexp_match` |
| safe cast | `TRY_CAST(x AS int)` | `CASE WHEN pg_input_is_valid(x, 'integer') THEN x::int END` (PG16+) |
| integer division | `5 / 2 = 2` | `5 / 2 = 2` as well; `5 / 2.0` or `5::numeric / 2` for decimals |
| divide safely | `a / NULLIF(b, 0)` | `a / NULLIF(b, 0)` |

## DML and upserts

| task | T-SQL | PostgreSQL |
|---|---|---|
| upsert | `MERGE ... WHEN MATCHED ... WHEN NOT MATCHED ...` | `INSERT ... ON CONFLICT (key) DO UPDATE SET c = EXCLUDED.c WHERE ...` (concurrency-safe); `MERGE` exists since PG15 |
| insert-if-absent | `IF NOT EXISTS (...) INSERT` / MERGE | `INSERT ... ON CONFLICT DO NOTHING` |
| returning changed rows | `OUTPUT inserted.*` | `RETURNING *` (also `MERGE ... RETURNING` in PG17) |
| update from join | `UPDATE t SET ... FROM t JOIN s ON ...` | `UPDATE t SET ... FROM s WHERE t.id = s.id` |
| delete with join | `DELETE t FROM t JOIN s ...` | `DELETE FROM t USING s WHERE t.id = s.id` |
| identity | `IDENTITY(1,1)` | `GENERATED ALWAYS AS IDENTITY` (or `bigserial`) |
| temp table | `#tmp` | `CREATE TEMP TABLE tmp (...)` (session-scoped), or CTEs |
| transactional DDL | partially | fully: `CREATE`/`DROP` roll back (this lab's sandboxes rely on it) |

## CTEs, windows and recursion

| topic | T-SQL | PostgreSQL |
|---|---|---|
| CTE | `WITH x AS (...)` | same; PG12+ inlines non-recursive CTEs (`MATERIALIZED` / `NOT MATERIALIZED` hints) |
| recursive CTE | `WITH x AS (anchor UNION ALL recursive)` | `WITH RECURSIVE x AS (...)`; also `SEARCH`/`CYCLE` clauses |
| window frames | `ROWS`/`RANGE` | `ROWS`/`RANGE`/`GROUPS`, `RANGE BETWEEN interval '6 days' PRECEDING AND CURRENT ROW` on dates |
| named window | (no) | `WINDOW w AS (PARTITION BY ... ORDER BY ...)` |
| percentiles | `PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY x) OVER ()` (window form) | `percentile_cont(0.95) WITHIN GROUP (ORDER BY x)` as an **aggregate** (GROUP BY), no OVER |
| mode | (none) | `mode() WITHIN GROUP (ORDER BY x)` |
| boolean aggregates | `MIN(CAST(flag AS int))` | `bool_and()`, `bool_or()` |

## JSON

| task | T-SQL | PostgreSQL (`jsonb`) |
|---|---|---|
| get text value | `JSON_VALUE(doc, '$.amount')` | `doc->>'amount'` (text), `doc->'items'` (jsonb), `doc #>> '{a,b}'` |
| explode array | `OPENJSON(doc, '$.items')` | `jsonb_array_elements(doc->'items')` (check `jsonb_typeof(...) = 'array'` first) |
| exists key | `JSON_PATH_EXISTS` | `doc ? 'amount'`, `doc @> '{"k": 1}'`, `jsonb_path_exists()` |
| type of value | (n/a) | `jsonb_typeof(doc->'amount')` → string/number/null/array/object/boolean |

## Performance and introspection

| task | T-SQL | PostgreSQL |
|---|---|---|
| actual plan | `SET STATISTICS IO, TIME ON` + actual execution plan | `EXPLAIN (ANALYZE, BUFFERS) SELECT ...` |
| estimated plan | `SET SHOWPLAN_XML ON` | `EXPLAIN SELECT ...` |
| update statistics | `UPDATE STATISTICS t` | `ANALYZE t` |
| covering index | `CREATE INDEX ... INCLUDE (...)` | same syntax: `INCLUDE (...)` |
| filtered index | `WHERE status = 'X'` | partial index, same idea: `CREATE INDEX ... WHERE status = 'COMPLETED'` |
| expression index | computed column + index | `CREATE INDEX ON t ((lower(email)))` directly |
| partitioning | partition function + scheme | `PARTITION BY RANGE (col)` + `CREATE TABLE p PARTITION OF ...` |
| clustered index | yes (table order) | no clustered indexes; heap + `CLUSTER` (one-off), BRIN for naturally ordered data |
| query hints | `OPTION (RECOMPILE)`, `WITH (NOLOCK)` | no hints; `SET LOCAL enable_seqscan = off` for experiments only. NOLOCK has no equivalent: MVCC readers never block writers. |

## Features with no exact PostgreSQL equivalent (and what to say instead)

- **Clustered indexes / index-organised tables:** PostgreSQL tables are heaps. Use a good
  composite index, `CLUSTER` as a one-off, BRIN for append-ordered data, or partitioning.
- **`NOLOCK` / READ UNCOMMITTED:** not needed. MVCC means readers never block, and PostgreSQL
  treats READ UNCOMMITTED as READ COMMITTED.
- **Temporal tables (`SYSTEM_VERSIONING`):** build SCD2/history tables yourself with triggers
  or CDC (the lab's `dim_customer_scd2`). Exclusion constraints can prevent overlaps.
- **`TRY_CAST` / `TRY_CONVERT`:** `pg_input_is_valid()` (PG16+) or a regex guard.
- **Table variables and `#temp` semantics, `SELECT INTO #t`:** CTEs, `CREATE TEMP TABLE`,
  `CREATE TABLE AS`.
- **Columnstore indexes / Synapse distributions (HASH / ROUND_ROBIN / REPLICATE):** no native
  columnstore. Discuss partitioning, BRIN, materialised summaries, or a warehouse engine.
- **`OUTPUT` into a table variable inside MERGE:** use `RETURNING` in a CTE:
  `WITH ins AS (INSERT ... RETURNING *) INSERT INTO audit SELECT * FROM ins`.
- **`DATEADD` with a column-specified datepart:** use `interval` arithmetic,
  `make_interval(days => n)`, or `n * interval '1 day'`.
- **SQL Agent jobs / ADF orchestration:** use external schedulers (cron, Airflow, Azure Data
  Factory) or the `pg_cron` extension.
