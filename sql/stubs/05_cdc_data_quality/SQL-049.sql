-- =============================================================================
-- SQL-049 | Commit order vs arrival order - CDC sequence anomalies
-- Level: hard | Target time: ~35 min | Mode: query
-- Question: sql/questions/05_cdc_data_quality/SQL-049.md   (python -m lab show SQL-049)
-- Tables  : cdc_transaction_events
-- Output  : cdc_event_id, source_system, business_key, operation, source_lsn, issue_type, related_event_id
-- Run     : python -m lab run SQL-049        Check: python -m lab check SQL-049
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>



-- <<< end of answer <<<
