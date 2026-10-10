-- SQL-016 reference solution (a): pre-aggregate completed purchases, LEFT JOIN from customers.
WITH purchases AS (                                   -- one row per buying customer
    SELECT customer_id,
           MIN(transaction_ts) AS first_ts,
           MAX(transaction_ts) AS last_ts,
           COUNT(*)            AS completed_purchases
    FROM transactions
    WHERE transaction_status = 'COMPLETED'            -- pending/cancelled never count
      AND customer_id IS NOT NULL
    GROUP BY customer_id
)
SELECT c.customer_id,
       (c.registered_at AT TIME ZONE 'UTC')::date                      AS registration_date,
       (p.first_ts      AT TIME ZONE 'UTC')::date                      AS first_purchase_date,
       (p.last_ts       AT TIME ZONE 'UTC')::date                      AS last_purchase_date,
       COALESCE(p.completed_purchases, 0)                              AS completed_purchases,
       (p.first_ts AT TIME ZONE 'UTC')::date
         - (c.registered_at AT TIME ZONE 'UTC')::date                  AS days_to_first_purchase  -- date - date = calendar days
FROM customers c
LEFT JOIN purchases p ON p.customer_id = c.customer_id;              -- keeps never-purchasing customers
