"""Tests for PY-009 (imports your practice file by default; see _loader.py)."""
import random

import pytest

from _loader import load

mod = load("PY-009")


def test_example_from_question():
    events = ["COIN_DEPOSIT", " coin_deposit ", "bill  jam", "Bill Jam", None, "", "door_open", "  ", "BILL\tJAM"]
    assert mod.event_type_counts(events) == [("bill jam", 3), ("coin_deposit", 2), ("door_open", 1)]


def test_empty_and_all_ignored():
    assert mod.event_type_counts([]) == []
    assert mod.event_type_counts([None, "", "   ", "\t\n"]) == []


def test_ties_are_alphabetical_not_first_seen():
    events = ["zeta", "alpha", "mid", "zeta", "alpha", "mid", "beta"]
    assert mod.event_type_counts(events) == [("alpha", 2), ("mid", 2), ("zeta", 2), ("beta", 1)]


def test_whitespace_inside_and_around_names():
    events = ["\tcard \n swipe ", "CARD SWIPE", "card swipe", "card_swipe"]
    assert mod.event_type_counts(events) == [("card swipe", 3), ("card_swipe", 1)]


def test_case_insensitive_but_otherwise_exact():
    events = ["Door-Open", "door-open", "door open", "DOOR_OPEN"]
    assert mod.event_type_counts(events) == [("door-open", 2), ("door open", 1), ("door_open", 1)]


@pytest.mark.parametrize("bad", [7, b"coin", ["coin"]])
def test_non_string_values_raise_type_error(bad):
    with pytest.raises(TypeError):
        mod.event_type_counts(["coin", bad])


def test_one_pass_iterator_and_tuple_output():
    result = mod.event_type_counts(e for e in ["a", "B", "b"])
    assert result == [("b", 2), ("a", 1)]
    assert all(type(item) is tuple for item in result)


def test_matches_oracle_on_random_inputs():
    rng = random.Random(9)
    names = ["coin", "bill jam", "door", "Coin", " COIN ", "bill\t jam", None, "", "a b"]
    for _ in range(300):
        events = [rng.choice(names) for _ in range(rng.randint(0, 40))]
        counts = {}
        for e in events:
            if e is None or not e.strip():
                continue
            key = " ".join(e.split()).lower()
            counts[key] = counts.get(key, 0) + 1
        expected = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        assert mod.event_type_counts(events) == expected
