-- =============================================================================
-- SQL-043 | Late-arriving sales missed by the daily report
-- Level: easy | Target time: ~15 min | Mode: query
-- Question: sql/questions/05_cdc_data_quality/SQL-043.md   (python -m lab show SQL-043)
-- Tables  : pipeline_watermarks, transactions
-- Output  : business_date, late_txn_count, late_amount, reported_amount, final_amount, late_pct
-- Run     : python -m lab run SQL-043        Check: python -m lab check SQL-043
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>



-- <<< end of answer <<<
