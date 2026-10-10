-- SQL-052 reference solution: replace "cast the column, compare with a date" by a half-open
-- range on the bare column. Explicit +00 offsets make the bounds independent of the session
-- TimeZone (the original ::date cast silently depended on it).
SELECT store_id,
       count(*)          AS completed_txns,
       sum(gross_amount) AS gross_sales
FROM transactions
WHERE transaction_status = 'COMPLETED'
  AND transaction_ts >= TIMESTAMPTZ '2025-02-28 00:00:00+00'   -- first instant of the day
  AND transaction_ts <  TIMESTAMPTZ '2025-03-01 00:00:00+00'   -- first instant of the next day (excluded)
GROUP BY store_id;
