-- =============================================================================
-- SQL-002 | Daily completed sales per store for a fixed date range
-- Level: easy | Target time: ~10 min | Mode: query
-- Question: sql/questions/01_foundations/SQL-002.md   (python -m lab show SQL-002)
-- Tables  : transactions
-- Output  : store_id, business_date, completed_txn_count, gross_amount
-- Run     : python -m lab run SQL-002        Check: python -m lab check SQL-002
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>

select *
from transactions;

-- select timestamptz '2025-03-03 12:00:00+03' AT TIME ZONE 'UTC'

-- select timestamptz '2025-03-03 12:00:00+03' = timestamptz '2025-03-03 09:00:00+00'

select store_id
    , (transaction_ts AT TIME ZONE 'UTC')::date as business_date
    , count(1) as completed_txn_count
    , sum(gross_amount) as gross_amount
from transactions
where transaction_status = 'COMPLETED'
and transaction_ts >= '2025-03-01 00:00:00+00'::timestamptz
and transaction_ts < '2025-03-17 00:00:00+00'::timestamptz
group by store_id
    ,  (transaction_ts AT TIME ZONE 'UTC')::date

-- <<< end of answer <<<
