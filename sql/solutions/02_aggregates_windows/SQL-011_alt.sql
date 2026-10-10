-- SQL-011 alternative (b): PostgreSQL DISTINCT ON.
-- DISTINCT ON (customer_id) keeps the FIRST row of each customer_id group in ORDER BY order,
-- so the ORDER BY must start with the DISTINCT ON key and then express "latest, highest id".
SELECT DISTINCT ON (customer_id)
       customer_id,
       transaction_id,
       transaction_ts,
       store_id,
       gross_amount
FROM transactions
WHERE transaction_status = 'COMPLETED'
  AND customer_id IS NOT NULL
ORDER BY customer_id, transaction_ts DESC, transaction_id DESC;
