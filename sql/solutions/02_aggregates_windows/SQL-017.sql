-- SQL-017 reference solution (a): NTILE with a total order + CEIL(4 * CUME_DIST()).
WITH cohort AS (
    SELECT customer_id
    FROM customers
    WHERE registered_at >= TIMESTAMPTZ '2023-12-01 00:00:00+00'
      AND registered_at <  TIMESTAMPTZ '2023-12-02 00:00:00+00'
),
spend AS (                                  -- one row per cohort customer, zero spenders included
    SELECT c.customer_id,
           COALESCE(SUM(t.gross_amount), 0) AS spend_2025
    FROM cohort c
    LEFT JOIN transactions t
           ON t.customer_id = c.customer_id
          AND t.transaction_status = 'COMPLETED'                         -- in ON, not WHERE
          AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
          AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
    GROUP BY c.customer_id
)
SELECT customer_id,
       spend_2025,
       -- equal-size buckets; customer_id makes the order total, so ties split reproducibly
       NTILE(4) OVER (ORDER BY spend_2025 DESC, customer_id)        AS ntile_quartile,
       -- CUME_DIST = (rows with spend >= mine, peers included) / N; equal spend -> equal value
       CEIL(4 * CUME_DIST() OVER (ORDER BY spend_2025 DESC))::int   AS tie_safe_quartile
FROM spend;
