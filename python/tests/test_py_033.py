"""Tests for PY-033 (imports your practice file by default; see _loader.py)."""
import pytest

from _loader import load

mod = load("PY-033")


class FakeTime:
    """Fake clock + sleeper: sleeping advances the clock; nothing really sleeps."""

    def __init__(self, start=100.0):
        self.now = start
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class ScriptedRng:
    """uniform(a, b) returns a + (b - a) * fraction, recording its calls."""

    def __init__(self, fraction=0.5):
        self.fraction = fraction
        self.calls = []

    def uniform(self, a, b):
        self.calls.append((a, b))
        return a + (b - a) * self.fraction


def flaky(failures, result="ok", exc=None):
    """A callable that raises ``failures`` times then returns ``result``."""
    state = {"calls": 0}

    def fn():
        state["calls"] += 1
        if state["calls"] <= failures:
            raise (exc or mod.TransientError)(f"boom {state['calls']}")
        return result

    fn.state = state
    return fn


def run(fn, ft=None, **kw):
    ft = ft or FakeTime()
    return ft, mod.retry(fn, sleep=ft.sleep, clock=ft.clock, **kw)


def test_success_on_first_try_never_sleeps():
    fn = flaky(0, result=42)
    ft, out = run(fn)
    assert out == 42 and ft.sleeps == [] and fn.state["calls"] == 1


def test_example_schedule_is_capped_and_exhaustion_raises_retry_error():
    fn = flaky(99)
    ft = FakeTime()
    with pytest.raises(mod.RetryError) as info:
        mod.retry(fn, retries=4, base_delay=0.5, max_delay=3, multiplier=2, sleep=ft.sleep, clock=ft.clock)
    assert ft.sleeps == [0.5, 1.0, 2.0, 3.0]
    assert fn.state["calls"] == 5
    err = info.value
    assert err.attempts == 5
    assert isinstance(err.last_error, mod.TransientError) and str(err.last_error) == "boom 5"
    assert err.__cause__ is err.last_error


def test_succeeds_after_transient_failures():
    fn = flaky(2, result="done")
    ft, out = run(fn, retries=5, base_delay=1.0, multiplier=3.0, max_delay=100.0)
    assert out == "done" and ft.sleeps == [1.0, 3.0] and fn.state["calls"] == 3


def test_retries_zero_means_a_single_attempt():
    fn = flaky(1)
    ft = FakeTime()
    with pytest.raises(mod.RetryError) as info:
        mod.retry(fn, retries=0, sleep=ft.sleep, clock=ft.clock)
    assert fn.state["calls"] == 1 and ft.sleeps == [] and info.value.attempts == 1


def test_non_retryable_error_propagates_immediately_and_unchanged():
    ft = FakeTime()
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise mod.TransientError("t")
        raise KeyError("bug")

    with pytest.raises(KeyError):
        mod.retry(fn, retries=10, base_delay=1.0, sleep=ft.sleep, clock=ft.clock)
    assert len(calls) == 3 and ft.sleeps == [1.0, 2.0]


def test_custom_retry_on_and_subclasses():
    class Busy(OSError):
        pass

    fn = flaky(2, exc=Busy)
    ft, out = run(fn, retry_on=(OSError,), base_delay=0.25)
    assert out == "ok" and ft.sleeps == [0.25, 0.5]
    # TransientError is NOT retried once retry_on is overridden
    fn = flaky(1)
    with pytest.raises(mod.TransientError):
        run(fn, retry_on=(OSError,))


def test_max_delay_smaller_than_base_delay_caps_every_sleep():
    fn = flaky(99)
    ft = FakeTime()
    with pytest.raises(mod.RetryError):
        mod.retry(fn, retries=3, base_delay=5.0, max_delay=2.0, sleep=ft.sleep, clock=ft.clock)
    assert ft.sleeps == [2.0, 2.0, 2.0]


def test_very_large_retry_count_does_not_overflow():
    fn = flaky(2000)
    ft = FakeTime()
    out = mod.retry(fn, retries=2500, base_delay=1.0, max_delay=60.0, multiplier=2.0, sleep=ft.sleep, clock=ft.clock)
    assert out == "ok" and len(ft.sleeps) == 2000
    assert ft.sleeps[:8] == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0] and set(ft.sleeps[6:]) == {60.0}


def test_full_jitter_uses_the_capped_schedule_as_the_upper_bound():
    rng = ScriptedRng(0.25)
    fn = flaky(99)
    ft = FakeTime()
    with pytest.raises(mod.RetryError):
        mod.retry(fn, retries=4, base_delay=2.0, max_delay=5.0, jitter="full", rng=rng, sleep=ft.sleep, clock=ft.clock)
    assert rng.calls == [(0, 2.0), (0, 4.0), (0, 5.0), (0, 5.0)]
    assert ft.sleeps == [0.5, 1.0, 1.25, 1.25]


def test_equal_jitter_keeps_half_of_the_schedule():
    rng = ScriptedRng(1.0)
    fn = flaky(99)
    ft = FakeTime()
    with pytest.raises(mod.RetryError):
        mod.retry(fn, retries=3, base_delay=2.0, max_delay=5.0, jitter="equal", rng=rng, sleep=ft.sleep, clock=ft.clock)
    assert rng.calls == [(0, 1.0), (0, 2.0), (0, 2.5)]
    assert ft.sleeps == [2.0, 4.0, 5.0]
    rng0 = ScriptedRng(0.0)
    ft = FakeTime()
    with pytest.raises(mod.RetryError):
        mod.retry(flaky(99), retries=2, base_delay=2.0, jitter="equal", rng=rng0, sleep=ft.sleep, clock=ft.clock)
    assert ft.sleeps == [1.0, 2.0]


def test_no_random_draw_without_jitter_or_after_the_last_attempt():
    rng = ScriptedRng()
    ft = FakeTime()
    with pytest.raises(mod.RetryError):
        mod.retry(flaky(99), retries=2, rng=rng, sleep=ft.sleep, clock=ft.clock)
    assert rng.calls == []
    rng = ScriptedRng()
    with pytest.raises(mod.RetryError):
        mod.retry(flaky(99), retries=2, jitter="full", rng=rng, sleep=FakeTime().sleep, clock=ft.clock)
    assert len(rng.calls) == 2


def test_budget_stops_before_a_sleep_that_would_overrun_it():
    fn = flaky(99)
    ft = FakeTime(100.0)
    with pytest.raises(mod.RetryError) as info:
        mod.retry(fn, retries=10, base_delay=1.0, budget=5.0, sleep=ft.sleep, clock=ft.clock)
    # sleeps 1, 2 (t=103); the next sleep of 4 would end at 107 > 105
    assert ft.sleeps == [1.0, 2.0] and fn.state["calls"] == 3 and info.value.attempts == 3
    assert isinstance(info.value.last_error, mod.TransientError)


def test_budget_boundary_is_inclusive():
    fn = flaky(99)
    ft = FakeTime(0.0)
    with pytest.raises(mod.RetryError):
        mod.retry(fn, retries=10, base_delay=1.0, budget=7.0, sleep=ft.sleep, clock=ft.clock)
    assert ft.sleeps == [1.0, 2.0, 4.0]           # ends exactly at 7.0, the next (8.0) would not


def test_budget_accounts_for_time_spent_inside_fn():
    ft = FakeTime(0.0)
    calls = []

    def slow():
        calls.append(1)
        ft.now += 4.0                              # each attempt takes 4 s
        raise mod.TransientError("slow")

    with pytest.raises(mod.RetryError) as info:
        mod.retry(slow, retries=10, base_delay=1.0, budget=10.0, sleep=ft.sleep, clock=ft.clock)
    # t=4 -> sleep 1 (5) -> t=9 -> sleep 2 would end at 11 > 10
    assert ft.sleeps == [1.0] and len(calls) == 2 and info.value.attempts == 2


def test_budget_does_not_prevent_success():
    fn = flaky(2)
    ft, out = run(fn, base_delay=1.0, budget=3.0)
    assert out == "ok" and ft.sleeps == [1.0, 2.0]


def test_on_retry_observes_each_sleep():
    seen = []
    fn = flaky(2)
    run(fn, base_delay=1.0, on_retry=lambda n, exc, d: seen.append((n, str(exc), d)))
    assert seen == [(1, "boom 1", 1.0), (2, "boom 2", 2.0)]


@pytest.mark.parametrize("kw", [
    {"retries": -1}, {"base_delay": -0.1}, {"max_delay": -1}, {"multiplier": 0.5},
    {"budget": -1}, {"jitter": "wild"},
])
def test_invalid_parameters_raise_before_calling_fn(kw):
    fn = flaky(0)
    with pytest.raises(ValueError):
        mod.retry(fn, sleep=lambda s: None, **kw)
    assert fn.state["calls"] == 0
