-- SQL-005 alternative (b): correlated scalar subqueries per transaction (no child joins at all).
-- Each subquery returns exactly one value per header row, so fan-out is impossible by construction.
-- PostgreSQL runs them as SubPlans probing the transaction_items PK and the refunds(transaction_id) index.
WITH per_txn AS (
    SELECT t.customer_id,
           t.gross_amount,
           (SELECT SUM(i.quantity)
            FROM transaction_items i
            WHERE i.transaction_id = t.transaction_id)           AS items_sold,
           (SELECT COALESCE(SUM(r.refund_amount), 0)
            FROM refunds r
            WHERE r.transaction_id = t.transaction_id)           AS refunded_amount
    FROM transactions t
    WHERE t.transaction_status = 'COMPLETED'
      AND t.customer_id IS NOT NULL
      AND t.transaction_ts >= TIMESTAMPTZ '2025-10-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
)
SELECT customer_id,
       COUNT(*)                                 AS completed_txn_count,
       COALESCE(SUM(items_sold), 0)             AS items_sold,
       SUM(gross_amount)                        AS gross_spend,
       SUM(refunded_amount)                     AS refunded_amount,
       SUM(gross_amount) - SUM(refunded_amount) AS net_spend
FROM per_txn
GROUP BY customer_id;
