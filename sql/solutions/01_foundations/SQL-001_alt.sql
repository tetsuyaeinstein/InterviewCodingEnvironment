-- SQL-001 alternative (b): LEFT JOIN LATERAL with a per-customer aggregate.
-- An aggregate without GROUP BY always returns exactly one row (COUNT = 0, SUM = NULL),
-- so every customer survives even with no completed transactions.
SELECT c.customer_id,
       agg.completed_txn_count,
       COALESCE(agg.total_completed_spend, 0.00) AS total_completed_spend
FROM customers c
CROSS JOIN LATERAL (
    SELECT COUNT(*)            AS completed_txn_count,
           SUM(t.gross_amount) AS total_completed_spend
    FROM transactions t
    WHERE t.customer_id = c.customer_id            -- uses the transactions(customer_id) index
      AND t.transaction_status = 'COMPLETED'
) agg;
