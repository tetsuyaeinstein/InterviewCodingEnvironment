-- SQL-044 alternative (b): set difference first, columns second.
-- EXCEPT compares whole rows with "not distinct" semantics (NULL equals NULL), so
-- (source EXCEPT target) ∪ (target EXCEPT source) yields exactly the keys that differ in any
-- business column, without writing eight IS DISTINCT FROM predicates for the filter.
-- Only those few keys are then joined back to name the columns that differ.
WITH s AS (
    SELECT transaction_id, customer_id, store_id, transaction_ts, amount, status,
           payment_method, merchant_ref, note
    FROM source_transactions
),
t AS (
    SELECT transaction_id, customer_id, store_id, transaction_ts, amount, status,
           payment_method, merchant_ref, note
    FROM target_transactions
),
diff_keys AS (
    SELECT transaction_id FROM (SELECT * FROM s EXCEPT SELECT * FROM t) only_in_source
    UNION
    SELECT transaction_id FROM (SELECT * FROM t EXCEPT SELECT * FROM s) only_in_target
)
SELECT k.transaction_id,
       CASE WHEN t.transaction_id IS NULL THEN 'MISSING_IN_TARGET'
            WHEN s.transaction_id IS NULL THEN 'EXTRA_IN_TARGET'
            ELSE 'CHANGED' END AS diff_type,
       CASE WHEN s.transaction_id IS NOT NULL AND t.transaction_id IS NOT NULL THEN
           array_to_string(ARRAY(
               SELECT c.col
               FROM (VALUES (1, 'customer_id',    s.customer_id    IS DISTINCT FROM t.customer_id),
                            (2, 'store_id',       s.store_id       IS DISTINCT FROM t.store_id),
                            (3, 'transaction_ts', s.transaction_ts IS DISTINCT FROM t.transaction_ts),
                            (4, 'amount',         s.amount         IS DISTINCT FROM t.amount),
                            (5, 'status',         s.status         IS DISTINCT FROM t.status),
                            (6, 'payment_method', s.payment_method IS DISTINCT FROM t.payment_method),
                            (7, 'merchant_ref',   s.merchant_ref   IS DISTINCT FROM t.merchant_ref),
                            (8, 'note',           s.note           IS DISTINCT FROM t.note)) AS c(pos, col, differs)
               WHERE c.differs
               ORDER BY c.pos), ',')
       END AS diff_columns
FROM diff_keys k
LEFT JOIN s ON s.transaction_id = k.transaction_id
LEFT JOIN t ON t.transaction_id = k.transaction_id;
