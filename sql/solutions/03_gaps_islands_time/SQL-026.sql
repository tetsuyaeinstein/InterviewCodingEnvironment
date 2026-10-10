-- SQL-026 reference solution (a): LAG gap flag + running sum = session number.
-- A new session starts when the gap to the customer's previous event is MORE than 30 minutes.
WITH scoped AS (
    SELECT customer_id, event_id, event_ts
    FROM customer_events
    WHERE customer_id IS NOT NULL
      AND event_ts >= TIMESTAMPTZ '2025-07-01 00:00:00+00'
      AND event_ts <  TIMESTAMPTZ '2025-08-01 00:00:00+00'
),
flagged AS (
    SELECT customer_id, event_id, event_ts,
           CASE
               WHEN LAG(event_ts) OVER w IS NULL                        THEN 1   -- first event of the customer
               WHEN event_ts - LAG(event_ts) OVER w > INTERVAL '30 minutes' THEN 1   -- exactly 30:00 continues
               ELSE 0
           END AS is_session_start
    FROM scoped
    WINDOW w AS (PARTITION BY customer_id ORDER BY event_ts, event_id)       -- event_id breaks equal timestamps
),
numbered AS (
    SELECT customer_id, event_id, event_ts,
           SUM(is_session_start) OVER (PARTITION BY customer_id ORDER BY event_ts, event_id
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS session_number
    FROM flagged
)
SELECT customer_id,
       session_number::int AS session_number,
       MIN(event_ts)       AS session_start,
       MAX(event_ts)       AS session_end,
       COUNT(*)::int       AS event_count
FROM numbered
GROUP BY customer_id, session_number;
