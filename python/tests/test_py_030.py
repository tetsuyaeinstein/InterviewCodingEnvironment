"""Tests for PY-030 (imports your practice file by default; see _loader.py)."""
import random
from datetime import datetime, timedelta, timezone

import pytest

from _loader import load

mod = load("PY-030")
UTC = timezone.utc
T0 = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
M = timedelta(minutes=1)
S = mod.WatermarkState


def rec(key, minutes, **extra):
    return {"id": key, "updated_at": T0 + minutes * M, **extra}


def run(records, state=None, overlap=10, upper=60):
    return mod.select_incremental(records, state or S(), overlap=overlap * M, upper_bound=T0 + upper * M)


def ids(rows):
    return [(r["id"], int((r["updated_at"] - T0) / M)) for r in rows]


def test_first_run_has_no_lower_bound_and_upper_bound_is_exclusive():
    res = run([rec("b", 5), rec("a", -500), rec("c", 60), rec("d", 59), rec("a", 5)])
    assert ids(res.to_process) == [("a", -500), ("a", 5), ("b", 5), ("d", 59)]   # ordered by (ts, key)
    assert res.late == []
    assert res.state.watermark == T0 + 59 * M


def test_lower_bound_is_inclusive_and_older_records_are_late():
    state = S(watermark=T0 + 30 * M)
    early = {"id": "x", "updated_at": T0 + 20 * M - timedelta(microseconds=1)}
    res = run([rec("edge", 20), early, rec("mid", 25), rec("new", 40)], state)
    assert ids(res.to_process) == [("edge", 20), ("mid", 25), ("new", 40)]
    assert res.late == [early]
    assert res.state.watermark == T0 + 40 * M


def test_redelivered_versions_inside_the_overlap_are_not_reprocessed():
    first = run([rec("a", 10), rec("b", 12)])
    second = run([rec("a", 10), rec("b", 12), rec("b", 13), rec("c", 5)], first.state, upper=90)
    assert ids(second.to_process) == [("c", 5), ("b", 13)]
    assert second.state.watermark == T0 + 13 * M


def test_duplicates_within_one_batch_are_processed_once():
    res = run([rec("a", 3, v=1), rec("a", 3, v=2), rec("a", 4)])
    assert ids(res.to_process) == [("a", 3), ("a", 4)]
    assert res.to_process[0]["v"] == 1   # first delivery wins


def test_equal_instants_in_different_offsets_are_the_same_version():
    plus2 = timezone(timedelta(hours=2))
    first = run([rec("a", 10)])
    again = {"id": "a", "updated_at": (T0 + 10 * M).astimezone(plus2)}
    assert run([again], first.state, upper=70).to_process == []


def test_watermark_never_moves_backwards():
    state = S(watermark=T0 + 50 * M, processed=frozenset({("z", T0 + 50 * M)}))
    res = run([rec("a", 45), rec("b", 41)], state, upper=70)
    assert ids(res.to_process) == [("b", 41), ("a", 45)]
    assert res.state.watermark == T0 + 50 * M


def test_empty_batch_keeps_state():
    state = S(watermark=T0 + 50 * M, processed=frozenset({("z", T0 + 45 * M)}))
    res = run([], state, upper=70)
    assert res.to_process == [] and res.late == []
    assert res.state == state
    assert run([], S()).state == S()


def test_processed_state_is_pruned_to_the_next_window():
    state = S(watermark=T0 + 30 * M,
              processed=frozenset({("old", T0 + 20 * M), ("keep", T0 + 31 * M), ("edge", T0 + 30 * M)}))
    res = run([rec("n1", 40), rec("n2", 35), rec("n3", 29)], state, upper=100)
    # new watermark 40, overlap 10 -> keep pairs with updated_at >= 30
    assert res.state.watermark == T0 + 40 * M
    assert res.state.processed == frozenset({("keep", T0 + 31 * M), ("edge", T0 + 30 * M),
                                             ("n1", T0 + 40 * M), ("n2", T0 + 35 * M)})


def test_input_state_is_not_modified():
    processed = frozenset({("a", T0 + 5 * M)})
    state = S(watermark=T0 + 5 * M, processed=processed)
    run([rec("b", 6), rec("a", 5)], state)
    assert state == S(watermark=T0 + 5 * M, processed=processed)


@pytest.mark.parametrize("kwargs", [
    {"records": [{"id": "a", "updated_at": datetime(2025, 6, 1, 12)}]},          # naive record
    {"records": [{"id": "a", "updated_at": "2025-06-01T12:00:00+00:00"}]},       # not a datetime
    {"records": [{"id": "a"}]},                                                  # missing ts
    {"records": [{"updated_at": T0}]},                                           # missing key
    {"upper": datetime(2025, 6, 2)},                                             # naive upper bound
    {"overlap": -M},
    {"state": S(watermark=T0 + 120 * M)},                                        # upper < watermark
])
def test_invalid_inputs_raise(kwargs):
    records = kwargs.get("records", [rec("a", 1)])
    state = kwargs.get("state", S())
    overlap = kwargs.get("overlap", 10 * M)
    upper = kwargs.get("upper", T0 + 60 * M)
    with pytest.raises(ValueError):
        mod.select_incremental(records, state, overlap=overlap, upper_bound=upper)


def simulate(seed, overlap_min, max_lag_min, redeliver_min):
    rng = random.Random(seed)
    events = []
    for i in range(400):
        ts = T0 + timedelta(seconds=rng.randint(0, 6 * 3600))
        key = f"k{rng.randint(0, 40)}"
        visible = ts + timedelta(seconds=rng.randint(0, max_lag_min * 60))
        events.append(({"id": key, "updated_at": ts, "n": i}, visible))
    state, step = S(), timedelta(minutes=15)
    processed, late = [], []
    upper = T0
    while upper < T0 + timedelta(hours=8):
        prev, upper = upper, upper + step
        batch = [e for e, vis in events if prev - redeliver_min * M <= vis < upper]
        rng.shuffle(batch)
        res = mod.select_incremental(batch, state, overlap=overlap_min * M, upper_bound=upper)
        for r in res.to_process:
            assert (state.watermark is None or r["updated_at"] >= state.watermark - overlap_min * M)
            assert r["updated_at"] < upper
        assert state.watermark is None or res.state.watermark >= state.watermark
        processed += [(r["id"], r["updated_at"]) for r in res.to_process]
        late += [(r["id"], r["updated_at"]) for r in res.late]
        state = res.state
        assert all(ts >= state.watermark - overlap_min * M for _, ts in state.processed), "state not pruned"
    return events, processed, late


def test_simulation_exactly_once_when_overlap_covers_lateness():
    events, processed, late = simulate(30, overlap_min=20, max_lag_min=15, redeliver_min=25)
    versions = {(e["id"], e["updated_at"]) for e, _ in events}
    assert len(processed) == len(set(processed)), "a version was processed twice"
    assert set(processed) == versions, "a version was never processed"
    assert late == [] or set(late) <= set(processed)   # only re-deliveries of already-processed versions


def test_simulation_too_late_records_are_reported_not_silently_dropped():
    events, processed, late = simulate(31, overlap_min=5, max_lag_min=60, redeliver_min=0)
    versions = {(e["id"], e["updated_at"]) for e, _ in events}
    assert len(processed) == len(set(processed))
    missing = versions - set(processed)
    assert missing, "scenario should produce versions that arrive after the overlap window"
    assert missing <= set(late), "every unprocessed version must have been reported as late"
