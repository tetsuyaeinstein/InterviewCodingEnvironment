-- SQL-007 alternative (b): compute two explicit "parent exists" flags with EXISTS, then classify.
-- EXISTS never returns NULL (unlike NOT IN over a NULLable list), so the flags are always TRUE/FALSE.
-- NULL keys are tested first and explicitly, so they are never mislabelled as "missing".
WITH flagged AS (
    SELECT s.load_batch_id,
           s.transaction_id,
           s.line_number,
           s.product_id,
           EXISTS (SELECT 1 FROM transactions t WHERE t.transaction_id = s.transaction_id) AS txn_exists,
           EXISTS (SELECT 1 FROM products p     WHERE p.product_id     = s.product_id)     AS product_exists
    FROM stg_transaction_items s
)
SELECT load_batch_id,
       transaction_id,
       line_number,
       product_id,
       CASE
           WHEN transaction_id IS NULL                    THEN 'NULL_TRANSACTION_ID'
           WHEN product_id IS NULL                        THEN 'NULL_PRODUCT_ID'
           WHEN NOT txn_exists AND NOT product_exists     THEN 'MISSING_TRANSACTION_AND_PRODUCT'
           WHEN NOT txn_exists                            THEN 'MISSING_TRANSACTION'
           ELSE                                                'MISSING_PRODUCT'
       END AS issue
FROM flagged
WHERE NOT (txn_exists AND product_exists);
