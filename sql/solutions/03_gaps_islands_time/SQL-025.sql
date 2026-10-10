-- SQL-025 reference solution: February-2025 first-purchase cohort, day-7 and week-1 retention.
-- Retention is measured on UTC calendar dates, not on elapsed hours.
WITH purchase_days AS (          -- one row per customer per UTC purchase date (completed only)
    SELECT DISTINCT
           customer_id,
           (transaction_ts AT TIME ZONE 'UTC')::date AS purchase_date
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL
),
first_purchase AS (              -- first completed purchase over ALL history, not just February
    SELECT customer_id, MIN(purchase_date) AS first_purchase_date
    FROM purchase_days
    GROUP BY customer_id
),
cohort AS (
    SELECT customer_id, first_purchase_date
    FROM first_purchase
    WHERE first_purchase_date >= DATE '2025-02-01'
      AND first_purchase_date <  DATE '2025-03-01'
)
SELECT c.customer_id,
       c.first_purchase_date,
       COALESCE(BOOL_OR(p.purchase_date = c.first_purchase_date + 7), false)          AS retained_day_7,
       COALESCE(BOOL_OR(p.purchase_date BETWEEN c.first_purchase_date + 1
                                            AND c.first_purchase_date + 7), false)    AS retained_week_1
FROM cohort c
LEFT JOIN purchase_days p
       ON p.customer_id   = c.customer_id
      AND p.purchase_date >  c.first_purchase_date        -- only the 7 days after the first day matter
      AND p.purchase_date <= c.first_purchase_date + 7
GROUP BY c.customer_id, c.first_purchase_date;
