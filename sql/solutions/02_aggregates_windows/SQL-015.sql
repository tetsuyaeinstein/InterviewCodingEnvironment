-- SQL-015 reference solution (a): dense month calendar (with one month of lookback) + LAG.
WITH params AS (
    SELECT DATE '2025-02-01' AS first_month,      -- first report month
           DATE '2025-12-01' AS last_month        -- last report month
),
months AS (                                       -- dense: one row per store per month, Jan..Dec
    SELECT s.store_id, g::date AS month_start
    FROM params p
    CROSS JOIN (VALUES (4), (5)) AS s(store_id)
    CROSS JOIN LATERAL generate_series(p.first_month - INTERVAL '1 month', p.last_month, INTERVAL '1 month') AS g
),
monthly AS (                                      -- sparse: only months with completed sales
    SELECT t.store_id,
           date_trunc('month', t.transaction_ts AT TIME ZONE 'UTC')::date AS month_start,
           SUM(t.gross_amount) AS revenue
    FROM transactions t
    WHERE t.store_id IN (4, 5)
      AND t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'   -- includes the lookback month
      AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
    GROUP BY t.store_id, date_trunc('month', t.transaction_ts AT TIME ZONE 'UTC')::date
),
series AS (
    SELECT m.store_id,
           m.month_start,
           COALESCE(r.revenue, 0) AS revenue
    FROM months m
    LEFT JOIN monthly r ON r.store_id = m.store_id AND r.month_start = m.month_start
),
with_prev AS (
    SELECT store_id,
           month_start,
           revenue,
           LAG(revenue) OVER (PARTITION BY store_id ORDER BY month_start) AS prev_month_revenue
    FROM series
)
SELECT store_id,
       month_start,
       revenue,
       prev_month_revenue,
       ROUND(100 * (revenue - prev_month_revenue) / NULLIF(prev_month_revenue, 0), 2) AS mom_change_pct
FROM with_prev, params
WHERE month_start >= params.first_month;          -- drop the lookback month AFTER LAG has used it
