-- SQL-013 alternative (b): report calendar + correlated range sums, no window function.
-- For each report day d the trailing window is the half-open timestamp range [d - 6, d + 1) in UTC,
-- so it naturally reaches back before the report period and never depends on row counts.
WITH params (store_id, first_day, last_day) AS (
    VALUES (4, DATE '2025-01-15', DATE '2025-03-31'),
           (5, DATE '2025-11-01', DATE '2025-12-07')
),
calendar AS (
    SELECT p.store_id, d::date AS business_date
    FROM params p
    CROSS JOIN LATERAL generate_series(p.first_day, p.last_day, INTERVAL '1 day') AS g(d)
)
SELECT c.store_id,
       c.business_date,
       (SELECT COALESCE(SUM(t.gross_amount), 0)
          FROM transactions t
         WHERE t.store_id = c.store_id
           AND t.transaction_status = 'COMPLETED'
           AND t.transaction_ts >= c.business_date::timestamp AT TIME ZONE 'UTC'
           AND t.transaction_ts <  (c.business_date + 1)::timestamp AT TIME ZONE 'UTC') AS daily_revenue,
       (SELECT COALESCE(SUM(t.gross_amount), 0)
          FROM transactions t
         WHERE t.store_id = c.store_id
           AND t.transaction_status = 'COMPLETED'
           AND t.transaction_ts >= (c.business_date - 6)::timestamp AT TIME ZONE 'UTC'
           AND t.transaction_ts <  (c.business_date + 1)::timestamp AT TIME ZONE 'UTC') AS rolling_7d_revenue
FROM calendar c;
