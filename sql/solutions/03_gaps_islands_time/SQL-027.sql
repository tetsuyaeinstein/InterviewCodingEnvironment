-- SQL-027 reference solution (a): classic interval merge with a running MAX(end).
-- 1) keep incidents that intersect January 2025 and clip them to the month,
-- 2) sort by start; a row opens a new outage when its start is AFTER every earlier end
--    (start = earlier end means the intervals touch, which merges),
-- 3) number the outages with a running sum, 4) sum the merged lengths.
WITH clipped AS (
    SELECT device_id,
           incident_id,
           GREATEST(down_from, TIMESTAMPTZ '2025-01-01 00:00:00+00') AS s,
           LEAST(down_to,      TIMESTAMPTZ '2025-02-01 00:00:00+00') AS e
    FROM device_downtime_incidents
    WHERE down_from < TIMESTAMPTZ '2025-02-01 00:00:00+00'      -- half-open overlap test with the month
      AND down_to   > TIMESTAMPTZ '2025-01-01 00:00:00+00'
),
flagged AS (
    SELECT device_id, incident_id, s, e,
           CASE WHEN s <= MAX(e) OVER (PARTITION BY device_id ORDER BY s, e, incident_id
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
                THEN 0 ELSE 1 END AS is_new_outage                  -- NULL (first row) -> 1
    FROM clipped
),
grouped AS (
    SELECT device_id, s, e,
           SUM(is_new_outage) OVER (PARTITION BY device_id ORDER BY s, e, incident_id   -- same order as above
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS outage_no
    FROM flagged
),
outages AS (
    SELECT device_id, outage_no, MIN(s) AS outage_from, MAX(e) AS outage_to
    FROM grouped
    GROUP BY device_id, outage_no
)
SELECT device_id,
       COUNT(*)::int                                                         AS outage_count,
       ROUND(SUM(EXTRACT(EPOCH FROM (outage_to - outage_from))) / 60, 2)     AS downtime_minutes
FROM outages
GROUP BY device_id;
