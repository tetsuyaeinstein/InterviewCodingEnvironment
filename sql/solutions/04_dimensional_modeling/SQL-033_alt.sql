-- SQL-033 reference solution (b): outer join on the validity interval and keep the facts that
-- found nothing; then two LATERAL index probes fetch the closest version before and after.
-- Each probe is a backward/forward scan of dim_customer_scd2(customer_id, effective_from) with
-- LIMIT 1, which is the plan you want when only a handful of facts are unmatched.
SELECT t.transaction_id,
       t.customer_id,
       t.transaction_ts,
       CASE
           WHEN NOT EXISTS (SELECT 1 FROM dim_customer_scd2 x WHERE x.customer_id = t.customer_id)
                                         THEN 'CUSTOMER_NOT_IN_DIMENSION'
           WHEN prev.effective_to IS NULL THEN 'NO_VERSION_YET'
           WHEN nxt.effective_from IS NULL THEN 'AFTER_LAST_VERSION'
           ELSE 'GAP_BETWEEN_VERSIONS'
       END AS reason,
       prev.effective_to   AS previous_version_end,
       nxt.effective_from  AS next_version_start
FROM transactions t
LEFT JOIN dim_customer_scd2 hit
       ON hit.customer_id = t.customer_id
      AND t.transaction_ts >= hit.effective_from
      AND t.transaction_ts <  hit.effective_to
LEFT JOIN LATERAL (                       -- latest version that ended at or before the fact
        SELECT d.effective_to
        FROM dim_customer_scd2 d
        WHERE d.customer_id = t.customer_id
          AND d.effective_to <= t.transaction_ts
        ORDER BY d.effective_to DESC
        LIMIT 1) prev ON true
LEFT JOIN LATERAL (                       -- earliest version that starts after the fact
        SELECT d.effective_from
        FROM dim_customer_scd2 d
        WHERE d.customer_id = t.customer_id
          AND d.effective_from > t.transaction_ts
        ORDER BY d.effective_from
        LIMIT 1) nxt ON true
WHERE t.transaction_status = 'COMPLETED'
  AND t.customer_id IS NOT NULL
  AND hit.customer_sk IS NULL;            -- anti-join: no containing version
