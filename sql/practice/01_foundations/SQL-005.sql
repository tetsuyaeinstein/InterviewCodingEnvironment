-- =============================================================================
-- SQL-005 | Q4 net spend after refunds without join fan-out
-- Level: medium | Target time: ~20 min | Mode: query
-- Question: sql/questions/01_foundations/SQL-005.md   (python -m lab show SQL-005)
-- Tables  : transactions, transaction_items, refunds
-- Output  : customer_id, completed_txn_count, items_sold, gross_spend, refunded_amount, net_spend
-- Run     : python -m lab run SQL-005        Check: python -m lab check SQL-005
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>

-- select *
-- from transactions;

-- select *
-- from transaction_items;

-- select *
-- from refunds;


; with cte_q4_txs as (
    select *
    from transactions
    where transaction_status = 'COMPLETED'
    and transaction_ts >= '2025-10-01 00:00:00+00'::timestamptz
    and transaction_ts < '2026-01-01 00:00:00+00'::timestamptz
    and customer_id is not null
), cte_items as (
    select t.transaction_id
        , sum(ti.quantity) as items_sold
    from transaction_items ti
    join cte_q4_txs t
    on t.transaction_id = ti.transaction_id
    group by t.transaction_id
), cte_refunds as (
    select t.transaction_id
        , sum(rf.refund_amount) as refunded_amount
    from refunds rf
    join cte_q4_txs t
    on t.transaction_id = rf.transaction_id
    group by t.transaction_id
)

select t.customer_id
    , count(1) as completed_txn_count
    , sum(i.items_sold) as items_sold
    , sum(t.gross_amount) as gross_spend
    , sum(coalesce(refunded_amount,0.00)) as refunded_amount
    , sum(t.gross_amount) - sum(coalesce(refunded_amount,0.00)) as net_spend
from cte_q4_txs t
join cte_items i
on i.transaction_id = t.transaction_id
left join cte_refunds rf
on rf.transaction_id = t.transaction_id
group by t.customer_id


-- ; with cte_transactions_Q4_2025 as (
--     select *
--     from transactions
--     where transaction_ts >= '2025-10-01 00:00:00+00'::timestamptz
--     and transaction_ts < '2026-01-01 00:00:00+00'::timestamptz
--     and transaction_status = 'COMPLETED'
--     and customer_id is not null
-- ), cte_refunds as (
--     select t.customer_id
--         , count(1) as refunds
--         , sum(refund_amount) as refunded_amount
--     from refunds rf
--     join cte_transactions_Q4_2025 t
--     on rf.transaction_id = t.transaction_id
--     group by t.customer_id
-- ), cte_transaction_items_Q4_2025 as (
--     select t.customer_id
--         , sum(quantity) as items_sold
--     from cte_transactions_Q4_2025 t
--     join transaction_items ti
--     on ti.transaction_id = t.transaction_id
--     group by t.customer_id
-- )

-- select t.customer_id
--     , t.completed_txn_count
--     , ti.items_sold
--     , t.gross_spend
--     , coalesce(refunded_amount,0.00) as refunded_amount
--     , t.gross_spend - coalesce(refunded_amount,0.00) as net_spend
-- from
-- (
--     select customer_id
--     , count(1) as completed_txn_count
--     , sum(gross_amount) as gross_spend
--     from cte_transactions_Q4_2025
--     group by customer_id
-- ) t
-- join cte_transaction_items_Q4_2025 ti
-- on t.customer_id = ti.customer_id
-- left join cte_refunds rf
-- on t.customer_id = rf.customer_id
-- order by t.customer_id

-- <<< end of answer <<<
