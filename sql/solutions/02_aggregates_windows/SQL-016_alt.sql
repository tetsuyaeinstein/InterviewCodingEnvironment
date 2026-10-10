-- SQL-016 alternative (b): window functions on the joined rows, then one row per customer.
-- The status condition lives in the JOIN's ON clause so customers without completed purchases
-- keep one row with NULL transaction columns (a WHERE filter would remove them).
-- LAST_VALUE needs an explicit full frame: with ORDER BY the default frame ends at the current
-- row, so LAST_VALUE would just return the current row's value.
WITH joined AS (
    SELECT c.customer_id,
           (c.registered_at AT TIME ZONE 'UTC')::date AS registration_date,
           (t.transaction_ts AT TIME ZONE 'UTC')::date AS purchase_date,
           t.transaction_id
    FROM customers c
    LEFT JOIN transactions t
           ON t.customer_id = c.customer_id
          AND t.transaction_status = 'COMPLETED'
),
windowed AS (
    SELECT customer_id,
           registration_date,
           FIRST_VALUE(purchase_date) OVER w AS first_purchase_date,
           LAST_VALUE(purchase_date)  OVER w AS last_purchase_date,
           COUNT(transaction_id)      OVER w AS completed_purchases,   -- counts non-NULL ids only
           ROW_NUMBER()               OVER w AS rn
    FROM joined
    WINDOW w AS (PARTITION BY customer_id
                 ORDER BY purchase_date NULLS LAST
                 ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
)
SELECT customer_id,
       registration_date,
       first_purchase_date,
       last_purchase_date,
       completed_purchases,
       first_purchase_date - registration_date AS days_to_first_purchase
FROM windowed
WHERE rn = 1;
