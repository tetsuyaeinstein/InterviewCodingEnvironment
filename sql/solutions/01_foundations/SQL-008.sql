-- SQL-008 reference solution (a): aggregate to category grain, then rank with window functions.
WITH category_revenue AS (
    SELECT pc.category_id,
           pc.category_name,
           SUM(i.quantity * i.unit_price)                     AS gross_revenue,
           SUM(i.discount_amount)                             AS discount_amount,
           SUM(i.quantity * i.unit_price - i.discount_amount) AS net_revenue
    FROM transactions t
    JOIN transaction_items  i  ON i.transaction_id = t.transaction_id
    JOIN products           p  ON p.product_id     = i.product_id
    JOIN product_categories pc ON pc.category_id   = p.category_id
    WHERE t.store_id = 5
      AND t.transaction_status = 'COMPLETED'                         -- the CANCELLED 300.00 order is not revenue
      AND t.transaction_ts >= TIMESTAMPTZ '2025-11-01 00:00:00+00'   -- November 2025 UTC, half-open
      AND t.transaction_ts <  TIMESTAMPTZ '2025-12-01 00:00:00+00'
    GROUP BY pc.category_id, pc.category_name
),
ranked AS (
    SELECT category_name,
           gross_revenue,
           discount_amount,
           net_revenue,
           DENSE_RANK() OVER (ORDER BY net_revenue DESC) AS revenue_dense_rank,  -- 1,1,2,2,3
           RANK()       OVER (ORDER BY net_revenue DESC) AS revenue_rank         -- 1,1,3,3,5
    FROM category_revenue
)
SELECT category_name, gross_revenue, discount_amount, net_revenue, revenue_dense_rank, revenue_rank
FROM ranked
WHERE revenue_dense_rank <= 2              -- the top two revenue LEVELS, every tied category kept
ORDER BY net_revenue DESC, category_name;  -- deterministic order inside a tie
