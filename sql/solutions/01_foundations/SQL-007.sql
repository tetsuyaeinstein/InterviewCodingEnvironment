-- SQL-007 reference solution (a): LEFT JOIN anti-join against both parents, classify with CASE.
-- Both parents are joined on their primary keys, so the LEFT JOINs cannot fan out: every staging
-- row (including exact duplicates, which are a separate problem) yields exactly one joined row.
SELECT s.load_batch_id,
       s.transaction_id,
       s.line_number,
       s.product_id,
       CASE                                       -- precedence as specified in the question
           WHEN s.transaction_id IS NULL                        THEN 'NULL_TRANSACTION_ID'
           WHEN s.product_id IS NULL                            THEN 'NULL_PRODUCT_ID'
           WHEN t.transaction_id IS NULL AND p.product_id IS NULL THEN 'MISSING_TRANSACTION_AND_PRODUCT'
           WHEN t.transaction_id IS NULL                        THEN 'MISSING_TRANSACTION'
           ELSE                                                      'MISSING_PRODUCT'
       END AS issue
FROM stg_transaction_items s
LEFT JOIN transactions t ON t.transaction_id = s.transaction_id   -- NULL key never matches -> t.* NULL
LEFT JOIN products     p ON p.product_id     = s.product_id
WHERE t.transaction_id IS NULL                    -- NULL or dangling transaction reference
   OR p.product_id IS NULL;                       -- NULL or dangling product reference
