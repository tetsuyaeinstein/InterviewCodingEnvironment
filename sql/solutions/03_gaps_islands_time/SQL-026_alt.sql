-- SQL-026 reference solution (b): carry the session's start timestamp forward instead of counting.
-- Each event is labelled with the timestamp of the most recent "session start" at or before it;
-- that label is the session key, and DENSE_RANK over it gives the session number.
WITH scoped AS (
    SELECT customer_id, event_id, event_ts
    FROM customer_events
    WHERE customer_id IS NOT NULL
      AND event_ts >= TIMESTAMPTZ '2025-07-01 00:00:00+00'
      AND event_ts <  TIMESTAMPTZ '2025-08-01 00:00:00+00'
),
starts AS (                      -- the start timestamp on session-opening rows, NULL elsewhere
    SELECT customer_id, event_id, event_ts,
           CASE WHEN COALESCE(event_ts - LAG(event_ts) OVER w > INTERVAL '30 minutes', true)
                THEN event_ts END AS start_ts
    FROM scoped
    WINDOW w AS (PARTITION BY customer_id ORDER BY event_ts, event_id)
),
labelled AS (                    -- timestamps only grow within a customer, so a running MAX carries it forward
    SELECT customer_id, event_ts,
           MAX(start_ts) OVER (PARTITION BY customer_id ORDER BY event_ts, event_id
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS session_key
    FROM starts
)
SELECT customer_id,
       DENSE_RANK() OVER (PARTITION BY customer_id ORDER BY session_key)::int AS session_number,
       session_key   AS session_start,
       MAX(event_ts) AS session_end,
       COUNT(*)::int AS event_count
FROM labelled
GROUP BY customer_id, session_key;
