-- SQL-042 reference solution: read the committed watermark, re-read a 10-minute overlap before
-- it, and stop at the run's fixed high mark (exclusive). The interval is half-open:
--     [watermark - 10 minutes, 2025-12-15 07:00 UTC)
-- Rows in [watermark - 10 min, watermark) were probably processed by the previous run; they are
-- re-read on purpose and made harmless by an idempotent upsert downstream.
WITH run_bounds AS (
    SELECT w.watermark_ts,
           w.watermark_ts - interval '10 minutes'        AS read_from,
           timestamptz '2025-12-15 07:00:00+00'          AS read_to
    FROM pipeline_watermarks w
    WHERE w.pipeline_name = 'transactions_incremental'
      AND w.source_system = 'POS'
)
SELECT t.transaction_id,
       t.ingested_at,
       (t.ingested_at < b.watermark_ts) AS is_overlap_reread
FROM transactions t
JOIN run_bounds b
  ON t.ingested_at >= b.read_from
 AND t.ingested_at <  b.read_to
WHERE t.source_system = 'POS';
