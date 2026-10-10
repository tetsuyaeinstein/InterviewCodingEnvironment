-- SQL-012 reference solution (a): DENSE_RANK over amounts, then conditional aggregation per store.
-- DENSE_RANK gives equal amounts the same rank and does not skip numbers: 78,78,66,66,60 -> 1,1,2,2,3.
WITH scoped AS (
    SELECT store_id, gross_amount
    FROM transactions
    WHERE transaction_status = 'COMPLETED'                            -- a CANCELLED 300.00 is not a basket
      AND transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'      -- UTC year 2025, half-open
      AND transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
),
ranked AS (
    SELECT store_id,
           gross_amount,
           DENSE_RANK() OVER (PARTITION BY store_id ORDER BY gross_amount DESC) AS amount_rank
    FROM scoped
)
SELECT store_id,
       MAX(gross_amount)                                   AS highest_amount,
       MAX(gross_amount) FILTER (WHERE amount_rank = 2)    AS second_highest_amount  -- NULL if no rank 2
FROM ranked
GROUP BY store_id;                                        -- keeps stores with a single distinct amount
