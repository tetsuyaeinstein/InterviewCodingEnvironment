"""Fixtures for the lab's own self-tests (`python -m pytest`)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def seeded_conn():
    """Read-only practice connection to a seeded lab database, or skip."""
    from lab import db
    try:
        conn = db.connect("practice")
    except db.LabDBError as e:
        pytest.skip(f"lab database not reachable: {str(e).splitlines()[0]}")
    info = db.seed_info(conn)
    if not info:
        conn.close()
        pytest.skip("lab database not seeded")
    yield conn
    conn.close()


@pytest.fixture
def isolated_progress(tmp_path, monkeypatch):
    """Point progress tracking at a temporary file."""
    from lab import progress
    path = tmp_path / "progress.json"
    monkeypatch.setattr(progress, "PROGRESS_FILE", path)
    monkeypatch.delenv("LAB_NO_PROGRESS", raising=False)
    return path
