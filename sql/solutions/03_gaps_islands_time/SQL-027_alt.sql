-- SQL-027 reference solution (b): let PostgreSQL merge the intervals with range_agg (PG 14+).
-- range_agg over '[)' ranges returns a multirange in which overlapping AND adjacent ranges are
-- already coalesced. Intersecting with the January multirange clips it; unnest() yields the outages.
WITH per_device AS (
    SELECT device_id,
           range_agg(tstzrange(down_from, down_to, '[)'))
             * tstzmultirange(tstzrange(TIMESTAMPTZ '2025-01-01 00:00:00+00',
                                        TIMESTAMPTZ '2025-02-01 00:00:00+00', '[)')) AS downtime
    FROM device_downtime_incidents
    WHERE down_from < TIMESTAMPTZ '2025-02-01 00:00:00+00'
      AND down_to   > TIMESTAMPTZ '2025-01-01 00:00:00+00'
    GROUP BY device_id
)
SELECT d.device_id,
       COUNT(*)::int                                                       AS outage_count,
       ROUND(SUM(EXTRACT(EPOCH FROM (upper(r) - lower(r)))) / 60, 2)       AS downtime_minutes
FROM per_device d
CROSS JOIN LATERAL unnest(d.downtime) AS r
GROUP BY d.device_id;
