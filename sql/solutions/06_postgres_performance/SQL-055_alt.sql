-- SQL-055 alternative (b): the same linear-interpolation percentile (the definition of
-- percentile_cont) computed by hand with ROW_NUMBER / COUNT window functions.
-- position = 1 + p * (n - 1); the result interpolates between the rows at floor(position) and ceil(position).
-- (A nearest-rank percentile_disc would give 570 instead of 615.00 for the FIXTURE p95: NOT what is graded.)
WITH first_loaded AS (
    SELECT raw_event_id, source_system, event_ts, ingest_ts,
           row_number() OVER (PARTITION BY raw_event_id ORDER BY ingest_ts, log_id) AS attempt_rank
    FROM event_ingestion_log
    WHERE ingestion_status = 'LOADED'
      AND event_ts >= TIMESTAMPTZ '2025-12-01 00:00:00+00'
      AND event_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
),
delays AS (
    SELECT source_system, extract(epoch FROM ingest_ts - event_ts) AS delay_s
    FROM first_loaded
    WHERE attempt_rank = 1
),
clean AS (
    SELECT source_system, delay_s,
           row_number() OVER (PARTITION BY source_system ORDER BY delay_s) AS rn,
           count(*)     OVER (PARTITION BY source_system)                  AS n
    FROM delays
    WHERE delay_s >= 0
),
interp AS (
    SELECT c.source_system, p.p,
           -- value at fractional position 1 + p*(n-1)
           sum(c.delay_s * CASE
                 WHEN c.rn = floor(1 + p.p * (c.n - 1)) AND c.rn = ceil(1 + p.p * (c.n - 1)) THEN 1
                 WHEN c.rn = floor(1 + p.p * (c.n - 1)) THEN 1 - ((1 + p.p * (c.n - 1)) - floor(1 + p.p * (c.n - 1)))
                 WHEN c.rn = ceil(1 + p.p * (c.n - 1))  THEN (1 + p.p * (c.n - 1)) - floor(1 + p.p * (c.n - 1))
                 ELSE 0 END) AS value
    FROM clean c CROSS JOIN (VALUES (0.5::float8), (0.95::float8)) AS p(p)
    GROUP BY c.source_system, p.p
),
counts AS (
    SELECT source_system,
           count(*) FILTER (WHERE delay_s >= 0) AS loaded_events,
           count(*) FILTER (WHERE delay_s <  0) AS skewed_events_excluded
    FROM delays
    GROUP BY source_system
)
SELECT c.source_system,
       c.loaded_events,
       c.skewed_events_excluded,
       round(max(i.value) FILTER (WHERE i.p = 0.5)::numeric, 2)  AS p50_delay_s,
       round(max(i.value) FILTER (WHERE i.p = 0.95)::numeric, 2) AS p95_delay_s
FROM counts c
JOIN interp i USING (source_system)
GROUP BY c.source_system, c.loaded_events, c.skewed_events_excluded;
