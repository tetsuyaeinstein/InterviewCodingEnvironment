-- SQL-051 reference solution: a plain, sargable statement query.
-- All predicates are on raw columns, the month is a half-open UTC range, and the ORDER BY has a
-- unique tie-breaker so the output (and any pagination built on it) is deterministic.
SELECT transaction_id,
       transaction_ts,
       store_id,
       gross_amount
FROM transactions
WHERE customer_id = 1001
  AND transaction_status = 'COMPLETED'
  AND transaction_ts >= TIMESTAMPTZ '2024-12-01 00:00:00+00'
  AND transaction_ts <  TIMESTAMPTZ '2025-01-01 00:00:00+00'
ORDER BY transaction_ts, transaction_id;
