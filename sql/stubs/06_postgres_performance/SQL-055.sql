-- =============================================================================
-- SQL-055 | p50 / p95 ingestion delay per source with ordered-set aggregates
-- Level: medium | Target time: ~20 min | Mode: query
-- Question: sql/questions/06_postgres_performance/SQL-055.md   (python -m lab show SQL-055)
-- Tables  : event_ingestion_log
-- Output  : source_system, loaded_events, skewed_events_excluded, p50_delay_s, p95_delay_s
-- Run     : python -m lab run SQL-055        Check: python -m lab check SQL-055
-- Rules   : ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.
-- =============================================================================

-- >>> Write your answer below this line >>>



-- <<< end of answer <<<
