-- SQL-013 reference solution (a): dense calendar (with 6 days of lookback) + ROWS frame.
-- On a DENSE calendar (exactly one row per day, no gaps), "6 PRECEDING rows" = "6 preceding days".
WITH params (store_id, first_day, last_day) AS (
    VALUES (4, DATE '2025-01-15', DATE '2025-03-31'),
           (5, DATE '2025-11-01', DATE '2025-12-07')
),
calendar AS (            -- starts 6 days early so the first report days see their full window
    SELECT p.store_id, p.first_day, d::date AS business_date
    FROM params p
    CROSS JOIN LATERAL generate_series(p.first_day - 6, p.last_day, INTERVAL '1 day') AS g(d)
),
daily AS (               -- completed revenue per store per UTC day (sparse: only days with sales)
    SELECT t.store_id,
           (t.transaction_ts AT TIME ZONE 'UTC')::date AS business_date,
           SUM(t.gross_amount) AS revenue
    FROM transactions t
    JOIN params p ON p.store_id = t.store_id
    WHERE t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= (p.first_day - 6)::timestamp AT TIME ZONE 'UTC'   -- sargable range
      AND t.transaction_ts <  (p.last_day + 1)::timestamp AT TIME ZONE 'UTC'
    GROUP BY t.store_id, (t.transaction_ts AT TIME ZONE 'UTC')::date
),
dense AS (
    SELECT c.store_id,
           c.first_day,
           c.business_date,
           COALESCE(d.revenue, 0) AS daily_revenue
    FROM calendar c
    LEFT JOIN daily d ON d.store_id = c.store_id AND d.business_date = c.business_date
),
rolled AS (
    SELECT store_id,
           first_day,
           business_date,
           daily_revenue,
           SUM(daily_revenue) OVER (PARTITION BY store_id
                                    ORDER BY business_date
                                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7d_revenue
    FROM dense
)
SELECT store_id, business_date, daily_revenue, rolling_7d_revenue
FROM rolled
WHERE business_date >= first_day;      -- drop the lookback days only AFTER the window ran
