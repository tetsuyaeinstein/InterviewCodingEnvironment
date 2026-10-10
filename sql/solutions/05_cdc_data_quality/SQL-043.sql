-- SQL-043 reference solution: classify every completed December sale as on-time or late
-- against the reporting cut-off, then aggregate both populations per business date in one pass.
-- "Late" = ingested_at >= cut-off (the report used ingested_at < cut-off, so a row ingested
-- exactly at the cut-off was NOT in the report).
WITH cutoff AS (
    SELECT watermark_ts
    FROM pipeline_watermarks
    WHERE pipeline_name = 'daily_sales_report'
      AND source_system = 'ALL'
),
december_sales AS (
    SELECT (t.transaction_ts AT TIME ZONE 'UTC')::date AS business_date,
           t.gross_amount,
           (t.ingested_at >= c.watermark_ts)            AS is_late
    FROM transactions t
    CROSS JOIN cutoff c
    WHERE t.transaction_status = 'COMPLETED'
      AND t.transaction_ts >= timestamptz '2025-12-01 00:00:00+00'
      AND t.transaction_ts <  timestamptz '2026-01-01 00:00:00+00'
)
SELECT business_date,
       COUNT(*) FILTER (WHERE is_late)                       AS late_txn_count,
       SUM(gross_amount) FILTER (WHERE is_late)              AS late_amount,
       COALESCE(SUM(gross_amount) FILTER (WHERE NOT is_late), 0) AS reported_amount,
       SUM(gross_amount)                                     AS final_amount,
       ROUND(100 * SUM(gross_amount) FILTER (WHERE is_late) / SUM(gross_amount), 2) AS late_pct
FROM december_sales
GROUP BY business_date
HAVING COUNT(*) FILTER (WHERE is_late) > 0;
