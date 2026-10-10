-- SQL-029 reference solution (a): expand transaction x selected product, LEFT JOIN the availability
-- row covering transaction_ts, then aggregate with boolean aggregates.
-- "No covering row" (NULL after the LEFT JOIN) means not stocked = unavailable.
WITH selected_products (product_id) AS (
    VALUES (4), (5), (6)
),
txns AS (
    SELECT transaction_id, store_id, transaction_ts
    FROM transactions
    WHERE store_id = 2
      AND transaction_status = 'COMPLETED'
      AND transaction_ts >= TIMESTAMPTZ '2025-05-10 00:00:00+00'
      AND transaction_ts <  TIMESTAMPTZ '2025-05-12 00:00:00+00'
),
status_at_ts AS (                -- exactly one row per (transaction, selected product)
    SELECT t.transaction_id,
           t.transaction_ts,
           sp.product_id,
           COALESCE(a.available, false) AS is_available
    FROM txns t
    CROSS JOIN selected_products sp
    LEFT JOIN store_product_availability a
           ON a.store_id    = t.store_id
          AND a.product_id  = sp.product_id
          AND a.valid_from <= t.transaction_ts
          AND (a.valid_to IS NULL OR t.transaction_ts < a.valid_to)
)
SELECT transaction_id,
       transaction_ts,
       BOOL_AND(is_available)                        AS all_available,
       BOOL_OR(is_available)                         AS any_available,
       COUNT(*) FILTER (WHERE is_available)::int     AS available_products
FROM status_at_ts
GROUP BY transaction_id, transaction_ts;
