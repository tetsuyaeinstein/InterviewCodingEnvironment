"""Tests for PY-035 (imports your practice file by default; see _loader.py)."""
import random
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-035")

UTC = timezone.utc
MIN = timedelta(minutes=1)
D = Decimal


def at(h, m, s=0, us=0, day=1, tz=UTC):
    return datetime(2025, 6, day, h, m, s, us, tzinfo=tz)


def ev(t, key="m", value=1):
    return mod.Event(t, key, D(value))


def win(start, key, count, total, size=5 * MIN):
    return mod.WindowResult(start, start + size, key, count, D(total))


def feed(tw, events):
    return [tw.process(e) for e in events]


def test_example_from_question():
    tw = mod.TumblingWindows(2 * MIN)
    events = [ev(at(12, 0, 30)), ev(at(12, 4, 59)), ev(at(12, 3)), ev(at(12, 6)), ev(at(12, 7)),
              ev(at(12, 4, 10)), ev(at(12, 5))]
    out = feed(tw, events)
    assert out[:4] == [[], [], [], []]
    assert out[4] == [win(at(12, 0), "m", 3, 3)]
    assert out[5] == [] and out[6] == []
    assert tw.late_events == [events[5]]
    assert tw.watermark == at(12, 5)
    assert tw.flush() == [win(at(12, 5), "m", 3, 3)]


def test_watermark_is_max_minus_lateness_and_never_moves_backwards():
    tw = mod.TumblingWindows(3 * MIN)
    assert tw.watermark is None
    tw.process(ev(at(12, 10)))
    assert tw.watermark == at(12, 7)
    tw.process(ev(at(12, 8)))                       # older event
    assert tw.watermark == at(12, 7)
    tw.process(ev(at(12, 20)))
    assert tw.watermark == at(12, 17)


def test_window_closes_exactly_when_watermark_reaches_its_end():
    tw = mod.TumblingWindows(MIN)
    tw.process(ev(at(12, 1)))
    assert tw.process(ev(at(12, 5, 59, 999999))) == []         # watermark 12:04:59.999999 < 12:05
    assert tw.process(ev(at(12, 6))) == [win(at(12, 0), "m", 1, 1)]   # watermark == 12:05:00


def test_boundary_event_belongs_to_the_next_window():
    tw = mod.TumblingWindows(timedelta(0))
    tw.process(ev(at(12, 4, 59, 999999), value=1))
    tw.process(ev(at(12, 5), value=10))
    out = tw.flush()
    assert out == [win(at(12, 5), "m", 1, 10)]


def test_zero_lateness_closes_immediately_and_older_event_is_late():
    tw = mod.TumblingWindows(timedelta(0))
    assert tw.process(ev(at(12, 1))) == []
    assert tw.process(ev(at(12, 5))) == [win(at(12, 0), "m", 1, 1)]
    late = ev(at(12, 4, 59))
    assert tw.process(late) == [] and tw.late_events == [late]
    assert tw.process(ev(at(12, 6))) == []                    # window [12:05,12:10) still open


def test_out_of_order_within_allowance_is_aggregated_not_late():
    tw = mod.TumblingWindows(10 * MIN)
    tw.process(ev(at(12, 30)))
    tw.process(ev(at(12, 21)))                       # 9 min behind, window [12:20,12:25) open
    tw.process(ev(at(12, 24, 59)))
    assert tw.late_events == []
    assert tw.process(ev(at(12, 36))) == [win(at(12, 20), "m", 2, 2)]


def test_late_event_is_kept_aside_and_does_not_touch_state():
    tw = mod.TumblingWindows(MIN)
    tw.process(ev(at(12, 1)))
    tw.process(ev(at(12, 7)))                        # closes [12:00,12:05)
    wm = tw.watermark
    late = ev(at(12, 2), key="x", value=99)
    assert tw.process(late) == []
    assert tw.watermark == wm and tw.late_events == [late]
    assert tw.flush() == [win(at(12, 5), "m", 1, 1)]         # nothing about "x", no reopened window
    copy = tw.late_events
    copy.clear()
    assert tw.late_events == [late]                  # defensive copy


def test_keys_are_aggregated_independently_and_emitted_in_order():
    tw = mod.TumblingWindows(timedelta(0))
    feed(tw, [ev(at(12, 6), "b", "2.50"), ev(at(12, 1), "z", 1), ev(at(12, 2), "a", 4), ev(at(12, 3), "z", 2)])
    out = tw.process(ev(at(12, 10), "a", 7))
    # 12:06 arrived first, so [12:00,12:05) events were already late at arrival except... check explicitly
    assert [r.window_start for r in out] == sorted(r.window_start for r in out)
    assert out == [win(at(12, 5), "b", 1, "2.50")]
    assert [e.key for e in tw.late_events] == ["z", "a", "z"]


def test_results_for_several_windows_closing_together_are_sorted_by_start_then_key():
    tw = mod.TumblingWindows(20 * MIN)
    feed(tw, [ev(at(12, 11), "b"), ev(at(12, 2), "b"), ev(at(12, 7), "a"), ev(at(12, 3), "a"), ev(at(12, 4), "c")])
    out = tw.process(ev(at(12, 40)))
    assert [(r.window_start, r.key) for r in out] == [
        (at(12, 0), "a"), (at(12, 0), "b"), (at(12, 0), "c"), (at(12, 5), "a"), (at(12, 10), "b")]


def test_flush_orders_results_and_closes_those_windows_for_good():
    tw = mod.TumblingWindows(30 * MIN)
    feed(tw, [ev(at(12, 7), "b"), ev(at(12, 1), "a"), ev(at(12, 6), "a"), ev(at(12, 2), "b")])
    out = tw.flush()
    assert [(r.window_start, r.key, r.count) for r in out] == [
        (at(12, 0), "a", 1), (at(12, 0), "b", 1), (at(12, 5), "a", 1), (at(12, 5), "b", 1)]
    assert tw.flush() == []
    straggler = ev(at(12, 3))
    assert tw.process(straggler) == [] and tw.late_events == [straggler]
    assert tw.process(ev(at(12, 10))) == []          # a new window can still open


def test_windows_are_aligned_in_utc_regardless_of_the_input_offset():
    plus9 = timezone(timedelta(hours=9))
    minus530 = timezone(-timedelta(hours=5, minutes=30))
    tw = mod.TumblingWindows(timedelta(0))
    out = []
    out += tw.process(ev(datetime(2025, 6, 1, 21, 3, tzinfo=plus9), value=1))        # 12:03Z
    out += tw.process(ev(datetime(2025, 6, 1, 6, 33, tzinfo=minus530), value=2))     # 12:03Z
    out += tw.process(ev(datetime(2025, 6, 1, 21, 5, tzinfo=plus9), value=4))        # 12:05Z
    out += tw.flush()
    assert out == [win(at(12, 0), "m", 2, 3), win(at(12, 5), "m", 1, 4)]
    assert all(r.window_start.utcoffset() == timedelta(0) for r in out)
    assert tw.watermark == at(12, 5) and tw.watermark.utcoffset() == timedelta(0)


def test_one_hour_windows_with_a_half_hour_offset_align_to_utc():
    ist = timezone(timedelta(hours=5, minutes=30))
    tw = mod.TumblingWindows(timedelta(0), window=timedelta(hours=1))
    tw.process(ev(datetime(2025, 6, 1, 17, 45, tzinfo=ist)))                  # 12:15Z
    out = tw.flush()
    assert out == [mod.WindowResult(at(12, 0), at(13, 0), "m", 1, D(1))]


def test_pre_epoch_events_are_assigned_correctly():
    tw = mod.TumblingWindows(timedelta(0))
    tw.process(ev(datetime(1969, 12, 31, 23, 59, 59, tzinfo=UTC)))
    out = tw.flush()
    assert out == [mod.WindowResult(datetime(1969, 12, 31, 23, 55, tzinfo=UTC), datetime(1970, 1, 1, tzinfo=UTC), "m", 1, D(1))]


def test_decimal_totals_are_exact():
    tw = mod.TumblingWindows(timedelta(0))
    for _ in range(3):
        tw.process(ev(at(12, 1), value="0.10"))
    (r,) = tw.flush()
    assert r.total == D("0.30") and r.count == 3


@pytest.mark.parametrize("make", [
    lambda: mod.TumblingWindows(-MIN),
    lambda: mod.TumblingWindows(MIN, window=timedelta(0)),
    lambda: mod.TumblingWindows(MIN, window=-MIN),
])
def test_invalid_configuration(make):
    with pytest.raises(ValueError):
        make()


@pytest.mark.parametrize("bad", [
    mod.Event(datetime(2025, 6, 1, 12, 0), "m", D(1)),      # naive
    mod.Event(at(12, 0), "m", 1),                           # int, not Decimal
    mod.Event(at(12, 0), "m", D("NaN")),
])
def test_invalid_events(bad):
    with pytest.raises(ValueError):
        mod.TumblingWindows(MIN).process(bad)


def reference(events, lateness, size=5 * MIN):
    """Brute-force model: returns (list of per-call emissions, final flush, late events)."""
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    aggs, emitted_starts, calls, late = {}, set(), [], []
    mx = None
    for e in events:
        t = e.event_time.astimezone(UTC)
        mx = t if mx is None or t > mx else mx
        wm = mx - lateness
        start = epoch + ((t - epoch) // size) * size
        closed_before = {s for s in emitted_starts}
        if start + size <= wm or start in closed_before:
            late.append(e)
            calls.append([])
            continue
        a = aggs.setdefault((start, e.key), [0, D(0)])
        a[0] += 1
        a[1] += e.value
        ready = sorted(k for k in aggs if k[0] + size <= wm and k[0] not in emitted_starts)
        calls.append([mod.WindowResult(s, s + size, k, aggs[(s, k)][0], aggs[(s, k)][1]) for s, k in ready])
        emitted_starts |= {s for s, _ in ready}
    rest = sorted(k for k in aggs if k[0] not in emitted_starts)
    final = [mod.WindowResult(s, s + size, k, aggs[(s, k)][0], aggs[(s, k)][1]) for s, k in rest]
    return calls, final, late


def test_random_streams_match_a_brute_force_model():
    rng = random.Random(35)
    base = at(12, 0)
    zones = [UTC, timezone(timedelta(hours=9)), timezone(-timedelta(hours=7))]
    for _ in range(200):
        lateness = rng.choice([timedelta(0), MIN, 3 * MIN, 12 * MIN])
        events = [ev((base + timedelta(seconds=rng.randint(0, 3000))).astimezone(rng.choice(zones)),
                     rng.choice("abc"), rng.randint(1, 9)) for _ in range(rng.randint(0, 40))]
        calls, final, late = reference(events, lateness)
        tw = mod.TumblingWindows(lateness)
        assert [tw.process(e) for e in events] == calls
        assert tw.flush() == final
        assert tw.late_events == late
        # conservation: every event is aggregated exactly once or reported late
        counted = sum(r.count for c in calls for r in c) + sum(r.count for r in final)
        assert counted + len(late) == len(events)


def test_large_stream_with_bounded_disorder_is_fast():
    rng = random.Random(7)
    base = at(0, 0)
    n = 100_000
    tw = mod.TumblingWindows(2 * MIN)
    t0 = time.perf_counter()
    closed = 0
    for i in range(n):
        t = base + timedelta(seconds=i // 5 - rng.randint(0, 60))
        closed += sum(r.count for r in tw.process(ev(t, f"k{i % 20}")))
    closed += sum(r.count for r in tw.flush())
    elapsed = time.perf_counter() - t0
    assert closed + len(tw.late_events) == n
    assert elapsed < 4.0, f"took {elapsed:.2f}s"
