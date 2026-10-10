-- SQL-045 reference solution (a): hash a typed JSON array of the business columns.
--
-- jsonb_build_array(...)::text is an unambiguous encoding:
--   * every value is quoted/escaped by the JSON serializer, so delimiters inside values
--     ('X|Y', 'A,B', '"') can't shift column boundaries: ["AB","C"] <> ["A","BC"];
--   * SQL NULL becomes the JSON literal null, which differs from the string "NULL" and from "";
--   * position encodes the column, so (NULL, 'X') <> ('X', NULL).
-- Formatting is pinned explicitly where it could drift:
--   * transaction_ts is rendered in UTC with a fixed format (timestamptz::text depends on the
--     session TimeZone), and amount is rendered with its declared 2-decimal scale.
-- The key (transaction_id) and load metadata (extracted_at / loaded_at) are excluded, so the
-- same business row gets the same fingerprint in both systems.
WITH both_systems AS (
    SELECT 'SOURCE' AS system, transaction_id, customer_id, store_id, transaction_ts, amount,
           status, payment_method, merchant_ref, note
    FROM source_transactions
    UNION ALL
    SELECT 'TARGET', transaction_id, customer_id, store_id, transaction_ts, amount,
           status, payment_method, merchant_ref, note
    FROM target_transactions
)
SELECT system,
       transaction_id,
       encode(sha256(convert_to(
           jsonb_build_array(
               customer_id,
               store_id,
               to_char(transaction_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US'),
               amount::numeric(12,2)::text,
               status,
               payment_method,
               merchant_ref,
               note)::text,
           'UTF8')), 'hex') AS row_fingerprint
FROM both_systems;
