-- SQL-028 reference solution (b): "latest version at or before the timestamp" via LATERAL.
-- For each line, take the price row with the greatest valid_from <= transaction_ts, then check
-- that the row is still valid at that instant (valid_to is exclusive; NULL = open-ended).
-- With non-overlapping history (guaranteed here by an EXCLUDE constraint) this equals the range join;
-- the explicit valid_to check makes a gap in the history return NULL instead of a stale price.
SELECT ti.transaction_id,
       ti.line_number,
       ti.product_id,
       t.transaction_ts,
       ti.unit_price,
       lp.price                  AS list_price,
       ti.unit_price - lp.price  AS price_diff
FROM transactions t
JOIN transaction_items ti
  ON ti.transaction_id = t.transaction_id
LEFT JOIN LATERAL (
    SELECT CASE WHEN ph.valid_to IS NULL OR t.transaction_ts < ph.valid_to THEN ph.price END AS price
    FROM product_price_history ph
    WHERE ph.product_id = ti.product_id
      AND ph.valid_from <= t.transaction_ts
    ORDER BY ph.valid_from DESC          -- uses the (product_id, valid_from) primary key backwards
    LIMIT 1
) lp ON true
WHERE t.transaction_status = 'COMPLETED'
  AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
  AND t.transaction_ts <  TIMESTAMPTZ '2025-07-01 00:00:00+00'
  AND ti.product_id IN (1, 3, 7, 9);
