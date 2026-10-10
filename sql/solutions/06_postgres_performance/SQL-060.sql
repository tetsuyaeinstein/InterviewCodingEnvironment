-- SQL-060 reference solution (a): in-place dedup with ROW_NUMBER + ctid, then the unique constraint,
-- then an idempotent load with ON CONFLICT DO NOTHING.

-- 1) Remove duplicates, keeping the earliest delivery per message_id.
--    ctid (the physical row address) identifies exactly one row among otherwise identical copies.
DELETE FROM txn_events
WHERE ctid IN (
    SELECT ctid
    FROM (SELECT ctid,
                 row_number() OVER (PARTITION BY message_id ORDER BY delivered_at, ctid) AS rn
          FROM txn_events) d
    WHERE d.rn > 1
);

-- 2) Make the database enforce the key. Only possible AFTER step 1 (otherwise: duplicate key error).
ALTER TABLE txn_events ADD CONSTRAINT uq_txn_events_message UNIQUE (message_id);

-- 3) Load the new batch. Order by delivered_at so that when the batch itself holds the same message
--    twice, the earliest delivery is inserted first and the later one is skipped by DO NOTHING.
INSERT INTO txn_events (message_id, transaction_id, event_type, delivered_at, payload)
SELECT message_id, transaction_id, event_type, delivered_at, payload
FROM new_batch
ORDER BY delivered_at
ON CONFLICT (message_id) DO NOTHING;
