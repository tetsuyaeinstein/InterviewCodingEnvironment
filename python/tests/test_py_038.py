"""Tests for PY-038 (imports your practice file by default; see _loader.py).

No sleeps are used for correctness: ordering and blocking are forced with Events/Barriers, and
every pipeline runs in a helper thread with a generous join timeout so that a deadlock is a
test failure and never a hang.
"""
import itertools
import random
import threading
from collections import Counter

import pytest

from _loader import load

mod = load("PY-038")

TIMEOUT = 10.0


def run_guarded(*args, **kwargs):
    """Run mod.run_pipeline in a helper thread; return ("ok", result) or ("err", exception)."""
    box = {}

    def target():
        try:
            box["r"] = ("ok", mod.run_pipeline(*args, **kwargs))
        except BaseException as exc:                       # noqa: BLE001
            if isinstance(exc, NotImplementedError):
                box["r"] = ("stub", exc)
            else:
                box["r"] = ("err", exc)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(TIMEOUT)
    assert not t.is_alive(), "pipeline deadlocked (did not finish within the timeout)"
    kind, value = box["r"]
    if kind == "stub":
        raise value
    return kind, value


class Probe:
    """Instrumented source/consumer: in_flight = items pulled from the source - items the consumer finished."""

    def __init__(self, n=None, fail_source_at=None):
        self.n, self.fail_source_at = n, fail_source_at
        self.pulled = self.done = self.max_in_flight = 0
        self.lock = threading.Lock()
        self.consumed = []
        self.overlap = False
        self._busy = threading.Lock()
        self.on_pull = None

    def source(self):
        for i in (itertools.count() if self.n is None else range(self.n)):
            if self.fail_source_at is not None and i == self.fail_source_at:
                raise RuntimeError("source broke")
            with self.lock:
                self.pulled += 1
                self.max_in_flight = max(self.max_in_flight, self.pulled - self.done)
                if self.on_pull:
                    self.on_pull(self.pulled)
            yield i

    def consume(self, value):
        if not self._busy.acquire(blocking=False):
            self.overlap = True
            return
        try:
            self.consumed.append(value)
            with self.lock:
                self.done += 1
        finally:
            self._busy.release()


def test_basic_run_transforms_and_consumes_in_input_order():
    p = Probe(50)
    kind, n = run_guarded(p.source(), lambda x: x * x, p.consume, max_in_flight=4, workers=3)
    assert (kind, n) == ("ok", 50)
    assert p.consumed == [i * i for i in range(50)]


def test_empty_source():
    p = Probe(0)
    assert run_guarded(p.source(), lambda x: x, p.consume, max_in_flight=2, workers=2) == ("ok", 0)
    assert p.consumed == []


@pytest.mark.parametrize("max_in_flight, workers", [(1, 1), (1, 4), (3, 1), (3, 3), (5, 2), (16, 8)])
def test_in_flight_items_never_exceed_the_bound(max_in_flight, workers):
    p = Probe(400)
    kind, n = run_guarded(p.source(), lambda x: x + 1, p.consume, max_in_flight=max_in_flight, workers=workers)
    assert (kind, n) == ("ok", 400)
    assert p.max_in_flight <= max_in_flight, p.max_in_flight
    assert p.consumed == list(range(1, 401))


def test_a_stalled_consumer_stops_the_producer_from_pulling():
    bound = 5
    p = Probe(1000)
    gate, runaway = threading.Event(), threading.Event()
    p.on_pull = lambda pulled: pulled > bound + 3 and runaway.set()

    def slow_consumer(v):
        assert gate.wait(TIMEOUT)
        p.consume(v)

    box = {}

    def pipeline():
        try:
            box["r"] = run_guarded(p.source(), lambda x: x, slow_consumer, max_in_flight=bound, workers=3)
        except BaseException as exc:                    # noqa: BLE001
            box["exc"] = exc

    t = threading.Thread(target=pipeline, daemon=True)
    t.start()
    try:
        assert not runaway.wait(0.05), "the source kept being pulled while the consumer was stalled"
        assert p.pulled <= bound
    finally:
        gate.set()
    t.join(TIMEOUT)
    if "exc" in box:
        raise box["exc"]
    assert box["r"] == ("ok", 1000)
    assert p.consumed == list(range(1000)) and p.max_in_flight <= bound


def test_workers_really_run_concurrently():
    barrier = threading.Barrier(4, timeout=TIMEOUT)

    def transform(x):
        barrier.wait()                                  # only passes if 4 transforms are in progress together
        return x

    p = Probe(4)
    assert run_guarded(p.source(), transform, p.consume, max_in_flight=4, workers=4) == ("ok", 4)
    assert p.consumed == [0, 1, 2, 3]


def test_input_order_is_kept_even_when_the_last_item_finishes_first():
    n = 5
    finished = [threading.Event() for _ in range(n)]

    def transform(i):
        if i + 1 < n:
            assert finished[i + 1].wait(TIMEOUT), "needs item i+1 to run concurrently"
        finished[i].set()
        return i * 10

    p = Probe(n)
    assert run_guarded(p.source(), transform, p.consume, max_in_flight=n, workers=n) == ("ok", n)
    assert p.consumed == [0, 10, 20, 30, 40]


def test_every_item_is_transformed_and_consumed_exactly_once_and_none_is_a_valid_result():
    seen = Counter()
    lock = threading.Lock()

    def transform(i):
        with lock:
            seen[i] += 1
        return None if i % 3 == 0 else i

    p = Probe(3000)
    assert run_guarded(p.source(), transform, p.consume, max_in_flight=16, workers=8) == ("ok", 3000)
    assert set(seen.values()) == {1} and len(seen) == 3000
    assert p.consumed == [None if i % 3 == 0 else i for i in range(3000)]
    assert not p.overlap


def test_consumer_is_never_called_concurrently():
    p = Probe(500)
    assert run_guarded(p.source(), lambda x: x, p.consume, max_in_flight=12, workers=6) == ("ok", 500)
    assert not p.overlap and len(p.consumed) == 500


def threads_now():
    return set(threading.enumerate())


def test_transform_error_is_reraised_and_only_earlier_items_are_consumed():
    boom = ValueError("bad item 7")

    def transform(i):
        if i == 7:
            raise boom
        return i

    before = threads_now()
    p = Probe(100)
    kind, exc = run_guarded(p.source(), transform, p.consume, max_in_flight=6, workers=3)
    assert kind == "err" and exc is boom
    assert p.consumed == list(range(7))
    assert threads_now() <= before, "pipeline threads were left running"


def test_first_failure_in_input_order_wins_even_if_a_later_item_fails_first():
    first, second = KeyError("item 3"), RuntimeError("item 6")
    six_failed = threading.Event()

    def transform(i):
        if i == 6:
            six_failed.set()
            raise second
        if i == 3:
            assert six_failed.wait(TIMEOUT)
            raise first
        return i

    p = Probe(10)
    kind, exc = run_guarded(p.source(), transform, p.consume, max_in_flight=10, workers=8)
    assert kind == "err" and exc is first
    assert p.consumed == [0, 1, 2]


def test_consumer_error_stops_an_infinite_source_without_deadlock():
    boom = OSError("sink unavailable")
    p = Probe(None)                                     # infinite source
    consumed = []

    def consumer(v):
        if v == 9:
            raise boom
        consumed.append(v)

    before = threads_now()
    kind, exc = run_guarded(p.source(), lambda x: x, consumer, max_in_flight=1, workers=2)
    assert kind == "err" and exc is boom and consumed == list(range(9))
    assert p.pulled <= 10 + 1 + 1, "kept pulling after the failure"
    assert threads_now() <= before


def test_source_error_is_reraised_after_the_earlier_items_were_consumed():
    p = Probe(100, fail_source_at=5)
    kind, exc = run_guarded(p.source(), lambda x: x, p.consume, max_in_flight=4, workers=2)
    assert kind == "err" and isinstance(exc, RuntimeError) and str(exc) == "source broke"
    assert p.consumed == [0, 1, 2, 3, 4]


def test_source_is_pulled_lazily():
    pulled = []

    def source():
        for i in range(10_000_000):
            pulled.append(i)
            yield i

    consumed = []

    def consumer(v):
        consumed.append(v)
        if v == 20:
            raise RuntimeError("stop")

    kind, _ = run_guarded(source(), lambda x: x, consumer, max_in_flight=8, workers=2)
    assert kind == "err" and len(pulled) <= 21 + 8 + 1


def test_returns_after_all_threads_have_stopped_on_success():
    before = threads_now()
    p = Probe(100)
    assert run_guarded(p.source(), lambda x: x, p.consume, max_in_flight=3, workers=5) == ("ok", 100)
    assert threads_now() <= before


@pytest.mark.parametrize("kw", [{"max_in_flight": 0}, {"max_in_flight": -1}, {"max_in_flight": 2, "workers": 0}])
def test_invalid_arguments_raise_before_pulling_anything(kw):
    p = Probe(5)
    kind, exc = run_guarded(p.source(), lambda x: x, p.consume, **kw)
    assert kind == "err" and isinstance(exc, ValueError)
    assert p.pulled == 0


def test_random_configurations_always_deliver_everything_in_order_within_the_bound():
    rng = random.Random(38)
    for _ in range(20):
        n = rng.randint(0, 120)
        bound, workers = rng.randint(1, 8), rng.randint(1, 6)
        p = Probe(n)
        assert run_guarded(p.source(), lambda x: -x, p.consume, max_in_flight=bound, workers=workers) == ("ok", n)
        assert p.consumed == [-i for i in range(n)] and p.max_in_flight <= bound
