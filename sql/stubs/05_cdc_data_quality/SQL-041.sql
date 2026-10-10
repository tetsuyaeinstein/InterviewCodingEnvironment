-- =============================================================================
-- SQL-041 | Current state of every CDC key (latest by commit order)
-- Level: medium | Target time: ~20 min | Mode: query
-- Question: sql/questions/05_cdc_data_quality/SQL-041.md   (python -m lab show SQL-041)
-- Tables  : cdc_transaction_events
-- Output  : source_system, business_key, cdc_event_id, last_operation, source_lsn, amount, status, is_deleted, has_lsn_conflict
-- Run     : python -m lab run SQL-041        Check: python -m lab check SQL-041
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>



-- <<< end of answer <<<
