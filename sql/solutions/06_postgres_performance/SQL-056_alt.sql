-- SQL-056 alternative (b): no pg_input_is_valid(). A strict regular-expression guard decides
-- whether the text is a plain decimal (optional sign, digits, optional fraction, optional exponent)
-- and only then is it cast; CASE evaluates lazily so the cast never sees 'N/A'.
-- Trade-off: you must keep the regex in sync with numeric's real grammar; pg_input_is_valid is exact.
SELECT e.event_id,
       e.event_type,
       p.amount,
       CASE WHEN e.payload -> 'is_member' = 'true'::jsonb  OR lower(btrim(e.payload ->> 'is_member')) = 'true'  AND jsonb_typeof(e.payload -> 'is_member') = 'string' THEN true
            WHEN e.payload -> 'is_member' = 'false'::jsonb OR lower(btrim(e.payload ->> 'is_member')) = 'false' AND jsonb_typeof(e.payload -> 'is_member') = 'string' THEN false
       END AS is_member,
       e.payload ->> 'device' AS device,
       (e.event_type = 'checkout' AND p.amount IS NULL) OR COALESCE(p.amount < 0, false) AS has_amount_issue,
       CASE WHEN p.amount < 0 THEN 'NEGATIVE'
            WHEN e.event_type = 'checkout' AND p.amount IS NULL AND COALESCE(jsonb_typeof(e.payload -> 'amount'), 'null') = 'null' THEN 'MISSING'
            WHEN e.event_type = 'checkout' AND p.amount IS NULL THEN 'INVALID'
       END AS amount_issue
FROM customer_events e
CROSS JOIN LATERAL (
    SELECT CASE
             WHEN jsonb_typeof(e.payload -> 'amount') = 'number' THEN (e.payload ->> 'amount')::numeric
             WHEN jsonb_typeof(e.payload -> 'amount') = 'string'
                  AND btrim(e.payload ->> 'amount') ~ '^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$'
                  THEN btrim(e.payload ->> 'amount')::numeric
           END AS amount
) p
WHERE e.customer_id = 67;
