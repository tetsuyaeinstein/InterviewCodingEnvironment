-- SQL-005 reference solution (a): aggregate each child table to transaction grain BEFORE joining.
-- transactions 1:N transaction_items and transactions 1:N refunds. Joining both children directly
-- multiplies rows (lines x refunds per transaction), so every SUM/COUNT after that join is inflated.
WITH q4_txn AS (                -- header grain, scoped to the business question
    SELECT transaction_id, customer_id, gross_amount
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL
      AND transaction_ts >= TIMESTAMPTZ '2025-10-01 00:00:00+00'
      AND transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
),
items AS (                      -- one row per transaction
    SELECT i.transaction_id, SUM(i.quantity) AS items_sold
    FROM transaction_items i
    JOIN q4_txn t USING (transaction_id)
    GROUP BY i.transaction_id
),
refunded AS (                   -- one row per transaction; refund_ts is deliberately NOT filtered
    SELECT r.transaction_id, SUM(r.refund_amount) AS refunded_amount
    FROM refunds r
    JOIN q4_txn t USING (transaction_id)
    GROUP BY r.transaction_id
)
SELECT t.customer_id,
       COUNT(*)                                                     AS completed_txn_count,
       COALESCE(SUM(i.items_sold), 0)                               AS items_sold,
       SUM(t.gross_amount)                                          AS gross_spend,
       COALESCE(SUM(r.refunded_amount), 0.00)                       AS refunded_amount,
       SUM(t.gross_amount) - COALESCE(SUM(r.refunded_amount), 0.00) AS net_spend
FROM q4_txn t
LEFT JOIN items    i USING (transaction_id)   -- 1:1 after pre-aggregation, so no fan-out
LEFT JOIN refunded r USING (transaction_id)   -- 1:1 after pre-aggregation, so no fan-out
GROUP BY t.customer_id;
