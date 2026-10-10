-- SQL-047 alternative (b): materialise the applicable changes once, then two MERGE statements
-- (PostgreSQL 15+). MERGE expresses insert / update / delete for one target in a single
-- statement, which maps naturally onto I/U/D change events.
--
-- The "applicable" set must be computed BEFORE either table is modified: once the tombstone
-- table changes, the newer-than-everything-known test would give different answers.
CREATE TABLE cdc_apply AS
WITH winner AS (
    SELECT source_system, business_key, operation, source_lsn, amount, status,
           ROW_NUMBER() OVER (PARTITION BY source_system, business_key
                              ORDER BY source_lsn DESC, cdc_event_id DESC) AS rn
    FROM cdc_batch
)
SELECT w.source_system, w.business_key, w.operation, w.source_lsn, w.amount, w.status
FROM winner w
WHERE w.rn = 1
  AND w.source_lsn > COALESCE((SELECT c.source_lsn FROM txn_current c
                               WHERE c.source_system = w.source_system AND c.business_key = w.business_key), -1)
  AND w.source_lsn > COALESCE((SELECT d.deleted_lsn FROM txn_tombstone d
                               WHERE d.source_system = w.source_system AND d.business_key = w.business_key), -1);

-- live rows: deletes remove, inserts/updates upsert
MERGE INTO txn_current AS t
USING cdc_apply AS a
   ON t.source_system = a.source_system AND t.business_key = a.business_key
WHEN MATCHED AND a.operation = 'D' THEN
    DELETE
WHEN MATCHED THEN
    UPDATE SET amount = a.amount, status = a.status, source_lsn = a.source_lsn
WHEN NOT MATCHED AND a.operation <> 'D' THEN
    INSERT (source_system, business_key, amount, status, source_lsn)
    VALUES (a.source_system, a.business_key, a.amount, a.status, a.source_lsn);

-- tombstones: remembered for deletes (also for keys we never saw), cleared by a newer insert
MERGE INTO txn_tombstone AS t
USING cdc_apply AS a
   ON t.source_system = a.source_system AND t.business_key = a.business_key
WHEN MATCHED AND a.operation = 'D' THEN
    UPDATE SET deleted_lsn = a.source_lsn
WHEN MATCHED THEN
    DELETE
WHEN NOT MATCHED AND a.operation = 'D' THEN
    INSERT (source_system, business_key, deleted_lsn)
    VALUES (a.source_system, a.business_key, a.source_lsn);
