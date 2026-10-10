"""Tests for PY-036 (imports your practice file by default; see _loader.py)."""
import copy
import random
from datetime import datetime, timedelta, timezone

import pytest

from _loader import load

mod = load("PY-036")

UTC = timezone.utc
TRACKED = ["tier", "city"]


def d(month, day=1, hour=0):
    return datetime(2025, month, day, hour, tzinfo=UTC)


def row(cid, version, frm, to, tier, city, **extra):
    return {"customer_id": cid, "version": version, "effective_from": frm, "effective_to": to,
            "is_current": to is None, "tier": tier, "city": city, **extra}


def chg(cid, ts, **attrs):
    return {"customer_id": cid, "change_ts": ts, "attributes": attrs}


def apply(dim, changes):
    return mod.apply_scd2(dim, changes, tracked=TRACKED)


def check_invariants(rows):
    by = {}
    for r in rows:
        by.setdefault(r["customer_id"], []).append(r)
    for cid, rs in by.items():
        assert [r["effective_from"] for r in rs] == sorted(r["effective_from"] for r in rs)
        assert [r["version"] for r in rs] == list(range(1, len(rs) + 1)), cid
        for a, b in zip(rs, rs[1:]):
            assert a["effective_to"] == b["effective_from"], f"gap or overlap for {cid}"
            assert a["effective_from"] < a["effective_to"], f"empty/negative interval for {cid}"
            assert not a["is_current"]
        assert rs[-1]["is_current"] and rs[-1]["effective_to"] is None
        assert sum(r["is_current"] for r in rs) == 1


BASE = [row(7, 1, d(1), None, "silver", "Oslo")]


def test_example_from_question():
    res = apply(BASE, [chg(7, d(3), tier="gold"), chg(7, d(2), city="Bergen"), chg(7, d(3), tier="gold"),
                       chg(9, d(3, 5), tier="basic")])
    assert res.rejected == []
    assert res.rows == [
        row(7, 1, d(1), d(2), "silver", "Oslo"),
        row(7, 2, d(2), d(3), "silver", "Bergen"),
        row(7, 3, d(3), None, "gold", "Bergen"),
        row(9, 1, d(3, 5), None, "basic", None),
    ]


def test_simple_change_closes_current_and_opens_new_version():
    res = apply(BASE, [chg(7, d(6), city="Bergen")])
    assert res.rows == [row(7, 1, d(1), d(6), "silver", "Oslo"), row(7, 2, d(6), None, "silver", "Bergen")]
    assert res.rows[0]["effective_to"] == res.rows[1]["effective_from"]
    assert res.rows[0]["is_current"] is False and res.rows[1]["is_current"] is True


def test_unchanged_attributes_create_no_new_version():
    res = apply(BASE, [chg(7, d(5), tier="silver"), chg(7, d(6), tier="silver", city="Oslo"), chg(7, d(7))])
    assert res.rows == BASE and res.rejected == []


def test_replay_of_the_current_versions_own_change_is_a_noop():
    dim = [row(7, 1, d(1), d(3), "silver", "Oslo"), row(7, 2, d(3), None, "gold", "Oslo")]
    res = apply(dim, [chg(7, d(3), tier="gold")])
    assert res.rows == dim and res.rejected == []


def test_multiple_changes_in_one_batch_apply_in_timestamp_order_not_arrival_order():
    res = apply(BASE, [chg(7, d(5), tier="platinum"), chg(7, d(3), tier="gold"), chg(7, d(4), city="Bergen")])
    assert [(r["version"], r["effective_from"], r["tier"], r["city"]) for r in res.rows] == [
        (1, d(1), "silver", "Oslo"), (2, d(3), "gold", "Oslo"), (3, d(4), "gold", "Bergen"), (4, d(5), "platinum", "Bergen")]
    check_invariants(res.rows)


def test_change_before_current_effective_from_is_rejected_as_out_of_order():
    dim = [row(7, 1, d(1), d(3), "silver", "Oslo"), row(7, 2, d(3), None, "gold", "Oslo")]
    late = chg(7, d(2), city="Bergen")
    res = apply(dim, [late])
    assert res.rows == dim
    assert res.rejected == [mod.Rejected(late, "out_of_order")]
    # even when it would not change anything: the check comes before the no-op rule
    res = apply(dim, [chg(7, d(2), tier="gold")])
    assert [r.reason for r in res.rejected] == ["out_of_order"]


def test_same_timestamp_with_different_attributes_is_a_conflict_first_wins():
    a, b = chg(7, d(4), tier="gold"), chg(7, d(4), tier="platinum")
    res = apply(BASE, [a, b])
    assert res.rows[-1]["tier"] == "gold" and len(res.rows) == 2
    assert res.rejected == [mod.Rejected(b, "same_timestamp_conflict")]
    # at the current row's own effective_from, with a different value
    res = apply(BASE, [chg(7, d(1), tier="gold")])
    assert res.rows == BASE and [r.reason for r in res.rejected] == ["same_timestamp_conflict"]


def test_unknown_attribute_is_rejected_and_nothing_is_applied():
    bad = chg(7, d(4), tier="gold", shoe_size=44)
    res = apply(BASE, [bad])
    assert res.rows == BASE and res.rejected == [mod.Rejected(bad, "unknown_attribute")]


def test_rejections_are_reported_in_arrival_order():
    c1 = chg(7, d(9), nope=1)
    c2 = chg(7, d(1, 1, 0), tier="x")                 # same ts as current, conflict
    c3 = chg(7, d(1) - timedelta(days=5), tier="y")   # older than current
    res = apply(BASE, [c1, c2, c3])
    assert [r.change for r in res.rejected] == [c1, c2, c3]
    assert [r.reason for r in res.rejected] == ["unknown_attribute", "same_timestamp_conflict", "out_of_order"]


def test_new_customer_gets_version_one_with_missing_attributes_none():
    res = apply([], [chg(3, d(2), tier="basic"), chg(3, d(3), city="Rome"), chg(1, d(1, 12), tier="gold", city="Oslo")])
    assert res.rows == [row(1, 1, d(1, 12), None, "gold", "Oslo"),
                        row(3, 1, d(2), d(3), "basic", None), row(3, 2, d(3), None, "basic", "Rome")]


def test_explicit_none_is_a_real_change():
    res = apply(BASE, [chg(7, d(4), city=None)])
    assert res.rows[-1] == row(7, 2, d(4), None, "silver", None)


def test_inputs_are_not_mutated_and_other_fields_survive_on_untouched_rows():
    dim = [row(7, 1, d(1), None, "silver", "Oslo", sk=101), row(8, 1, d(1), d(2), "a", "b", sk=5),
           row(8, 2, d(2), None, "c", "d", sk=6)]
    changes = [chg(7, d(5), tier="gold")]
    snapshot = copy.deepcopy((dim, changes))
    res = apply(dim, changes)
    assert (dim, changes) == snapshot
    assert res.rows[0]["sk"] == 101 and res.rows[0]["effective_to"] == d(5)
    assert [r["sk"] for r in res.rows if r["customer_id"] == 8] == [5, 6]
    res.rows[0]["tier"] = "tampered"
    assert dim[0]["tier"] == "silver"


def test_other_customers_history_is_untouched_and_output_is_sorted():
    dim = [row(8, 1, d(1), None, "a", "b"), row(2, 1, d(1), d(2), "x", "y"), row(2, 2, d(2), None, "z", "y")]
    res = apply(dim, [chg(8, d(3), tier="q")])
    assert [(r["customer_id"], r["version"]) for r in res.rows] == [(2, 1), (2, 2), (8, 1), (8, 2)]
    assert res.rows[:2] == sorted(dim[1:], key=lambda r: r["version"])


def test_applying_the_same_batch_twice_changes_nothing_the_second_time():
    batch = [chg(7, d(3), tier="gold"), chg(7, d(2), city="Bergen"), chg(9, d(2), tier="b"), chg(9, d(5), tier="c")]
    once = apply(BASE, batch)
    twice = apply(once.rows, batch)
    assert twice.rows == once.rows
    check_invariants(twice.rows)


@pytest.mark.parametrize("dim, changes", [
    ([row(7, 1, d(1), None, "a", "b"), row(7, 2, d(2), None, "a", "b")], []),                  # two current rows
    ([row(7, 1, d(1), d(2), "a", "b")], []),                                                   # no current row
    ([{**row(7, 1, d(1), None, "a", "b"), "is_current": False}], []),                          # open but not current
    (BASE, [{"change_ts": d(2), "attributes": {}}]),                                           # no customer_id
    (BASE, [{"customer_id": 7, "attributes": {}}]),                                            # no change_ts
    (BASE, [chg(7, datetime(2025, 3, 1))]),                                                    # naive ts
])
def test_invalid_input_raises(dim, changes):
    with pytest.raises(ValueError):
        apply(dim, changes)


def test_random_batches_keep_the_intervals_valid_and_match_a_sequential_model():
    rng = random.Random(36)
    tiers, cities = ["a", "b", "c"], ["x", "y"]
    for _ in range(150):
        dim = []
        for cid in range(1, 4):
            if rng.random() < 0.7:
                start = d(1)
                dim.append(row(cid, 1, start, None, rng.choice(tiers), rng.choice(cities)))
        changes = []
        for _ in range(rng.randint(0, 12)):
            attrs = {}
            if rng.random() < 0.6:
                attrs["tier"] = rng.choice(tiers)
            if rng.random() < 0.4:
                attrs["city"] = rng.choice(cities)
            changes.append(chg(rng.randint(1, 4), d(1) + timedelta(days=rng.randint(0, 5)), **attrs))
        res = apply(dim, changes)
        check_invariants(res.rows)
        # model: replay each customer's changes sorted by (ts, arrival) against the latest state
        for cid in range(1, 5):
            mine = sorted((c["change_ts"], i, c) for i, c in enumerate(changes) if c["customer_id"] == cid)
            cur = next((dict(r) for r in dim if r["customer_id"] == cid), None)
            versions = 1 if cur else 0
            for ts, _, c in mine:
                if cur is None:
                    cur = {"from": ts, "tier": c["attributes"].get("tier"), "city": c["attributes"].get("city")}
                    versions = 1
                    cur["effective_from"] = ts
                    continue
                if ts < cur["effective_from"]:
                    continue
                new = {a: c["attributes"].get(a, cur[a]) for a in TRACKED}
                if new == {a: cur[a] for a in TRACKED} or ts == cur["effective_from"]:
                    continue
                cur = {**new, "effective_from": ts}
                versions += 1
            got = [r for r in res.rows if r["customer_id"] == cid]
            assert len(got) == versions
            if got:
                assert (got[-1]["tier"], got[-1]["city"], got[-1]["effective_from"]) == (cur["tier"], cur["city"], cur["effective_from"])


def test_many_customers_are_handled_quickly():
    dim = [row(i, 1, d(1), None, "a", "b") for i in range(5000)]
    changes = [chg(i % 6000, d(2) + timedelta(minutes=i % 7), tier="z" if i % 2 else "y") for i in range(20000)]
    res = apply(dim, changes)
    check_invariants(res.rows)
