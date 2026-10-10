-- SQL-021 reference solution (b): LAG + running sum of "streak breaks" (sessionization style).
-- A new streak starts whenever the previous purchase day is not exactly yesterday.
WITH purchase_days AS (
    SELECT DISTINCT
           customer_id,
           (transaction_ts AT TIME ZONE 'UTC')::date AS purchase_date
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL
),
flagged AS (
    SELECT customer_id,
           purchase_date,
           CASE WHEN purchase_date - LAG(purchase_date) OVER w = 1 THEN 0 ELSE 1 END AS starts_new_streak
    FROM purchase_days
    WINDOW w AS (PARTITION BY customer_id ORDER BY purchase_date)
),
numbered AS (
    SELECT customer_id,
           purchase_date,
           SUM(starts_new_streak) OVER (PARTITION BY customer_id ORDER BY purchase_date
                                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS streak_no
    FROM flagged
)
SELECT DISTINCT customer_id          -- DISTINCT is applied after GROUP BY/HAVING
FROM numbered
GROUP BY customer_id, streak_no
HAVING COUNT(*) >= 5;
