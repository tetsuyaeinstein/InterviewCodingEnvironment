-- SQL-032 reference solution (a): explicit comparisons, one branch per issue type.
-- Sentinel for "open-ended" = 9999-12-31 00:00:00+00 (convention of dim_customer_scd2).
WITH overlap_pairs AS (               -- every unordered pair of versions whose half-open intervals intersect
    SELECT a.customer_id,
           'OVERLAPPING_VERSIONS'::text           AS issue_type,
           a.customer_sk,
           b.customer_sk                          AS other_customer_sk,
           GREATEST(a.effective_from, b.effective_from) AS overlap_from,
           LEAST(a.effective_to, b.effective_to)        AS overlap_to
    FROM dim_customer_scd2 a
    JOIN dim_customer_scd2 b
      ON  b.customer_id = a.customer_id
      AND a.customer_sk < b.customer_sk           -- each pair once, never a row with itself
      AND a.effective_from < b.effective_to       -- [a) and [b) intersect  <=>  a.start < b.end AND b.start < a.end
      AND b.effective_from < a.effective_to       -- touching (a.end = b.start) is NOT an overlap
),
multi_current AS (              -- every current row of a customer that has more than one
    SELECT customer_id, 'MULTIPLE_CURRENT'::text AS issue_type, customer_sk
    FROM (SELECT customer_id, customer_sk, is_current,
                 COUNT(*) FILTER (WHERE is_current) OVER (PARTITION BY customer_id) AS n_current
          FROM dim_customer_scd2) x
    WHERE is_current AND n_current > 1
),
flag_mismatch AS (               -- is_current must be true exactly for open-ended rows
    SELECT customer_id,
           CASE WHEN is_current THEN 'CLOSED_BUT_CURRENT' ELSE 'OPEN_BUT_NOT_CURRENT' END AS issue_type,
           customer_sk
    FROM dim_customer_scd2
    WHERE is_current <> (effective_to = TIMESTAMPTZ '9999-12-31 00:00:00+00')
)
SELECT customer_id, issue_type, customer_sk, other_customer_sk, overlap_from, overlap_to
FROM overlap_pairs
UNION ALL
SELECT customer_id, issue_type, customer_sk, NULL::bigint, NULL::timestamptz, NULL::timestamptz
FROM multi_current
UNION ALL
SELECT customer_id, issue_type, customer_sk, NULL::bigint, NULL::timestamptz, NULL::timestamptz
FROM flag_mismatch;
