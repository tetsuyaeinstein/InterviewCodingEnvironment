-- SQL-020 reference solution (a): row-based running sum, then LAG of that balance.
WITH balances AS (
    SELECT account_id,
           entry_id,
           posting_ts,
           signed_amount,
           SUM(signed_amount) OVER (PARTITION BY account_id
                                    ORDER BY posting_ts, entry_id            -- total order: ts, then id
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_balance
    FROM account_ledger
    WHERE account_id BETWEEN 1 AND 5
)
SELECT account_id,
       entry_id,
       posting_ts,
       signed_amount,
       running_balance,
       running_balance < 0 AS is_negative,                                    -- exactly 0.00 is not negative
       running_balance < 0
         AND LAG(running_balance, 1, 0::numeric) OVER (PARTITION BY account_id
                                                       ORDER BY posting_ts, entry_id) >= 0 AS enters_negative
FROM balances;
