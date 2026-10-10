-- SQL-052 alternative: state the day once as a half-open tstzrange and test containment.
-- PostgreSQL 14+ has a planner support function for "element <@ range" that rewrites it into
-- the two B-tree comparisons (transaction_ts >= lower AND transaction_ts < upper), so the plan
-- shows the same Index Cond on ix_transactions_ts. The '[)' flag makes the half-open intent explicit.
SELECT store_id,
       count(*)          AS completed_txns,
       sum(gross_amount) AS gross_sales
FROM transactions
WHERE transaction_status = 'COMPLETED'
  AND transaction_ts <@ tstzrange(TIMESTAMPTZ '2025-02-28 00:00:00+00',
                                  TIMESTAMPTZ '2025-03-01 00:00:00+00', '[)')
GROUP BY store_id;
