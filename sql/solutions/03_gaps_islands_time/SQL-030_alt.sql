-- SQL-030 reference solution (b): no calendar table. Look at consecutive report days with LEAD;
-- any jump of more than one day is a gap. Two sentinel "reports" per device close the edges:
-- the day before the device's first expected day and the day after its last expected day.
WITH bounds AS (                 -- each device's expected window inside the period (inclusive dates)
    SELECT device_id,
           GREATEST(installed_on, DATE '2025-01-01')                                    AS first_day,
           LEAST(COALESCE(decommissioned_on, DATE '2025-03-01'), DATE '2025-03-01') - 1  AS last_day
    FROM devices
),
report_days AS (                 -- distinct UTC report dates inside each device's window
    SELECT DISTINCT s.device_id, (s.event_ts AT TIME ZONE 'UTC')::date AS report_date
    FROM device_status_events s
    JOIN bounds b ON b.device_id = s.device_id
    WHERE s.event_kind = 'SCHEDULED'
      AND (s.event_ts AT TIME ZONE 'UTC')::date BETWEEN b.first_day AND b.last_day
    UNION ALL
    SELECT device_id, first_day - 1 FROM bounds WHERE first_day <= last_day   -- left sentinel
    UNION ALL
    SELECT device_id, last_day + 1  FROM bounds WHERE first_day <= last_day   -- right sentinel
),
steps AS (
    SELECT device_id,
           report_date,
           LEAD(report_date) OVER (PARTITION BY device_id ORDER BY report_date) AS next_report_date
    FROM report_days
)
SELECT device_id,
       report_date + 1                       AS gap_start,
       next_report_date - 1                  AS gap_end,
       (next_report_date - report_date - 1)  AS missing_days
FROM steps
WHERE next_report_date - report_date > 1;
