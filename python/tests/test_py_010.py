"""Tests for PY-010 (imports your practice file by default; see _loader.py)."""
import itertools
import random

import pytest

from _loader import load

mod = load("PY-010")


class CountingSource:
    """Iterator that records how many items were pulled and fails after `fail_after` items."""

    def __init__(self, n=None, fail_after=None):
        self.n, self.fail_after, self.pulled = n, fail_after, 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.fail_after is not None and self.pulled >= self.fail_after:
            raise RuntimeError(f"source failed after {self.fail_after} items")
        if self.n is not None and self.pulled >= self.n:
            raise StopIteration
        self.pulled += 1
        return self.pulled - 1


@pytest.mark.parametrize("data, size, expected", [
    ([1, 2, 3, 4, 5], 2, [[1, 2], [3, 4], [5]]),
    (range(6), 3, [[0, 1, 2], [3, 4, 5]]),
    ([], 10, []),
    ("abcd", 3, [["a", "b", "c"], ["d"]]),
    ([1, 2], 5, [[1, 2]]),
    ([7], 1, [[7]]),
])
def test_examples(data, size, expected):
    assert list(mod.chunked(data, size)) == expected


def test_returns_an_iterator_of_lists():
    result = mod.chunked((x for x in range(3)), 2)
    assert iter(result) is result
    assert next(result) == [0, 1]
    assert type(next(result)) is list
    with pytest.raises(StopIteration):
        next(result)


def test_infinite_source():
    chunks = mod.chunked(itertools.count(), 4)
    assert [next(chunks) for _ in range(3)] == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]]


def test_no_read_ahead():
    src = CountingSource()
    chunks = mod.chunked(src, 3)
    assert src.pulled == 0, "nothing may be consumed before the first chunk is requested"
    assert next(chunks) == [0, 1, 2]
    assert src.pulled == 3, "producing a chunk must consume exactly that chunk's items"
    assert next(chunks) == [3, 4, 5]
    assert src.pulled == 6


def test_source_failure_surfaces_only_with_the_affected_chunk():
    src = CountingSource(fail_after=5)
    chunks = mod.chunked(src, 2)
    assert next(chunks) == [0, 1]
    assert next(chunks) == [2, 3]
    with pytest.raises(RuntimeError):
        next(chunks)


def test_exact_multiple_has_no_empty_trailing_chunk():
    src = CountingSource(n=6)
    assert list(mod.chunked(src, 3)) == [[0, 1, 2], [3, 4, 5]]


def test_each_chunk_is_a_new_list():
    chunks = list(mod.chunked(range(6), 2))
    chunks[0].append("x")
    assert chunks == [[0, 1, "x"], [2, 3], [4, 5]]
    assert len({id(c) for c in chunks}) == 3


@pytest.mark.parametrize("size", [0, -1])
def test_non_positive_size_raises_at_call_time(size):
    with pytest.raises(ValueError):
        mod.chunked([1, 2, 3], size)          # note: not iterated


@pytest.mark.parametrize("size", [True, 2.0, "3", None])
def test_non_int_size_raises_type_error_at_call_time(size):
    with pytest.raises(TypeError):
        mod.chunked([1, 2, 3], size)


def test_non_iterable_raises_type_error_at_call_time():
    with pytest.raises(TypeError):
        mod.chunked(42, 2)


def test_list_source_is_consumed_once_and_order_kept():
    rng = random.Random(10)
    for _ in range(200):
        data = [rng.randint(0, 9) for _ in range(rng.randint(0, 30))]
        size = rng.randint(1, 8)
        chunks = list(mod.chunked(data, size))
        assert [x for c in chunks for x in c] == data
        assert all(len(c) == size for c in chunks[:-1])
        assert all(1 <= len(c) <= size for c in chunks)
        assert len(chunks) == -(-len(data) // size)
