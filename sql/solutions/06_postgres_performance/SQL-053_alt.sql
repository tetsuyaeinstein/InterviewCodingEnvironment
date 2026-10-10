-- SQL-053 alternative: a covering index. Same key order (equality, then range/sort) plus the
-- selected columns in INCLUDE, so the planner can answer from the index alone (Index Only Scan).
-- Trade-off: a bigger index, more write cost, and heap fetches unless the visibility map is fresh.
CREATE INDEX ix_txn_copy_cust_ts_cov ON txn_copy (customer_id, transaction_ts)
    INCLUDE (transaction_id, store_id, gross_amount);

SELECT transaction_id,
       transaction_ts,
       store_id,
       gross_amount
FROM txn_copy
WHERE customer_id = 1001
  AND transaction_ts >= TIMESTAMPTZ '2025-04-01 00:00:00+00'
  AND transaction_ts <  TIMESTAMPTZ '2025-07-01 00:00:00+00'
ORDER BY transaction_ts
LIMIT 20;
