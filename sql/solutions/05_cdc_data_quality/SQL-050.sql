-- SQL-050 reference solution (a): interval gaps-and-islands over SUCCEEDED windows.
--
-- Contiguous coverage from the history start: sort the successful windows, carry the running
-- maximum window_end, and a window that starts after that running end opens a new island
-- (a gap). The safe watermark is the end of the island that starts at the history start.
-- Retries and re-runs are harmless: duplicate successful windows simply overlap.
WITH params AS (
    SELECT timestamptz '2025-12-15 00:00:00+00' AS history_start
),
ok AS (
    SELECT DISTINCT r.source_system, r.window_start, r.window_end
    FROM pipeline_runs r
    CROSS JOIN params p
    WHERE r.pipeline_name = 'transactions_incremental'
      AND r.status = 'SUCCEEDED'
      AND r.window_end > p.history_start
),
marked AS (
    SELECT o.*,
           MAX(window_end) OVER (PARTITION BY source_system ORDER BY window_start, window_end
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS covered_until
    FROM ok o
),
islands AS (
    SELECT m.*,
           SUM(CASE WHEN covered_until IS NULL OR window_start > covered_until THEN 1 ELSE 0 END)
               OVER (PARTITION BY source_system ORDER BY window_start, window_end
                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS island_no
    FROM marked m
),
safe AS (                         -- only the first island counts, and only if it starts on time
    SELECT i.source_system, MAX(i.window_end) AS safe_watermark
    FROM islands i
    CROSS JOIN params p
    WHERE i.island_no = 1
    GROUP BY i.source_system
    HAVING MIN(i.window_start) <= MIN(p.history_start)
),
summary AS (
    SELECT w.source_system,
           s.safe_watermark,
           w.watermark_ts                              AS recorded_watermark,
           COALESCE(s.safe_watermark, p.history_start) AS next_window_start
    FROM pipeline_watermarks w
    CROSS JOIN params p
    LEFT JOIN safe s ON s.source_system = w.source_system
    WHERE w.pipeline_name = 'transactions_incremental'
)
SELECT su.source_system,
       su.safe_watermark,
       su.recorded_watermark,
       (su.recorded_watermark > su.next_window_start) AS recorded_is_unsafe,
       COALESCE((SELECT r.status
                 FROM pipeline_runs r
                 WHERE r.pipeline_name = 'transactions_incremental'
                   AND r.source_system = su.source_system
                   AND r.window_start  = su.next_window_start
                 ORDER BY r.started_at DESC, r.run_id DESC
                 LIMIT 1), 'NOT_RUN')               AS next_window_status
FROM summary su;
