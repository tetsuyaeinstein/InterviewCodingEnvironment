"""Tests for PY-045 (pure Python, fakes only)."""
import pytest

from _loader import load

mod = load("PY-045")


class Sink:
    """In-memory sink. Keyed upserts make it idempotent; `poison` ids make load() raise atomically."""

    def __init__(self, poison=(), fail_all=False):
        self.rows = {}
        self.calls = []
        self.poison, self.fail_all = set(poison), fail_all

    def __call__(self, batch):
        self.calls.append(list(batch))
        if self.fail_all or any(r["id"] in self.poison for r in batch):
            raise RuntimeError("sink rejected batch")
        for r in batch:                    # atomic: reached only if every row is acceptable
            self.rows[r["id"]] = r


def ident(r):
    return {"id": r, "v": r * 10}


def test_loads_in_order_in_exact_batches():
    sink = Sink()
    s = mod.run_etl(lambda: range(1, 8), ident, sink, batch_size=3)
    assert [[r["id"] for r in c] for c in sink.calls] == [[1, 2, 3], [4, 5, 6], [7]]
    assert (s.read, s.filtered, s.loaded, s.batches, s.quarantined) == (7, 0, 7, 3, [])


def test_exact_multiple_has_no_empty_trailing_batch():
    sink = Sink()
    s = mod.run_etl(lambda: range(6), ident, sink, batch_size=3)
    assert len(sink.calls) == 2 and all(sink.calls) and s.batches == 2


def test_empty_source():
    sink = Sink()
    s = mod.run_etl(lambda: [], ident, sink)
    assert sink.calls == [] and (s.read, s.loaded, s.batches) == (0, 0, 0) and s.quarantined == []


def test_source_is_consumed_lazily_and_called_once():
    consumed, calls_to_extract = [], []

    def extract():
        calls_to_extract.append(1)
        for i in range(10):
            consumed.append(i)
            yield i

    seen_at_load = []

    def load_fn(batch):
        seen_at_load.append(len(consumed))

    mod.run_etl(extract, ident, load_fn, batch_size=4)
    assert seen_at_load == [4, 8, 10]          # no read-ahead beyond a full batch
    assert calls_to_extract == [1]


def test_none_filters_the_record_out():
    sink = Sink()
    s = mod.run_etl(lambda: range(1, 7), lambda r: None if r % 2 else ident(r), sink, batch_size=2)
    assert sorted(sink.rows) == [2, 4, 6]
    assert (s.read, s.filtered, s.loaded) == (6, 3, 3)
    assert [r["id"] for c in sink.calls for r in c] == [2, 4, 6]


def test_transform_errors_are_quarantined_and_the_run_continues():
    def tf(r):
        if r == "x":
            raise ValueError("not a number")
        return ident(int(r))

    sink = Sink()
    s = mod.run_etl(lambda: [1, 2, "x", 4, 5], tf, sink, batch_size=2)
    assert sorted(sink.rows) == [1, 2, 4, 5]
    assert s.read == 5 and s.loaded == 4
    assert s.quarantined == [mod.Quarantined(2, "transform", "ValueError: not a number", "x")]


def test_poison_row_is_isolated_and_neighbours_are_kept():
    sink = Sink(poison={5})
    s = mod.run_etl(lambda: range(1, 10), ident, sink, batch_size=4)    # batches 1-4, 5-8, 9
    assert sorted(sink.rows) == [1, 2, 3, 4, 6, 7, 8, 9]
    assert s.loaded == 8 and s.batches == 3
    assert len(s.quarantined) == 1
    q = s.quarantined[0]
    assert (q.position, q.stage, q.record) == (4, "load", {"id": 5, "v": 50})
    assert q.error == "RuntimeError: sink rejected batch"


def test_positions_count_filtered_records_and_are_sorted():
    def tf(r):
        if r == 1:
            return None
        if r == 3:
            raise KeyError("k")
        return ident(r)

    sink = Sink(poison={2})
    s = mod.run_etl(lambda: [0, 1, 2, 3, 4], tf, sink, batch_size=10)
    assert [(q.position, q.stage) for q in s.quarantined] == [(2, "load"), (3, "transform")]
    assert s.read == 5 and s.filtered == 1 and s.loaded == 2
    assert s.read == s.filtered + s.loaded + len(s.quarantined)


def test_sink_that_rejects_everything():
    sink = Sink(fail_all=True)
    s = mod.run_etl(lambda: range(5), ident, sink, batch_size=2)
    assert s.loaded == 0 and len(s.quarantined) == 5
    assert [q.position for q in s.quarantined] == [0, 1, 2, 3, 4]


def test_raise_mode_propagates_the_original_exception():
    def tf(r):
        if r == 3:
            raise ValueError("boom")
        return ident(r)

    sink = Sink()
    with pytest.raises(ValueError, match="boom"):
        mod.run_etl(lambda: range(6), tf, sink, batch_size=2, on_error="raise")
    assert sorted(sink.rows) == [0, 1]          # full batch loaded, pending row 2 was not

    sink2 = Sink(poison={3})
    with pytest.raises(RuntimeError):
        mod.run_etl(lambda: range(6), ident, sink2, batch_size=2, on_error="raise")
    assert sorted(sink2.rows) == [0, 1]
    assert len(sink2.calls) == 2                # no per-row retries in raise mode


def test_extract_failure_propagates_after_earlier_batches_stay_loaded():
    def extract():
        yield from range(5)
        raise ConnectionError("source went away")

    sink = Sink()
    with pytest.raises(ConnectionError):
        mod.run_etl(extract, ident, sink, batch_size=2)
    assert sorted(sink.rows) == [0, 1, 2, 3]


def test_base_exceptions_are_not_swallowed():
    def tf(r):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        mod.run_etl(lambda: [1], tf, Sink())


def test_argument_validation_happens_before_reading():
    touched = []

    def extract():
        touched.append(1)
        return [1]

    with pytest.raises(ValueError):
        mod.run_etl(extract, ident, Sink(), on_error="ignore")
    with pytest.raises(ValueError):
        mod.run_etl(extract, ident, Sink(), batch_size=0)
    assert touched == []


def test_rerun_into_an_idempotent_sink_is_stable():
    sink = Sink()
    first = mod.run_etl(lambda: range(25), ident, sink, batch_size=7)
    snapshot = dict(sink.rows)
    second = mod.run_etl(lambda: range(25), ident, sink, batch_size=7)
    assert sink.rows == snapshot and len(sink.rows) == 25
    assert first == second


def test_large_input_with_small_batches_runs_fast():
    sink = Sink()
    s = mod.run_etl(lambda: range(50_000), ident, sink, batch_size=500)
    assert s.loaded == 50_000 and s.batches == 100
