-- 001_core.sql — core retail / financial transaction entities.
-- Idempotent: safe to re-run. All timestamps are timestamptz stored in UTC.
-- Applied by `python -m lab db migrate` as the lab_admin role.

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Stores (current-state dimension). store_id 1-5 are hand-curated fixtures.
CREATE TABLE IF NOT EXISTS stores (
    store_id        integer PRIMARY KEY,
    store_code      text        NOT NULL UNIQUE,              -- business key, e.g. 'ST-0001'
    store_name      text        NOT NULL,
    region          text        NOT NULL CHECK (region IN ('NORTH','SOUTH','EAST','WEST')),
    store_type      text        NOT NULL CHECK (store_type IN ('KIOSK','CONVENIENCE','SUPERMARKET','ONLINE')),
    timezone        text        NOT NULL,                     -- IANA zone used for store-local business dates
    opened_on       date        NOT NULL,
    closed_on       date
);

-- Customers (current-state dimension; history lives in dim_customer_scd2).
CREATE TABLE IF NOT EXISTS customers (
    customer_id     integer PRIMARY KEY,
    customer_code   text        NOT NULL UNIQUE,              -- business key, e.g. 'CUST-000001'
    registered_at   timestamptz NOT NULL,
    segment         text        NOT NULL CHECK (segment IN ('CONSUMER','SMALL_BUSINESS','ENTERPRISE','PILOT')),
    home_region     text        CHECK (home_region IN ('NORTH','SOUTH','EAST','WEST')),  -- NULL = unknown
    status          text        NOT NULL CHECK (status IN ('ACTIVE','DORMANT','CLOSED')),
    loyalty_tier    text        CHECK (loyalty_tier IN ('BRONZE','SILVER','GOLD'))       -- NULL = not enrolled
);

CREATE TABLE IF NOT EXISTS product_categories (
    category_id     integer PRIMARY KEY,
    category_name   text NOT NULL UNIQUE,
    department      text NOT NULL
);

-- Products (current state). standard_price = current list price.
CREATE TABLE IF NOT EXISTS products (
    product_id      integer PRIMARY KEY,
    sku             text          NOT NULL UNIQUE,
    product_name    text          NOT NULL,
    category_id     integer       NOT NULL REFERENCES product_categories (category_id),
    standard_price  numeric(10,2) NOT NULL CHECK (standard_price >= 0),
    is_active       boolean       NOT NULL DEFAULT true,
    launched_on     date          NOT NULL
);

-- Transactions (header grain: one row per till/checkout transaction).
-- gross_amount = SUM(quantity * unit_price - discount_amount) of its lines.
-- customer_id NULL = guest checkout. ingested_at >= transaction_ts (late arrivals exist).
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id      bigint PRIMARY KEY,
    customer_id         integer       REFERENCES customers (customer_id),
    store_id            integer       NOT NULL REFERENCES stores (store_id),
    transaction_ts      timestamptz   NOT NULL,
    gross_amount        numeric(12,2) NOT NULL CHECK (gross_amount >= 0),
    currency            char(3)       NOT NULL DEFAULT 'USD',
    transaction_status  text          NOT NULL CHECK (transaction_status IN ('COMPLETED','PENDING','CANCELLED','DECLINED')),
    payment_method      text          CHECK (payment_method IN ('CARD','CASH','MOBILE','GIFT_CARD')),  -- NULL = not captured
    source_system       text          NOT NULL CHECK (source_system IN ('POS','ECOM')),
    ingested_at         timestamptz   NOT NULL
);

-- Transaction lines (order-line grain).
CREATE TABLE IF NOT EXISTS transaction_items (
    transaction_id   bigint        NOT NULL REFERENCES transactions (transaction_id),
    line_number      smallint      NOT NULL CHECK (line_number > 0),
    product_id       integer       NOT NULL REFERENCES products (product_id),
    quantity         integer       NOT NULL CHECK (quantity > 0),
    unit_price       numeric(10,2) NOT NULL CHECK (unit_price >= 0),
    discount_amount  numeric(10,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    PRIMARY KEY (transaction_id, line_number)
);

-- Refunds (immutable events). Multiple partial refunds per transaction are allowed;
-- SUM(refund_amount) per transaction never exceeds the transaction gross_amount.
CREATE TABLE IF NOT EXISTS refunds (
    refund_id       bigint PRIMARY KEY,
    transaction_id  bigint        NOT NULL REFERENCES transactions (transaction_id),
    refund_ts       timestamptz   NOT NULL,
    refund_amount   numeric(12,2) NOT NULL CHECK (refund_amount > 0),
    reason          text          NOT NULL CHECK (reason IN ('DAMAGED','CHANGED_MIND','PRICE_ADJUSTMENT','DUPLICATE_CHARGE'))
);

-- Clickstream / app events (immutable events). customer_id NULL = anonymous visitor.
CREATE TABLE IF NOT EXISTS customer_events (
    event_id     bigint PRIMARY KEY,
    customer_id  integer     REFERENCES customers (customer_id),
    event_ts     timestamptz NOT NULL,
    event_type   text        NOT NULL CHECK (event_type IN ('app_open','page_view','search','add_to_cart','checkout','promo_click')),
    session_id   text,                                   -- client-supplied; often NULL / unreliable
    payload      jsonb       NOT NULL DEFAULT '{}'::jsonb
);
