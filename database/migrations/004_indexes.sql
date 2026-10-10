-- 004_indexes.sql — baseline secondary indexes.
-- Deliberately NOT included: the composite (customer_id, transaction_ts) index and other
-- "answer" indexes that the performance exercises (SQL-051..053) ask you to design.
-- Those exercises build candidate indexes inside disposable lab_sb_* sandbox schemas.

CREATE INDEX IF NOT EXISTS ix_transactions_customer       ON transactions (customer_id);
CREATE INDEX IF NOT EXISTS ix_transactions_ts             ON transactions (transaction_ts);
CREATE INDEX IF NOT EXISTS ix_transactions_store_ts       ON transactions (store_id, transaction_ts);
CREATE INDEX IF NOT EXISTS ix_transaction_items_product   ON transaction_items (product_id);
CREATE INDEX IF NOT EXISTS ix_refunds_transaction         ON refunds (transaction_id);
CREATE INDEX IF NOT EXISTS ix_customer_events_cust_ts     ON customer_events (customer_id, event_ts);
CREATE INDEX IF NOT EXISTS ix_account_ledger_acct_ts      ON account_ledger (account_id, posting_ts, entry_id);
CREATE INDEX IF NOT EXISTS ix_device_status_device_ts     ON device_status_events (device_id, event_ts);
CREATE INDEX IF NOT EXISTS ix_dim_customer_scd2_bk        ON dim_customer_scd2 (customer_id, effective_from);
CREATE INDEX IF NOT EXISTS ix_cdc_key_lsn                 ON cdc_transaction_events (source_system, business_key, source_lsn);
CREATE INDEX IF NOT EXISTS ix_event_ingestion_raw_id      ON event_ingestion_log (raw_event_id);
CREATE INDEX IF NOT EXISTS ix_raw_txn_events_txn          ON raw_transaction_events (transaction_id);
CREATE INDEX IF NOT EXISTS ix_subscriptions_customer      ON subscriptions (customer_id, start_date);
CREATE INDEX IF NOT EXISTS ix_employees_manager           ON employees (manager_id);
