-- SQL-057 alternative (b): SQL/JSON path. In lax mode `$.items[*]` automatically wraps a non-array
-- (an object becomes a one-element sequence) and yields nothing for a missing key, so no explicit
-- jsonb_typeof guard is needed. The path filter drops items without a usable sku in the same step.
-- Trade-off: lax-mode behaviour is implicit; a reader must know the rule (strict mode would raise).
SELECT e.event_id,
       p.item ->> 'sku'                          AS sku,
       sum((p.item ->> 'qty')::int)::bigint      AS total_qty
FROM customer_events e
CROSS JOIN LATERAL jsonb_path_query(e.payload, 'lax $.items[*] ? (@.sku != null)') AS p(item)
WHERE e.event_type = 'checkout'
  AND e.event_ts >= TIMESTAMPTZ '2025-08-15 00:00:00+00'
  AND e.event_ts <  TIMESTAMPTZ '2025-08-16 00:00:00+00'
  AND (p.item ->> 'qty') ~ '^\s*[0-9]+\s*$'
GROUP BY e.event_id, p.item ->> 'sku';
