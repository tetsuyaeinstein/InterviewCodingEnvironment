-- SQL-019 alternative (b): scalar total computed once in a CROSS JOIN, no window function.
WITH lines AS (
    SELECT i.product_id,
           i.quantity * i.unit_price - i.discount_amount AS line_net
    FROM transactions t
    JOIN transaction_items i ON i.transaction_id = t.transaction_id
    WHERE t.store_id = 5
      AND t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= TIMESTAMPTZ '2025-11-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2025-12-01 00:00:00+00'
),
total AS (SELECT SUM(line_net) AS store_net_revenue FROM lines)
SELECT 5 AS store_id,
       l.product_id,
       SUM(l.line_net)                                              AS net_revenue,
       tot.store_net_revenue,
       ROUND(100 * SUM(l.line_net) / tot.store_net_revenue, 2)      AS pct_of_store_revenue
FROM lines l
CROSS JOIN total tot
GROUP BY l.product_id, tot.store_net_revenue;
