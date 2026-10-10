-- SQL-049 reference solution: one candidate row per (event, issue) from self-joins, then keep
-- the highest-precedence issue per event.
--
-- Arrival order = cdc_event_id (ingested_at has ties); commit order = source_lsn.
-- Precedence: LSN_CONFLICT > DUPLICATE_DELIVERY > STALE_ARRIVAL > ORPHAN_CHANGE > COMMIT_TS_TIE
WITH e AS (
    SELECT cdc_event_id, source_system, business_key, operation::text AS operation,
           source_lsn, commit_ts, payload
    FROM cdc_transaction_events
),
candidates AS (
    -- 1. LSN_CONFLICT: another event of the key has the same LSN but a different version.
    SELECT e.cdc_event_id, 1 AS prio, 'LSN_CONFLICT' AS issue_type,
           MIN(o.cdc_event_id) AS related_event_id
    FROM e
    JOIN e o
      ON o.source_system = e.source_system AND o.business_key = e.business_key
     AND o.source_lsn = e.source_lsn AND o.cdc_event_id <> e.cdc_event_id
     AND (o.operation, o.payload) IS DISTINCT FROM (e.operation, e.payload)
    GROUP BY e.cdc_event_id

    UNION ALL
    -- 2. DUPLICATE_DELIVERY: an identical version (same LSN, operation, payload) arrived earlier.
    SELECT e.cdc_event_id, 2, 'DUPLICATE_DELIVERY', MIN(o.cdc_event_id)
    FROM e
    JOIN e o
      ON o.source_system = e.source_system AND o.business_key = e.business_key
     AND o.source_lsn = e.source_lsn AND o.cdc_event_id < e.cdc_event_id
     AND o.operation = e.operation AND o.payload = e.payload
    GROUP BY e.cdc_event_id

    UNION ALL
    -- 3. STALE_ARRIVAL: an event of the key with a strictly higher LSN had already arrived.
    SELECT e.cdc_event_id, 3, 'STALE_ARRIVAL', MIN(o.cdc_event_id)
    FROM e
    JOIN e o
      ON o.source_system = e.source_system AND o.business_key = e.business_key
     AND o.cdc_event_id < e.cdc_event_id AND o.source_lsn > e.source_lsn
    GROUP BY e.cdc_event_id

    UNION ALL
    -- 4. ORPHAN_CHANGE: an update/delete with no insert of the key at a lower LSN.
    SELECT e.cdc_event_id, 4, 'ORPHAN_CHANGE', NULL::bigint
    FROM e
    WHERE e.operation IN ('U', 'D')
      AND NOT EXISTS (SELECT 1
                      FROM e i
                      WHERE i.source_system = e.source_system AND i.business_key = e.business_key
                        AND i.operation = 'I' AND i.source_lsn < e.source_lsn)

    UNION ALL
    -- 5. COMMIT_TS_TIE: same commit_ts as another event of the key with a different LSN
    --    (informational: the LSN still decides the order).
    SELECT e.cdc_event_id, 5, 'COMMIT_TS_TIE', MIN(o.cdc_event_id)
    FROM e
    JOIN e o
      ON o.source_system = e.source_system AND o.business_key = e.business_key
     AND o.commit_ts = e.commit_ts AND o.source_lsn <> e.source_lsn
    GROUP BY e.cdc_event_id
),
best AS (
    SELECT DISTINCT ON (cdc_event_id) cdc_event_id, issue_type, related_event_id
    FROM candidates
    ORDER BY cdc_event_id, prio
)
SELECT e.cdc_event_id, e.source_system, e.business_key, e.operation, e.source_lsn,
       b.issue_type, b.related_event_id
FROM best b
JOIN e ON e.cdc_event_id = b.cdc_event_id;
