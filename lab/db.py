"""Database connections, roles, migrations, seeding and the guarded reset.

Roles (all local-only):
  admin    - container superuser; ONLY used for migrate / seed / reset.
  grader   - SELECT on shared tables + CREATE on the database so it can build disposable
             ``lab_sb_*`` sandbox schemas inside a transaction that is always rolled back.
  practice - SELECT only, sessions default to read-only. Used by `lab run` / query checks
             and recommended for SQLTools.
"""
from __future__ import annotations

import hashlib
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql

from .config import DB_DIR, ROOT, settings

SANDBOX_PREFIX = "lab_sb_"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


class LabDBError(RuntimeError):
    """Friendly, user-facing database problem."""


def _conninfo(role: str) -> dict:
    s = settings()
    user, password = {
        "admin": (s.admin_user, s.admin_password),
        "grader": (s.grader_user, s.grader_password),
        "practice": (s.practice_user, s.practice_password),
    }[role]
    return dict(host=s.host, port=s.port, dbname=s.dbname, user=user, password=password,
                connect_timeout=5, application_name=f"interview-lab-{role}",
                options=f"-c timezone=UTC -c statement_timeout={s.statement_timeout_ms if role != 'admin' else 0}")


def connect(role: str = "practice", autocommit: bool = False) -> psycopg.Connection:
    try:
        return psycopg.connect(**_conninfo(role), autocommit=autocommit)
    except psycopg.OperationalError as e:
        s = settings()
        msg = str(e).strip().splitlines()[0] if str(e).strip() else repr(e)
        hint = ("Is the container running?  docker compose up -d   (then: python -m lab db status)"
                if "password" not in msg.lower() else
                "Role/password mismatch. Run: python -m lab db migrate   (creates the lab roles)")
        raise LabDBError(f"Cannot connect to PostgreSQL at {s.host}:{s.port}/{s.dbname} as {role}: {msg}\n  -> {hint}") from e


def admin_factory(autocommit: bool = False):
    return connect("admin", autocommit=autocommit)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
def seed_info(conn) -> dict | None:
    try:
        row = conn.execute("SELECT meta_value FROM lab_meta WHERE meta_key = 'seed'").fetchone()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        return None
    return row[0] if row else None


def status() -> int:
    s = settings()
    print(f"Database: postgresql://{s.host}:{s.port}/{s.dbname}")
    try:
        with connect("admin") as conn:
            version = conn.execute("SHOW server_version").fetchone()[0]
            print(f"  server        : PostgreSQL {version}  (connected as admin)")
            applied = _applied_migrations(conn)
            pending = [p.name for p in _migration_files() if p.name not in applied]
            print(f"  migrations    : {len(applied)} applied, {len(pending)} pending" + (f"  {pending}" if pending else ""))
            roles = {r[0] for r in conn.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
                                                ([s.grader_user, s.practice_user],))}
            print(f"  lab roles     : {', '.join(sorted(roles)) or 'missing (run: python -m lab db migrate)'}")
            info = seed_info(conn) if applied else None
            if info:
                n_tx = info["row_counts"].get("transactions")
                print(f"  seed          : profile={info['profile']} version={info['seed_version']} "
                      f"transactions={n_tx:,} checksum={info['checksum'][:12]}")
            else:
                print("  seed          : not seeded (run: python -m lab db seed --size small)")
            sandboxes = conn.execute("SELECT count(*) FROM pg_namespace WHERE nspname LIKE %s",
                                     (SANDBOX_PREFIX + "%",)).fetchone()[0]
            if sandboxes:
                print(f"  sandboxes     : {sandboxes} leftover lab_sb_* schema(s) (removed by: python -m lab db reset --confirm)")
        if roles == {s.grader_user, s.practice_user}:
            with connect("practice") as conn:
                ro = conn.execute("SHOW default_transaction_read_only").fetchone()[0]
                print(f"  practice role : connects OK, read-only sessions = {ro}")
        return 0
    except LabDBError as e:
        print(f"  {e}")
        return 1


# ---------------------------------------------------------------------------
# Migrations + roles
# ---------------------------------------------------------------------------
def _migration_files() -> list[Path]:
    return sorted((DB_DIR / "migrations").glob("[0-9][0-9][0-9]_*.sql"))


def _applied_migrations(conn) -> dict[str, str]:
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                        filename text PRIMARY KEY, checksum text NOT NULL,
                        applied_at timestamptz NOT NULL DEFAULT now())""")
    conn.commit()
    return dict(conn.execute("SELECT filename, checksum FROM schema_migrations").fetchall())


def ensure_roles(conn) -> None:
    s = settings()
    for user, password, read_only in ((s.grader_user, s.grader_password, False),
                                      (s.practice_user, s.practice_password, True)):
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(user)))
        conn.execute(sql.SQL("ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}")
                     .format(sql.Identifier(user), sql.Literal(password)))
        conn.execute(sql.SQL("ALTER ROLE {} SET timezone = 'UTC'").format(sql.Identifier(user)))
        conn.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = {}")
                     .format(sql.Identifier(user), sql.Literal("on" if read_only else "off")))
        conn.execute(sql.SQL("ALTER ROLE {} SET statement_timeout = {}")
                     .format(sql.Identifier(user), sql.Literal(f"{s.statement_timeout_ms}ms")))
    db = sql.Identifier(s.dbname)
    grader, practice = sql.Identifier(s.grader_user), sql.Identifier(s.practice_user)
    conn.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
    conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(db, grader, practice))
    conn.execute(sql.SQL("GRANT CREATE, TEMPORARY ON DATABASE {} TO {}").format(db, grader))
    conn.execute(sql.SQL("REVOKE CREATE ON DATABASE {} FROM {}").format(db, practice))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}, {}").format(grader, practice))
    grant_select(conn)
    conn.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}, {}")
                 .format(grader, practice))


def grant_select(conn) -> None:
    s = settings()
    conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}, {}")
                 .format(sql.Identifier(s.grader_user), sql.Identifier(s.practice_user)))


def migrate(verbose: bool = True) -> int:
    with connect("admin") as conn:
        applied = _applied_migrations(conn)
        n = 0
        for path in _migration_files():
            text = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(text.encode()).hexdigest()
            if path.name in applied:
                if applied[path.name] != digest and verbose:
                    print(f"  ! {path.name} changed since it was applied; re-applying (migrations are idempotent)")
                else:
                    continue
            with conn.transaction():
                conn.execute(text)
                conn.execute("""INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)
                                ON CONFLICT (filename) DO UPDATE SET checksum = EXCLUDED.checksum, applied_at = now()""",
                             (path.name, digest))
            n += 1
            if verbose:
                print(f"  applied {path.name}")
        with conn.transaction():
            ensure_roles(conn)
        if verbose:
            print(f"Migrations up to date ({n} applied this run). Roles lab_grader / lab_practice ensured.")
    return 0


# ---------------------------------------------------------------------------
# Seed / reset
# ---------------------------------------------------------------------------
def seed(size: str, assume_yes: bool = False) -> int:
    sys.path.insert(0, str(ROOT))
    from database.seed import generator
    from database.seed.profiles import PROFILES

    profile = PROFILES[size]
    if profile.warning and not assume_yes:
        print(f"WARNING: {profile.warning}\nRe-run with --yes to proceed.")
        return 2
    migrate(verbose=False)
    t0 = time.perf_counter()
    info = generator.run(admin_factory, size)
    with connect("admin") as conn:
        grant_select(conn)
        drop_sandboxes(conn)
        conn.commit()
    n = info["row_counts"]
    print(f"Seeded profile '{size}' in {time.perf_counter() - t0:.1f}s: "
          f"{n['customers']:,} customers, {n['transactions']:,} transactions, {n['transaction_items']:,} lines, "
          f"{sum(n.values()):,} rows total.")
    print(f"Seed checksum: {info['checksum']}  (identical on every run of this profile + seed version)")
    return 0


def drop_sandboxes(conn) -> int:
    """Drop leftover grader sandboxes. Narrowly targeted: only schemas named lab_sb_*."""
    names = [r[0] for r in conn.execute("SELECT nspname FROM pg_namespace WHERE nspname LIKE %s",
                                        (SANDBOX_PREFIX + "%",)).fetchall()]
    for name in names:
        if not name.startswith(SANDBOX_PREFIX):
            continue
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
    return len(names)


def reset(confirm: bool, size: str = "small") -> int:
    s = settings()
    if not confirm:
        print("Refusing to reset without --confirm. This drops and recreates every lab table in the LOCAL database.")
        return 2
    if s.host not in LOCAL_HOSTS:
        print(f"Refusing to reset: LAB_DB_HOST={s.host!r} is not a local host {sorted(LOCAL_HOSTS)}.")
        return 2
    with connect("admin") as conn:
        marker = conn.execute("SELECT to_regclass('public.schema_migrations') IS NOT NULL").fetchone()[0]
        empty = conn.execute("""SELECT count(*) = 0 FROM pg_tables WHERE schemaname = 'public'""").fetchone()[0]
        if not marker and not empty:
            print("Refusing to reset: public schema has tables but no lab schema_migrations marker; this does not look like the lab DB.")
            return 2
        dropped = drop_sandboxes(conn)
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(s.admin_user)))
        conn.commit()
        print(f"Dropped lab objects in schema public{f' and {dropped} sandbox schema(s)' if dropped else ''}.")
    migrate()
    return seed(size, assume_yes=True)


@contextmanager
def sandbox(conn, label: str = "x"):
    """Open a disposable schema inside the CURRENT transaction; always rolled back.

    Usage: with db.sandbox(conn) as schema: ...  (conn must be a grader, non-autocommit connection)
    """
    name = f"{SANDBOX_PREFIX}{label}_{int(time.time() * 1000) % 10**10}"
    try:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        conn.execute(sql.SQL("SET LOCAL search_path = {}, public").format(sql.Identifier(name)))
        yield name
    finally:
        conn.rollback()
