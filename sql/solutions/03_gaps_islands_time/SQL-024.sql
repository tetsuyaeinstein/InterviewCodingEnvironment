-- SQL-024 reference solution: aggregate to customer-day spend FIRST, filter days > 100.00,
-- then find runs of consecutive qualifying days and report each customer's earliest run of >= 5.
WITH daily_spend AS (            -- grain: customer x UTC date, completed spend only
    SELECT customer_id,
           (transaction_ts AT TIME ZONE 'UTC')::date AS spend_date,
           SUM(gross_amount)                         AS day_total
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL
    GROUP BY customer_id, (transaction_ts AT TIME ZONE 'UTC')::date
),
big_days AS (                    -- strictly greater than 100.00 (exactly 100.00 does not count)
    SELECT customer_id, spend_date
    FROM daily_spend
    WHERE day_total > 100.00
),
runs AS (                        -- maximal runs of consecutive qualifying days
    SELECT customer_id,
           MIN(spend_date) AS run_start,
           MAX(spend_date) AS run_end,
           COUNT(*)::int   AS run_days
    FROM (
        SELECT customer_id,
               spend_date,
               spend_date
                 - (ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY spend_date))::int AS island_key
        FROM big_days
    ) b
    GROUP BY customer_id, island_key
    HAVING COUNT(*) >= 5
)
SELECT DISTINCT ON (customer_id)  -- earliest qualifying run per customer
       customer_id,
       run_start,
       run_end,
       run_days
FROM runs
ORDER BY customer_id, run_start;
