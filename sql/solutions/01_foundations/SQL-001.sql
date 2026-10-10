-- SQL-001 reference solution (a): pre-aggregate the fact, then LEFT JOIN from the customer dimension.
-- Grain of the answer = one row per customer, so the customer table drives the query.
WITH completed AS (              -- grain: one row per customer with >= 1 completed transaction
    SELECT customer_id,
           COUNT(*)          AS completed_txn_count,
           SUM(gross_amount) AS total_completed_spend
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
      AND customer_id IS NOT NULL          -- guests can never match a customer anyway; explicit is clearer
    GROUP BY customer_id
)
SELECT c.customer_id,
       COALESCE(x.completed_txn_count, 0)      AS completed_txn_count,     -- no match -> 0, not NULL
       COALESCE(x.total_completed_spend, 0.00) AS total_completed_spend   -- no match -> 0.00, not NULL
FROM customers c
LEFT JOIN completed x ON x.customer_id = c.customer_id;
