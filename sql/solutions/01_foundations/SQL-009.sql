-- SQL-009 reference solution: customer grain first (LEFT JOIN keeps non-buyers), then segment grain.
-- Two different averages, two different denominators:
--   avg_txn_value          = total amount / number of completed transactions  (NULL when there are none)
--   avg_spend_per_customer = total amount / number of customers in the segment (0.00 when nobody bought)
WITH per_customer AS (
    SELECT c.customer_id,
           c.segment,                                    -- current segment (customers is current state)
           COUNT(t.transaction_id)          AS completed_txns,   -- counts matches only, 0 for non-buyers
           COALESCE(SUM(t.gross_amount), 0) AS completed_amount
    FROM customers c
    LEFT JOIN transactions t
           ON t.customer_id = c.customer_id
          AND t.transaction_status = 'COMPLETED'                         -- in ON, not WHERE
          AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
          AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
    GROUP BY c.customer_id, c.segment
)
SELECT segment,
       COUNT(*)                                        AS customers,
       COUNT(*) FILTER (WHERE completed_txns = 0)      AS customers_without_purchases,
       SUM(completed_txns)                             AS completed_txn_count,
       SUM(completed_amount)                           AS total_completed_amount,
       ROUND(SUM(completed_amount) / NULLIF(SUM(completed_txns), 0), 2) AS avg_txn_value,  -- weighted, not avg of avgs
       ROUND(SUM(completed_amount) / COUNT(*), 2)      AS avg_spend_per_customer
FROM per_customer
GROUP BY segment;
