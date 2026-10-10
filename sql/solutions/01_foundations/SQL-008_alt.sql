-- SQL-008 alternative (b): ranks without window functions (portable to engines/versions without
-- RANK/DENSE_RANK, and a good way to prove you understand what the ranks mean):
--   dense rank = 1 + number of DISTINCT revenue values strictly above mine
--   rank       = 1 + number of categories strictly above me
WITH category_revenue AS (
    SELECT pc.category_name,
           SUM(i.quantity * i.unit_price)                     AS gross_revenue,
           SUM(i.discount_amount)                             AS discount_amount,
           SUM(i.quantity * i.unit_price - i.discount_amount) AS net_revenue
    FROM transactions t
    JOIN transaction_items  i  ON i.transaction_id = t.transaction_id
    JOIN products           p  ON p.product_id     = i.product_id
    JOIN product_categories pc ON pc.category_id   = p.category_id
    WHERE t.store_id = 5
      AND t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= TIMESTAMPTZ '2025-11-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2025-12-01 00:00:00+00'
    GROUP BY pc.category_id, pc.category_name
),
ranked AS (
    SELECT c.*,
           1 + (SELECT COUNT(DISTINCT h.net_revenue) FROM category_revenue h WHERE h.net_revenue > c.net_revenue) AS revenue_dense_rank,
           1 + (SELECT COUNT(*)                      FROM category_revenue h WHERE h.net_revenue > c.net_revenue) AS revenue_rank
    FROM category_revenue c
)
SELECT category_name, gross_revenue, discount_amount, net_revenue, revenue_dense_rank, revenue_rank
FROM ranked
WHERE revenue_dense_rank <= 2
ORDER BY net_revenue DESC, category_name;
