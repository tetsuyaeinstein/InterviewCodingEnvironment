"""Seed determinism and data-integrity self-tests.

* Generation determinism is tested offline (no database): the small profile is generated twice
  into temp folders and the COPY files must be byte-identical.
* Integrity tests read the live database (read-only) and skip when it is not seeded.
* A full re-seed repeatability test runs only when LAB_SELFTEST_RESEED=1 (it rewrites the DB).
"""
from __future__ import annotations

import hashlib
import os

import pytest

from database.seed import generator
from database.seed.profiles import PROFILES


def _digest(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob("*.copy"))}


def test_generation_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generator.generate(PROFILES["small"], a, log=lambda *_: None)
    generator.generate(PROFILES["small"], b, log=lambda *_: None)
    da, db_ = _digest(a), _digest(b)
    assert da and da == db_


def scalar(conn, sql):
    return conn.execute(sql).fetchone()[0]


INVARIANTS = {
    "transaction gross equals the sum of its lines":
        """SELECT count(*) FROM transactions t JOIN (SELECT transaction_id, sum(quantity*unit_price - discount_amount) s
           FROM transaction_items GROUP BY 1) i USING (transaction_id) WHERE i.s <> t.gross_amount""",
    "every transaction has at least one line":
        "SELECT count(*) FROM transactions t WHERE NOT EXISTS (SELECT 1 FROM transaction_items i WHERE i.transaction_id = t.transaction_id)",
    "refunds never exceed the sale":
        """SELECT count(*) FROM (SELECT transaction_id, sum(refund_amount) s FROM refunds GROUP BY 1) r
           JOIN transactions t USING (transaction_id) WHERE r.s > t.gross_amount""",
    "refunds only for completed transactions":
        "SELECT count(*) FROM refunds r JOIN transactions t USING (transaction_id) WHERE t.transaction_status <> 'COMPLETED'",
    "no purchase before registration":
        "SELECT count(*) FROM transactions t JOIN customers c USING (customer_id) WHERE t.transaction_ts < c.registered_at",
    "never ingested before it happened": "SELECT count(*) FROM transactions WHERE ingested_at < transaction_ts",
    "generated data stays out of fixture stores 4/5":
        "SELECT count(*) FROM transactions WHERE store_id IN (4, 5) AND transaction_id >= 100001",
    "generated data never uses fixture customers":
        "SELECT count(*) FROM transactions WHERE customer_id < 1000 AND transaction_id >= 100001",
    "generated facts always find an SCD2 version":
        """SELECT count(*) FROM transactions t WHERE customer_id > 1000 AND NOT EXISTS (
           SELECT 1 FROM dim_customer_scd2 d WHERE d.customer_id = t.customer_id
           AND t.transaction_ts >= d.effective_from AND t.transaction_ts < d.effective_to)""",
    "customer_daily_activity matches completed transactions":
        """SELECT count(*) FROM (SELECT customer_id, (transaction_ts AT TIME ZONE 'UTC')::date d, count(*) n, sum(gross_amount) s
           FROM transactions WHERE transaction_status = 'COMPLETED' AND customer_id IS NOT NULL GROUP BY 1, 2) x
           FULL JOIN customer_daily_activity a ON a.customer_id = x.customer_id AND a.activity_date = x.d
           WHERE a.customer_id IS NULL OR x.customer_id IS NULL OR a.transaction_count <> x.n OR a.daily_spend <> x.s""",
    "partitioned fact matches completed lines":
        """SELECT abs((SELECT count(*) FROM fact_sales_partitioned) - (SELECT count(*) FROM transaction_items i
           JOIN transactions t USING (transaction_id) WHERE t.transaction_status = 'COMPLETED'))""",
}


@pytest.mark.parametrize("name", list(INVARIANTS))
def test_invariants(seeded_conn, name):
    assert scalar(seeded_conn, INVARIANTS[name]) == 0, name


def test_fixture_facts(seeded_conn):
    c = seeded_conn
    assert scalar(c, "SELECT count(*) FROM transactions WHERE customer_id = 1") == 0
    assert scalar(c, "SELECT count(DISTINCT (transaction_ts AT TIME ZONE 'UTC')::date) FROM transactions WHERE customer_id = 6") == 5
    assert scalar(c, "SELECT count(*) FROM transactions WHERE customer_id = 6") == 7
    assert scalar(c, "SELECT sum(refund_amount) FROM refunds WHERE transaction_id = 2301") == 50
    assert scalar(c, "SELECT count(*) FROM transactions WHERE store_id = 4 AND transaction_status = 'COMPLETED'") == 11
    assert scalar(c, "SELECT count(*) FROM dim_customer_scd2 WHERE customer_id = 52 AND is_current") == 2
    assert scalar(c, "SELECT count(*) FROM cdc_transaction_events WHERE business_key = 'FX-0006' AND source_lsn = 9000520") == 2
    assert scalar(c, "SELECT count(*) FROM product_price_history WHERE product_id = 7") == 0


def test_stored_checksum_matches_contents(seeded_conn):
    from lab import db
    info = db.seed_info(seeded_conn)
    for table, expected in info["table_checksums"].items():
        assert scalar(seeded_conn, generator.checksum_sql(table)) == expected, table


@pytest.mark.skipif(os.environ.get("LAB_SELFTEST_RESEED") != "1", reason="set LAB_SELFTEST_RESEED=1 to re-seed twice")
def test_reseed_twice_gives_identical_checksum():
    from lab import db
    checksums = []
    for _ in range(2):
        info = generator.run(db.admin_factory, "small", log=lambda *_: None)
        checksums.append(info["checksum"])
    assert checksums[0] == checksums[1]
