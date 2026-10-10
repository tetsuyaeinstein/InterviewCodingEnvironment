-- SQL-023 reference solution: longest 2025 streak per customer, earliest start wins ties.
-- Purchases outside calendar 2025 are ignored, so a run crossing 2024-12-31 is clipped at 2025-01-01.
WITH purchase_days AS (          -- one row per customer per UTC purchase date in 2025
    SELECT DISTINCT
           customer_id,
           (transaction_ts AT TIME ZONE 'UTC')::date AS purchase_date
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL
      AND transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'   -- sargable half-open range
      AND transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
),
streaks AS (                     -- one row per maximal run of consecutive days
    SELECT customer_id,
           MIN(purchase_date) AS streak_start,
           MAX(purchase_date) AS streak_end,
           COUNT(*)::int      AS streak_days
    FROM (
        SELECT customer_id,
               purchase_date,
               purchase_date
                 - (ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY purchase_date))::int AS island_key
        FROM purchase_days
    ) d
    GROUP BY customer_id, island_key
),
ranked AS (
    SELECT s.*,
           ROW_NUMBER() OVER (PARTITION BY customer_id
                              ORDER BY streak_days DESC, streak_start ASC) AS rn,   -- deterministic tie-break
           COUNT(*)     OVER (PARTITION BY customer_id, streak_days)         AS same_length_streaks
    FROM streaks s
)
SELECT customer_id,
       streak_days         AS longest_streak_days,
       streak_start,
       streak_end,
       same_length_streaks AS tied_streaks
FROM ranked
WHERE rn = 1
  AND streak_days >= 2;
