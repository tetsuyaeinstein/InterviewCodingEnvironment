-- SQL-011 reference solution (a): ROW_NUMBER over (newest timestamp, highest id) per customer.
WITH ranked AS (
    SELECT transaction_id,
           customer_id,
           store_id,
           transaction_ts,
           gross_amount,
           ROW_NUMBER() OVER (PARTITION BY customer_id
                              ORDER BY transaction_ts DESC, transaction_id DESC) AS rn  -- id breaks timestamp ties
    FROM transactions
    WHERE transaction_status = 'COMPLETED'   -- filter BEFORE ranking: a later PENDING row must not win
      AND customer_id IS NOT NULL            -- guests are not customers
)
SELECT customer_id, transaction_id, transaction_ts, store_id, gross_amount
FROM ranked
WHERE rn = 1;                                -- exactly one row per customer, deterministic
