-- =============================================================================
-- SQL-003 | Customers inactive in the last 90 days
-- Level: easy | Target time: ~12 min | Mode: query
-- Question: sql/questions/01_foundations/SQL-003.md   (python -m lab show SQL-003)
-- Tables  : customers, transactions
-- Output  : customer_id, last_completed_purchase_date
-- Run     : python -m lab run SQL-003        Check: python -m lab check SQL-003
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>

-- select c.customer_id
--     , lt.last_completed_purchase_date
-- from customers c
-- left join (
--     select customer_id
--         , max(transaction_ts AT Time ZONe 'UTC')::date as last_completed_purchase_date
--     from transactions
--     where transaction_ts AT time zone 'UTC' >= '2025-10-03 00:00:00+00'::timestamptz
--     and transaction_ts AT time zone 'UTC' < '2026-01-01 00:00:00+00'::timestamptz
--     and transaction_status = 'COMPLETED'
--     group by customer_id
-- ) lt
-- on lt.customer_id = c.customer_id

WITH per_customer AS (
    SELECT c.customer_id,
           MAX(t.transaction_ts) AS last_completed_ts,
           COUNT(t.transaction_id) FILTER (
               WHERE t.transaction_ts >= TIMESTAMPTZ '2025-10-03 00:00:00+00'
           )                     AS completed_in_window
    FROM customers c
    LEFT JOIN transactions t
           ON t.customer_id = c.customer_id
          AND t.transaction_status = 'COMPLETED'                      -- in ON, so customers without purchases survive
          AND t.transaction_ts < TIMESTAMPTZ '2026-01-01 00:00:00+00'  -- nothing after the anchor date counts
    GROUP BY c.customer_id
)
SELECT customer_id,
       (last_completed_ts AT TIME ZONE 'UTC')::date AS last_completed_purchase_date   -- NULL if never purchased
FROM per_customer
WHERE completed_in_window = 0;

-- select *
-- from transactions
-- where customer_id = 35
-- order by transaction_ts desc;


-- <<< end of answer <<<
