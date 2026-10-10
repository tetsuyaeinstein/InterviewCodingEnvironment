-- SQL-002 reference solution: half-open range filter on the raw timestamp, then group by store and UTC date.
SELECT store_id,
       (transaction_ts AT TIME ZONE 'UTC')::date AS business_date,
       COUNT(*)                                   AS completed_txn_count,
       SUM(gross_amount)                          AS gross_amount
FROM transactions
WHERE transaction_status = 'COMPLETED'
  -- [2025-03-01 00:00 UTC, 2025-03-17 00:00 UTC): business dates 03-01 ... 03-16 inclusive.
  -- Filtering the bare column keeps the predicate sargable for the (store_id, transaction_ts) index.
  AND transaction_ts >= TIMESTAMPTZ '2025-03-01 00:00:00+00'
  AND transaction_ts <  TIMESTAMPTZ '2025-03-17 00:00:00+00'
  -- guest checkouts (customer_id NULL) are store sales too: no customer filter, no join to customers
GROUP BY store_id, (transaction_ts AT TIME ZONE 'UTC')::date;
