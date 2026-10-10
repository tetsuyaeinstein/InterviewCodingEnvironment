-- SQL-017 alternative (b): both tiers from first principles with integer arithmetic
-- (portable to engines without NTILE/CUME_DIST, and proves what those functions do).
--   equal-size tiers : N = 4q + r; the first r tiers hold q + 1 rows, the others q rows.
--   tie-safe tiers   : s = customers with spend >= mine (correlated count), tier = ceil(4s / N).
WITH cohort AS (
    SELECT customer_id
    FROM customers
    WHERE registered_at >= TIMESTAMPTZ '2023-12-01 00:00:00+00'
      AND registered_at <  TIMESTAMPTZ '2023-12-02 00:00:00+00'
),
spend AS (
    SELECT c.customer_id,
           COALESCE((SELECT SUM(t.gross_amount)
                       FROM transactions t
                      WHERE t.customer_id = c.customer_id
                        AND t.transaction_status = 'COMPLETED'
                        AND t.transaction_ts >= TIMESTAMPTZ '2025-01-01 00:00:00+00'
                        AND t.transaction_ts <  TIMESTAMPTZ '2026-01-01 00:00:00+00'), 0) AS spend_2025
    FROM cohort c
),
numbered AS (
    SELECT s.customer_id,
           s.spend_2025,
           ROW_NUMBER() OVER (ORDER BY s.spend_2025 DESC, s.customer_id)           AS rn,
           (SELECT COUNT(*) FROM spend s2 WHERE s2.spend_2025 >= s.spend_2025)     AS s_ge,
           (SELECT COUNT(*) FROM spend)                                            AS n
    FROM spend s
),
sized AS (
    SELECT *, n / 4 AS q, n % 4 AS r FROM numbered
)
SELECT customer_id,
       spend_2025,
       CASE WHEN rn <= r * (q + 1) THEN (rn - 1) / (q + 1) + 1               -- inside the bigger tiers
            ELSE r + (rn - r * (q + 1) - 1) / q + 1                          -- inside the smaller tiers
       END::int                                    AS ntile_quartile,
       ((4 * s_ge + n - 1) / n)::int               AS tie_safe_quartile      -- integer ceil(4s/N)
FROM sized;
