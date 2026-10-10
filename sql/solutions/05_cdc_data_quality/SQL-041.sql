-- SQL-041 reference solution (a): rank events per key by commit order with ROW_NUMBER, and
-- detect conflicting versions at the winning LSN with a window COUNT(DISTINCT ...)-style check.
--
-- Ordering rule: source_lsn DESC is the only trustworthy "newest" (ingested_at / cdc_event_id
-- are arrival order). Tie policy for equal max LSN: pick the event that arrived last
-- (highest cdc_event_id) and flag has_lsn_conflict when the tied events disagree.
WITH ranked AS (
    SELECT e.*,
           ROW_NUMBER() OVER (PARTITION BY source_system, business_key
                              ORDER BY source_lsn DESC, cdc_event_id DESC) AS rn,
           MAX(source_lsn) OVER (PARTITION BY source_system, business_key) AS max_lsn
    FROM cdc_transaction_events e
),
conflicts AS (                       -- keys whose top LSN carries more than one distinct version
    SELECT source_system, business_key
    FROM ranked
    WHERE source_lsn = max_lsn
    GROUP BY source_system, business_key
    HAVING COUNT(DISTINCT (operation, payload)) > 1
)
SELECT r.source_system,
       r.business_key,
       r.cdc_event_id,
       r.operation::text                                         AS last_operation,
       r.source_lsn,
       CASE WHEN r.operation <> 'D' THEN (r.payload->>'amount')::numeric(12,2) END AS amount,
       CASE WHEN r.operation <> 'D' THEN r.payload->>'status' END               AS status,
       (r.operation = 'D')                                       AS is_deleted,
       (c.business_key IS NOT NULL)                              AS has_lsn_conflict
FROM ranked r
LEFT JOIN conflicts c
       ON c.source_system = r.source_system
      AND c.business_key  = r.business_key
WHERE r.rn = 1;
