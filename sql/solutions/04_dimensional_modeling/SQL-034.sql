-- SQL-034 reference solution (a): set-based. Running balance per posting -> daily aggregates ->
-- dense calendar x accounts grid -> carry the balance forward with a cumulative window sum.
WITH params AS (
    SELECT DATE '2025-01-01' AS first_day, DATE '2025-01-07' AS last_day
),
grid AS (                                   -- dense periodic-snapshot grain: account x day
    SELECT a.account_id, d::date AS balance_date
    FROM accounts a
    CROSS JOIN params p
    CROSS JOIN generate_series(p.first_day, p.last_day, INTERVAL '1 day') AS d
    WHERE a.account_id BETWEEN 1 AND 5
),
opening AS (                                -- everything posted before the first snapshot day
    SELECT a.account_id, COALESCE(SUM(l.signed_amount), 0) AS opening_balance
    FROM accounts a
    CROSS JOIN params p
    LEFT JOIN account_ledger l
           ON l.account_id = a.account_id
          AND l.posting_ts < p.first_day::timestamp AT TIME ZONE 'UTC'
    WHERE a.account_id BETWEEN 1 AND 5
    GROUP BY a.account_id
),
postings AS (                               -- postings inside the window, with the running balance
    SELECT l.account_id,
           (l.posting_ts AT TIME ZONE 'UTC')::date AS balance_date,
           l.signed_amount,
           o.opening_balance
             + SUM(l.signed_amount) OVER (PARTITION BY l.account_id
                                          ORDER BY l.posting_ts, l.entry_id
                                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS balance_after
    FROM account_ledger l
    JOIN opening o ON o.account_id = l.account_id
    CROSS JOIN params p
    WHERE l.posting_ts >= p.first_day::timestamp AT TIME ZONE 'UTC'
      AND l.posting_ts <  (p.last_day + 1)::timestamp AT TIME ZONE 'UTC'
),
daily AS (
    SELECT account_id, balance_date,
           COUNT(*)           AS posting_count,
           SUM(signed_amount) AS net_change,
           MIN(balance_after) AS lowest_after_posting
    FROM postings
    GROUP BY account_id, balance_date
),
dense AS (
    SELECT g.account_id, g.balance_date,
           COALESCE(d.posting_count, 0) AS posting_count,
           COALESCE(d.net_change, 0)    AS net_change,
           d.lowest_after_posting,
           o.opening_balance
             + SUM(COALESCE(d.net_change, 0)) OVER (PARTITION BY g.account_id ORDER BY g.balance_date
                                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS closing_balance
    FROM grid g
    JOIN opening o USING (account_id)
    LEFT JOIN daily d USING (account_id, balance_date)
)
SELECT account_id,
       balance_date,
       posting_count,
       net_change,
       closing_balance,
       -- the day starts at (closing - net_change); LEAST ignores NULL on days without postings
       LEAST(closing_balance - net_change, lowest_after_posting) AS lowest_balance
FROM dense;
