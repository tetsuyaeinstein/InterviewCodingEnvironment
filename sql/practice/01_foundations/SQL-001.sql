-- =============================================================================
-- SQL-001 | Lifetime completed spend per customer, zeros included
-- Level: easy | Target time: ~10 min | Mode: query
-- Question: sql/questions/01_foundations/SQL-001.md   (python -m lab show SQL-001)
-- Tables  : customers, transactions
-- Output  : customer_id, completed_txn_count, total_completed_spend
-- Run     : python -m lab run SQL-001        Check: python -m lab check SQL-001
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>

SELECT c.customer_id,
    COALESCE(a.n, 0)     AS completed_txn_count,
    COALESCE(a.spend, 0) AS total_completed_spend
FROM customers c
LEFT JOIN (
    SELECT customer_id
        , COUNT(*) AS n
        , SUM(gross_amount) AS spend
    FROM transactions
    WHERE transaction_status = 'COMPLETED'
    GROUP BY customer_id
) a USING (customer_id);


-- select *
-- from customers
-- where status <> 'ACTIVE'

select count(1)
from transactions
where transaction_status <> 'COMPLETED'

-- select *-- sum(gross_amount),COUNT(*)
-- from transactions t
-- -- where t.customer_id = 32
EXPLAIN (ANALYZE, BUFFERS)
select c.customer_id
    , COALESCE(count(t.transaction_id),0) as completed_txn_count
    , COALESCE(sum(t.gross_amount),0) as total_completed_spend
from customers c
left join transactions t
on c.customer_id = t.customer_id
and t.transaction_status = 'COMPLETED'
-- where t.customer_id = 32
group by c.customer_id
order by c.customer_id;

EXPLAIN (ANALYZE, BUFFERS)
SELECT c.customer_id,
       agg.completed_txn_count,
       COALESCE(agg.total_completed_spend, 0.00) AS total_completed_spend
FROM customers c
LEFT JOIN LATERAL (
    SELECT COUNT(*)            AS completed_txn_count,
           SUM(t.gross_amount) AS total_completed_spend
    FROM transactions t
    WHERE t.customer_id = c.customer_id            -- uses the transactions(customer_id) index
      AND t.transaction_status = 'COMPLETED'
) agg on true
order by c.customer_id

select sum(null)

-- <<< end of answer <<<
