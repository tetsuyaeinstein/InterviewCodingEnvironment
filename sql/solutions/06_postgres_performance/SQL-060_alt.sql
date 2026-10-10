-- SQL-060 alternative (b): rebuild instead of delete. Create the de-duplicated copy with DISTINCT ON,
-- swap it in, then create a UNIQUE INDEX (an index, not a table constraint) and load with
-- ON CONFLICT DO NOTHING, with the batch de-duplicated up front by DISTINCT ON as well.
-- Trade-off: no DELETE (no dead tuples, no ctid), but it needs a rewrite of the table, exclusive
-- locks for the swap and re-creation of grants/indexes. That is the pattern for very large tables.
CREATE TABLE txn_events_dedup AS
SELECT DISTINCT ON (message_id)
       message_id, transaction_id, event_type, delivered_at, payload
FROM txn_events
ORDER BY message_id, delivered_at;

DROP TABLE txn_events;
ALTER TABLE txn_events_dedup RENAME TO txn_events;

CREATE UNIQUE INDEX ux_txn_events_message ON txn_events (message_id);

INSERT INTO txn_events (message_id, transaction_id, event_type, delivered_at, payload)
SELECT DISTINCT ON (message_id)
       message_id, transaction_id, event_type, delivered_at, payload
FROM new_batch
ORDER BY message_id, delivered_at
ON CONFLICT (message_id) DO NOTHING;
