-- SQL-055 reference solution (a): percentile_cont over the delay of the FIRST LOADED attempt of
-- every raw event. Negative delays (clock skew) are counted but excluded from the percentiles.
WITH first_loaded AS (            -- grain: one row per raw_event_id
    SELECT DISTINCT ON (raw_event_id)
           raw_event_id,
           source_system,
           extract(epoch FROM ingest_ts - event_ts) AS delay_s
    FROM event_ingestion_log
    WHERE ingestion_status = 'LOADED'                       -- RETRIED / DUPLICATE / REJECTED attempts never count
      AND event_ts >= TIMESTAMPTZ '2025-12-01 00:00:00+00'
      AND event_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
    ORDER BY raw_event_id, ingest_ts, log_id                 -- earliest LOADED attempt wins
)
SELECT source_system,
       count(*) FILTER (WHERE delay_s >= 0)                  AS loaded_events,
       count(*) FILTER (WHERE delay_s <  0)                  AS skewed_events_excluded,
       round((percentile_cont(0.5)  WITHIN GROUP (ORDER BY delay_s) FILTER (WHERE delay_s >= 0))::numeric, 2) AS p50_delay_s,
       round((percentile_cont(0.95) WITHIN GROUP (ORDER BY delay_s) FILTER (WHERE delay_s >= 0))::numeric, 2) AS p95_delay_s
FROM first_loaded
GROUP BY source_system;
