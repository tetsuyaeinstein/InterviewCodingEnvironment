"""Tests for PY-001 (imports your practice file by default; see _loader.py)."""
import random
import time

from _loader import load

mod = load("PY-001")


def oracle(records):
    """Brute force: keep a record unless an equal, same-typed id was kept before it."""
    out, kept_ids = [], []
    for r in records:
        tid = r.get("transaction_id")
        if tid is None:
            out.append(r)
        elif not any(tid == s and type(tid) is type(s) for s in kept_ids):
            kept_ids.append(tid)
            out.append(r)
    return out


def test_example_from_question():
    recs = [
        {"transaction_id": "T-9", "amount": "4.00"},
        {"transaction_id": "T-7", "amount": "1.50"},
        {"transaction_id": "T-9", "amount": "4.10"},
        {"amount": "2.00"},
        {"transaction_id": None, "amount": "2.00"},
        {"transaction_id": "T-7", "amount": "1.50"},
    ]
    result = mod.dedupe_transactions(recs)
    assert result == [recs[0], recs[1], recs[3], recs[4]]


def test_empty_input():
    assert mod.dedupe_transactions([]) == []


def test_first_occurrence_wins_over_later_payloads():
    recs = [
        {"transaction_id": 5, "status": "PENDING"},
        {"transaction_id": 5, "status": "COMPLETED"},
        {"transaction_id": 5, "status": "REFUNDED"},
    ]
    result = mod.dedupe_transactions(recs)
    assert len(result) == 1
    assert result[0]["status"] == "PENDING"


def test_input_order_preserved():
    recs = [{"transaction_id": i} for i in (30, 10, 20, 10, 30, 40)]
    assert [r["transaction_id"] for r in mod.dedupe_transactions(recs)] == [30, 10, 20, 40]


def test_records_without_id_are_all_kept_in_position():
    a = {"transaction_id": None, "kiosk": "K1"}
    b = {"transaction_id": None, "kiosk": "K1"}  # identical content, still a separate record
    c = {"kiosk": "K2"}
    recs = [{"transaction_id": 1}, a, {"transaction_id": 1}, b, c, {"transaction_id": 2}]
    result = mod.dedupe_transactions(recs)
    assert result == [recs[0], a, b, c, recs[5]]
    assert result[1] is a and result[2] is b


def test_ids_are_not_coerced_between_types():
    recs = [{"transaction_id": 1001}, {"transaction_id": "1001"}, {"transaction_id": "1001 "}]
    assert mod.dedupe_transactions(recs) == recs


def test_single_pass_generator_input():
    def gen():
        yield {"transaction_id": "A"}
        yield {"transaction_id": "B"}
        yield {"transaction_id": "A"}

    assert [r["transaction_id"] for r in mod.dedupe_transactions(gen())] == ["A", "B"]


def test_returns_original_objects_and_does_not_mutate():
    recs = [{"transaction_id": "X", "items": [1, 2]}, {"transaction_id": "X", "items": [3]}]
    snapshot = [dict(r) for r in recs]
    result = mod.dedupe_transactions(recs)
    assert result[0] is recs[0]
    assert recs == snapshot
    assert len(recs) == 2


def test_matches_brute_force_on_random_inputs():
    rng = random.Random(1)
    for _ in range(300):
        recs = []
        for i in range(rng.randint(0, 30)):
            roll = rng.random()
            if roll < 0.1:
                recs.append({"seq": i})
            elif roll < 0.2:
                recs.append({"transaction_id": None, "seq": i})
            else:
                tid = rng.choice([rng.randint(1, 8), str(rng.randint(1, 8))])
                recs.append({"transaction_id": tid, "seq": i})
        assert mod.dedupe_transactions(recs) == oracle(recs)


def test_large_input_runs_in_linear_time():
    n = 30_000
    recs = [{"transaction_id": f"T{i:07d}"} for i in range(n)]
    recs += [{"transaction_id": f"T{i:07d}", "dup": True} for i in range(0, n, 3)]
    t0 = time.perf_counter()
    result = mod.dedupe_transactions(recs)
    elapsed = time.perf_counter() - t0
    assert len(result) == n
    assert not any("dup" in r for r in result)
    assert elapsed < 2.0, f"took {elapsed:.2f}s - expected a linear-time approach"
