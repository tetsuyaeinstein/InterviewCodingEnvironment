-- SQL-039 reference solution (b): "as-of" lookup with LATERAL (latest version starting at or before
-- the sale, valid only if the sale is before its end) and COUNT(DISTINCT customer_id) directly on
-- the grouped output: no intermediate DISTINCT set.
SELECT date_trunc('month', t.transaction_ts AT TIME ZONE 'UTC')::date AS purchase_month,
       CASE WHEN t.transaction_ts < v.effective_to THEN v.region END   AS region,
       COUNT(DISTINCT t.customer_id)                                   AS active_customers
FROM transactions t
LEFT JOIN LATERAL (
        SELECT d.region, d.effective_to
        FROM dim_customer_scd2 d
        WHERE d.customer_id = t.customer_id
          AND d.effective_from <= t.transaction_ts
        ORDER BY d.effective_from DESC
        LIMIT 1
     ) v ON true
WHERE t.transaction_status = 'COMPLETED'
  AND t.customer_id IS NOT NULL
  AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
  AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
GROUP BY 1, 2;
