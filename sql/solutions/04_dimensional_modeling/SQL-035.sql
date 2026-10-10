-- SQL-035 reference solution: convert to New York wall-clock time FIRST, then derive the ISO
-- week (ISO year 'IYYY' + ISO week 'IW'; never calendar year 'YYYY' + 'IW').
WITH purchases AS (
    SELECT customer_id,
           (transaction_ts AT TIME ZONE 'America/New_York')::date AS ny_date   -- DST-aware local date
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL
)
SELECT to_char(ny_date, 'IYYY-"W"IW')                  AS iso_week,
       date_trunc('week', ny_date)::date               AS week_start,      -- ISO weeks start on Monday
       COUNT(DISTINCT customer_id)                     AS active_customers,
       COUNT(*)                                        AS purchases
FROM purchases
WHERE ny_date >= DATE '2024-12-30'                     -- Monday of 2025-W01
  AND ny_date <  DATE '2025-12-29'                     -- Monday of 2026-W01
GROUP BY 1, 2;
