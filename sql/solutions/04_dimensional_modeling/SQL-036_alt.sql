-- SQL-036 reference solution (b): range types and per-cell EXISTS / point lookups.
-- any-time    = an available row's range overlaps the day range (&&)
-- end-of-day  = a point lookup at the last representable microsecond of the day (@>)
-- minutes     = length of the intersection (*) of each available range with the day range
WITH cells AS (
    SELECT d::date AS snapshot_date,
           p.product_id,
           tstzrange(d::date::timestamp AT TIME ZONE 'UTC',
                     (d::date + 1)::timestamp AT TIME ZONE 'UTC') AS day_range,            -- '[)'
           (d::date + 1)::timestamp AT TIME ZONE 'UTC' - INTERVAL '1 microsecond' AS last_instant
    FROM generate_series(DATE '2025-05-09', DATE '2025-05-12', INTERVAL '1 day') AS d
    CROSS JOIN products p
    WHERE p.product_id IN (4, 5, 6)
)
SELECT c.snapshot_date,
       c.product_id,
       EXISTS (SELECT 1 FROM store_product_availability a
               WHERE a.store_id = 2 AND a.product_id = c.product_id AND a.available
                 AND tstzrange(a.valid_from, a.valid_to) && c.day_range)           AS available_any_time,
       EXISTS (SELECT 1 FROM store_product_availability a
               WHERE a.store_id = 2 AND a.product_id = c.product_id AND a.available
                 AND tstzrange(a.valid_from, a.valid_to) @> c.last_instant)        AS available_end_of_day,
       ROUND(COALESCE((SELECT SUM(EXTRACT(EPOCH FROM upper(i) - lower(i)) / 60)
                       FROM (SELECT tstzrange(a.valid_from, a.valid_to) * c.day_range AS i
                             FROM store_product_availability a
                             WHERE a.store_id = 2 AND a.product_id = c.product_id AND a.available) x
                       WHERE NOT isempty(i)), 0), 2)                               AS available_minutes
FROM cells c;

-- RATIONALE:
-- Three measures serve three questions. available_any_time is the "was it sellable today"
-- flag used to validate sales lines and conversion denominators. available_end_of_day is the
-- point-in-time stock position suited to a nightly snapshot and consistent with other end-of-day
-- facts, but it hides intraday outages. available_minutes is the additive on-shelf availability
-- KPI. Time not covered by any history row counts as unavailable (not stocked), per the data
-- dictionary convention.
