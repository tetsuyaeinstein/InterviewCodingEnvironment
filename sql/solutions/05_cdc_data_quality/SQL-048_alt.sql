-- SQL-048 alternative (b): a single PostgreSQL 17 MERGE with WHEN NOT MATCHED BY SOURCE.
--
-- The source is the recomputed summary for the batch's dates. Rows are SET (not incremented),
-- which is what makes a re-run harmless. WHEN NOT MATCHED BY SOURCE deletes target rows that
-- have no recomputed counterpart, but the action condition limits that to the restated dates,
-- so older days stay untouched. Without that condition the MERGE would wipe the whole table.
WITH latest AS (
    SELECT transaction_id, store_id, transaction_ts, transaction_status, gross_amount,
           ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY delivery_id DESC) AS rn
    FROM stg_sales_batch
),
restated_dates AS (
    SELECT DISTINCT (transaction_ts AT TIME ZONE 'UTC')::date AS sales_date FROM stg_sales_batch
),
recomputed AS (
    SELECT (transaction_ts AT TIME ZONE 'UTC')::date AS sales_date, store_id,
           COUNT(*) AS txn_count, SUM(gross_amount) AS gross_amount
    FROM latest
    WHERE rn = 1 AND transaction_status = 'COMPLETED'
    GROUP BY 1, 2
)
MERGE INTO daily_store_sales AS t
USING recomputed AS s
   ON t.sales_date = s.sales_date AND t.store_id = s.store_id
WHEN MATCHED AND (t.txn_count, t.gross_amount) IS DISTINCT FROM (s.txn_count, s.gross_amount) THEN
    UPDATE SET txn_count = s.txn_count, gross_amount = s.gross_amount
WHEN NOT MATCHED BY TARGET THEN
    INSERT (sales_date, store_id, txn_count, gross_amount)
    VALUES (s.sales_date, s.store_id, s.txn_count, s.gross_amount)
WHEN NOT MATCHED BY SOURCE
     AND t.sales_date IN (SELECT sales_date FROM restated_dates) THEN
    DELETE;
