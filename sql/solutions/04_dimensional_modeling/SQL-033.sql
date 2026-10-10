-- SQL-033 reference solution (a): anti-join for "no containing version", then one aggregate over
-- the customer's versions to find the nearest version ending before / starting after the fact.
WITH facts AS (
    SELECT t.transaction_id, t.customer_id, t.transaction_ts
    FROM transactions t
    WHERE t.transaction_status = 'COMPLETED'
      AND t.customer_id IS NOT NULL                       -- guests are not a dimension miss
),
unmatched AS (                                           -- no version contains the fact (half-open)
    SELECT f.*
    FROM facts f
    WHERE NOT EXISTS (
        SELECT 1
        FROM dim_customer_scd2 d
        WHERE d.customer_id = f.customer_id
          AND f.transaction_ts >= d.effective_from
          AND f.transaction_ts <  d.effective_to
    )
),
neighbours AS (                                          -- every version is now either before or after the fact
    SELECT u.transaction_id, u.customer_id, u.transaction_ts,
           COUNT(d.customer_sk)                                                  AS n_versions,
           MAX(d.effective_to)   FILTER (WHERE d.effective_to   <= u.transaction_ts) AS previous_version_end,
           MIN(d.effective_from) FILTER (WHERE d.effective_from >  u.transaction_ts) AS next_version_start
    FROM unmatched u
    LEFT JOIN dim_customer_scd2 d ON d.customer_id = u.customer_id
    GROUP BY u.transaction_id, u.customer_id, u.transaction_ts
)
SELECT transaction_id,
       customer_id,
       transaction_ts,
       CASE
           WHEN n_versions = 0                    THEN 'CUSTOMER_NOT_IN_DIMENSION'
           WHEN previous_version_end IS NULL      THEN 'NO_VERSION_YET'
           WHEN next_version_start  IS NULL       THEN 'AFTER_LAST_VERSION'
           ELSE                                        'GAP_BETWEEN_VERSIONS'
       END AS reason,
       previous_version_end,
       next_version_start
FROM neighbours;
