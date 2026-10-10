-- SQL-040 reference solution (b): stack the three event streams (sales header, sales lines, refunds)
-- with UNION ALL into one signed "recognition events" set (month, orders, units, sales, refunds) and
-- aggregate once. Nothing is joined, so fan-out is impossible by construction.
WITH events AS (
    SELECT date_trunc('month', t.transaction_ts AT TIME ZONE 'UTC')::date AS month_start,
           1 AS orders, 0 AS units, t.gross_amount AS sales, 0::numeric AS refunds
    FROM transactions t
    WHERE t.transaction_status = 'COMPLETED'
    UNION ALL
    SELECT date_trunc('month', t.transaction_ts AT TIME ZONE 'UTC')::date,
           0, ti.quantity, 0::numeric, 0::numeric
    FROM transaction_items ti
    JOIN transactions t ON t.transaction_id = ti.transaction_id
    WHERE t.transaction_status = 'COMPLETED'
    UNION ALL
    SELECT date_trunc('month', r.refund_ts AT TIME ZONE 'UTC')::date,
           0, 0, 0::numeric, r.refund_amount
    FROM refunds r
)
SELECT g.month_start,
       COALESCE(SUM(e.orders), 0)               AS orders,
       COALESCE(SUM(e.units), 0)                AS units_sold,
       COALESCE(SUM(e.sales), 0)                AS gross_sales,
       COALESCE(SUM(e.refunds), 0)              AS refunded_amount,
       COALESCE(SUM(e.sales - e.refunds), 0)    AS net_sales
FROM generate_series(DATE '2025-10-01', DATE '2026-01-01', INTERVAL '1 month') AS gm(m)
CROSS JOIN LATERAL (SELECT gm.m::date AS month_start) g
LEFT JOIN events e ON e.month_start = g.month_start
GROUP BY g.month_start;
