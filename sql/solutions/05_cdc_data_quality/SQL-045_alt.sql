-- SQL-045 alternative (b): explicit length-prefixed encoding + md5.
--
-- Each column becomes either 'N' (SQL NULL) or 'V<length>:<value>'. The length prefix makes the
-- encoding self-delimiting, so no escaping is needed and no value can imitate a boundary:
--   ('AB','C')  -> V2:AB V1:C      ('A','BC') -> V1:A V2:BC
--   ('X|Y',NULL)-> V3:X|Y N        ('X','Y')  -> V1:X V1:Y
--   'NULL'      -> V4:NULL         NULL       -> N          ''  -> V0:
-- md5 (128-bit) is fine for change detection between two copies of the same key (accidental
-- collisions are ~2^-64 at billions of rows); use sha256 when fingerprints are compared across
-- keys at huge scale or when an adversary could craft inputs.
WITH both_systems AS (
    SELECT 'SOURCE' AS system, transaction_id, customer_id, store_id, transaction_ts, amount,
           status, payment_method, merchant_ref, note
    FROM source_transactions
    UNION ALL
    SELECT 'TARGET', transaction_id, customer_id, store_id, transaction_ts, amount,
           status, payment_method, merchant_ref, note
    FROM target_transactions
),
as_text AS (                                   -- stable text rendering per column, NULL kept
    SELECT system, transaction_id,
           ARRAY[customer_id::text,
                 store_id::text,
                 to_char(transaction_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US'),
                 to_char(amount, 'FM999999999990.00'),
                 status, payment_method, merchant_ref, note] AS cols
    FROM both_systems
)
SELECT system,
       transaction_id,
       md5(array_to_string(ARRAY(
               SELECT CASE WHEN c IS NULL THEN 'N' ELSE 'V' || length(c) || ':' || c END
               FROM unnest(cols) WITH ORDINALITY AS u(c, pos)
               ORDER BY pos), '')) AS row_fingerprint
FROM as_text;
