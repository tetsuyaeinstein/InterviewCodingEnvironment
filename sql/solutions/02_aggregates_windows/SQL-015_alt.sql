-- SQL-015 alternative (b): no window function. Join each report month to "its month minus one"
-- by date arithmetic. The previous month never has to be in the result set, so there is no
-- lookback-row trick and gaps in the series cannot shift the comparison.
WITH report_months AS (
    SELECT s.store_id, g::date AS month_start
    FROM (VALUES (4), (5)) AS s(store_id)
    CROSS JOIN generate_series(DATE '2025-02-01', DATE '2025-12-01', INTERVAL '1 month') AS g
),
monthly AS (
    SELECT store_id,
           date_trunc('month', transaction_ts AT TIME ZONE 'UTC')::date AS month_start,
           SUM(gross_amount) AS revenue
    FROM transactions
    WHERE store_id IN (4, 5)
      AND transaction_status = 'COMPLETED'
      AND transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
      AND transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
    GROUP BY 1, 2
),
joined AS (
    SELECT rm.store_id,
           rm.month_start,
           COALESCE(cur.revenue, 0) AS revenue,
           COALESCE(prv.revenue, 0) AS prev_month_revenue
    FROM report_months rm
    LEFT JOIN monthly cur ON cur.store_id = rm.store_id AND cur.month_start = rm.month_start
    LEFT JOIN monthly prv ON prv.store_id = rm.store_id
                         AND prv.month_start = (rm.month_start - INTERVAL '1 month')::date
)
SELECT store_id,
       month_start,
       revenue,
       prev_month_revenue,
       CASE WHEN prev_month_revenue = 0 THEN NULL                  -- explicit NULL policy
            ELSE ROUND(100 * (revenue - prev_month_revenue) / prev_month_revenue, 2)
       END AS mom_change_pct
FROM joined;
