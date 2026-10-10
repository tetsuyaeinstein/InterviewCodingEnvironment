-- SQL-048 reference solution (a): partition overwrite = delete the batch's dates, re-insert them
-- recomputed from the batch. Both statements depend only on the batch, never on what the target
-- held before, so running the script twice yields the same final state (idempotent).
--
-- Step 1: replace every business date contained in the batch (this also removes summary rows
--         that no longer have any completed sale, e.g. the 2025-12-09 store 4 row).
DELETE FROM daily_store_sales
WHERE sales_date IN (SELECT DISTINCT (transaction_ts AT TIME ZONE 'UTC')::date
                     FROM stg_sales_batch);

-- Step 2: recompute from the latest delivery of each transaction (redeliveries and corrections
--         collapse to one version), counting only versions whose final status is COMPLETED.
INSERT INTO daily_store_sales (sales_date, store_id, txn_count, gross_amount)
SELECT (transaction_ts AT TIME ZONE 'UTC')::date AS sales_date,
       store_id,
       COUNT(*)                                  AS txn_count,
       SUM(gross_amount)                         AS gross_amount
FROM (
    SELECT DISTINCT ON (transaction_id)
           transaction_id, store_id, transaction_ts, transaction_status, gross_amount
    FROM stg_sales_batch
    ORDER BY transaction_id, delivery_id DESC
) latest
WHERE transaction_status = 'COMPLETED'
GROUP BY 1, 2;
