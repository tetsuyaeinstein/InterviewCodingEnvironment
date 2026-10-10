-- SQL-018 reference solution (a): aggregate to (region, product), then rank and total with windows.
WITH region_product AS (                 -- grain: one row per region per product
    SELECT s.region,
           i.product_id,
           SUM(i.quantity * i.unit_price - i.discount_amount) AS net_revenue   -- line grain, no header amount
    FROM transactions t
    JOIN transaction_items i ON i.transaction_id = t.transaction_id
    JOIN stores s            ON s.store_id       = t.store_id               -- region of the STORE
    WHERE t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
    GROUP BY s.region, i.product_id
),
ranked AS (                              -- both windows see ALL products of the region
    SELECT region,
           product_id,
           net_revenue,
           RANK() OVER (PARTITION BY region ORDER BY net_revenue DESC) AS revenue_rank,  -- 1,2,2,4
           SUM(net_revenue) OVER (PARTITION BY region)                AS region_total
    FROM region_product
)
SELECT r.region,
       r.revenue_rank,
       r.product_id,
       p.product_name,
       r.net_revenue,
       ROUND(100 * r.net_revenue / r.region_total, 2) AS pct_of_region_revenue
FROM ranked r
JOIN products p ON p.product_id = r.product_id
WHERE r.revenue_rank <= 3;               -- filter AFTER the total was computed; ties kept
