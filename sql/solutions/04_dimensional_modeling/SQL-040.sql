-- SQL-040 reference solution (a): aggregate each fact at its OWN grain and recognition month, then
-- combine on a month grid. Header (sales), line (units) and refund tables are never joined to each other
-- before aggregation, so no join can multiply another table's rows.
WITH months AS (
    SELECT m::date AS month_start
    FROM generate_series(DATE '2025-10-01', DATE '2026-01-01', INTERVAL '1 month') AS m
),
sales AS (                                    -- header grain: recognised at transaction_ts
    SELECT date_trunc('month', t.transaction_ts AT TIME ZONE 'UTC')::date AS month_start,
           COUNT(*)            AS orders,
           SUM(t.gross_amount) AS gross_sales
    FROM transactions t
    WHERE t.transaction_status = 'COMPLETED'
    GROUP BY 1
),
units AS (                                    -- line grain: same recognition rule, separate aggregation
    SELECT date_trunc('month', t.transaction_ts AT TIME ZONE 'UTC')::date AS month_start,
           SUM(ti.quantity) AS units_sold
    FROM transactions t
    JOIN transaction_items ti ON ti.transaction_id = t.transaction_id
    WHERE t.transaction_status = 'COMPLETED'
    GROUP BY 1
),
refunded AS (                                 -- refund grain: recognised at refund_ts, whatever the sale month
    SELECT date_trunc('month', r.refund_ts AT TIME ZONE 'UTC')::date AS month_start,
           SUM(r.refund_amount) AS refunded_amount
    FROM refunds r
    GROUP BY 1
)
SELECT m.month_start,
       COALESCE(s.orders, 0)                          AS orders,
       COALESCE(u.units_sold, 0)                      AS units_sold,
       COALESCE(s.gross_sales, 0)                     AS gross_sales,
       COALESCE(r.refunded_amount, 0)                 AS refunded_amount,
       COALESCE(s.gross_sales, 0) - COALESCE(r.refunded_amount, 0) AS net_sales
FROM months m
LEFT JOIN sales    s ON s.month_start = m.month_start
LEFT JOIN units    u ON u.month_start = m.month_start
LEFT JOIN refunded r ON r.month_start = m.month_start;
