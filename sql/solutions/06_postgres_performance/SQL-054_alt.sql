-- SQL-054 alternative (b): one scan with GROUPING SETS instead of two aggregations + UNION ALL.
-- GROUPING(col) = 1 marks the rows where that column is NOT a grouping column, which is the only
-- reliable way to tell "customer_id is NULL because guest" from "customer_id is not grouped".
WITH sets AS (
    SELECT store_id, customer_id,
           GROUPING(store_id)    AS store_not_grouped,
           GROUPING(customer_id) AS cust_not_grouped,
           count(*)              AS txn_count
    FROM transactions
    GROUP BY GROUPING SETS ((store_id), (customer_id))
),
keyed AS (
    SELECT CASE WHEN store_not_grouped = 0 THEN 'store' ELSE 'customer' END       AS key_type,
           CASE WHEN store_not_grouped = 0 THEN store_id::text
                ELSE COALESCE(customer_id::text, '(null)') END                      AS key_value,
           CASE WHEN store_not_grouped = 0 THEN store_id ELSE COALESCE(customer_id, 0) END AS sort_key,
           txn_count
    FROM sets
),
ranked AS (
    SELECT *, row_number() OVER (PARTITION BY key_type ORDER BY txn_count DESC, sort_key) AS rank_in_type,
              sum(txn_count) OVER (PARTITION BY key_type) AS type_total   -- every row falls in exactly one group per type
    FROM keyed
)
SELECT key_type, key_value, rank_in_type::int, txn_count,
       round(100.0 * txn_count / type_total, 2) AS pct_of_total
FROM ranked
WHERE rank_in_type <= 5
ORDER BY key_type, rank_in_type;

-- RATIONALE:
-- Store 6 (online flagship) holds about 16% of transactions and customer 1001 about 2.5%, with
-- guests (NULL customer_id) forming one 1.4% bucket. Hash-distributing on store_id in Synapse
-- (60 distributions) or shuffling by store_id in Spark creates a straggler partition for store 6;
-- hashing NULL puts all guest rows on one node. Prefer a high-cardinality, evenly spread key such
-- as transaction_id (or customer_id plus a salt for hot customers), broadcast or replicate small
-- dimensions, salt hot keys and merge partial aggregates, and handle NULL keys in a separate path.
