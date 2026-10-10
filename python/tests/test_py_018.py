"""Tests for PY-018 (imports your practice file by default; see _loader.py)."""
import random
import time

import pytest

from _loader import load

mod = load("PY-018")

MISSING = object()


class Model:
    """Reference model: a plain list of [key, value], least recently used first. O(n) per operation."""

    def __init__(self, capacity):
        self.capacity = capacity
        self.items = []
        self.evicted = []

    def _find(self, key):
        for i, (k, _) in enumerate(self.items):
            if k == key:
                return i
        return None

    def get(self, key, default=None):
        i = self._find(key)
        if i is None:
            return default
        entry = self.items.pop(i)
        self.items.append(entry)
        return entry[1]

    def put(self, key, value):
        i = self._find(key)
        if i is not None:
            self.items.pop(i)
            self.items.append([key, value])
            return
        self.items.append([key, value])
        if len(self.items) > self.capacity:
            self.evicted.append(tuple(self.items.pop(0)))

    def contains(self, key):
        return self._find(key) is not None


def keys_in_eviction_order(cache, universe):
    """Observe which keys are present without touching recency (uses `in` only)."""
    return [k for k in universe if k in cache]


def test_example_from_question():
    c = mod.LRUCache(2)
    c.put("A", 1)
    c.put("B", 2)
    assert c.get("A") == 1
    c.put("C", 3)
    assert "B" not in c and "A" in c and "C" in c
    c.put("D", 4)
    assert "A" not in c            # `in` above did not refresh A
    assert "C" in c and "D" in c
    assert len(c) == 2


@pytest.mark.parametrize("capacity", [0, -1, -100])
def test_capacity_below_one_raises_value_error(capacity):
    with pytest.raises(ValueError):
        mod.LRUCache(capacity)


@pytest.mark.parametrize("capacity", [True, 2.0, "3", None, 2.5])
def test_non_int_capacity_raises_type_error(capacity):
    with pytest.raises(TypeError):
        mod.LRUCache(capacity)


def test_capacity_one():
    c = mod.LRUCache(1)
    c.put("a", 1)
    c.put("b", 2)
    assert "a" not in c and c.get("b") == 2 and len(c) == 1
    c.put("b", 3)
    assert c.get("b") == 3 and len(c) == 1


def test_get_refreshes_recency():
    c = mod.LRUCache(3)
    for k in "abc":
        c.put(k, k.upper())
    assert c.get("a") == "A"        # order now b, c, a
    c.put("d", "D")                 # evicts b
    assert keys_in_eviction_order(c, "abcd") == ["a", "c", "d"]
    c.put("e", "E")                 # evicts c
    assert keys_in_eviction_order(c, "abcde") == ["a", "d", "e"]


def test_put_on_existing_key_updates_and_refreshes_without_evicting():
    evicted = []
    c = mod.LRUCache(2, on_evict=lambda k, v: evicted.append((k, v)))
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)                  # full cache, existing key: no eviction; a is now newest
    assert evicted == [] and len(c) == 2
    assert c.get("a") == 10
    c.put("c", 3)                   # evicts b (a was refreshed)
    assert evicted == [("b", 2)]
    assert "a" in c and "b" not in c


def test_contains_does_not_change_recency():
    c = mod.LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    for _ in range(3):
        assert "a" in c
    assert "zzz" not in c
    c.put("c", 3)                   # a is still the oldest
    assert "a" not in c and "b" in c and "c" in c


def test_missing_key_returns_default_and_never_inserts():
    c = mod.LRUCache(2)
    assert c.get("x") is None
    assert c.get("x", 42) == 42
    assert len(c) == 0 and "x" not in c
    c.put("a", 1)
    c.put("b", 2)
    c.get("x")                      # a miss must not disturb the order
    c.put("c", 3)
    assert "a" not in c


def test_stored_none_is_a_real_hit():
    c = mod.LRUCache(2)
    c.put("a", None)
    c.put("b", 2)
    assert c.get("a", "fallback") is None      # hit: returns the stored None, not the default
    c.put("c", 3)                               # the get refreshed a, so b is evicted
    assert "a" in c and "b" not in c


def test_eviction_callback_receives_key_and_value_once_per_eviction():
    evicted = []
    c = mod.LRUCache(2, on_evict=lambda k, v: evicted.append((k, v)))
    for i in range(5):
        c.put(i, f"v{i}")
    assert evicted == [(0, "v0"), (1, "v1"), (2, "v2")]
    assert len(c) == 2


def test_callback_sees_the_entry_already_removed():
    seen = []
    holder = {}

    def cb(key, value):
        seen.append((key, key in holder["cache"], len(holder["cache"])))

    c = mod.LRUCache(1, on_evict=cb)
    holder["cache"] = c
    c.put("a", 1)
    c.put("b", 2)
    assert seen == [("a", False, 1)]


def test_keys_can_be_any_hashable_and_values_any_object():
    c = mod.LRUCache(3)
    c.put((1, "x"), [1, 2])
    c.put(None, {"k": "v"})
    c.put(3.5, None)
    assert c.get((1, "x")) == [1, 2] and c.get(None) == {"k": "v"} and 3.5 in c


def test_matches_reference_model_on_random_operations():
    rng = random.Random(18)
    universe = list(range(8))
    for capacity in (1, 2, 3, 5):
        evicted = []
        cache = mod.LRUCache(capacity, on_evict=lambda k, v: evicted.append((k, v)))
        model = Model(capacity)
        for step in range(1500):
            op = rng.random()
            key = rng.choice(universe)
            if op < 0.45:
                value = rng.randint(0, 99) if rng.random() < 0.9 else None
                cache.put(key, value)
                model.put(key, value)
            elif op < 0.8:
                got = cache.get(key, MISSING)
                want = model.get(key, MISSING)
                assert got is want or got == want, (capacity, step, key)
            else:
                assert (key in cache) == model.contains(key)
            assert len(cache) == len(model.items) <= capacity, (capacity, step)
            assert evicted == model.evicted, (capacity, step)
    # final state check, read through `in` only
    assert keys_in_eviction_order(cache, universe) == sorted(k for k, _ in model.items)


def test_constant_time_operations_on_a_large_cache():
    rng = random.Random(7)
    capacity = 50_000
    cache = mod.LRUCache(capacity)
    t0 = time.perf_counter()
    for step in range(200_000):
        key = rng.randrange(100_000)
        if rng.random() < 0.5:
            cache.put(key, key)
        else:
            cache.get(key)
        _ = key in cache
        if step % 2_000 == 0:      # fail fast instead of grinding through a quadratic run
            assert time.perf_counter() - t0 < 2.0, f"too slow after {step} operations; expected O(1) each"
    elapsed = time.perf_counter() - t0
    assert len(cache) <= capacity
    assert elapsed < 2.0, f"took {elapsed:.2f}s - operations must be O(1) on average"
