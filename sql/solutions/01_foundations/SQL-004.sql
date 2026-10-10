-- SQL-004 reference solution (a): one aggregation pass per transaction_id.
-- Three different identities live in this feed:
--   delivery_id    = one physical delivery (the broker's unit; every redelivery gets a new one)
--   message_id     = one logical message (the producer's unit; repeats on redelivery)
--   transaction_id = the business key (exactly one CREATED fact is expected per key)
WITH per_txn AS (
    SELECT transaction_id,
           COUNT(*)                                                                 AS deliveries,
           COUNT(DISTINCT message_id)                                               AS distinct_messages,
           COUNT(DISTINCT message_id) FILTER (WHERE event_type = 'CREATED')         AS created_messages,
           COUNT(DISTINCT message_id) FILTER (WHERE event_type = 'STATUS_CHANGED')  AS status_change_messages,
           -- jsonb equality is semantic (key order and whitespace do not matter), so DISTINCT on jsonb
           -- counts genuinely different CREATED payloads. Only CREATED payloads are compared:
           -- a STATUS_CHANGED payload is supposed to differ (it carries the new status).
           COUNT(DISTINCT payload) FILTER (WHERE event_type = 'CREATED')            AS created_payload_versions
    FROM raw_transaction_events
    GROUP BY transaction_id
    HAVING COUNT(*) > 1                      -- the business key appears in more than one delivery
)
SELECT transaction_id,
       deliveries,
       distinct_messages,
       created_messages,
       status_change_messages,
       deliveries > distinct_messages AS has_redelivery,      -- at least one message arrived twice
       CASE                                                   -- precedence: most severe finding first
           WHEN created_messages > 1 AND created_payload_versions > 1 THEN 'CONFLICTING_DUPLICATE'
           WHEN created_messages > 1                                  THEN 'BUSINESS_KEY_DUPLICATE'
           WHEN distinct_messages > 1                                 THEN 'LIFECYCLE_EVENTS'
           ELSE                                                            'REDELIVERY_ONLY'
       END AS classification
FROM per_txn;
