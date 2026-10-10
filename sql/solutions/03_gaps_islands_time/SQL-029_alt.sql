-- SQL-029 reference solution (b): relational division with NOT EXISTS / EXISTS.
-- ALL available  <=>  there is NO selected product for which NO "available" row covers the instant.
-- ANY available  <=>  there EXISTS a selected product with an "available" row covering the instant.
-- Uncovered instants need no special case: no covering available row simply does not exist.
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
available_at_ts AS (             -- the selected products that ARE available for each transaction
    SELECT t.transaction_id, sp.product_id
    FROM txns t
    JOIN selected_products sp ON true
    WHERE EXISTS (
        SELECT 1
        FROM store_product_availability a
        WHERE a.store_id   = t.store_id
          AND a.product_id = sp.product_id
          AND a.available
          AND a.valid_from <= t.transaction_ts
          AND (a.valid_to IS NULL OR t.transaction_ts < a.valid_to)
    )
)
SELECT t.transaction_id,
       t.transaction_ts,
       NOT EXISTS (SELECT 1 FROM selected_products sp
                   WHERE NOT EXISTS (SELECT 1 FROM available_at_ts x
                                     WHERE x.transaction_id = t.transaction_id
                                       AND x.product_id     = sp.product_id))      AS all_available,
       EXISTS (SELECT 1 FROM available_at_ts x
               WHERE x.transaction_id = t.transaction_id)                          AS any_available,
       (SELECT COUNT(*)::int FROM available_at_ts x
        WHERE x.transaction_id = t.transaction_id)                                 AS available_products
FROM txns t;
