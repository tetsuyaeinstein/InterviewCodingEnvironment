-- SQL-019 reference solution (a): per-product aggregate, then a window total over those rows.
WITH product_rev AS (
    SELECT t.store_id,
           i.product_id,
           SUM(i.quantity * i.unit_price - i.discount_amount) AS net_revenue  -- line grain, discounts applied
    FROM transactions t
    JOIN transaction_items i ON i.transaction_id = t.transaction_id
    WHERE t.store_id = 5
      AND t.transaction_status = 'COMPLETED'                           -- the CANCELLED 300.00 basket is out
      AND t.transaction_ts >= TIMESTAMPTZ '2025-11-01 00:00:00+00'
      AND t.transaction_ts <  TIMESTAMPTZ '2025-12-01 00:00:00+00'
    GROUP BY t.store_id, i.product_id                                  -- product 8's two lines -> one row
)
SELECT store_id,
       product_id,
       net_revenue,
       SUM(net_revenue) OVER ()                                         AS store_net_revenue,
       ROUND(100 * net_revenue / SUM(net_revenue) OVER (), 2)           AS pct_of_store_revenue
FROM product_rev;
