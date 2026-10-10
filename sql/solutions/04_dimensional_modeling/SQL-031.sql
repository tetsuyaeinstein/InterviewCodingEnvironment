-- SQL-031 reference solution (a): range join on the half-open validity interval.
-- The interval predicate lives in the LEFT JOIN's ON clause, so guests and facts that fall into a
-- dimension gap survive with NULL attributes instead of being dropped.
SELECT t.transaction_id,
       t.customer_id,
       t.transaction_ts,
       d.region       AS region_at_purchase,
       d.segment      AS segment_at_purchase,
       c.home_region  AS current_region
FROM transactions t
LEFT JOIN dim_customer_scd2 d
       ON d.customer_id = t.customer_id
      AND t.transaction_ts >= d.effective_from     -- start inclusive
      AND t.transaction_ts <  d.effective_to       -- end exclusive: at a change instant the NEW version wins
LEFT JOIN customers c
       ON c.customer_id = t.customer_id
WHERE t.transaction_status = 'COMPLETED'
  AND t.transaction_ts >= TIMESTAMPTZ '2025-06-01 00:00:00+00'
  AND t.transaction_ts <  TIMESTAMPTZ '2025-07-01 00:00:00+00';
