"""Tests for PY-012 (imports your practice file by default; see _loader.py)."""
import random
import time

import pytest

from _loader import load

mod = load("PY-012")


def oracle(s: str) -> str:
    """Brute force: first window of maximal length with all-distinct characters."""
    best = ""
    for i in range(len(s)):
        seen = set()
        for j in range(i, len(s)):
            if s[j] in seen:
                break
            seen.add(s[j])
            if j - i + 1 > len(best):
                best = s[i:j + 1]
    return best


@pytest.mark.parametrize("s, expected", [
    ("abcabcbb", "abc"),
    ("bbbbb", "b"),
    ("pwwkew", "wke"),
    ("a", "a"),
    ("au", "au"),
    ("dvdf", "vdf"),
])
def test_examples(s, expected):
    assert mod.longest_unique_substring(s) == expected


def test_empty_input():
    assert mod.longest_unique_substring("") == ""


@pytest.mark.parametrize("s, expected", [("abba", "ab"), ("tmmzuxt", "mzuxt"), ("abcdbea", "cdbea")])
def test_repeat_outside_current_window(s, expected):
    assert mod.longest_unique_substring(s) == expected


@pytest.mark.parametrize("s, expected", [("xyzxyz", "xyz"), ("abab", "ab"), ("aabbcc", "ab")])
def test_tie_returns_earliest(s, expected):
    assert mod.longest_unique_substring(s) == expected


def test_case_sensitive_and_unicode():
    assert mod.longest_unique_substring("aAbBaA") == "aAbB"
    assert mod.longest_unique_substring("日本日本語") == "日本語"
    assert mod.longest_unique_substring("a b  c") == "a b"


def test_matches_brute_force_on_random_inputs():
    rng = random.Random(12)
    for _ in range(400):
        alphabet = "abcde"[: rng.randint(1, 5)]
        s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 25)))
        assert mod.longest_unique_substring(s) == oracle(s), s


def test_large_alphabet_runs_in_linear_time():
    block = "".join(chr(0x4E00 + i) for i in range(20_000))
    s = block + block
    t0 = time.perf_counter()
    result = mod.longest_unique_substring(s)
    elapsed = time.perf_counter() - t0
    assert result == block
    assert elapsed < 2.0, f"took {elapsed:.2f}s - expected a linear-time approach"
