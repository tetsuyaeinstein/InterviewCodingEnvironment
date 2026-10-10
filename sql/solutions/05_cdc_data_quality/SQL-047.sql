-- SQL-047 reference solution (a): one statement built from data-modifying CTEs + ON CONFLICT.
--
-- 1. winner : newest event per key in the batch (source_lsn DESC, then cdc_event_id DESC as the
--             documented tie policy for equal LSNs, e.g. FX-0006).
-- 2. apply  : keep a winner only if it is newer than everything we already know about the key:
--             the live row's LSN OR the tombstone's deleted LSN. This is what stops the stale
--             FX-0002 update (9000115) from resurrecting a key deleted at 9000120.
-- 3. Four writes, each touching disjoint rows (a key is either a delete or an upsert), all
--    reading the same pre-statement snapshot:
--      D  -> remove the live row, insert/raise the tombstone
--      I/U-> upsert the live row (U for an unknown key is an insert: payloads are after-images),
--            remove the tombstone (legitimate re-insert, e.g. FX-0003 and FX-0010)
WITH winner AS (
    SELECT DISTINCT ON (source_system, business_key)
           source_system, business_key, operation, source_lsn, amount, status
    FROM cdc_batch
    ORDER BY source_system, business_key, source_lsn DESC, cdc_event_id DESC
),
apply AS (
    SELECT w.*
    FROM winner w
    LEFT JOIN txn_current   c ON c.source_system = w.source_system AND c.business_key = w.business_key
    LEFT JOIN txn_tombstone d ON d.source_system = w.source_system AND d.business_key = w.business_key
    WHERE w.source_lsn > GREATEST(c.source_lsn, d.deleted_lsn)          -- GREATEST ignores NULLs
       OR (c.source_lsn IS NULL AND d.deleted_lsn IS NULL)              -- key never seen before
),
del_live AS (
    DELETE FROM txn_current c
    USING apply a
    WHERE a.operation = 'D'
      AND c.source_system = a.source_system AND c.business_key = a.business_key
),
put_tombstone AS (
    INSERT INTO txn_tombstone (source_system, business_key, deleted_lsn)
    SELECT source_system, business_key, source_lsn FROM apply WHERE operation = 'D'
    ON CONFLICT (source_system, business_key) DO UPDATE
    SET deleted_lsn = EXCLUDED.deleted_lsn
    WHERE EXCLUDED.deleted_lsn > txn_tombstone.deleted_lsn
),
upsert_live AS (
    INSERT INTO txn_current AS c (source_system, business_key, amount, status, source_lsn)
    SELECT source_system, business_key, amount, status, source_lsn FROM apply WHERE operation <> 'D'
    ON CONFLICT (source_system, business_key) DO UPDATE
    SET amount = EXCLUDED.amount, status = EXCLUDED.status, source_lsn = EXCLUDED.source_lsn
    WHERE EXCLUDED.source_lsn > c.source_lsn
),
clear_tombstone AS (
    DELETE FROM txn_tombstone d
    USING apply a
    WHERE a.operation <> 'D'
      AND d.source_system = a.source_system AND d.business_key = a.business_key
)
SELECT (SELECT count(*) FROM apply) AS keys_applied;
