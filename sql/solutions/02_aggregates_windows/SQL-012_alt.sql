-- SQL-012 alternative (b): "max below the max", no window functions.
-- second = MAX(amount) over the rows strictly below the store's maximum. The LEFT JOIN keeps stores
-- that have no such row (one distinct amount) with a NULL second value.
WITH scoped AS (
    SELECT store_id, gross_amount
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
      AND transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
),
store_max AS (
    SELECT store_id, MAX(gross_amount) AS highest_amount
    FROM scoped
    GROUP BY store_id
)
SELECT m.store_id,
       m.highest_amount,
       MAX(s.gross_amount) AS second_highest_amount
FROM store_max m
LEFT JOIN scoped s
       ON s.store_id = m.store_id
      AND s.gross_amount < m.highest_amount     -- strictly smaller: duplicates of the max never qualify
GROUP BY m.store_id, m.highest_amount;
