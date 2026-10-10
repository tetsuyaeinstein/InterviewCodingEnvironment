-- SQL-022 reference solution (a): ROW_NUMBER island key on DISTINCT purchase days.
-- Every maximal run of consecutive UTC purchase days is one island; keep islands of >= 3 days.
WITH purchase_days AS (          -- grain: one row per customer per UTC purchase date
    SELECT DISTINCT
           customer_id,
           (transaction_ts AT TIME ZONE 'UTC')::date AS purchase_date
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL
),
islands AS (                     -- consecutive dates share the same (date - row_number)
    SELECT customer_id,
           purchase_date,
           purchase_date
             - (ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY purchase_date))::int AS island_key
    FROM purchase_days
)
SELECT customer_id,
       MIN(purchase_date)      AS streak_start,
       MAX(purchase_date)      AS streak_end,
       COUNT(*)::int           AS streak_days   -- = streak_end - streak_start + 1 (days are distinct)
FROM islands
GROUP BY customer_id, island_key
HAVING COUNT(*) >= 3;
