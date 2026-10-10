-- SQL-050 alternative (b): recursive walk. Start every source at the history start and keep
-- stepping to the end of a SUCCEEDED run whose window begins exactly at the current position.
-- The walk stops at the first hour without a success; how far it got is the safe watermark.
-- UNION (not UNION ALL) removes the duplicate step produced by re-runs (POS 01-02 succeeded
-- twice), so the recursion stays linear in the number of windows.
-- Assumes aligned, non-overlapping windows (true for this hourly pipeline); the island version
-- (a) also copes with overlapping or multi-hour windows.
WITH RECURSIVE params AS (
    SELECT timestamptz '2025-12-15 00:00:00+00' AS history_start
),
walk (source_system, position) AS (
    SELECT w.source_system, p.history_start
    FROM pipeline_watermarks w
    CROSS JOIN params p
    WHERE w.pipeline_name = 'transactions_incremental'
    UNION
    SELECT wk.source_system, r.window_end
    FROM walk wk
    JOIN pipeline_runs r
      ON r.pipeline_name = 'transactions_incremental'
     AND r.source_system = wk.source_system
     AND r.status        = 'SUCCEEDED'
     AND r.window_start  = wk.position
),
reached AS (
    SELECT source_system, MAX(position) AS next_window_start
    FROM walk
    GROUP BY source_system
),
latest_attempt AS (                   -- most recent attempt per (source, window_start)
    SELECT DISTINCT ON (source_system, window_start) source_system, window_start, status
    FROM pipeline_runs
    WHERE pipeline_name = 'transactions_incremental'
    ORDER BY source_system, window_start, started_at DESC, run_id DESC
)
SELECT w.source_system,
       NULLIF(r.next_window_start, p.history_start) AS safe_watermark,
       w.watermark_ts                               AS recorded_watermark,
       (w.watermark_ts > r.next_window_start)       AS recorded_is_unsafe,
       COALESCE(l.status, 'NOT_RUN')                AS next_window_status
FROM pipeline_watermarks w
CROSS JOIN params p
JOIN reached r
  ON r.source_system = w.source_system
LEFT JOIN latest_attempt l
  ON l.source_system = w.source_system
 AND l.window_start  = r.next_window_start
WHERE w.pipeline_name = 'transactions_incremental';
