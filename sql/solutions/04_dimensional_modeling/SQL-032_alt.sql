-- SQL-032 reference solution (b): PostgreSQL range types.
-- tstzrange(from, to) defaults to '[)' (half-open), so && (overlaps) treats touching versions as
-- NOT overlapping, and * returns the intersection. One pass with a LATERAL "issue generator"
-- handles the single-row checks; a GROUP BY finds customers with several current rows.
WITH v AS (
    SELECT customer_id, customer_sk, is_current,
           tstzrange(effective_from, effective_to) AS validity,           -- '[)' by default
           effective_to = TIMESTAMPTZ '9999-12-31 00:00:00+00'  AS is_open_ended
    FROM dim_customer_scd2
),
pairs AS (
    SELECT a.customer_id, a.customer_sk, b.customer_sk AS other_customer_sk,
           a.validity * b.validity AS overlap                               -- range intersection
    FROM v a
    JOIN v b ON b.customer_id = a.customer_id
            AND b.customer_sk > a.customer_sk
            AND a.validity && b.validity
),
multi AS (
    SELECT customer_id
    FROM v
    GROUP BY customer_id
    HAVING COUNT(*) FILTER (WHERE is_current) > 1
)
SELECT customer_id, 'OVERLAPPING_VERSIONS' AS issue_type, customer_sk, other_customer_sk,
       lower(overlap) AS overlap_from, upper(overlap) AS overlap_to
FROM pairs
UNION ALL
SELECT v.customer_id, i.issue_type, v.customer_sk, NULL::bigint, NULL::timestamptz, NULL::timestamptz
FROM v
LEFT JOIN multi m ON m.customer_id = v.customer_id
CROSS JOIN LATERAL (
    VALUES (CASE WHEN v.is_current AND m.customer_id IS NOT NULL     THEN 'MULTIPLE_CURRENT'     END),
           (CASE WHEN v.is_current AND NOT v.is_open_ended           THEN 'CLOSED_BUT_CURRENT'   END),
           (CASE WHEN NOT v.is_current AND v.is_open_ended           THEN 'OPEN_BUT_NOT_CURRENT' END)
) AS i(issue_type)
WHERE i.issue_type IS NOT NULL;
