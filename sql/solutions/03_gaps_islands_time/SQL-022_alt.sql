-- SQL-022 reference solution (b): LAG + running sum of "streak breaks".
-- A purchase day starts a new streak unless the previous purchase day was exactly yesterday.
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
           CASE WHEN LAG(purchase_date) OVER w = purchase_date - 1 THEN 0 ELSE 1 END AS is_streak_start
    FROM purchase_days
    WINDOW w AS (PARTITION BY customer_id ORDER BY purchase_date)
),
numbered AS (                    -- running count of streak starts = streak number per customer
    SELECT customer_id,
           purchase_date,
           SUM(is_streak_start) OVER (PARTITION BY customer_id ORDER BY purchase_date
                                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS streak_no
    FROM flagged
)
SELECT customer_id,
       MIN(purchase_date)                          AS streak_start,
       MAX(purchase_date)                          AS streak_end,
       (MAX(purchase_date) - MIN(purchase_date) + 1) AS streak_days
FROM numbered
GROUP BY customer_id, streak_no
HAVING MAX(purchase_date) - MIN(purchase_date) + 1 >= 3;
