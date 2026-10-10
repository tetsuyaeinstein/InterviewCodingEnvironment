-- SQL-058 reference solution (a): build the calendar with generate_series, then anti-join the days
-- that have at least one COMPLETED sale. Integer series + date arithmetic avoids time zone surprises
-- (generate_series over dates returns timestamptz).
WITH calendar AS (
    SELECT DATE '2025-01-01' + g AS sale_date
    FROM generate_series(0, DATE '2025-03-31' - DATE '2025-01-01') AS g     -- 0..89 = 90 days, both ends inclusive
),
sale_days AS (
    SELECT DISTINCT (transaction_ts AT TIME ZONE 'UTC')::date AS sale_date
    FROM transactions
    WHERE store_id = 4
      AND transaction_status = 'COMPLETED'
      AND transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
      AND transaction_ts <  TIMESTAMPTZ '2025-04-01 00:00:00+00'
)
SELECT c.sale_date,
       EXTRACT(isodow FROM c.sale_date)::int AS iso_weekday
FROM calendar c
LEFT JOIN sale_days s USING (sale_date)
WHERE s.sale_date IS NULL;
