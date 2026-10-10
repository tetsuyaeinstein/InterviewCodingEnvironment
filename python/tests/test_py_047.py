"""Tests for PY-047 (pure Python; time is injected, nothing really sleeps)."""
import pytest

from _loader import load

mod = load("PY-047")


class FakeTime:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def scripted(t, outcomes, call_duration=0.0):
    """call() that plays back outcomes: exceptions are raised, other values returned."""
    it = iter(outcomes)
    calls = []

    def call():
        calls.append(t.now)
        t.now += call_duration
        out = next(it)
        if isinstance(out, BaseException):
            raise out
        return out

    call.calls = calls
    return call


def run(t, outcomes, **kw):
    call = scripted(t, outcomes, kw.pop("call_duration", 0.0))
    return mod.call_with_rate_limit(call, sleep=t.sleep, clock=t.clock, **kw), call


def test_success_on_first_attempt_never_sleeps():
    t = FakeTime()
    result, call = run(t, ["ok"])
    assert result == "ok" and t.sleeps == [] and len(call.calls) == 1


def test_retry_after_is_honoured_exactly_in_order():
    t = FakeTime()
    result, call = run(t, [mod.RateLimited(2), mod.RateLimited(0.5), mod.RateLimited(7), "done"])
    assert result == "done"
    assert t.sleeps == [2, 0.5, 7]
    assert len(call.calls) == 4


def test_missing_retry_after_uses_exponential_backoff():
    t = FakeTime()
    run(t, [mod.RateLimited(), mod.RateLimited(None), mod.RateLimited(), "ok"], default_backoff=1.0)
    assert t.sleeps == [1.0, 2.0, 4.0]
    t2 = FakeTime()
    run(t2, [mod.RateLimited(), mod.RateLimited(), "ok"], default_backoff=0.25)
    assert t2.sleeps == [0.25, 0.5]


def test_mixed_header_and_backoff_attempt_numbers():
    t = FakeTime()
    run(t, [mod.RateLimited(3), mod.RateLimited(), "ok"], default_backoff=1.0)
    assert t.sleeps == [3, 2.0]          # backoff index follows the attempt number


def test_zero_and_negative_retry_after_do_not_sleep():
    t = FakeTime()
    result, call = run(t, [mod.RateLimited(0), mod.RateLimited(-5), mod.RateLimited(0.0), "ok"])
    assert result == "ok" and t.sleeps == [] and len(call.calls) == 4


def test_attempt_limit_reraises_the_last_error_without_a_final_sleep():
    t = FakeTime()
    errors = [mod.RateLimited(1), mod.RateLimited(2), mod.RateLimited(3), "never"]
    with pytest.raises(mod.RateLimited) as info:
        run(t, errors, max_attempts=3)
    assert info.value is errors[2]
    assert t.sleeps == [1, 2]


def test_single_attempt_means_no_retry():
    t = FakeTime()
    with pytest.raises(mod.RateLimited):
        run(t, [mod.RateLimited(1)], max_attempts=1)
    assert t.sleeps == []


def test_total_wait_budget_is_a_hard_cap():
    t = FakeTime()
    errs = [mod.RateLimited(30), mod.RateLimited(30), mod.RateLimited(30), "ok"]
    with pytest.raises(mod.RateLimited):
        run(t, errs, max_total_wait=60)
    assert t.sleeps == [30, 30]          # reaching exactly 60 is allowed; a third wait is not


def test_server_asking_for_more_than_the_budget_fails_fast():
    t = FakeTime()
    with pytest.raises(mod.RateLimited):
        run(t, [mod.RateLimited(3600), "ok"], max_total_wait=60)
    assert t.sleeps == []


def test_time_spent_inside_the_call_counts_towards_the_budget():
    t = FakeTime()
    errs = [mod.RateLimited(5), mod.RateLimited(5), "ok"]
    # each call takes 10s: after attempt 1 elapsed=10, +5 = 15 <= 22 ok; after attempt 2 elapsed=25 > 22
    with pytest.raises(mod.RateLimited):
        run(t, errs, call_duration=10, max_total_wait=22)
    assert t.sleeps == [5]


def test_other_errors_propagate_immediately():
    t = FakeTime()
    with pytest.raises(ValueError, match="bad request"):
        run(t, [mod.RateLimited(1), ValueError("bad request"), "ok"])
    assert t.sleeps == [1]
    t2 = FakeTime()
    with pytest.raises(ConnectionError):
        run(t2, [ConnectionError("reset")])
    assert t2.sleeps == []


def test_return_value_is_passed_through_even_if_falsy():
    t = FakeTime()
    result, _ = run(t, [mod.RateLimited(1), None])
    assert result is None
    result, _ = run(FakeTime(), [0])
    assert result == 0


def test_invalid_max_attempts():
    with pytest.raises(ValueError):
        mod.call_with_rate_limit(lambda: 1, sleep=lambda s: None, clock=lambda: 0.0, max_attempts=0)


# ---------------------------------------------------------------- RateLimiter

def limiter(t, n=2, period=10):
    return mod.RateLimiter(n, period, clock=t.clock, sleep=t.sleep)


def test_limiter_admits_burst_then_waits_for_the_window():
    t = FakeTime()
    lim = limiter(t)
    assert lim.acquire() == 0.0
    t.now += 1
    assert lim.acquire() == 0.0
    assert t.sleeps == []
    assert lim.acquire() == pytest.approx(9.0)       # until the first admission leaves the window
    assert t.sleeps == [pytest.approx(9.0)]


def test_limiter_window_boundary_is_exact():
    t = FakeTime()
    lim = limiter(t)
    lim.acquire()
    lim.acquire()
    t.now += 10                                      # exactly one period later: both have left
    assert lim.acquire() == 0.0 and lim.acquire() == 0.0
    assert t.sleeps == []


def test_limiter_spreads_a_long_run_evenly():
    t = FakeTime()
    lim = limiter(t, n=3, period=6)
    times = []
    for _ in range(9):
        lim.acquire()
        times.append(t.now - 1000.0)
    assert times == [0, 0, 0, 6, 6, 6, 12, 12, 12]
    for a, b in zip(times, times[3:]):
        assert b - a >= 6


def test_limiter_rechecks_after_an_early_wakeup():
    t = FakeTime()
    calls = {"n": 0}

    def sleepy(seconds):                              # the first sleep returns after half the time
        calls["n"] += 1
        t.now += seconds / 2 if calls["n"] == 1 else seconds

    lim = mod.RateLimiter(1, 8, clock=t.clock, sleep=sleepy)
    lim.acquire()
    waited = lim.acquire()
    assert t.now - 1000.0 >= 8 and calls["n"] == 2
    assert waited == pytest.approx(12.0)              # 8 requested, then the remaining 4


def test_limiter_validation():
    t = FakeTime()
    with pytest.raises(ValueError):
        mod.RateLimiter(0, 1, clock=t.clock, sleep=t.sleep)
    with pytest.raises(ValueError):
        mod.RateLimiter(1, 0, clock=t.clock, sleep=t.sleep)
