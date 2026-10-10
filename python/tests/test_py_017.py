"""Tests for PY-017 (imports your practice file by default; see _loader.py)."""
import itertools
import random
import time

import pytest

from _loader import load

mod = load("PY-017")


class Tracked:
    """Iterator over `items` that records how many items were read and rejects misuse."""

    def __init__(self, items, limit=None, poison_after=None):
        self._it = iter(items)
        self.read = 0
        self.done = False
        self._limit = limit                  # raise AssertionError if more than `limit` items are read
        self._poison_after = poison_after    # raise RuntimeError instead of ending after this many items

    def __iter__(self):
        return self

    def __next__(self):
        assert not self.done, "read from a stream that already finished"
        if self._limit is not None:
            assert self.read < self._limit, f"over-consumed: more than {self._limit} items read"
        try:
            item = next(self._it)
        except StopIteration:
            if self._poison_after is not None and self.read >= self._poison_after:
                raise RuntimeError("stream was read past the point the test allows")
            self.done = True
            raise
        self.read += 1
        return item


def merged_list(streams, **kw):
    return list(mod.merge_sorted_streams(streams, **kw))


def test_example_from_question():
    assert merged_list([[1, 4, 9], [2, 4, 10], []]) == [1, 2, 4, 4, 9, 10]


def test_ties_are_ordered_by_stream_position():
    a = [(1, "A"), (5, "A")]
    b = [(1, "B"), (5, "B")]
    c = [(1, "C"), (1, "C2"), (5, "C")]
    assert merged_list([a, b, c], key=lambda r: r[0]) == [
        (1, "A"), (1, "B"), (1, "C"), (1, "C2"), (5, "A"), (5, "B"), (5, "C")]
    assert merged_list([c, b, a], key=lambda r: r[0])[:3] == [(1, "C"), (1, "C2"), (1, "B")]


def test_raw_items_are_never_compared_when_a_key_is_given():
    class NoCompare:
        def __init__(self, tag):
            self.tag = tag

        def __lt__(self, other):
            raise AssertionError("raw items must not be compared")

        __le__ = __gt__ = __ge__ = __lt__

    a = [NoCompare("a1"), NoCompare("a2")]
    b = [NoCompare("b1"), NoCompare("b2")]
    out = merged_list([[(0, a[0]), (7, a[1])], [(0, b[0]), (7, b[1])]], key=lambda p: p[0])
    assert [p[1].tag for p in out] == ["a1", "b1", "a2", "b2"]
    # same, with dicts as items (not orderable at all)
    d1 = [{"ts": 1}, {"ts": 3}]
    d2 = [{"ts": 1}, {"ts": 2}]
    out = merged_list([d1, d2], key=lambda d: d["ts"])
    assert out == [{"ts": 1}, {"ts": 1}, {"ts": 2}, {"ts": 3}]
    assert out[0] is d1[0] and out[1] is d2[0]


@pytest.mark.parametrize("streams", [[], [[]], [[], [], []], [iter(())]])
def test_no_streams_or_only_empty_streams(streams):
    assert merged_list(streams) == []


def test_single_stream_and_empty_streams_around_data():
    assert merged_list([[3, 5, 8]]) == [3, 5, 8]
    assert merged_list([[], [1, 2], [], [], [0, 3], []]) == [0, 1, 2, 3]


def test_streams_can_be_generators_and_the_outer_iterable_can_be_a_generator():
    outer = ((x for x in range(s, 30, 3)) for s in range(3))
    assert merged_list(outer) == list(range(30))


def test_key_function_and_descending_streams():
    a = [9, 7, 2]
    b = [8, 8, 1]
    assert merged_list([a, b], key=lambda x: -x) == [9, 8, 8, 7, 2, 1]
    words = [["bb", "cc", "dddd"], ["a", "eee"]]
    assert merged_list(words, key=len) == ["a", "bb", "cc", "eee", "dddd"]


def test_key_is_called_once_per_item():
    calls = []

    def key(x):
        calls.append(x)
        return x

    streams = [[1, 3, 5], [2, 4], [], [0, 6]]
    out = merged_list(streams, key=key)
    assert out == [0, 1, 2, 3, 4, 5, 6]
    assert len(calls) == 7


def test_creating_the_merge_reads_nothing():
    streams = [Tracked([1, 2]), Tracked([3])]
    result = mod.merge_sorted_streams(streams)
    assert all(s.read == 0 for s in streams)
    assert next(iter(result)) == 1
    assert [s.read for s in streams] == [1, 1] or [s.read for s in streams] == [2, 1]


def test_each_stream_is_read_at_most_one_item_ahead():
    rng = random.Random(17)
    data = [sorted(rng.randint(0, 40) for _ in range(rng.randint(0, 12))) for _ in range(6)]
    streams = [Tracked([(v, i) for v in vals]) for i, vals in enumerate(data)]
    yielded = [0] * len(streams)
    for v, i in mod.merge_sorted_streams(streams, key=lambda p: p[0]):
        yielded[i] += 1
        for s, y in zip(streams, yielded):
            assert s.read <= y + 1, f"stream read {s.read} items with only {y} yielded"


def test_never_reads_past_the_point_the_consumer_reached():
    # stream 0 would blow up if read beyond its 3rd item; we only take two outputs
    boom = Tracked([1, 2, 3], poison_after=3)
    other = Tracked([10, 20])
    it = mod.merge_sorted_streams([boom, other])
    assert [next(it), next(it)] == [1, 2]


def test_exhausted_streams_are_not_polled_again():
    streams = [Tracked([1, 2]), Tracked([5]), Tracked([])]
    assert merged_list(streams) == [1, 2, 5]


def test_infinite_streams():
    evens = Tracked(itertools.count(0, 2), limit=10_000)
    odds = Tracked(itertools.count(1, 2), limit=10_000)
    sq = Tracked((i * i for i in itertools.count()), limit=10_000)
    first = list(itertools.islice(mod.merge_sorted_streams([evens, odds, sq]), 12))
    assert first == [0, 0, 1, 1, 2, 3, 4, 4, 5, 6, 7, 8]
    assert evens.read <= 12 and odds.read <= 12 and sq.read <= 12


def test_result_is_an_iterator():
    result = mod.merge_sorted_streams([[1, 2], [3]])
    assert iter(result) is result
    assert next(result) == 1


def test_inputs_are_not_mutated():
    a, b = [1, 3], [2, 4]
    merged_list([a, b])
    assert a == [1, 3] and b == [2, 4]


def test_matches_stable_sort_on_random_inputs():
    rng = random.Random(170)
    for _ in range(300):
        k = rng.randint(0, 7)
        streams = []
        for s in range(k):
            keys = sorted(rng.randint(0, 6) for _ in range(rng.randint(0, 8)))
            streams.append([(kv, s, pos) for pos, kv in enumerate(keys)])
        expected = sorted((rec for st in streams for rec in st), key=lambda r: r[0])   # stable sort oracle
        assert merged_list([iter(st) for st in streams], key=lambda r: r[0]) == expected, streams


def test_many_streams_scale_as_n_log_k():
    rng = random.Random(3)
    k, per = 1000, 200
    streams = [sorted(rng.randrange(10**6) for _ in range(per)) for _ in range(k)]
    t0 = time.perf_counter()
    out = list(mod.merge_sorted_streams(iter(s) for s in streams))
    elapsed = time.perf_counter() - t0
    assert len(out) == k * per
    assert out == sorted(x for s in streams for x in s)
    assert elapsed < 2.0, f"took {elapsed:.2f}s - expected O(N log K)"
