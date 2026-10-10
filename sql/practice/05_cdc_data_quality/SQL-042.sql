-- =============================================================================
-- SQL-042 | Rows for the next incremental run (watermark with overlap)
-- Level: medium | Target time: ~15 min | Mode: query
-- Question: sql/questions/05_cdc_data_quality/SQL-042.md   (python -m lab show SQL-042)
-- Tables  : pipeline_watermarks, transactions
-- Output  : transaction_id, ingested_at, is_overlap_reread
-- Run     : python -m lab run SQL-042        Check: python -m lab check SQL-042
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>



-- <<< end of answer <<<
