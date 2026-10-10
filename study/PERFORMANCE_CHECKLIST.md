# Performance checklist (PostgreSQL first, warehouse notes second)

Use this order in interviews and in real incidents: **measure → understand estimates → reduce
work → give the planner better access paths → change the physical design**.

## 1. Measure, don't guess

```text
EXPLAIN (ANALYZE, BUFFERS) <query>;          -- actual rows, time, buffer hits/reads
EXPLAIN (ANALYZE, BUFFERS, SETTINGS) <query>; -- also non-default planner settings
```

Read from the innermost node outward. For each node compare `rows=` (estimated) with `actual
rows=`, and multiply per-loop numbers by `loops`.

| symptom in the plan | likely meaning | first fix |
|---|---|---|
| estimated rows ≪ actual rows (10×+) | stale or insufficient statistics, correlated columns | `ANALYZE`; `ALTER TABLE ... ALTER COLUMN ... SET STATISTICS 1000`; `CREATE STATISTICS` (dependencies / ndistinct / mcv) |
| `Seq Scan` on a big table with a selective filter | no usable index, or a non-sargable predicate | rewrite the predicate (no functions on the column); add or adjust the index |
| `Sort Method: external merge  Disk: …kB` | sort spilled | reduce rows before sorting; raise `work_mem` for that query; use an index that provides order |
| `Hash ... Batches: 8` (> 1) | hash join/agg spilled | `work_mem`; filter earlier; join on fewer columns |
| `Nested Loop` with a large `loops=` count | bad estimate made a nested loop look cheap | fix the estimates; an index on the inner side; sometimes rewrite as a join over pre-aggregated data |
| `Rows Removed by Filter` ≫ rows returned | index on the wrong column order, or a missing partial index | composite index with equality columns first; partial index |
| `Buffers: shared read=` huge | cold cache / reading too much | narrower index (covering/INCLUDE), partition pruning, less data |
| `Heap Fetches` high on an Index Only Scan | visibility map not set | `VACUUM` (autovacuum tuning) |

**Never** claim a query is faster from one elapsed-time sample. Compare buffers and rows, and
warm the cache before timing.

## 2. Sargable predicates

- `ts >= '2025-03-01' AND ts < '2025-03-02'`, not `ts::date = '2025-03-01'` or
  `date_trunc('day', ts) = ...`.
- Compare with the column's own type (no implicit casts on the column side). `customer_id =
  '42'` is fine because the literal is coerced, but `customer_id::text = '42'` is not.
- `col LIKE 'abc%'` can use a B-tree index only with `text_pattern_ops` or the C collation.
  `ILIKE '%x%'` needs `pg_trgm`.
- `OR` across different columns usually becomes a BitmapOr, or forces a rewrite as `UNION ALL`.
- Expression indexes exist (`CREATE INDEX ON t ((lower(email)))`), but the query must use the
  identical expression.

## 3. Composite index design

1. **Equality** columns first (most selective is usually best, but the equality set matters more
   than the order among them).
2. Then the **range** column.
3. Then columns needed for **ORDER BY**. A B-tree scanned forward or backward satisfies
   `ORDER BY a, b DESC` only if the column directions match.
4. `INCLUDE (...)` payload columns for index-only scans.
5. Partial indexes for hot subsets (`WHERE transaction_status = 'COMPLETED'`).

> Example (SQL-053): `WHERE customer_id = $1 AND transaction_ts >= $2 AND transaction_ts < $3
> ORDER BY transaction_ts`. The index `(customer_id, transaction_ts)` returns rows already in
> order with no Sort node. `(transaction_ts, customer_id)` scans the whole range for every
> customer.

## 4. Reduce the work

- Filter and pre-aggregate **before** joins and windows (grain discipline).
- Replace correlated subqueries that run per row with joins over aggregated sets. The reverse
  also holds: a LATERAL top-1 per key with an index can beat a global window sort.
- `EXISTS` instead of `JOIN ... DISTINCT` for semi-joins.
- Avoid `SELECT *` in wide tables when an index-only scan is possible.
- CTEs are inlined since PG12. Use `MATERIALIZED` only when you deliberately want an
  optimisation fence.

## 5. Physical design

- **Partitioning** (range by date) gives pruning, cheap retention (`DETACH/DROP PARTITION`) and
  partition-wise joins and aggregates. It is not a substitute for indexes. Keep the partition
  count in the hundreds, not tens of thousands.
- **BRIN** indexes for huge append-only tables ordered by time: tiny, good for range scans.
- **Summary tables** maintained incrementally (daily customer activity, daily store sales) give
  the biggest win at 500M+ rows.
- **Fill factor / HOT updates** for heavily updated tables. **Autovacuum** tuning for churn.

## 6. Data skew and parallelism (SQL-054)

- Look for heavy keys: `SELECT key, count(*) ... ORDER BY 2 DESC LIMIT 20`, the NULL-key share,
  and percentiles of rows per key.
- In distributed engines (Synapse, Spark, Snowflake), one heavy distribution key turns one
  worker into the bottleneck: the whole job waits for it.
  - Pick distribution keys with high cardinality and even spread.
  - Salt hot keys, broadcast small dimensions, and handle NULL keys separately.
- In PostgreSQL, parallel query splits scans, not keys. Skew mostly hurts estimates (MCV lists),
  and plan choice for parameterised queries (custom vs generic plans).

## 7. Warehouse translation (Synapse / Spark / Snowflake)

| PostgreSQL idea | Synapse dedicated pool | Spark / Databricks | Snowflake |
|---|---|---|---|
| composite index | ordered clustered columnstore / heap + nonclustered index | Z-order / liquid clustering | clustering key |
| partitioning | partitions (on top of 60 distributions) | partitionBy on write | micro-partitions (automatic) + clustering |
| join locality | HASH distribution on the join key; REPLICATE small dims | bucketing / broadcast join | automatic; watch for spill |
| statistics | `CREATE STATISTICS` / auto | `ANALYZE TABLE ... COMPUTE STATISTICS` | automatic |
| EXPLAIN ANALYZE | `sys.dm_pdw_request_steps`, EXPLAIN WITH_RECOMMENDATIONS | Spark UI, `EXPLAIN FORMATTED` | Query Profile |
