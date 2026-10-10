-- SQL-010 reference solution (a): semi-join for A, anti-join (NOT EXISTS) for B.
-- Both A and B are evaluated with the SAME purchase definition: COMPLETED, known customer,
-- UTC business date in [2025-01-01, 2025-07-01).
WITH purchases AS (                         -- one row per (customer, product) line in scope
    SELECT t.customer_id, i.product_id
    FROM transactions t
    JOIN transaction_items i ON i.transaction_id = t.transaction_id
    WHERE t.transaction_status = 'COMPLETED'
      AND t.customer_id IS NOT NULL
      AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2025-07-01 00:00:00+00'
      AND i.product_id IN (1, 2)
)
SELECT DISTINCT a.customer_id               -- a customer can have many A lines
FROM purchases a
WHERE a.product_id = 1
  AND NOT EXISTS (                          -- NULL-safe, unlike NOT IN
      SELECT 1
      FROM purchases b
      WHERE b.customer_id = a.customer_id
        AND b.product_id = 2
  );
