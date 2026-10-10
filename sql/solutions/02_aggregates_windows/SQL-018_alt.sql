-- SQL-018 alternative (b): per-region LATERAL top-N with FETCH FIRST ... WITH TIES.
-- WITH TIES keeps every row that ties with the last kept row, which is exactly "RANK() <= 3".
-- Rank and region total are computed separately because the LATERAL only sees the top rows.
WITH region_product AS (
    SELECT s.region,
           i.product_id,
           SUM(i.quantity * i.unit_price - i.discount_amount) AS net_revenue
    FROM transactions t
    JOIN transaction_items i ON i.transaction_id = t.transaction_id
    JOIN stores s            ON s.store_id       = t.store_id
    WHERE t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
    GROUP BY s.region, i.product_id
),
regions AS (
    SELECT region, SUM(net_revenue) AS region_total
    FROM region_product
    GROUP BY region
)
SELECT g.region,
       -- competition rank = 1 + number of products in the region with strictly more revenue
       (1 + (SELECT COUNT(*) FROM region_product x
              WHERE x.region = g.region AND x.net_revenue > top.net_revenue))::int AS revenue_rank,
       top.product_id,
       p.product_name,
       top.net_revenue,
       ROUND(100 * top.net_revenue / g.region_total, 2) AS pct_of_region_revenue
FROM regions g
CROSS JOIN LATERAL (
    SELECT rp.product_id, rp.net_revenue
    FROM region_product rp
    WHERE rp.region = g.region
    ORDER BY rp.net_revenue DESC
    FETCH FIRST 3 ROWS WITH TIES
) AS top
JOIN products p ON p.product_id = top.product_id;
