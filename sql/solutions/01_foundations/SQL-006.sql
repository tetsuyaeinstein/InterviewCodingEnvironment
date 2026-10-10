-- SQL-006 reference solution: one pass, conditional aggregation with FILTER (SQL standard, PostgreSQL 9.4+).
-- COUNT(*) FILTER (...) is 0 when nothing matches; SUM(...) FILTER (...) is NULL, hence the COALESCE.
-- DECLINED rows are counted (total + declined_count) but never contribute to any amount column.
SELECT store_id,
       COUNT(*)                                                                          AS total_txn_count,
       COUNT(*) FILTER (WHERE transaction_status = 'COMPLETED')                          AS completed_count,
       COALESCE(SUM(gross_amount) FILTER (WHERE transaction_status = 'COMPLETED'), 0.00) AS completed_amount,
       COUNT(*) FILTER (WHERE transaction_status = 'PENDING')                            AS pending_count,
       COALESCE(SUM(gross_amount) FILTER (WHERE transaction_status = 'PENDING'), 0.00)   AS pending_amount,
       COUNT(*) FILTER (WHERE transaction_status = 'CANCELLED')                          AS cancelled_count,
       COALESCE(SUM(gross_amount) FILTER (WHERE transaction_status = 'CANCELLED'), 0.00) AS cancelled_amount,
       COUNT(*) FILTER (WHERE transaction_status = 'DECLINED')                           AS declined_count
FROM transactions
WHERE transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'      -- UTC business year 2025, half-open
  AND transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'
GROUP BY store_id;
