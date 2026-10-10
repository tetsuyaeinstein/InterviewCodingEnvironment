-- SQL-039 reference solution (a): resolve the region AS OF each purchase, reduce to the target
-- grain (month x region x customer) with DISTINCT, then count customers per month and region.
WITH purchases AS (
    SELECT t.customer_id,
           date_trunc('month', t.transaction_ts AT TIME ZONE 'UTC')::date AS purchase_month,
           d.region                                                       AS region_at_purchase   -- NULL: unknown or no version
    FROM transactions t
    LEFT JOIN dim_customer_scd2 d
           ON d.customer_id = t.customer_id
          AND t.transaction_ts >= d.effective_from
          AND t.transaction_ts <  d.effective_to
    WHERE t.transaction_status = 'COMPLETED'
      AND t.customer_id IS NOT NULL
      AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
),
customer_month_region AS (          -- the grain of the metric: a customer once per month per region
    SELECT DISTINCT purchase_month, region_at_purchase, customer_id
    FROM purchases
)
SELECT purchase_month,
       region_at_purchase AS region,
       COUNT(*)           AS active_customers
FROM customer_month_region
GROUP BY purchase_month, region_at_purchase;
