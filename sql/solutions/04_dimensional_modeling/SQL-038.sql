-- SQL-038 reference solution (a): MIN() per customer defines the cohort over ALL history,
-- then LEFT JOIN the customer-month activity twice (month +1 and +2).
WITH activity AS (                     -- grain: one row per customer per active UTC month
    SELECT DISTINCT
           customer_id,
           date_trunc('month', transaction_ts AT TIME ZONE 'UTC')::date AS active_month
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL
),
cohorts AS (                           -- first completed purchase EVER (do not pre-filter to 2025!)
    SELECT customer_id, MIN(active_month) AS cohort_month
    FROM activity
    GROUP BY customer_id
)
SELECT c.cohort_month,
       COUNT(*)                         AS cohort_size,
       COUNT(a1.customer_id)            AS month1_customers,
       COUNT(a2.customer_id)            AS month2_customers,
       -- the data ends 2025-12-31: a month after December 2025 is not observable, so NULL, not 0.00
       CASE WHEN c.cohort_month + INTERVAL '1 month' <= DATE '2025-12-01'
            THEN ROUND(COUNT(a1.customer_id)::numeric / COUNT(*), 2) END AS month1_rate,
       CASE WHEN c.cohort_month + INTERVAL '2 month' <= DATE '2025-12-01'
            THEN ROUND(COUNT(a2.customer_id)::numeric / COUNT(*), 2) END AS month2_rate
FROM cohorts c
LEFT JOIN activity a1
       ON a1.customer_id = c.customer_id
      AND a1.active_month = (c.cohort_month + INTERVAL '1 month')::date
LEFT JOIN activity a2
       ON a2.customer_id = c.customer_id
      AND a2.active_month = (c.cohort_month + INTERVAL '2 month')::date
WHERE c.cohort_month >= DATE '2025-01-01'
  AND c.cohort_month <  DATE '2026-01-01'
GROUP BY c.cohort_month;
