-- SQL-014 reference solution: aggregate to customer-day grain, then a per-customer running sum.
WITH daily AS (
    SELECT customer_id,
           (transaction_ts AT TIME ZONE 'UTC')::date AS purchase_date,
           SUM(gross_amount)                         AS daily_spend
    FROM transactions
    WHERE transaction_status = 'COMPLETED'                            -- cancelled/pending spend is not spend
      AND customer_id BETWEEN 15 AND 26
      AND transaction_ts >= TIMESTAMPTZ '2025-09-01 00:00:00+00'      -- half-open campaign window (UTC)
      AND transaction_ts <  TIMESTAMPTZ '2025-11-01 00:00:00+00'
    GROUP BY customer_id, (transaction_ts AT TIME ZONE 'UTC')::date   -- several purchases a day -> one row
)
SELECT customer_id,
       purchase_date,
       daily_spend,
       SUM(daily_spend) OVER (PARTITION BY customer_id                 -- restarts for every customer
                              ORDER BY purchase_date
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
FROM daily;
