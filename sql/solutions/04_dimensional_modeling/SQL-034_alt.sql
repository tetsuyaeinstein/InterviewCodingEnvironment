-- SQL-034 reference solution (b): calendar x accounts grid + correlated LATERAL lookups.
-- For every (account, day) cell: the start-of-day balance is "everything posted before midnight",
-- and the day's postings are replayed on top of it to get the count, net change and intraday low.
-- Easy to reason about and index-friendly (account_ledger(account_id, posting_ts, entry_id)),
-- but it re-reads the account's history once per cell: O(days x postings) instead of one pass.
SELECT a.account_id,
       g.d::date                                         AS balance_date,
       day_stats.posting_count,
       day_stats.net_change,
       sod.balance + day_stats.net_change                AS closing_balance,
       LEAST(sod.balance, day_stats.lowest_after_posting) AS lowest_balance
FROM accounts a
CROSS JOIN generate_series(DATE '2025-01-01', DATE '2025-01-07', INTERVAL '1 day') AS g(d)
CROSS JOIN LATERAL (                                  -- start-of-day balance (UTC midnight)
        SELECT COALESCE(SUM(l.signed_amount), 0) AS balance
        FROM account_ledger l
        WHERE l.account_id = a.account_id
          AND l.posting_ts < g.d::date::timestamp AT TIME ZONE 'UTC'
     ) sod
CROSS JOIN LATERAL (                                  -- replay the day's postings in ledger order
        SELECT COUNT(*)                         AS posting_count,
               COALESCE(SUM(p.signed_amount), 0) AS net_change,
               MIN(sod.balance + p.running)     AS lowest_after_posting   -- NULL when no postings
        FROM (SELECT l.signed_amount,
                     SUM(l.signed_amount) OVER (ORDER BY l.posting_ts, l.entry_id
                                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running
              FROM account_ledger l
              WHERE l.account_id = a.account_id
                AND l.posting_ts >= g.d::date::timestamp AT TIME ZONE 'UTC'
                AND l.posting_ts <  (g.d::date + 1)::timestamp AT TIME ZONE 'UTC') p
     ) day_stats
WHERE a.account_id BETWEEN 1 AND 5;
