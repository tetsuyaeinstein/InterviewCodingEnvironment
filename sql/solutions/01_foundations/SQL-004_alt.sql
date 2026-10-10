-- SQL-004 alternative (b): collapse deliveries to logical messages first (exactly what an
-- idempotent consumer does with its dedup key), then aggregate messages, and detect conflicting
-- CREATED payloads with a pairwise self-join instead of COUNT(DISTINCT jsonb).
WITH delivery_counts AS (                  -- delivery grain -> one row per repeated key
    SELECT transaction_id,
           COUNT(*) AS deliveries
    FROM raw_transaction_events
    GROUP BY transaction_id
    HAVING COUNT(*) > 1
),
messages AS (                              -- message grain: one row per message_id
    SELECT DISTINCT ON (message_id)
           message_id, transaction_id, event_type, payload
    FROM raw_transaction_events
    WHERE transaction_id IN (SELECT transaction_id FROM delivery_counts)
    ORDER BY message_id, delivery_id       -- keep the first delivery of each message
),
conflicts AS (                             -- two CREATED messages for one key whose payloads differ
    SELECT DISTINCT a.transaction_id
    FROM messages a
    JOIN messages b
      ON  b.transaction_id = a.transaction_id
      AND b.event_type     = 'CREATED'
      AND b.message_id     > a.message_id  -- each unordered pair once
      AND b.payload IS DISTINCT FROM a.payload
    WHERE a.event_type = 'CREATED'
),
per_txn AS (
    SELECT transaction_id,
           COUNT(*)                                                     AS distinct_messages,
           SUM(CASE WHEN event_type = 'CREATED'        THEN 1 ELSE 0 END) AS created_messages,
           SUM(CASE WHEN event_type = 'STATUS_CHANGED' THEN 1 ELSE 0 END) AS status_change_messages
    FROM messages
    GROUP BY transaction_id
)
SELECT d.transaction_id,
       d.deliveries,
       p.distinct_messages,
       p.created_messages,
       p.status_change_messages,
       d.deliveries > p.distinct_messages AS has_redelivery,
       CASE
           WHEN c.transaction_id IS NOT NULL THEN 'CONFLICTING_DUPLICATE'
           WHEN p.created_messages > 1       THEN 'BUSINESS_KEY_DUPLICATE'
           WHEN p.distinct_messages > 1      THEN 'LIFECYCLE_EVENTS'
           ELSE                                   'REDELIVERY_ONLY'
       END AS classification
FROM delivery_counts d
JOIN per_txn p USING (transaction_id)
LEFT JOIN conflicts c USING (transaction_id);
