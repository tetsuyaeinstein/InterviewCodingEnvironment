-- 002_retail.sql — temporal retail history, ledger, devices, summaries, HR.
-- Interval convention for this file: [valid_from, valid_to) half-open; valid_to NULL = open-ended (still valid).

-- Price history (immutable history, non-overlapping per product, enforced by EXCLUDE).
CREATE TABLE IF NOT EXISTS product_price_history (
    product_id  integer       NOT NULL REFERENCES products (product_id),
    valid_from  timestamptz   NOT NULL,
    valid_to    timestamptz,
    price       numeric(10,2) NOT NULL CHECK (price >= 0),
    PRIMARY KEY (product_id, valid_from),
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    EXCLUDE USING gist (product_id WITH =, tstzrange(valid_from, valid_to, '[)') WITH &&)
);

-- Store/product availability history. Rows for a (store, product) never overlap.
-- A timestamp not covered by any row means "not stocked" (treat as unavailable).
CREATE TABLE IF NOT EXISTS store_product_availability (
    store_id    integer     NOT NULL REFERENCES stores (store_id),
    product_id  integer     NOT NULL REFERENCES products (product_id),
    valid_from  timestamptz NOT NULL,
    valid_to    timestamptz,
    available   boolean     NOT NULL,
    PRIMARY KEY (store_id, product_id, valid_from),
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    EXCLUDE USING gist (store_id WITH =, product_id WITH =, tstzrange(valid_from, valid_to, '[)') WITH &&)
);

-- Subscriptions. [start_date, end_date) half-open dates; end_date NULL = still running.
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id  integer PRIMARY KEY,
    customer_id      integer      NOT NULL REFERENCES customers (customer_id),
    plan             text         NOT NULL CHECK (plan IN ('BASIC','PLUS','PREMIUM')),
    start_date       date         NOT NULL,
    end_date         date,
    status           text         NOT NULL CHECK (status IN ('TRIAL','ACTIVE','CANCELLED','EXPIRED')),
    monthly_fee      numeric(8,2) NOT NULL CHECK (monthly_fee >= 0),
    CHECK (end_date IS NULL OR end_date > start_date)
);

-- Employees (current state, self-referencing hierarchy; manager_id NULL = top of tree).
CREATE TABLE IF NOT EXISTS employees (
    employee_id       integer PRIMARY KEY,
    manager_id        integer       REFERENCES employees (employee_id),
    employee_name     text          NOT NULL,
    department        text          NOT NULL,
    job_title         text          NOT NULL,
    salary            numeric(10,2) NOT NULL CHECK (salary > 0),
    hire_date         date          NOT NULL,
    termination_date  date
);

-- Stored-value accounts and their posting ledger (immutable, append-only).
CREATE TABLE IF NOT EXISTS accounts (
    account_id    integer PRIMARY KEY,
    customer_id   integer       NOT NULL REFERENCES customers (customer_id),
    account_type  text          NOT NULL CHECK (account_type IN ('WALLET','PREPAID','CREDIT_LINE')),
    opened_at     timestamptz   NOT NULL,
    credit_limit  numeric(14,2) NOT NULL DEFAULT 0
);

-- signed_amount: + increases balance, - decreases. transaction_id is a soft reference (no FK).
-- Several entries may share the same posting_ts; entry_id breaks ties (posting order).
CREATE TABLE IF NOT EXISTS account_ledger (
    entry_id        bigint PRIMARY KEY,
    account_id      integer       NOT NULL REFERENCES accounts (account_id),
    transaction_id  bigint,
    posting_ts      timestamptz   NOT NULL,
    signed_amount   numeric(14,2) NOT NULL CHECK (signed_amount <> 0),
    entry_type      text          NOT NULL CHECK (entry_type IN ('DEPOSIT','PURCHASE','REFUND','FEE','WITHDRAWAL','ADJUSTMENT'))
);

-- Kiosk / terminal devices (current state).
CREATE TABLE IF NOT EXISTS devices (
    device_id          text PRIMARY KEY,                  -- e.g. 'KIOSK-0001'
    store_id           integer NOT NULL REFERENCES stores (store_id),
    device_type        text    NOT NULL CHECK (device_type IN ('KIOSK','POS_TERMINAL')),
    installed_on       date    NOT NULL,
    decommissioned_on  date                               -- NULL = still in service
);

-- Device status stream (events). Devices send one SCHEDULED report per UTC day (~02:00 UTC)
-- plus CHANGE events when state flips. received_at order != event_ts order (out-of-order delivery).
CREATE TABLE IF NOT EXISTS device_status_events (
    event_id     bigint PRIMARY KEY,
    device_id    text        NOT NULL REFERENCES devices (device_id),
    event_ts     timestamptz NOT NULL,
    received_at  timestamptz NOT NULL,
    state        text        NOT NULL CHECK (state IN ('UP','DOWN')),
    event_kind   text        NOT NULL CHECK (event_kind IN ('SCHEDULED','CHANGE'))
);

-- Downtime incidents reported independently by several sources; intervals may overlap,
-- nest, or touch. [down_from, down_to) half-open.
CREATE TABLE IF NOT EXISTS device_downtime_incidents (
    incident_id  integer PRIMARY KEY,
    device_id    text        NOT NULL REFERENCES devices (device_id),
    reported_by  text        NOT NULL CHECK (reported_by IN ('MONITORING','TECHNICIAN','VENDOR')),
    down_from    timestamptz NOT NULL,
    down_to      timestamptz NOT NULL,
    CHECK (down_to > down_from)
);

-- Summary table populated by the seed from COMPLETED transactions; activity_date = UTC date.
CREATE TABLE IF NOT EXISTS customer_daily_activity (
    customer_id        integer       NOT NULL REFERENCES customers (customer_id),
    activity_date      date          NOT NULL,
    transaction_count  integer       NOT NULL CHECK (transaction_count > 0),
    daily_spend        numeric(12,2) NOT NULL,
    PRIMARY KEY (customer_id, activity_date)
);

-- Periodic snapshot: end-of-day stock position per store/product (subset of stores/products).
CREATE TABLE IF NOT EXISTS daily_store_snapshot (
    snapshot_date  date    NOT NULL,
    store_id       integer NOT NULL REFERENCES stores (store_id),
    product_id     integer NOT NULL REFERENCES products (product_id),
    on_hand_qty    integer NOT NULL,
    units_sold     integer NOT NULL,
    PRIMARY KEY (snapshot_date, store_id, product_id)
);
