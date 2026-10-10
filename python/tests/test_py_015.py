"""Tests for PY-015 (imports your practice file by default; see _loader.py)."""
import ctypes
import random
import threading
import time

from _loader import load

mod = load("PY-015")


def call_with_deadline(fn, seconds=6.0):
    """Run fn(); if it is still running after `seconds`, interrupt it and fail (guards against quadratic runs)."""
    tid = threading.get_ident()

    def interrupt():
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), ctypes.py_object(TimeoutError))

    timer = threading.Timer(seconds, interrupt)
    timer.start()
    try:
        return fn()
    except TimeoutError:
        pytest.fail(f"still running after {seconds:.0f}s - expected a much faster algorithm")
    finally:
        timer.cancel()


def same_chars(a, b):
    """Oracle predicate: compare character counts by hand after the documented normalisation."""
    def counts(s):
        d = {}
        for ch in s.casefold():
            if not ch.isspace():
                d[ch] = d.get(ch, 0) + 1
        return d
    return counts(a) == counts(b)


def oracle(labels):
    """Quadratic: put each label in the first existing group whose first member matches."""
    groups = []
    for label in labels:
        for g in groups:
            if same_chars(g[0], label):
                g.append(label)
                break
        else:
            groups.append([label])
    return groups


def test_example_from_question():
    labels = ["TEA BAG", "lamp", "tae gab", "palm", "Bag Eat", "LAMP", "tea bag", "teabags"]
    assert mod.group_anagram_labels(labels) == [
        ["TEA BAG", "tae gab", "Bag Eat", "tea bag"],
        ["lamp", "palm", "LAMP"],
        ["teabags"],
    ]


def test_empty_input():
    assert mod.group_anagram_labels([]) == []


def test_character_counts_matter_not_just_the_set():
    assert mod.group_anagram_labels(["aab", "abb", "ab", "bba", "baa"]) == [["aab", "baa"], ["abb", "bba"], ["ab"]]


def test_case_and_whitespace_are_ignored():
    labels = ["Ab C", "c\tBA", "CBA\n", "  abc  ", "abcc"]
    assert mod.group_anagram_labels(labels) == [["Ab C", "c\tBA", "CBA\n", "  abc  "], ["abcc"]]


def test_case_folding_is_full_unicode():
    labels = ["Straße", "STRASSE", "strase", "Été", "éTÉ"]
    assert mod.group_anagram_labels(labels) == [["Straße", "STRASSE"], ["strase"], ["Été", "éTÉ"]]


def test_punctuation_and_digits_count():
    labels = ["A-1", "1-a", "A1", "a 1", "-1A", "A--1"]
    assert mod.group_anagram_labels(labels) == [["A-1", "1-a", "-1A"], ["A1", "a 1"], ["A--1"]]


def test_duplicates_kept_and_original_spelling_preserved():
    labels = ["Kiosk", "kiosk", "Kiosk", "SKIOK"]
    assert mod.group_anagram_labels(labels) == [["Kiosk", "kiosk", "Kiosk", "SKIOK"]]


def test_labels_empty_after_normalisation_group_together():
    labels = ["x", "", "  ", "X", "\t"]
    assert mod.group_anagram_labels(labels) == [["x", "X"], ["", "  ", "\t"]]


def test_group_order_follows_first_appearance_not_alphabet():
    labels = ["zz", "yy", "aa", "zz", "aa"]
    assert mod.group_anagram_labels(labels) == [["zz", "zz"], ["yy"], ["aa", "aa"]]


def test_accepts_a_generator_and_does_not_mutate():
    labels = ["ab", "ba", "c"]
    snapshot = list(labels)
    assert mod.group_anagram_labels(x for x in labels) == [["ab", "ba"], ["c"]]
    assert labels == snapshot


def test_matches_oracle_on_random_inputs():
    rng = random.Random(15)
    alphabet = "aAbB c-"
    for _ in range(300):
        labels = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 4)))
                  for _ in range(rng.randint(0, 15))]
        assert mod.group_anagram_labels(labels) == oracle(labels), labels


def test_large_feed():
    rng = random.Random(1)
    base = ["".join(rng.choice("ABCDEFGHIJ-0123") for _ in range(12)) for _ in range(20_000)]
    labels = []
    for _ in range(100_000):
        chars = list(rng.choice(base))
        rng.shuffle(chars)
        labels.append("".join(chars).lower() if rng.random() < 0.5 else "".join(chars))
    t0 = time.perf_counter()
    groups = call_with_deadline(lambda: mod.group_anagram_labels(labels))
    elapsed = time.perf_counter() - t0
    assert sum(len(g) for g in groups) == len(labels)
    assert len(groups) <= 20_000
    assert elapsed < 2.0, f"took {elapsed:.2f}s - comparing every pair is too slow"
