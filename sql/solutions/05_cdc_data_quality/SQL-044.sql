-- SQL-044 reference solution (a): FULL OUTER JOIN on the key, NULL-safe comparison per column.
-- IS DISTINCT FROM treats NULL vs NULL as equal and NULL vs value as different, which plain
-- `<>` does not (NULL <> 1001 is NULL, i.e. "not true", so the row would silently pass).
WITH joined AS (
    SELECT COALESCE(s.transaction_id, t.transaction_id) AS transaction_id,
           s.transaction_id IS NOT NULL AS in_source,
           t.transaction_id IS NOT NULL AS in_target,
           concat_ws(',',                                  -- concat_ws skips NULL arguments
               CASE WHEN s.customer_id    IS DISTINCT FROM t.customer_id    THEN 'customer_id'    END,
               CASE WHEN s.store_id       IS DISTINCT FROM t.store_id       THEN 'store_id'       END,
               CASE WHEN s.transaction_ts IS DISTINCT FROM t.transaction_ts THEN 'transaction_ts' END,
               CASE WHEN s.amount         IS DISTINCT FROM t.amount         THEN 'amount'         END,
               CASE WHEN s.status         IS DISTINCT FROM t.status         THEN 'status'         END,
               CASE WHEN s.payment_method IS DISTINCT FROM t.payment_method THEN 'payment_method' END,
               CASE WHEN s.merchant_ref   IS DISTINCT FROM t.merchant_ref   THEN 'merchant_ref'   END,
               CASE WHEN s.note           IS DISTINCT FROM t.note           THEN 'note'           END
           ) AS changed_columns
    FROM source_transactions s
    FULL OUTER JOIN target_transactions t
      ON t.transaction_id = s.transaction_id
)
SELECT transaction_id,
       CASE WHEN NOT in_target THEN 'MISSING_IN_TARGET'
            WHEN NOT in_source THEN 'EXTRA_IN_TARGET'
            ELSE 'CHANGED' END                         AS diff_type,
       CASE WHEN in_source AND in_target THEN changed_columns END AS diff_columns
FROM joined
WHERE NOT (in_source AND in_target)
   OR changed_columns <> '';
