-- SQL-021 reference solution (a): ROW_NUMBER gaps-and-islands on distinct purchase days.
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
           purchase_date - (ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY purchase_date))::int AS island_key
    FROM purchase_days
),
streaks AS (
    SELECT customer_id, island_key, COUNT(*) AS streak_days
    FROM islands
    GROUP BY customer_id, island_key
)
SELECT DISTINCT customer_id
FROM streaks
WHERE streak_days >= 5;
