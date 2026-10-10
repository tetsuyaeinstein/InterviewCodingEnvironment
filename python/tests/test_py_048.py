"""Tests for PY-048 (asyncio driven with asyncio.run; only asyncio.sleep(0) ticks, no real waiting)."""
import asyncio

import pytest

from _loader import load

mod = load("PY-048")


class Boom(Exception):
    """Distinct from RuntimeError, which NotImplementedError subclasses."""


class Probe:
    """Instrumented work: records concurrency, start order and cancellation."""

    def __init__(self):
        self.running = 0
        self.max_running = 0
        self.started = []
        self.finished = []
        self.cancelled = []
        self.cleaned = []

    def job(self, i, ticks=3, result=None, error=None):
        async def run():
            self.started.append(i)
            self.running += 1
            self.max_running = max(self.max_running, self.running)
            try:
                for _ in range(ticks):
                    await asyncio.sleep(0)
                if error is not None:
                    raise error
                self.finished.append(i)
                return i if result is None else result
            except asyncio.CancelledError:
                self.cancelled.append(i)
                raise
            finally:
                self.running -= 1
                self.cleaned.append(i)
        return lambda: run()


def run(coro):
    return asyncio.run(coro)


def test_results_follow_input_order_not_completion_order():
    p = Probe()
    n = 6
    jobs = [p.job(i, ticks=(n - i) * 2, result=i * 10) for i in range(n)]   # later items finish first
    out = run(mod.gather_limited(jobs, limit=n))
    assert out == [0, 10, 20, 30, 40, 50]
    assert p.finished == sorted(p.finished, key=lambda i: -i)               # they really did finish reversed


@pytest.mark.parametrize("limit", [1, 2, 3, 7])
def test_concurrency_never_exceeds_the_limit_and_reaches_it(limit):
    p = Probe()
    out = run(mod.gather_limited([p.job(i) for i in range(12)], limit=limit))
    assert out == list(range(12))
    assert p.max_running == limit


def test_limit_larger_than_the_work():
    p = Probe()
    assert run(mod.gather_limited([p.job(i) for i in range(3)], limit=50)) == [0, 1, 2]
    assert p.max_running == 3


def test_limit_one_is_strictly_sequential_in_order():
    p = Probe()
    run(mod.gather_limited([p.job(i) for i in range(5)], limit=1))
    assert p.started == [0, 1, 2, 3, 4] and p.finished == [0, 1, 2, 3, 4] and p.max_running == 1


def test_work_does_not_start_before_a_slot_is_free():
    p = Probe()
    seen_running = []

    def spying(i):
        inner = p.job(i, ticks=2)

        def factory():
            seen_running.append(p.running)          # how many are in flight when this one is created
            return inner()
        return factory

    run(mod.gather_limited([spying(i) for i in range(8)], limit=3))
    assert max(seen_running) <= 2                   # a new item is only created when a slot is free


def test_empty_input():
    assert run(mod.gather_limited([], limit=3)) == []
    assert run(mod.gather_limited(iter(()), limit=1)) == []


def test_accepts_any_iterable_of_factories():
    p = Probe()
    out = run(mod.gather_limited((p.job(i) for i in range(5)), limit=2))
    assert out == [0, 1, 2, 3, 4]


@pytest.mark.parametrize("bad", [0, -1, 1.5, None, True])
def test_limit_validation(bad):
    with pytest.raises(ValueError):
        run(mod.gather_limited([], limit=bad))


def test_fail_fast_raises_the_first_error_and_cleans_up():
    p = Probe()
    first, second = ValueError("first"), KeyError("second")
    jobs = [
        p.job(0, ticks=1000),                        # long-running, must be cancelled
        p.job(1, ticks=2, error=first),              # fails earlier ...
        p.job(2, ticks=6, error=second),             # ... than this one
    ]

    async def main():
        with pytest.raises(ValueError) as info:
            await mod.gather_limited(jobs, limit=3)
        assert info.value is first
        # nothing left running: only this task remains
        assert asyncio.all_tasks() == {asyncio.current_task()}

    run(main())
    assert 0 in p.cancelled and 0 in p.cleaned, "the long-running job was not cancelled and awaited"
    assert p.running == 0


def test_items_not_yet_started_never_start_after_a_failure():
    p = Probe()
    jobs = [p.job(0, ticks=50), p.job(1, ticks=1, error=Boom("x")),
            p.job(2), p.job(3), p.job(4)]
    with pytest.raises(Boom):
        run(mod.gather_limited(jobs, limit=2))
    assert 3 not in p.started and 4 not in p.started
    assert p.started[:2] == [0, 1]


def test_factory_that_raises_when_called_counts_as_a_failure():
    p = Probe()

    def broken():
        raise ValueError("cannot even build the request")

    with pytest.raises(ValueError, match="cannot even build"):
        run(mod.gather_limited([p.job(0, ticks=20), broken, p.job(2)], limit=2))
    assert p.running == 0


def test_collect_mode_returns_exceptions_in_place_and_runs_everything():
    p = Probe()
    err = ValueError("bad item 2")
    jobs = [p.job(0), p.job(1), p.job(2, error=err), p.job(3), p.job(4, error=KeyError("k"))]
    out = run(mod.gather_limited(jobs, limit=2, return_exceptions=True))
    assert out[0] == 0 and out[1] == 1 and out[3] == 3
    assert out[2] is err and isinstance(out[4], KeyError)
    assert sorted(p.started) == [0, 1, 2, 3, 4] and p.cancelled == []


def test_collect_mode_with_all_failures():
    p = Probe()
    out = run(mod.gather_limited([p.job(i, error=OSError(i)) for i in range(4)], limit=2, return_exceptions=True))
    assert [type(o) for o in out] == [OSError] * 4 and [o.args[0] for o in out] == [0, 1, 2, 3]


def test_outer_cancellation_cancels_and_awaits_everything():
    p = Probe()

    async def main():
        t = asyncio.ensure_future(mod.gather_limited([p.job(i, ticks=10_000) for i in range(6)], limit=3))
        for _ in range(5):
            await asyncio.sleep(0)
        if t.done():
            t.result()                              # surfaces an unimplemented stub
        assert p.running == 3
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
        assert p.running == 0 and sorted(p.cancelled) == [0, 1, 2]
        assert 3 not in p.started
        assert asyncio.all_tasks() == {asyncio.current_task()}

    run(main())


def test_many_items_finish_quickly():
    async def quick():
        return 1

    out = run(mod.gather_limited([quick for _ in range(20_000)], limit=50))
    assert len(out) == 20_000 and sum(out) == 20_000
