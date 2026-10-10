-- SQL-037 reference solution (a): de-duplicate to basket x product, self-join on the basket,
-- order the pair with a < b (no self-pairs, no mirrored pairs), count distinct baskets.
WITH basket_products AS (          -- grain: one row per (transaction, product), duplicates of lines removed
    SELECT DISTINCT ti.transaction_id, ti.product_id
    FROM transaction_items ti
    JOIN transactions t ON t.transaction_id = ti.transaction_id
    WHERE t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= TIMESTAMPTZ '2025-11-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
)
SELECT a.product_id                  AS product_a,
       b.product_id                  AS product_b,
       COUNT(*)                      AS co_occurrences   -- distinct baskets, because (txn, product) is now unique
FROM basket_products a
JOIN basket_products b
  ON b.transaction_id = a.transaction_id
 AND a.product_id < b.product_id
GROUP BY a.product_id, b.product_id
HAVING COUNT(*) >= 2;
