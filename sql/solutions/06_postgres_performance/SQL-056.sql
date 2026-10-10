-- SQL-056 reference solution (a): classify the JSON type first, then parse strings with
-- pg_input_is_valid() so that invalid text becomes NULL instead of raising an error.
WITH raw AS (
    SELECT event_id, event_type, payload,
           jsonb_typeof(payload -> 'amount') AS amount_type,
           btrim(payload ->> 'amount')       AS amount_txt          -- ' 42.10 ' -> '42.10'; trim policy: strip blanks
    FROM customer_events
    WHERE customer_id = 67
),
typed AS (
    SELECT event_id, event_type, payload, amount_type,
           CASE amount_type
                WHEN 'number' THEN (payload ->> 'amount')::numeric
                WHEN 'string' THEN CASE
                        WHEN pg_input_is_valid(amount_txt, 'numeric')
                             AND amount_txt !~* '^[+-]?(nan|inf)'      -- 'NaN'/'Infinity' are valid numerics: reject
                        THEN amount_txt::numeric
                     END                                              -- else NULL ('N/A', '', 'abc')
           END AS amount
    FROM raw
)
SELECT event_id,
       event_type,
       amount,
       CASE jsonb_typeof(payload -> 'is_member')
            WHEN 'boolean' THEN (payload ->> 'is_member')::boolean
            WHEN 'string'  THEN CASE lower(btrim(payload ->> 'is_member'))
                                     WHEN 'true'  THEN true
                                     WHEN 'false' THEN false          -- 'yes'/'1'/'on' are NOT accepted: NULL
                                END
       END AS is_member,
       payload ->> 'device' AS device,
       (event_type = 'checkout' AND amount IS NULL) OR COALESCE(amount < 0, false) AS has_amount_issue,
       CASE WHEN amount < 0                                          THEN 'NEGATIVE'
            WHEN event_type = 'checkout' AND amount IS NULL
                 AND (amount_type IS NULL OR amount_type = 'null')   THEN 'MISSING'
            WHEN event_type = 'checkout' AND amount IS NULL          THEN 'INVALID'
       END AS amount_issue
FROM typed;
