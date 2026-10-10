-- SQL-003 reference solution (a): one aggregation pass with FILTERed aggregates.
-- Window: business dates 2025-10-03 ... 2025-12-31 inclusive = [2025-10-03 00:00 UTC, 2026-01-01 00:00 UTC).
WITH per_customer AS (
    SELECT c.customer_id,
           MAX(t.transaction_ts) AS last_completed_ts,
           COUNT(t.transaction_id) FILTER (
               WHERE t.transaction_ts >= TIMESTAMPTZ '2025-10-03 00:00:00+00'
           )                     AS completed_in_window
    FROM customers c
    LEFT JOIN transactions t
           ON t.customer_id = c.customer_id
          AND t.transaction_status = 'COMPLETED'                      -- in ON, so customers without purchases survive
          AND t.transaction_ts < TIMESTAMPTZ '2026-01-01 00:00:00+00'  -- nothing after the anchor date counts
    GROUP BY c.customer_id
)
SELECT customer_id,
       (last_completed_ts AT TIME ZONE 'UTC')::date AS last_completed_purchase_date   -- NULL if never purchased
FROM per_customer
WHERE completed_in_window = 0;
