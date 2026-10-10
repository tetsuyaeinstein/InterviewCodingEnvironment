-- =============================================================================
-- SQL-053 | Composite index column order for equality + range + ORDER BY ... LIMIT
-- Level: hard | Target time: ~30 min | Mode: plan
-- Question: sql/questions/06_postgres_performance/SQL-053.md   (python -m lab show SQL-053)
-- Tables  : txn_copy (sandbox copy of transactions)
-- Sandbox : txn_copy  (created for you inside the sandbox schema)
-- Output  : transaction_id, transaction_ts, store_id, gross_amount
-- Run     : python -m lab run SQL-053        Check: python -m lab check SQL-053
-- Rules   : Runs in a disposable sandbox schema (rolled back). You may CREATE INDEX / ANALYZE first; the LAST statement must be the SELECT being analysed (no EXPLAIN keyword).
-- =============================================================================

-- >>> Write your answer below this line >>>



-- <<< end of answer <<<
