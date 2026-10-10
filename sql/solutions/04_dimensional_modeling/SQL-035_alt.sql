-- SQL-035 alternative: build the label from EXTRACT(isoyear) / EXTRACT(week), and filter on UTC
-- instants instead of local dates. The window bounds are New York midnights converted to
-- timestamptz, so the predicate stays sargable on transactions(transaction_ts).
WITH bounds AS (
    SELECT TIMESTAMP '2024-12-30 00:00:00' AT TIME ZONE 'America/New_York' AS from_ts,   -- = 05:00 UTC (EST)
           TIMESTAMP '2025-12-29 00:00:00' AT TIME ZONE 'America/New_York' AS to_ts
),
purchases AS (
    SELECT t.customer_id,
           t.transaction_ts AT TIME ZONE 'America/New_York' AS ny_local          -- timestamp without tz
    FROM transactions t
    CROSS JOIN bounds b
    WHERE t.transaction_status = 'COMPLETED'
      AND t.customer_id IS NOT NULL
      AND t.transaction_ts >= b.from_ts
      AND t.transaction_ts <  b.to_ts
)
SELECT EXTRACT(isoyear FROM ny_local)::int || '-W' || lpad(EXTRACT(week FROM ny_local)::int::text, 2, '0') AS iso_week,
       (date_trunc('week', ny_local))::date AS week_start,
       COUNT(DISTINCT customer_id)          AS active_customers,
       COUNT(*)                             AS purchases
FROM purchases
GROUP BY 1, 2;
