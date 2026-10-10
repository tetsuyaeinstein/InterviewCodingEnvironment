-- SQL-059 reference solution (a): half-open range on the bare partition key with constant bounds.
-- Both bounds are constants, so the planner prunes at PLAN time and only fact_sales_p2025_12
-- (and neither the other monthly partitions nor the default partition) appears in the plan.
SELECT store_id,
       count(*)        AS line_count,
       sum(net_amount) AS net_sales
FROM fact_sales_partitioned
WHERE sale_date >= DATE '2025-12-01'
  AND sale_date <  DATE '2026-01-01'
GROUP BY store_id;
