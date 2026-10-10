"""Tests for PY-031 (imports your practice file by default; see _loader.py)."""
import itertools
import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from _loader import load

mod = load("PY-031")

T0 = datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc)


def ev(key, seq, op="U", payload=None, minute=0):
    return mod.Event(key, seq, T0 + timedelta(minutes=minute), {} if payload is None else payload, op)


def oracle(events):
    """Independent model: group, take the max sequence, distinct (op, payload) variants."""
    by_key = {}
    for e in events:
        by_key.setdefault(e.key, []).append(e)
    live, conflicts, records = {}, {}, {}
    for k, es in by_key.items():
        top = max(e.sequence for e in es)
        variants = {}
        for e in es:
            if e.sequence != top:
                continue
            vid = ("D", "") if e.op == "D" else (e.op, json.dumps(e.payload, sort_keys=True))
            if vid not in variants or e.ingest_ts < variants[vid].ingest_ts:
                variants[vid] = e
        if len(variants) > 1:
            conflicts[k] = (top, sorted(variants))
        else:
            (w,) = variants.values()
            records[k] = w
            if w.op != "D":
                live[k] = w.payload
    return live, conflicts, records


def run(events):
    s = mod.CurrentState()
    s.apply_all(events)
    return s


def test_example_from_question():
    s = mod.CurrentState()
    out = s.apply_all([
        ev("c1", 5, payload={"tier": "gold"}, minute=1),
        ev("c1", 3, payload={"tier": "basic"}, minute=2),
        ev("c1", 5, payload={"tier": "gold"}, minute=3),
        ev("c1", 6, "D", minute=4),
        ev("c1", 4, payload={"tier": "silver"}, minute=5),
    ])
    assert out == ["applied", "stale", "duplicate", "applied", "stale"]
    assert s.snapshot() == {}
    assert s.record("c1").op == "D" and s.record("c1").sequence == 6
    assert s.conflicts() == []


def test_sequence_beats_ingest_time():
    s = run([ev("a", 2, payload={"v": "new"}, minute=1), ev("a", 1, payload={"v": "old"}, minute=99)])
    assert s.snapshot() == {"a": {"v": "new"}}


def test_tombstone_blocks_older_update_but_not_newer_insert():
    s = run([ev("a", 5, "D"), ev("a", 4, "U", {"v": 1})])
    assert s.snapshot() == {} and s.record("a").op == "D"
    assert s.apply(ev("a", 7, "I", {"v": 2})) == "applied"
    assert s.snapshot() == {"a": {"v": 2}}


def test_update_before_insert_still_resolves_by_sequence():
    s = run([ev("a", 2, "U", {"v": "u"}), ev("a", 1, "I", {"v": "i"})])
    assert s.snapshot() == {"a": {"v": "u"}}


def test_duplicate_ignores_ingest_ts_and_keeps_the_earliest_copy():
    late_first = [ev("a", 3, payload={"v": 1}, minute=9), ev("a", 3, payload={"v": 1}, minute=2),
                  ev("a", 3, payload={"v": 1}, minute=5)]
    for perm in itertools.permutations(late_first):
        s = mod.CurrentState()
        out = s.apply_all(perm)
        assert out[0] == "applied" and out[1:] == ["duplicate", "duplicate"]
        assert s.record("a").ingest_ts == T0 + timedelta(minutes=2)


def test_same_sequence_different_payload_is_a_conflict():
    s = mod.CurrentState()
    assert s.apply(ev("a", 4, payload={"v": "x"})) == "applied"
    assert s.apply(ev("a", 4, payload={"v": "y"})) == "conflict"
    assert s.apply(ev("a", 4, payload={"v": "x"}, minute=3)) == "duplicate"   # matches a known variant
    assert s.snapshot() == {} and s.record("a") is None
    (c,) = s.conflicts()
    assert (c.key, c.sequence) == ("a", 4)
    assert [e.payload for e in c.variants] == [{"v": "x"}, {"v": "y"}]


def test_conflict_between_delete_and_update():
    s = run([ev("a", 4, "D"), ev("a", 4, "U", {"v": 1})])
    assert s.snapshot() == {}
    (c,) = s.conflicts()
    assert [e.op for e in c.variants] == ["D", "U"]


def test_conflict_is_healed_by_a_higher_sequence_only():
    s = run([ev("a", 4, payload={"v": 1}), ev("a", 4, payload={"v": 2})])
    assert len(s.conflicts()) == 1
    assert s.apply(ev("a", 3, payload={"v": 0})) == "stale"
    assert len(s.conflicts()) == 1
    assert s.apply(ev("a", 5, payload={"v": 3})) == "applied"
    assert s.conflicts() == [] and s.snapshot() == {"a": {"v": 3}}
    # a conflict that is superseded before it is noticed is never reported
    s = run([ev("b", 5, payload={"v": 3}), ev("b", 4, payload={"v": 1}), ev("b", 4, payload={"v": 2})])
    assert s.conflicts() == []


def test_delete_payload_is_ignored_when_comparing():
    s = mod.CurrentState()
    assert s.apply(ev("a", 2, "D", {"last": 1})) == "applied"
    assert s.apply(ev("a", 2, "D", {"last": 2})) == "duplicate"
    assert s.conflicts() == []


def test_nested_payloads_and_defensive_copies():
    payload = {"tags": ["x", "y"], "addr": {"city": "Oslo"}}
    s = run([ev("a", 1, payload=payload), ev("a", 1, payload={"addr": {"city": "Oslo"}, "tags": ["x", "y"]}, minute=1)])
    assert s.conflicts() == []
    snap = s.snapshot()
    snap["a"]["tags"].append("hacked")
    snap["zzz"] = {}
    assert s.snapshot() == {"a": payload}


def test_keys_are_independent_and_snapshot_is_sorted():
    s = run([ev("b", 1, payload={"v": 1}), ev("a", 1, payload={"v": 2}), ev("c", 1, "D"), ev("a", 0, payload={"v": 9})])
    assert list(s.snapshot()) == ["a", "b"]
    assert s.record("missing") is None


@pytest.mark.parametrize("bad", [
    lambda: ev("a", 1, "X"),
    lambda: ev("a", "1"),
    lambda: ev("a", True),
    lambda: ev("a", 1.0),
    lambda: mod.Event("a", 1, datetime(2025, 1, 1), {}, "U"),    # naive timestamp
])
def test_invalid_events_are_rejected(bad):
    s = mod.CurrentState()
    with pytest.raises(ValueError):
        s.apply(bad())


def test_all_permutations_of_a_tricky_set_give_the_same_state():
    events = [ev("a", 3, "U", {"v": 1}, 1), ev("a", 3, "U", {"v": 1}, 7), ev("a", 3, "U", {"v": 2}, 4),
              ev("b", 2, "D", None, 2), ev("b", 1, "I", {"v": 5}, 9), ev("b", 2, "D", {"x": 1}, 3),
              ev("c", 1, "I", {"v": 1}, 0), ev("c", 2, "U", {"v": 2}, 0)]
    results = set()
    for perm in itertools.permutations(events[:7]):
        s = run(perm)
        results.add((json.dumps(s.snapshot(), sort_keys=True),
                     tuple((c.key, c.sequence, tuple((v.op, json.dumps(v.payload, sort_keys=True), v.ingest_ts) for v in c.variants))
                           for c in s.conflicts()),
                     tuple((k, getattr(s.record(k), "sequence", None), getattr(s.record(k), "ingest_ts", None)) for k in "abc")))
    assert len(results) == 1


def rand_event(rng):
    op = rng.choice("IUD")
    payload = {} if op == "D" else {"v": rng.randint(0, 2)}
    return ev(rng.choice("abcd"), rng.randint(1, 4), op, payload, rng.randint(0, 30))


def test_random_streams_match_the_oracle_in_any_order():
    rng = random.Random(31)
    for _ in range(300):
        events = [rand_event(rng) for _ in range(rng.randint(0, 16))]
        live, conflicts, records = oracle(events)
        for _ in range(3):
            rng.shuffle(events)
            s = run(events)
            assert s.snapshot() == live
            assert {c.key: (c.sequence, len(c.variants)) for c in s.conflicts()} == {k: (v[0], len(v[1])) for k, v in conflicts.items()}
            assert [c.key for c in s.conflicts()] == sorted(conflicts)
            for k, w in records.items():
                assert s.record(k) == w
            for k in conflicts:
                assert s.record(k) is None


def test_many_events_are_processed_quickly():
    s = mod.CurrentState()
    events = [ev(f"k{i % 2000}", i // 2000, payload={"v": i}) for i in range(20_000)]
    s.apply_all(reversed(events))
    snap = s.snapshot()
    assert len(snap) == 2000 and snap["k0"] == {"v": 18_000}
