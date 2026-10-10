-- SQL-046 reference solution: dedupe the batch to the newest version per key, then upsert with a
-- guard so stale versions never overwrite newer stored rows.
INSERT INTO txn_current AS t (source_system, business_key, amount, status, source_lsn)
SELECT DISTINCT ON (source_system, business_key)
       source_system, business_key, amount, status, source_lsn
FROM stg_txn_batch
ORDER BY source_system, business_key, source_lsn DESC
ON CONFLICT (source_system, business_key) DO UPDATE
SET amount     = EXCLUDED.amount,
    status     = EXCLUDED.status,
    source_lsn = EXCLUDED.source_lsn
WHERE EXCLUDED.source_lsn > t.source_lsn;
