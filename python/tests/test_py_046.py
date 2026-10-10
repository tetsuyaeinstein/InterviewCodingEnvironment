"""Tests for PY-046 (pure Python, fake client)."""
import pytest

from _loader import load

mod = load("PY-046")


class FakeClient:
    """pages: {token: {"items": [...], "next": token|None}} - the first page is keyed by None."""

    def __init__(self, pages, error_at="<never>"):
        self.pages, self.calls, self.error_at = pages, [], error_at

    def get_page(self, token, page_size=None):
        self.calls.append((token, page_size))
        if len(self.calls) > 1000:
            raise AssertionError("runaway pagination: too many requests")
        if token == self.error_at:
            raise ConnectionError("boom")
        return self.pages[token]


def rec(i, **kw):
    return {"id": i, **kw}


def page(ids, nxt):
    return {"items": [rec(i) for i in ids], "next": nxt}


def ids(it):
    return [r["id"] for r in it]


def test_walks_all_pages_in_order():
    c = FakeClient({None: page([1, 2], "a"), "a": page([3, 4], "b"), "b": page([5], None)})
    assert ids(mod.iterate_pages(c)) == [1, 2, 3, 4, 5]
    assert [t for t, _ in c.calls] == [None, "a", "b"]


def test_single_empty_page_yields_nothing():
    c = FakeClient({None: page([], None)})
    assert list(mod.iterate_pages(c)) == []
    assert len(c.calls) == 1


def test_empty_pages_in_the_middle_do_not_stop_the_walk():
    c = FakeClient({None: page([1], "a"), "a": page([], "b"), "b": page([], "c"), "c": page([2], None)})
    assert ids(mod.iterate_pages(c)) == [1, 2]
    assert len(c.calls) == 4


def test_only_empty_pages_then_end():
    c = FakeClient({None: page([], "a"), "a": page([], None)})
    assert list(mod.iterate_pages(c)) == []


def test_duplicates_across_pages_are_dropped_first_wins():
    c = FakeClient({
        None: {"items": [rec(1, v="old"), rec(2)], "next": "a"},
        "a": {"items": [rec(2), rec(1, v="new"), rec(3)], "next": None},
    })
    out = list(mod.iterate_pages(c))
    assert ids(out) == [1, 2, 3]
    assert out[0]["v"] == "old"


def test_duplicates_inside_one_page_are_dropped_too():
    c = FakeClient({None: page([1, 1, 2, 2, 1], None)})
    assert ids(mod.iterate_pages(c)) == [1, 2]


def test_is_lazy_and_stops_requesting_when_the_consumer_stops():
    c = FakeClient({None: page([1, 2], "a"), "a": page([3, 4], "b"), "b": page([5], None)})
    it = mod.iterate_pages(c)
    assert next(it)["id"] == 1
    assert len(c.calls) == 1
    assert next(it)["id"] == 2 and len(c.calls) == 1
    assert next(it)["id"] == 3 and len(c.calls) == 2
    it.close()
    assert len(c.calls) == 2


def test_page_size_is_forwarded_on_every_call():
    c = FakeClient({None: page([1], "a"), "a": page([2], None)})
    list(mod.iterate_pages(c, page_size=25))
    assert c.calls == [(None, 25), ("a", 25)]


@pytest.mark.parametrize("bad", [0, -5, 2.5, True])
def test_page_size_validation(bad):
    with pytest.raises(ValueError):
        list(mod.iterate_pages(FakeClient({None: page([], None)}), page_size=bad))


def test_loop_back_to_an_earlier_token_raises_after_yielding_the_page():
    c = FakeClient({None: page([1], "a"), "a": page([2], "b"), "b": page([3], "a")})
    it = mod.iterate_pages(c)
    got = []
    with pytest.raises(mod.PaginationLoopError):
        for r in it:
            got.append(r["id"])
    assert got == [1, 2, 3]
    assert [t for t, _ in c.calls] == [None, "a", "b"]     # no fourth request


def test_page_pointing_at_itself():
    c = FakeClient({None: page([1], "a"), "a": page([2], "a")})
    got = []
    with pytest.raises(mod.PaginationLoopError):
        for r in mod.iterate_pages(c):
            got.append(r["id"])
    assert got == [1, 2] and len(c.calls) == 2


def test_runaway_pagination_with_fresh_tokens_hits_the_cap():
    class Endless:
        def __init__(self):
            self.n = 0

        def get_page(self, token, page_size=None):
            self.n += 1
            if self.n > 50:
                raise AssertionError("pagination was not capped")
            return {"items": [rec(self.n)], "next": f"t{self.n}"}

    c = Endless()
    got = []
    with pytest.raises(mod.PaginationLimitError):
        for r in mod.iterate_pages(c, max_pages=5):
            got.append(r["id"])
    assert got == [1, 2, 3, 4, 5] and c.n == 5


def test_cap_equal_to_the_number_of_pages_is_fine():
    c = FakeClient({None: page([1], "a"), "a": page([2], None)})
    assert ids(mod.iterate_pages(c, max_pages=2)) == [1, 2]
    with pytest.raises(mod.PaginationLimitError):
        list(mod.iterate_pages(FakeClient({None: page([1], "a"), "a": page([2], None)}), max_pages=1))


def test_invalid_max_pages():
    with pytest.raises(ValueError):
        list(mod.iterate_pages(FakeClient({None: page([], None)}), max_pages=0))


def test_custom_id_key_and_missing_id():
    c = FakeClient({None: {"items": [{"order_id": "x"}, {"order_id": "x"}, {"order_id": "y"}], "next": None}})
    assert [r["order_id"] for r in mod.iterate_pages(c, id_key="order_id")] == ["x", "y"]
    with pytest.raises(ValueError):
        list(mod.iterate_pages(FakeClient({None: {"items": [{"name": "no id"}], "next": None}})))


def test_client_errors_propagate_after_earlier_records():
    c = FakeClient({None: page([1], "a"), "a": page([2], None)}, error_at="a")
    got = []
    with pytest.raises(ConnectionError):
        for r in mod.iterate_pages(c):
            got.append(r["id"])
    assert got == [1]


def test_large_walk_with_overlapping_pages():
    n_pages = 400
    pages = {None: page(range(50), "p1")}
    for p in range(1, n_pages):
        pages[f"p{p}"] = page(range(p * 50 - 5, p * 50 + 50), f"p{p + 1}" if p < n_pages - 1 else None)
    out = ids(mod.iterate_pages(FakeClient(pages)))
    assert out == list(range(50 * n_pages))
