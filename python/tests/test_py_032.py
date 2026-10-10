"""Tests for PY-032 (imports your practice file by default; see _loader.py)."""
import random
from collections.abc import Mapping
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-032")

D = Decimal


class MemoryStore:
    """Atomic in-memory store with crash injection. Counts commits so tests can audit them."""

    def __init__(self):
        self.data = {}
        self.commits = []                 # copies of every successful commit
        self.fail_before = set()          # commit numbers (1-based, counting attempts) that fail untouched
        self.fail_after = set()           # commit numbers that are applied, then raise (lost ack)
        self.attempts = 0

    def get(self, key, default=None):
        return self.data.get(key, default)

    def commit(self, writes: Mapping):
        self.attempts += 1
        if self.attempts in self.fail_before:
            raise mod.StoreError("crash before commit")
        snapshot = dict(writes)
        self.data.update(snapshot)
        self.commits.append(snapshot)
        if self.attempts in self.fail_after:
            raise mod.StoreError("crash after commit")


def E(eid, acct, amount):
    return mod.Event(eid, acct, D(str(amount)))


def drive(consumer, events):
    """At-least-once driver: redeliver an event until process() returns without a store error."""
    out = []
    for e in events:
        for _ in range(10):
            try:
                out.append(consumer.process(e))
                break
            except mod.StoreError:
                continue
        else:
            raise AssertionError("never succeeded")
    return out


def test_example_from_question():
    store = MemoryStore()
    c = mod.IdempotentConsumer(store)
    assert [c.process(e) for e in [E("e1", "A", "100.00"), E("e2", "A", "-130.00"), E("e1", "A", "100.00"),
                                   E("e2", "A", "-130.00"), E("e3", "B", "-5.00")]] == \
        ["applied", "rejected", "duplicate", "duplicate", "rejected"]
    assert c.balance("A") == D("100.00") and c.balance("B") == D("0") and c.balance("nobody") == D("0")


def test_redelivery_has_no_effect_and_writes_nothing():
    store = MemoryStore()
    c = mod.IdempotentConsumer(store)
    c.process(E("e1", "A", 10))
    before = (dict(store.data), len(store.commits))
    for _ in range(5):
        assert c.process(E("e1", "A", 10)) == "duplicate"
    assert (store.data, len(store.commits)) == before


def test_exactly_one_atomic_commit_per_new_event():
    store = MemoryStore()
    c = mod.IdempotentConsumer(store)
    c.process(E("e1", "A", 10))
    c.process(E("e2", "A", 5))
    c.process(E("e3", "A", -100))      # rejected: still one commit (the decision is recorded)
    assert len(store.commits) == 3
    assert all(len(w) >= 1 for w in store.commits)


def test_same_event_id_with_different_payload_is_a_conflict():
    store = MemoryStore()
    c = mod.IdempotentConsumer(store)
    c.process(E("e1", "A", 10))
    for bad in (E("e1", "A", 11), E("e1", "B", 10)):
        with pytest.raises(mod.ConflictingEvent):
            c.process(bad)
    assert c.balance("A") == 10 and c.balance("B") == 0 and len(store.commits) == 1
    assert c.process(E("e1", "A", "10.000")) == "duplicate"     # equal by value


def test_rejection_is_final_even_if_balance_recovers():
    store = MemoryStore()
    c = mod.IdempotentConsumer(store)
    assert c.process(E("w", "A", -50)) == "rejected"
    c.process(E("d", "A", 100))
    assert c.process(E("w", "A", -50)) == "duplicate"
    assert c.balance("A") == 100
    with pytest.raises(mod.ConflictingEvent):
        c.process(E("w", "A", -40))


def test_exact_decimal_arithmetic():
    c = mod.IdempotentConsumer(MemoryStore())
    for i in range(3):
        c.process(E(f"e{i}", "A", "0.10"))
    assert c.balance("A") == D("0.30")
    assert c.process(E("z", "A", "-0.30")) == "applied" and c.balance("A") == 0


def test_balance_may_reach_exactly_zero():
    c = mod.IdempotentConsumer(MemoryStore())
    c.process(E("a", "A", 10))
    assert c.process(E("b", "A", -10)) == "applied"
    assert c.process(E("c", "A", "-0.01")) == "rejected"


def test_crash_before_commit_leaves_nothing_and_retry_applies_once():
    stream = [E("e1", "A", 10), E("e2", "B", 7), E("e3", "A", -4), E("e4", "A", 1)]
    for crash_at in range(1, 5):
        store = MemoryStore()
        store.fail_before = {crash_at}
        c = mod.IdempotentConsumer(store)
        assert drive(c, stream) == ["applied"] * 4
        assert (c.balance("A"), c.balance("B")) == (D(7), D(7))
        assert len(store.commits) == 4


def test_crash_after_commit_is_a_duplicate_on_redelivery():
    stream = [E("e1", "A", 10), E("e2", "B", 7), E("e3", "A", -4)]
    for crash_at in range(1, 4):
        store = MemoryStore()
        store.fail_after = {crash_at}
        c = mod.IdempotentConsumer(store)
        out = drive(c, stream)
        assert out.count("duplicate") == 1 and out.count("applied") == 2, (crash_at, out)
        assert (c.balance("A"), c.balance("B")) == (D(6), D(7))


def test_every_crash_combination_gives_the_same_final_state():
    stream = [E("e1", "A", 10), E("e2", "A", -30), E("e3", "B", 5), E("e4", "A", 25), E("e5", "A", -30)]
    ref = MemoryStore()
    drive(mod.IdempotentConsumer(ref), stream)
    for before in range(0, 6):
        for after in range(0, 6):
            store = MemoryStore()
            store.fail_before = {before} if before else set()
            store.fail_after = {after + 1} if after and after + 1 != before else set()
            drive(mod.IdempotentConsumer(store), stream)
            c = mod.IdempotentConsumer(store)
            assert (c.balance("A"), c.balance("B")) == (D(5), D(5)), (before, after)
            assert {k: v for k, v in store.data.items()} == ref.data


def test_state_lives_in_the_store_not_in_the_consumer():
    store = MemoryStore()
    c1 = mod.IdempotentConsumer(store)
    c1.process(E("e1", "A", 10))
    c2 = mod.IdempotentConsumer(store)            # restart, or a second instance
    assert c2.process(E("e1", "A", 10)) == "duplicate"
    assert c2.balance("A") == 10
    # a failed commit must not leave the consumer believing the event was processed
    store.fail_before = {store.attempts + 1}
    with pytest.raises(mod.StoreError):
        c1.process(E("e2", "A", 5))
    assert c1.balance("A") == 10
    assert c1.process(E("e2", "A", 5)) == "applied" and c2.balance("A") == 15


def test_identifiers_with_separators_do_not_collide():
    c = mod.IdempotentConsumer(MemoryStore())
    assert c.process(E("balance:A", "A", 10)) == "applied"
    assert c.process(E("e:1", "event:x", 3)) == "applied"
    assert c.balance("A") == 10 and c.balance("event:x") == 3
    assert c.process(E("balance:A", "A", 10)) == "duplicate"


@pytest.mark.parametrize("bad", [
    E("", "A", 1), E("e", "", 1), E("e", "A", 0),
    mod.Event("e", "A", 5), mod.Event("e", "A", 1.5), mod.Event("e", "A", D("NaN")),
    mod.Event(None, "A", D(1)),
])
def test_invalid_events_are_rejected_without_writes(bad):
    store = MemoryStore()
    with pytest.raises(ValueError):
        mod.IdempotentConsumer(store).process(bad)
    assert store.commits == []


def test_random_redelivery_and_crash_stream_matches_exactly_once_model():
    rng = random.Random(32)
    for _ in range(100):
        events = [E(f"e{i}", rng.choice("ABC"), rng.choice([-9, -5, -1, 1, 4, 8])) for i in range(12)]
        model, bal = [], {}
        for e in events:
            nb = bal.get(e.account_id, D(0)) + e.amount
            if nb >= 0:
                bal[e.account_id] = nb
        # delivery: each event 1-3 times, interleaved but each id's first delivery keeps stream order
        delivery = []
        for e in events:
            delivery.append(e)
            while rng.random() < 0.4:
                delivery.append(rng.choice(events[: events.index(e) + 1]))
        store = MemoryStore()
        store.fail_before = {rng.randint(1, 15) for _ in range(2)}
        store.fail_after = {rng.randint(1, 15) for _ in range(2)} - store.fail_before
        c = mod.IdempotentConsumer(store)
        drive(c, delivery)
        assert {a: c.balance(a) for a in "ABC"} == {a: bal.get(a, D(0)) for a in "ABC"}
        assert len(store.commits) == len(events)
