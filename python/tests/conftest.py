"""Shared pytest fixtures for the Python exercise bank.

Database fixtures (only used by tests marked ``requires_postgres``):
  pg_readonly   lab_practice connection, read-only, for query-only exercises.
  pg_sandbox    lab_grader connection whose search_path starts with a fresh lab_sb_* schema.
                Everything is rolled back / dropped afterwards; shared tables are never modified.
If PostgreSQL is not running or not seeded the tests are SKIPPED - and `lab check` reports
INCOMPLETE, never PASSED.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


def _connect(role: str):
    try:
        from lab import db
        conn = db.connect(role)
    except Exception as e:  # LabDBError, ImportError, ...
        pytest.skip(f"PostgreSQL not available ({str(e).splitlines()[0]})")
    try:
        seeded = conn.execute("SELECT count(*) FROM lab_meta WHERE meta_key = 'seed'").fetchone()[0]
    except Exception:
        conn.close()
        pytest.skip("lab database not migrated/seeded (python -m lab db seed --size small)")
    conn.rollback()
    if not seeded:
        conn.close()
        pytest.skip("lab database not seeded (python -m lab db seed --size small)")
    return conn


@pytest.fixture
def pg_readonly():
    conn = _connect("practice")
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def pg_sandbox():
    conn = _connect("grader")
    schema = f"lab_sb_pytest_{uuid.uuid4().hex[:10]}"
    conn.execute(f'CREATE SCHEMA "{schema}"')
    conn.execute(f'SET search_path = "{schema}", public')
    conn.commit()  # visible to code that opens its own transactions; dropped below
    try:
        yield conn
    finally:
        try:
            conn.rollback()
            conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            conn.commit()
        finally:
            conn.close()
