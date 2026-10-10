-- SQL-003 alternative (b): NOT EXISTS anti-join for the window, correlated MAX for the last purchase.
-- Reads as the business rule: "no completed purchase in the window exists for this customer".
SELECT c.customer_id,
       (SELECT (MAX(t2.transaction_ts) AT TIME ZONE 'UTC')::date
        FROM transactions t2
        WHERE t2.customer_id = c.customer_id
          AND t2.transaction_status = 'COMPLETED'
          AND t2.transaction_ts < TIMESTAMPTZ '2026-01-01 00:00:00+00') AS last_completed_purchase_date
FROM customers c
WHERE NOT EXISTS (
    SELECT 1
    FROM transactions t
    WHERE t.customer_id = c.customer_id
      AND t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= TIMESTAMPTZ '2025-10-03 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
);
