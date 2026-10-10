-- SQL-059 alternative (b): bounds built by IMMUTABLE functions of constants (make_date). The planner
-- folds them to constants during planning, so pruning is still plan-time. BETWEEN on a date
-- is equally fine here because the column is a date, not a timestamp. (With a timestamp column
-- BETWEEN would include the first instant of the next month.)
SELECT store_id,
       count(*)        AS line_count,
       sum(net_amount) AS net_sales
FROM fact_sales_partitioned
WHERE sale_date BETWEEN make_date(2025, 12, 1) AND make_date(2025, 12, 31)
GROUP BY store_id;
