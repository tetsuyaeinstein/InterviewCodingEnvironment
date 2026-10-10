-- SQL-031 reference solution (b): LEFT JOIN LATERAL "latest version that started at or before
-- the sale", then check that the sale is still before that version's end.
-- This is the classic "as-of" lookup: one index probe on dim_customer_scd2(customer_id,
-- effective_from) per fact, guaranteed to return at most one version even if the dimension had
-- overlapping rows (it would silently pick the latest-starting one; the range join would fan out).
SELECT t.transaction_id,
       t.customer_id,
       t.transaction_ts,
       CASE WHEN t.transaction_ts < v.effective_to THEN v.region  END AS region_at_purchase,
       CASE WHEN t.transaction_ts < v.effective_to THEN v.segment END AS segment_at_purchase,
       c.home_region AS current_region
FROM transactions t
LEFT JOIN LATERAL (
        SELECT d.region, d.segment, d.effective_to
        FROM dim_customer_scd2 d
        WHERE d.customer_id = t.customer_id
          AND d.effective_from <= t.transaction_ts
        ORDER BY d.effective_from DESC, d.customer_sk DESC
        LIMIT 1
     ) v ON true
LEFT JOIN customers c ON c.customer_id = t.customer_id
WHERE t.transaction_status = 'COMPLETED'
  AND t.transaction_ts >= TIMESTAMPTZ '2025-06-01 00:00:00+00'
  AND t.transaction_ts <  TIMESTAMPTZ '2025-07-01 00:00:00+00';
