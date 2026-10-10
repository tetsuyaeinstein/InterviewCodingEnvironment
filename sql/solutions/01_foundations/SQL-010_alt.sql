-- SQL-010 alternative (b): single pass, one group per customer, boolean aggregates in HAVING.
-- No second scan / anti-join: each customer's in-scope lines are read once and summarised as
-- "bought A at least once" and "bought B at least once".
SELECT t.customer_id
FROM transactions t
JOIN transaction_items i ON i.transaction_id = t.transaction_id
WHERE t.transaction_status = 'COMPLETED'
  AND t.customer_id IS NOT NULL
  AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
  AND t.transaction_ts <  TIMESTAMPTZ '2025-07-01 00:00:00+00'
  AND i.product_id IN (1, 2)
GROUP BY t.customer_id
HAVING BOOL_OR(i.product_id = 1)            -- bought A
   AND NOT BOOL_OR(i.product_id = 2);       -- never bought B (same scope)
