-- SQL-020 alternative (b): recursive CTE that replays the ledger one step at a time.
-- Number the entries per account in application order, then carry the balance from step n to n + 1.
-- Much slower than a window sum, but it generalises to state machines where the next state is not a
-- plain sum (overdraft fees, interest, caps), and it carries the previous balance with it.
WITH RECURSIVE ordered AS (
    SELECT account_id, entry_id, posting_ts, signed_amount,
           ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY posting_ts, entry_id) AS seq
    FROM account_ledger
    WHERE account_id BETWEEN 1 AND 5
),
replay AS (
    SELECT o.account_id, o.entry_id, o.posting_ts, o.signed_amount, o.seq,
           0::numeric                  AS prev_balance,
           o.signed_amount::numeric    AS running_balance
    FROM ordered o
    WHERE o.seq = 1
    UNION ALL
    SELECT o.account_id, o.entry_id, o.posting_ts, o.signed_amount, o.seq,
           r.running_balance,
           r.running_balance + o.signed_amount
    FROM replay r
    JOIN ordered o ON o.account_id = r.account_id AND o.seq = r.seq + 1
)
SELECT account_id,
       entry_id,
       posting_ts,
       signed_amount,
       running_balance,
       running_balance < 0                         AS is_negative,
       running_balance < 0 AND prev_balance >= 0   AS enters_negative
FROM replay;
