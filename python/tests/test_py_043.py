"""Tests for PY-043 (requires the seeded lab database; uses a sandbox schema table)."""
from decimal import Decimal

import psycopg
import pytest

from _loader import load

mod = load("PY-043")
pytestmark = pytest.mark.requires_postgres

DDL = """CREATE TABLE txn_load (
    business_key text PRIMARY KEY,
    amount numeric(12,2) NOT NULL,
    status text NOT NULL,
    seq integer NOT NULL)"""


@pytest.fixture
def conn(pg_sandbox):
    pg_sandbox.execute(DDL)
    pg_sandbox.commit()
    return pg_sandbox


def row(key, seq, amount="10.00", status="NEW"):
    return {"business_key": key, "amount": Decimal(amount), "status": status, "seq": seq}


def state(conn):
    conn.rollback()
    out = {k: (a, s, q) for k, a, s, q in conn.execute(
        "SELECT business_key, amount, status, seq FROM txn_load")}
    conn.rollback()     # leave no transaction open: the code under test must commit its own work
    return out


def counts(res):
    return (res.inserted, res.updated, res.skipped)


class _Spy:
    def __init__(self, conn):
        self._conn, self.calls = conn, 0

    def cursor(self, *a, **kw):
        return _SpyCur(self._conn.cursor(*a, **kw), self)

    def execute(self, *a, **kw):
        self.calls += 1
        return self._conn.execute(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _SpyCur:
    def __init__(self, cur, spy):
        self._cur, self._spy = cur, spy

    def __enter__(self):
        self._cur.__enter__()
        return self

    def __exit__(self, *exc):
        return self._cur.__exit__(*exc)

    def execute(self, *a, **kw):
        self._spy.calls += 1
        return self._cur.execute(*a, **kw)

    def executemany(self, *a, **kw):
        self._spy.calls += 1
        return self._cur.executemany(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._cur, name)


def test_fresh_load_inserts_everything(conn):
    res = mod.load_batch(conn, [row("A", 1, "1.10"), row("B", 1, "2.20", "PAID")])
    assert counts(res) == (2, 0, 0)
    assert state(conn) == {"A": (Decimal("1.10"), "NEW", 1), "B": (Decimal("2.20"), "PAID", 1)}


def test_commits_when_called_outside_a_transaction(conn):
    mod.load_batch(conn, [row("A", 1)])
    conn.rollback()  # a rollback after the call must not undo it
    assert len(state(conn)) == 1


def test_rerunning_the_same_batch_is_idempotent(conn):
    rows = [row("A", 1), row("B", 2), row("C", 3)]
    assert counts(mod.load_batch(conn, rows)) == (3, 0, 0)
    before = state(conn)
    assert counts(mod.load_batch(conn, rows)) == (0, 0, 3)
    assert state(conn) == before


def test_newer_version_updates_and_older_is_ignored(conn):
    mod.load_batch(conn, [row("A", 5, "5.00", "PAID")])
    res = mod.load_batch(conn, [row("A", 7, "7.00", "REFUNDED")])
    assert counts(res) == (0, 1, 0)
    assert state(conn)["A"] == (Decimal("7.00"), "REFUNDED", 7)
    res = mod.load_batch(conn, [row("A", 6, "6.00", "STALE")])  # arrives late
    assert counts(res) == (0, 0, 1)
    assert state(conn)["A"] == (Decimal("7.00"), "REFUNDED", 7)


def test_equal_sequence_is_not_an_update(conn):
    mod.load_batch(conn, [row("A", 3, "1.00")])
    res = mod.load_batch(conn, [row("A", 3, "9.99", "OTHER")])
    assert counts(res) == (0, 0, 1)
    assert state(conn)["A"] == (Decimal("1.00"), "NEW", 3)


def test_duplicates_inside_the_input(conn):
    rows = [row("C", 1, "1.00"), row("C", 3, "3.00"), row("C", 2, "2.00"), row("D", 4, "4.00"),
            row("D", 4, "4.44", "LAST")]
    res = mod.load_batch(conn, rows)
    assert counts(res) == (2, 0, 3)
    assert state(conn) == {"C": (Decimal("3.00"), "NEW", 3), "D": (Decimal("4.44"), "LAST", 4)}


def test_example_from_the_question(conn):
    mod.load_batch(conn, [row("A", 1)])
    res = mod.load_batch(conn, [row("A", 1), row("B", 5), row("C", 2), row("C", 4), row("A", 0)])
    assert counts(res) == (2, 0, 3)
    assert res.inserted + res.updated + res.skipped == 5


def test_mixed_counts_across_batches(conn):
    mod.load_batch(conn, [row(f"K{i}", 1) for i in range(10)])
    rows = [row(f"K{i}", 2) for i in range(0, 10, 2)]          # 5 updates
    rows += [row(f"K{i}", 1) for i in range(1, 10, 2)]          # 5 skipped (equal seq)
    rows += [row(f"N{i}", 1) for i in range(7)]                 # 7 inserts
    res = mod.load_batch(conn, rows, batch_size=4)
    assert counts(res) == (7, 5, 5)
    assert len(state(conn)) == 17


def test_batching_limits_round_trips_and_keeps_all_rows(conn):
    rows = [row(f"R{i:04d}", 1, "0.10") for i in range(1050)]
    spy = _Spy(conn)
    res = mod.load_batch(spy, rows, batch_size=100)
    assert counts(res) == (1050, 0, 0)
    assert spy.calls <= 11 + 4, f"{spy.calls} statements for 1050 rows at batch_size=100"
    assert len(state(conn)) == 1050
    assert all(v[0] == Decimal("0.10") for v in state(conn).values())


def test_same_key_in_different_batches(conn):
    rows = [row("X", 1, "1.00"), row("Y", 1), row("Z", 1), row("X", 2, "2.00")]
    res = mod.load_batch(conn, rows, batch_size=1)
    assert counts(res) == (3, 0, 1)
    assert state(conn)["X"][2] == 2


def test_failure_rolls_back_every_batch(conn):
    mod.load_batch(conn, [row("OLD", 1)])
    before = state(conn)
    rows = [row("A", 1), row("B", 1), row("OLD", 9, "9.00"), row("C", 1)]
    rows.append({"business_key": "BAD", "amount": None, "status": "NEW", "seq": 1})
    with pytest.raises(psycopg.Error):
        mod.load_batch(conn, rows, batch_size=2)
    conn.rollback()
    assert state(conn) == before


def test_missing_key_raises_before_writing(conn):
    with pytest.raises((KeyError, ValueError)):
        mod.load_batch(conn, [row("A", 1), {"business_key": "B", "amount": Decimal("1.00"), "status": "NEW"}])
    assert state(conn) == {}


def test_empty_input_and_generators(conn):
    assert counts(mod.load_batch(conn, [])) == (0, 0, 0)
    assert counts(mod.load_batch(conn, (row(f"G{i}", 1) for i in range(3)))) == (3, 0, 0)


def test_invalid_batch_size(conn):
    with pytest.raises(ValueError):
        mod.load_batch(conn, [row("A", 1)], batch_size=0)


def test_awkward_keys_are_data_not_sql(conn):
    keys = ["x'); DROP TABLE txn_load; --", "100%", "semi;colon", "O'Brien"]
    assert counts(mod.load_batch(conn, [row(k, 1) for k in keys])) == (4, 0, 0)
    assert set(state(conn)) == set(keys)


def test_hostile_table_name_is_rejected_safely(conn):
    mod.load_batch(conn, [row("A", 1)])
    with pytest.raises((psycopg.Error, ValueError)):
        mod.load_batch(conn, [row("B", 1)], table='txn_load (business_key) VALUES (1); DROP TABLE txn_load; --')
    conn.rollback()
    assert set(state(conn)) == {"A"}


def test_custom_table_name(conn):
    conn.execute(DDL.replace("txn_load", "other_load"))
    conn.commit()
    assert counts(mod.load_batch(conn, [row("A", 1)], table="other_load")) == (1, 0, 0)
    assert state(conn) == {}
    assert conn.execute("SELECT count(*) FROM other_load").fetchone()[0] == 1
