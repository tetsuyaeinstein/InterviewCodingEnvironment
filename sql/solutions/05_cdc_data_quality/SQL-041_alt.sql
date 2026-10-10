-- SQL-041 alternative (b): anti-join "no newer event exists" instead of a window ranking.
-- An event is the current version when no event of the same key has a higher LSN, or the same
-- LSN and a higher cdc_event_id (the tie policy). Conflicts are detected with a second
-- NOT-EXISTS-style probe: another event at the same LSN with a different operation/payload.
-- With the (source_system, business_key, source_lsn) index both probes are index lookups.
SELECT e.source_system,
       e.business_key,
       e.cdc_event_id,
       e.operation::text                                         AS last_operation,
       e.source_lsn,
       CASE WHEN e.operation <> 'D' THEN (e.payload->>'amount')::numeric(12,2) END AS amount,
       CASE WHEN e.operation <> 'D' THEN e.payload->>'status' END               AS status,
       (e.operation = 'D')                                       AS is_deleted,
       EXISTS (SELECT 1
               FROM cdc_transaction_events o
               WHERE o.source_system = e.source_system
                 AND o.business_key  = e.business_key
                 AND o.source_lsn    = e.source_lsn
                 AND (o.operation, o.payload) IS DISTINCT FROM (e.operation, e.payload)) AS has_lsn_conflict
FROM cdc_transaction_events e
WHERE NOT EXISTS (SELECT 1
                  FROM cdc_transaction_events n
                  WHERE n.source_system = e.source_system
                    AND n.business_key  = e.business_key
                    AND (n.source_lsn > e.source_lsn
                         OR (n.source_lsn = e.source_lsn AND n.cdc_event_id > e.cdc_event_id)));
