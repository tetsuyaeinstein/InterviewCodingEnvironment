-- SQL-028 reference solution (a): range join on the half-open validity interval.
-- LEFT JOIN keeps lines whose product has no price history (product 7) with NULL list price.
SELECT ti.transaction_id,
       ti.line_number,
       ti.product_id,
       t.transaction_ts,
       ti.unit_price,
       ph.price                  AS list_price,
       ti.unit_price - ph.price  AS price_diff        -- NULL when there is no list price
FROM transactions t
JOIN transaction_items ti
  ON ti.transaction_id = t.transaction_id
LEFT JOIN product_price_history ph
  ON  ph.product_id  = ti.product_id
  AND ph.valid_from <= t.transaction_ts                                  -- inclusive start
  AND (ph.valid_to IS NULL OR t.transaction_ts < ph.valid_to)            -- exclusive end, NULL = open
WHERE t.transaction_status = 'COMPLETED'
  AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
  AND t.transaction_ts <  TIMESTAMPTZ '2025-07-01 00:00:00+00'
  AND ti.product_id IN (1, 3, 7, 9);
