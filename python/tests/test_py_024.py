"""Tests for PY-024 (imports your practice file by default; see _loader.py)."""
import random
import time
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-024")


def r(acct, seq, **payload):
    return {"account_id": acct, "source_seq": seq, **payload}


def resolve(records, key=("account_id",), **kw):
    return mod.resolve_revisions(records, list(key), **kw)


def oracle(records, key_fields, seq_field="source_seq", ignore=()):
    keys = {}
    for i, rec in enumerate(records):
        keys.setdefault(tuple(rec[f] for f in key_fields), []).append((int(rec[seq_field]), i, rec))
    winners, conflicts = [], []
    for k in sorted(keys):
        top = max(s for s, _, _ in keys[k])
        distinct = []
        for s, _, rec in keys[k]:
            if s == top:
                p = {a: b for a, b in rec.items() if a not in ignore}
                if all(p != q for q, _ in distinct):
                    distinct.append((p, rec))
        if len(distinct) == 1:
            winners.append(distinct[0][1])
        else:
            conflicts.append((k, top, [x for _, x in distinct]))
    return winners, conflicts


def test_latest_by_sequence_not_by_arrival():
    current, conflicts = resolve([r("A", 2, status="ACTIVE"), r("A", 1, status="NEW"),   # seq 1 arrives late
                                  r("B", 1, status="NEW")])
    assert current == [r("A", 2, status="ACTIVE"), r("B", 1, status="NEW")]
    assert conflicts == []


def test_string_sequences_compare_numerically():
    current, _ = resolve([r("A", "9", v=1), r("A", "10", v=2), r("A", 3, v=3)])
    assert current == [r("A", "10", v=2)]


def test_identical_duplicates_collapse_to_the_first_arrival():
    recs = [r("A", 5, v=1, file="f1.csv"), r("A", 5, v=1, file="f2.csv"), r("A", 5, v=1, file="f1.csv")]
    current, conflicts = resolve(recs, ignore_fields={"file"})
    assert current == [recs[0]] and conflicts == []
    # without ignoring the metadata column the payloads differ -> conflict
    current, conflicts = resolve(recs)
    assert current == [] and len(conflicts) == 1
    assert conflicts[0].records == (recs[0], recs[1])


def test_conflict_at_latest_sequence_is_reported_and_not_resolved():
    recs = [r("A", 1, v="x"), r("A", 7, v="red"), r("B", 2, v="ok"), r("A", 7, v="blue"), r("A", 7, v="red")]
    current, conflicts = resolve(recs)
    assert current == [r("B", 2, v="ok")]
    assert conflicts == [mod.Conflict(("A",), 7, (r("A", 7, v="red"), r("A", 7, v="blue")))]


def test_conflict_superseded_by_a_later_revision_is_not_a_conflict():
    recs = [r("A", 3, v="red"), r("A", 3, v="blue"), r("A", 4, v="green")]
    for order in (recs, recs[::-1], [recs[2], recs[0], recs[1]]):
        current, conflicts = resolve(order)
        assert current == [r("A", 4, v="green")] and conflicts == []


def test_composite_keys_and_deterministic_sorted_output():
    recs = [{"store": "S2", "sku": "B", "seq": 1, "qty": 5},
            {"store": "S1", "sku": "Z", "seq": 1, "qty": 1},
            {"store": "S1", "sku": "A", "seq": 2, "qty": 2},
            {"store": "S1", "sku": "A", "seq": 1, "qty": 9},
            {"store": "S2", "sku": "B", "seq": 1, "qty": 6}]
    current, conflicts = mod.resolve_revisions(recs, ["store", "sku"], sequence_field="seq")
    assert [(c["store"], c["sku"], c["qty"]) for c in current] == [("S1", "A", 2), ("S1", "Z", 1)]
    assert [c.key for c in conflicts] == [("S2", "B")] and conflicts[0].sequence == 1


def test_nested_unhashable_payloads():
    a = r("A", 1, tags=["x", "y"], attrs={"tier": "gold"})
    b = r("A", 1, tags=["x", "y"], attrs={"tier": "gold"})
    c = r("B", 1, tags=["x"], attrs={})
    d = r("B", 1, tags=["x", "z"], attrs={})
    current, conflicts = resolve([a, b, c, d])
    assert current == [a]
    assert [x.key for x in conflicts] == [("B",)]


def test_payload_equality_uses_value_semantics():
    current, conflicts = resolve([r("A", 1, amount=Decimal("1.0")), r("A", 1, amount=Decimal("1.00"))])
    assert len(current) == 1 and conflicts == []


@pytest.mark.parametrize("bad", [
    [{"source_seq": 1, "v": 1}],                       # no key field
    [r(None, 1)],                                      # NULL key
    [{"account_id": "A", "v": 1}],                     # no sequence
    [r("A", None)], [r("A", "1.5")], [r("A", "abc")], [r("A", True)], [r("A", 1.0)],
])
def test_invalid_records_raise(bad):
    with pytest.raises(ValueError):
        resolve(bad)


def test_empty_and_one_shot_iterator():
    assert resolve([]) == ([], [])
    current, _ = resolve(iter([r("A", 1, v=1), r("A", 2, v=2)]))
    assert current == [r("A", 2, v=2)]


def test_matches_oracle_and_is_independent_of_arrival_order():
    rng = random.Random(24)
    for _ in range(300):
        recs = [r(rng.choice("ABCDE"), rng.randint(1, 4), v=rng.choice("xy")) for _ in range(rng.randint(0, 14))]
        exp_w, exp_c = oracle(recs, ["account_id"])
        current, conflicts = resolve(recs)
        assert current == exp_w
        assert [(c.key, c.sequence, list(c.records)) for c in conflicts] == exp_c
        shuffled = recs[:]
        rng.shuffle(shuffled)
        cur2, conf2 = resolve(shuffled)
        assert cur2 == current, "result must not depend on arrival order"
        assert [(c.key, c.sequence) for c in conf2] == [(c.key, c.sequence) for c in conflicts]


def test_large_input_is_near_linear():
    n = 200_000
    recs = ({"account_id": f"K{i % 20_000:05d}", "source_seq": i // 20_000, "v": i} for i in range(n))
    t0 = time.perf_counter()
    current, conflicts = resolve(recs)
    elapsed = time.perf_counter() - t0
    assert len(current) == 20_000 and conflicts == []
    assert current[0] == {"account_id": "K00000", "source_seq": 9, "v": 180_000}
    assert elapsed < 3.0, f"took {elapsed:.2f}s"
