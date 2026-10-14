-- =============================================================================
-- SQL-004 | Classify duplicate deliveries in an at-least-once event feed
-- Level: hard | Target time: ~30 min | Mode: query
-- Question: sql/questions/01_foundations/SQL-004.md   (python -m lab show SQL-004)
-- Tables  : raw_transaction_events
-- Output  : transaction_id, deliveries, distinct_messages, created_messages, status_change_messages, has_redelivery, classification
-- Run     : python -m lab run SQL-004        Check: python -m lab check SQL-004
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>

-- select *
-- from raw_transaction_events;

-- select transaction_id, count(distinct message_id)
-- from raw_transaction_events
-- group by transaction_id

-- ; with transactions as (
--     select transaction_id
--     from raw_transaction_events
--     where event_type = 'CREATED'
--     group by transaction_id
--     having count(1) >= 2
-- )
select rte.transaction_id
    , count(1) deliveries
    , count(distinct message_id) as distinct_messages
    , count(distinct message_id) filter (where event_type = 'CREATED') as created_messages
    , count(distinct message_id) filter (where event_type = 'STATUS_CHANGED') as status_change_messages
    , count(1) > count(distinct message_id) as has_redelivery
    , CASE
        when count(distinct message_id) filter (where event_type = 'CREATED') >= 2 and count(distinct payload) filter (where event_type = 'CREATED') >= 2 then 'CONFLICTING_DUPLICATE'
        when count(distinct message_id) filter (where event_type = 'CREATED') >= 2 and count(distinct payload) filter (where event_type = 'CREATED') = 1 then 'BUSINESS_KEY_DUPLICATE'
        when count(distinct message_id) >= 2 then 'LIFECYCLE_EVENTS'
        else 'REDELIVERY_ONLY'
    END as classification
from raw_transaction_events rte
-- on t.transaction_id = rte.transaction_id
-- where rte.transaction_id = 120196
-- where rte.message_id = 'msg-119140-c'
group by rte.transaction_id
having count(1) >= 2


select *
from raw_transaction_events
where transaction_id = 119292

select '{"a":1,"b":2}'::jsonb = '{"b":2,"a":1}'::jsonb

-- select *
-- from raw_transaction_events
-- where transaction_id = 120196

-- <<< end of answer <<<
