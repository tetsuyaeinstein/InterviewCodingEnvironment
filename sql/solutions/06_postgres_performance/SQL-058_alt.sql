-- SQL-058 alternative (b): the calendar from a recursive CTE, and NOT EXISTS for the anti-join.
-- Same result; the recursive form is portable to engines without generate_series (SQL Server, Synapse).
WITH RECURSIVE calendar (sale_date) AS (
    SELECT DATE '2025-01-01'
    UNION ALL
    SELECT sale_date + 1
    FROM calendar
    WHERE sale_date < DATE '2025-03-31'
)
SELECT c.sale_date,
       EXTRACT(isodow FROM c.sale_date)::int AS iso_weekday
FROM calendar c
WHERE NOT EXISTS (
    SELECT 1
    FROM transactions t
    WHERE t.store_id = 4
      AND t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= c.sale_date::timestamp AT TIME ZONE 'UTC'
      AND t.transaction_ts <  (c.sale_date + 1)::timestamp AT TIME ZONE 'UTC'
);
