-- =============================================================================
-- SQL-050 | Safe committed watermark after failed and retried batches
-- Level: medium | Target time: ~25 min | Mode: query
-- Question: sql/questions/05_cdc_data_quality/SQL-050.md   (python -m lab show SQL-050)
-- Tables  : pipeline_runs, pipeline_watermarks
-- Output  : source_system, safe_watermark, recorded_watermark, recorded_is_unsafe, next_window_status
-- Run     : python -m lab run SQL-050        Check: python -m lab check SQL-050
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>



-- <<< end of answer <<<
