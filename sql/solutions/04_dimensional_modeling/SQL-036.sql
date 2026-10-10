-- SQL-036 reference solution (a): dense day x product grid, clip every availability interval to
-- the day, then aggregate. One pass, three different "availability" measures.
WITH days AS (
    SELECT d::date AS snapshot_date,
           d::date::timestamp AT TIME ZONE 'UTC'       AS day_start,   -- [day_start, day_end) in UTC
           (d::date + 1)::timestamp AT TIME ZONE 'UTC' AS day_end
    FROM generate_series(DATE '2025-05-09', DATE '2025-05-12', INTERVAL '1 day') AS d
),
grid AS (
    SELECT dy.*, p.product_id
    FROM days dy
    CROSS JOIN products p
    WHERE p.product_id IN (4, 5, 6)
),
clipped AS (                     -- each history row that intersects the day, clipped to the day
    SELECT g.snapshot_date, g.product_id, g.day_end, a.available, a.valid_to,
           GREATEST(a.valid_from, g.day_start)                          AS seg_from,
           LEAST(COALESCE(a.valid_to, 'infinity'::timestamptz), g.day_end) AS seg_to
    FROM grid g
    JOIN store_product_availability a
      ON a.store_id   = 2
     AND a.product_id = g.product_id
     AND a.valid_from < g.day_end                                        -- half-open intersection test
     AND COALESCE(a.valid_to, 'infinity'::timestamptz) > g.day_start
)
SELECT g.snapshot_date,
       g.product_id,
       COALESCE(bool_or(c.available), false)                            AS available_any_time,
       -- the row in force at the last instant of the day is the one still open at day_end
       COALESCE(bool_or(c.available AND (c.valid_to IS NULL OR c.valid_to >= g.day_end)), false)
                                                                        AS available_end_of_day,
       ROUND(COALESCE(SUM(EXTRACT(EPOCH FROM c.seg_to - c.seg_from) / 60)
                      FILTER (WHERE c.available), 0), 2)                AS available_minutes
FROM grid g
LEFT JOIN clipped c USING (snapshot_date, product_id)
GROUP BY g.snapshot_date, g.product_id;

-- RATIONALE:
-- The three columns answer different business questions, so none of them replaces the others.
-- available_any_time ("could a customer have bought it at some point today?") is the right
-- denominator for conversion / "was it sellable" questions and for reconciling sales lines: a
-- product sold on a day must be available_any_time on that day, but it can still be unavailable
-- at end of day. available_end_of_day is a point-in-time stock position: it is what replenishment
-- and a nightly snapshot fact store, it is cheap (one row per product per day, no interval math)
-- and it is consistent with other end-of-day snapshots (balances, inventory). It hides intraday
-- outages: p4 on 05-10 was out for two hours but looks fine at both ends of the day.
-- available_minutes is the on-shelf-availability KPI and the input for lost-sales estimates; it
-- is additive across products and days, while the two booleans are not.
-- Uncovered time (no history row) is treated as unavailable because the dictionary says an
-- uncovered timestamp means "not stocked"; treating it as unknown would overstate availability.
-- I would store the minutes plus the end-of-day flag in the daily snapshot fact, and keep the
-- interval history table as the source of truth for any other cut.
