-- SQL-053 reference solution: equality column first, then the range/sort column.
-- (customer_id, transaction_ts): the index entries of customer 1001 are adjacent and already in
-- transaction_ts order, so the range is one contiguous slice, no Sort node is needed, and LIMIT 20
-- stops after 20 index entries.
CREATE INDEX ix_txn_copy_cust_ts ON txn_copy (customer_id, transaction_ts);

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
