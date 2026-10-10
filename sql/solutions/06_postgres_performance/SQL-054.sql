-- SQL-054 reference solution (a): rank every key within its key type, keep the top 5.
-- The guest bucket (customer_id IS NULL) is a key like any other: GROUP BY keeps NULL as one group.
WITH total AS (
    SELECT count(*) AS n FROM transactions
),
per_key AS (
    SELECT 'store'          AS key_type, store_id::text                    AS key_value, count(*) AS txn_count,
           store_id::bigint AS sort_key
    FROM transactions GROUP BY store_id
    UNION ALL
    SELECT 'customer',       COALESCE(customer_id::text, '(null)'),       count(*),
           COALESCE(customer_id, 0)::bigint          -- NULL bucket is never tied on count with customer 0 (none exists)
    FROM transactions GROUP BY customer_id
),
ranked AS (
    SELECT key_type, key_value, txn_count,
           row_number() OVER (PARTITION BY key_type ORDER BY txn_count DESC, sort_key) AS rank_in_type
    FROM per_key
)
SELECT r.key_type,
       r.key_value,
       r.rank_in_type::int,
       r.txn_count,
       round(100.0 * r.txn_count / t.n, 2) AS pct_of_total
FROM ranked r CROSS JOIN total t
WHERE r.rank_in_type <= 5
ORDER BY r.key_type, r.rank_in_type;

-- RATIONALE:
-- The data is heavily skewed. Store 6, the online flagship, carries about 16% of all
-- transactions, and customer 1001 about 2.5%, while a typical customer has around ten rows.
-- Guest checkouts (customer_id NULL) are a single 1.4% bucket: hashing NULL sends every guest
-- row to ONE distribution or Spark partition. In a Synapse dedicated pool (60 distributions),
-- distributing the fact on store_id would put 16% of rows, and most of the work for store 6,
-- on one distribution, so the whole query waits for that straggler; the same applies to a Spark
-- shuffle by store_id (one huge task, spill, out of memory). customer_id spreads far better
-- (top key 2.5%) but still needs care for 1001 and the NULL bucket: hash on transaction_id or a
-- composite (customer_id, transaction_id) for the fact, or salt hot keys (append a random 0..N
-- suffix, aggregate partially, then merge), and replicate or broadcast the small dimensions
-- (stores, products) so joins need no shuffle. Treat NULL keys explicitly: filter them
-- out and process them separately, or map them to a salted surrogate, rather than letting
-- them collapse into one partition. Check skew continuously with distribution row counts.
