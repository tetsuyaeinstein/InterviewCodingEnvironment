-- SQL-038 reference solution (b): window function stamps every customer-month row with the
-- customer's cohort month; one conditional aggregation then counts cohort / +1 / +2 in a single
-- pass (no joins back to the activity set).
WITH activity AS (
    SELECT DISTINCT
           customer_id,
           date_trunc('month', transaction_ts AT TIME ZONE 'UTC')::date AS active_month
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL
),
stamped AS (
    SELECT customer_id, active_month,
           MIN(active_month) OVER (PARTITION BY customer_id) AS cohort_month
    FROM activity
),
agg AS (
    SELECT cohort_month,
           COUNT(*) FILTER (WHERE active_month = cohort_month)                          AS cohort_size,
           COUNT(*) FILTER (WHERE active_month = (cohort_month + INTERVAL '1 month')::date) AS month1_customers,
           COUNT(*) FILTER (WHERE active_month = (cohort_month + INTERVAL '2 month')::date) AS month2_customers
    FROM stamped
    GROUP BY cohort_month
)
SELECT cohort_month, cohort_size, month1_customers, month2_customers,
       CASE WHEN cohort_month + INTERVAL '1 month' <= DATE '2025-12-01'
            THEN ROUND(month1_customers::numeric / cohort_size, 2) END AS month1_rate,
       CASE WHEN cohort_month + INTERVAL '2 month' <= DATE '2025-12-01'
            THEN ROUND(month2_customers::numeric / cohort_size, 2) END AS month2_rate
FROM agg
WHERE cohort_month >= DATE '2025-01-01' AND cohort_month < DATE '2026-01-01';
