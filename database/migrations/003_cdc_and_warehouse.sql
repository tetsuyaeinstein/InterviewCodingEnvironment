-- 003_cdc_and_warehouse.sql — SCD2 dimension, CDC feed, reconciliation snapshots,
-- pipeline control tables, ingestion logs, raw/staging landing tables, partitioned fact.

-- Type-2 customer dimension. Convention: [effective_from, effective_to) half-open,
-- current row has effective_to = '9999-12-31 00:00:00+00' and is_current = true.
-- No uniqueness constraints on purpose: a few known defects exist (see DATA_DICTIONARY.md).
CREATE TABLE IF NOT EXISTS dim_customer_scd2 (
    customer_sk     bigint PRIMARY KEY,                    -- surrogate key
    customer_id     integer     NOT NULL,                  -- business key (customers.customer_id)
    segment         text        NOT NULL,
    region          text,
    status          text        NOT NULL,
    effective_from  timestamptz NOT NULL,
    effective_to    timestamptz NOT NULL DEFAULT '9999-12-31 00:00:00+00',
    is_current      boolean     NOT NULL,
    CHECK (effective_to > effective_from)
);

-- Reconciliation: what the source system says vs what landed in the warehouse.
CREATE TABLE IF NOT EXISTS source_transactions (
    transaction_id  bigint PRIMARY KEY,
    customer_id     integer,
    store_id        integer       NOT NULL,
    transaction_ts  timestamptz   NOT NULL,
    amount          numeric(12,2) NOT NULL,
    status          text          NOT NULL,
    payment_method  text,
    merchant_ref    text,
    note            text,
    extracted_at    timestamptz   NOT NULL
);

CREATE TABLE IF NOT EXISTS target_transactions (
    transaction_id  bigint PRIMARY KEY,
    customer_id     integer,
    store_id        integer       NOT NULL,
    transaction_ts  timestamptz   NOT NULL,
    amount          numeric(12,2) NOT NULL,
    status          text          NOT NULL,
    payment_method  text,
    merchant_ref    text,
    note            text,
    loaded_at       timestamptz   NOT NULL
);

-- CDC change feed (events). Key = (source_system, business_key). source_lsn is the source
-- commit sequence and is the ONLY reliable ordering; ingested_at reflects arrival order.
-- payload is the full after-image for I/U and the key-only image for D.
CREATE TABLE IF NOT EXISTS cdc_transaction_events (
    cdc_event_id    bigint PRIMARY KEY,
    source_system   text        NOT NULL,
    business_key    text        NOT NULL,
    operation       char(1)     NOT NULL CHECK (operation IN ('I','U','D')),
    source_lsn      bigint      NOT NULL,
    commit_ts       timestamptz NOT NULL,
    ingested_at     timestamptz NOT NULL,
    payload         jsonb
);

-- Pipeline control. Each run processes the half-open window [window_start, window_end).
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          bigint PRIMARY KEY,
    pipeline_name   text        NOT NULL,
    source_system   text        NOT NULL,
    started_at      timestamptz NOT NULL,
    ended_at        timestamptz,
    status          text        NOT NULL CHECK (status IN ('SUCCEEDED','FAILED','RUNNING')),
    window_start    timestamptz NOT NULL,
    window_end      timestamptz NOT NULL,
    rows_read       integer,
    rows_written    integer,
    error_message   text,
    CHECK (window_end > window_start)
);

-- Last committed high-water mark per pipeline/source (current state).
CREATE TABLE IF NOT EXISTS pipeline_watermarks (
    pipeline_name     text        NOT NULL,
    source_system     text        NOT NULL,
    watermark_ts      timestamptz NOT NULL,
    committed_offset  bigint,
    updated_at        timestamptz NOT NULL,
    PRIMARY KEY (pipeline_name, source_system)
);

-- Ingestion attempts for raw events (one row per attempt; retries create more rows).
CREATE TABLE IF NOT EXISTS event_ingestion_log (
    log_id            bigint PRIMARY KEY,
    raw_event_id      text        NOT NULL,
    source_system     text        NOT NULL,
    event_ts          timestamptz NOT NULL,
    ingest_ts         timestamptz NOT NULL,
    ingestion_status  text        NOT NULL CHECK (ingestion_status IN ('LOADED','REJECTED','DUPLICATE','RETRIED')),
    error_reason      text,
    payload_bytes     integer
);

-- Raw message deliveries of transaction events from a message bus (at-least-once delivery).
-- message_id identifies a produced message; redelivery repeats it. transaction_id is the business key.
CREATE TABLE IF NOT EXISTS raw_transaction_events (
    delivery_id     bigint PRIMARY KEY,
    message_id      text        NOT NULL,
    transaction_id  bigint      NOT NULL,
    event_type      text        NOT NULL CHECK (event_type IN ('CREATED','STATUS_CHANGED')),
    delivered_at    timestamptz NOT NULL,
    payload         jsonb       NOT NULL
);

-- Untrusted staging copy of transaction lines: NO constraints on purpose (orphans, NULLs, dupes).
CREATE TABLE IF NOT EXISTS stg_transaction_items (
    load_batch_id    integer NOT NULL,
    transaction_id   bigint,
    line_number      smallint,
    product_id       integer,
    quantity         integer,
    unit_price       numeric(10,2),
    discount_amount  numeric(10,2)
);

-- Line-grain sales fact, range-partitioned by month on sale_date (UTC business date).
-- Only COMPLETED transactions. net_amount = quantity * unit_price - discount_amount.
CREATE TABLE IF NOT EXISTS fact_sales_partitioned (
    sale_date       date          NOT NULL,
    transaction_id  bigint        NOT NULL,
    line_number     smallint      NOT NULL,
    store_id        integer       NOT NULL,
    customer_id     integer,
    product_id      integer       NOT NULL,
    quantity        integer       NOT NULL,
    net_amount      numeric(12,2) NOT NULL,
    PRIMARY KEY (sale_date, transaction_id, line_number)
) PARTITION BY RANGE (sale_date);

DO $$
DECLARE
    m date := DATE '2024-01-01';
BEGIN
    WHILE m < DATE '2026-01-01' LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF fact_sales_partitioned FOR VALUES FROM (%L) TO (%L)',
            'fact_sales_p' || to_char(m, 'YYYY_MM'), m, (m + interval '1 month')::date);
        m := (m + interval '1 month')::date;
    END LOOP;
END $$;
CREATE TABLE IF NOT EXISTS fact_sales_p_default PARTITION OF fact_sales_partitioned DEFAULT;

-- Seed metadata (profile, version, row counts, checksum).
CREATE TABLE IF NOT EXISTS lab_meta (
    meta_key    text PRIMARY KEY,
    meta_value  jsonb       NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
