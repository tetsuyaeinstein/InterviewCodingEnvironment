-- SQL-037 reference solution (b): one sorted distinct array per basket, then generate the index
-- pairs (i < j) with generate_subscripts. No self-join of the line table: the pair explosion
-- happens per basket, so cost is sum(k^2) over basket sizes k.
WITH baskets AS (
    SELECT ti.transaction_id,
           array_agg(DISTINCT ti.product_id ORDER BY ti.product_id) AS products   -- distinct + sorted
    FROM transaction_items ti
    JOIN transactions t ON t.transaction_id = ti.transaction_id
    WHERE t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= TIMESTAMPTZ '2025-11-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
    GROUP BY ti.transaction_id
    HAVING COUNT(DISTINCT ti.product_id) >= 2
)
SELECT products[i] AS product_a,
       products[j] AS product_b,
       COUNT(*)    AS co_occurrences
FROM baskets
CROSS JOIN LATERAL generate_subscripts(products, 1) AS i
CROSS JOIN LATERAL generate_subscripts(products, 1) AS j
WHERE i < j
GROUP BY products[i], products[j]
HAVING COUNT(*) >= 2;
