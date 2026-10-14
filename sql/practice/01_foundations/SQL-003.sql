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

-- select *
-- from transactions;

with last_90_days as (
    select c.customer_id
        , max(t.transaction_ts) as last_purchased_date
        , count(*) filter (
            where t.transaction_ts >= '2025-10-03 00:00:00+00'::timestamptz
        ) as completed_txs_in_period
    from customers c
    left join transactions t
    on c.customer_id = t.customer_id
        AND t.transaction_ts < '2026-01-01 00:00:00+00'::timestamptz
        and t.transaction_status = 'COMPLETED'
    group by c.customer_id
)

select customer_id
    , (last_purchased_date AT TIME ZONE 'UTC')::date last_completed_purchase_date
from last_90_days
where completed_txs_in_period = 0
order by customer_id;

-- select *
-- from transactions
-- where customer_id = 31;

-- select c.customer_id
--     , t.transaction_ts
-- from customers c
-- left join transactions t
-- on c.customer_id = t.customer_id
--     AND t.transaction_ts < '2026-01-01 00:00:00+00'::timestamptz
--     and t.transaction_status = 'COMPLETED'
-- where c.customer_id = 35;

-- select c.customer_id
--     , max(t.transaction_ts) as last_purchased_date
--     , count(*) filter (
--         where t.transaction_ts >= '2025-10-03 00:00:00+00'::timestamptz
--     ) as completed_txs_in_period
-- from customers c
-- left join transactions t
-- on c.customer_id = t.customer_id
--     AND t.transaction_ts < '2026-01-01 00:00:00+00'::timestamptz
--     and t.transaction_status = 'COMPLETED'
-- where c.customer_id = 35
-- group by c.customer_id;

-- select count(null)

-- <<< end of answer <<<
