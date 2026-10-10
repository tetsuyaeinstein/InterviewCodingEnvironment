-- SQL-030 reference solution (a): build the expected calendar (device x in-service day),
-- anti-join the days that have a SCHEDULED report (by event_ts UTC date), then collapse
-- consecutive missing days into reporting gaps.
WITH calendar AS (
    SELECT d::date AS report_date
    FROM generate_series(DATE '2025-01-01', DATE '2025-02-28', INTERVAL '1 day') AS g(d)
),
expected AS (                    -- installed_on is in service, decommissioned_on is the first day out
    SELECT dv.device_id, c.report_date
    FROM devices dv
    JOIN calendar c
      ON c.report_date >= dv.installed_on
     AND (dv.decommissioned_on IS NULL OR c.report_date < dv.decommissioned_on)
),
missing AS (
    SELECT e.device_id, e.report_date
    FROM expected e
    WHERE NOT EXISTS (
        SELECT 1
        FROM device_status_events s
        WHERE s.device_id  = e.device_id
          AND s.event_kind = 'SCHEDULED'
          AND s.event_ts  >= e.report_date::timestamp AT TIME ZONE 'UTC'               -- [day, day + 1)
          AND s.event_ts  <  (e.report_date + 1)::timestamp AT TIME ZONE 'UTC'
    )
)
SELECT device_id,
       MIN(report_date)  AS gap_start,
       MAX(report_date)  AS gap_end,
       COUNT(*)::int     AS missing_days
FROM (
    SELECT device_id, report_date,
           report_date - (ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY report_date))::int AS gap_key
    FROM missing
) m
GROUP BY device_id, gap_key;
