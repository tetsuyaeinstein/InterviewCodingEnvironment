-- SQL-057 reference solution (a): jsonb_array_elements in a LATERAL join, guarded by jsonb_typeof.
-- jsonb_array_elements raises "cannot extract elements from an object/scalar" for non-arrays, so the
-- argument is normalised first: array -> itself, object -> one-element array (single-item shorthand),
-- null / missing / anything else -> empty array (no rows).
SELECT e.event_id,
       i.item ->> 'sku'                  AS sku,
       sum((i.item ->> 'qty')::int)::bigint AS total_qty     -- duplicate lines of the same sku are summed
FROM customer_events e
CROSS JOIN LATERAL jsonb_array_elements(
        CASE jsonb_typeof(e.payload -> 'items')
             WHEN 'array'  THEN e.payload -> 'items'
             WHEN 'object' THEN jsonb_build_array(e.payload -> 'items')
             ELSE '[]'::jsonb
        END) AS i(item)
WHERE e.event_type = 'checkout'
  AND e.event_ts >= TIMESTAMPTZ '2025-08-15 00:00:00+00'
  AND e.event_ts <  TIMESTAMPTZ '2025-08-16 00:00:00+00'
  AND jsonb_typeof(i.item) = 'object'
  AND i.item ->> 'sku' IS NOT NULL                              -- JSON null or missing sku: dropped
  AND pg_input_is_valid(i.item ->> 'qty', 'integer')            -- 'two', 2.5, missing qty: dropped
GROUP BY e.event_id, i.item ->> 'sku';
