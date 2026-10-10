"""Paths and settings. Reads .env from the repository root (falls back to .env.example defaults)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
PY_DIR = ROOT / "python"
STUDY_DIR = ROOT / "study"
DB_DIR = ROOT / "database"
TMP_DIR = ROOT / ".lab_tmp"


def rel(path: Path) -> str:
    """Repository-relative POSIX path for display."""
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in (".env.example", ".env"):  # .env overrides the documented defaults
        path = ROOT / name
        if path.exists():
            values.update({k: v for k, v in dotenv_values(path).items() if v is not None})
    values.update({k: v for k, v in os.environ.items() if k.startswith("LAB_")})
    return values


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    dbname: str
    admin_user: str
    admin_password: str
    grader_user: str
    grader_password: str
    practice_user: str
    practice_password: str
    statement_timeout_ms: int
    max_display_rows: int


def settings() -> Settings:
    env = _load_env()
    return Settings(
        host=env.get("LAB_DB_HOST", "localhost"),
        port=int(env.get("LAB_DB_PORT", "5433")),
        dbname=env.get("LAB_DB_NAME", "interview_lab"),
        admin_user=env.get("LAB_ADMIN_USER", "lab_admin"),
        admin_password=env.get("LAB_ADMIN_PASSWORD", "lab_admin_local_only"),
        grader_user=env.get("LAB_GRADER_USER", "lab_grader"),
        grader_password=env.get("LAB_GRADER_PASSWORD", "lab_grader_local_only"),
        practice_user=env.get("LAB_PRACTICE_USER", "lab_practice"),
        practice_password=env.get("LAB_PRACTICE_PASSWORD", "lab_practice_local_only"),
        statement_timeout_ms=int(env.get("LAB_STATEMENT_TIMEOUT_MS", "15000")),
        max_display_rows=int(env.get("LAB_MAX_DISPLAY_ROWS", "50")),
    )
