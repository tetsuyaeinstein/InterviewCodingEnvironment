"""Tests for PY-037 (imports your practice file by default; see _loader.py)."""
import random
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-037")

D = Decimal
F = ["id", "name", "tier"]


def fp(record, fields=F):
    return mod.fingerprint(record, fields)


def test_returns_sha256_hex():
    out = fp({"id": 1, "name": "x"})
    assert isinstance(out, str) and re.fullmatch(r"[0-9a-f]{64}", out)


def test_is_deterministic_and_ignores_key_and_field_order_and_unselected_keys():
    a = {"id": 7, "name": "Ida", "tier": "gold", "loaded_at": "2025-01-01"}
    b = {"tier": "gold", "name": "Ida", "id": 7, "loaded_at": "yesterday", "extra": [1, 2]}
    assert fp(a) == fp(a) == fp(b)
    assert fp(a, ["tier", "id", "name"]) == fp(a)


def test_example_from_question_schema_evolution():
    old = fp({"id": 7, "name": "Ida"}, ["id", "name"])
    assert fp({"id": 7, "name": "Ida", "tier": None}, ["id", "name", "tier"]) == old
    assert fp({"name": "Ida", "id": D("7.0")}, ["name", "id", "tier"]) == old
    assert fp({"id": 7, "name": "Ida", "tier": "gold"}, ["id", "name", "tier"]) != old
    assert fp({"id": 7, "name": "Ida", "tier": ""}, ["id", "name", "tier"]) != old


def test_adding_several_null_fields_keeps_every_existing_fingerprint():
    rows = [{"id": i, "name": f"n{i}"} for i in range(20)] + [{"id": 1}, {}]
    for r in rows:
        assert fp(r, ["id", "name"]) == fp(r, ["id", "name", "tier", "city", "x"])


def test_null_empty_and_text_none_are_all_different():
    values = [None, "", "None", "null", "NULL", " ", "0", 0, False]
    prints = [fp({"id": 1, "name": v}) for v in values]
    # None collapses with "absent" only; every other value is distinct from all of them
    assert prints[0] == fp({"id": 1})
    assert len(set(prints)) == len(values)


def test_field_boundaries_cannot_be_forged():
    assert fp({"a": "ab", "b": "c"}, ["a", "b"]) != fp({"a": "a", "b": "bc"}, ["a", "b"])
    assert fp({"a": "x|b=y"}, ["a", "b"]) != fp({"a": "x", "b": "y"}, ["a", "b"])
    assert fp({"a": "b"}, ["a", "b"]) != fp({"b": "a"}, ["a", "b"])
    assert fp({"a": 'x","b":"y'}, ["a", "b"]) != fp({"a": "x", "b": "y"}, ["a", "b"])
    assert fp({"a": "1\x00", "b": "2"}, ["a", "b"]) != fp({"a": "1", "b": "\x002"}, ["a", "b"])
    assert fp({"a": "1\n2"}, ["a", "b"]) != fp({"a": "1", "b": "2"}, ["a", "b"])
    assert fp({"a|b": "c"}, ["a|b", "c"]) != fp({"a": "b|c"}, ["a", "b|c"])


def test_numbers_compare_by_value_not_representation():
    same = [7, D("7"), D("7.0"), D("7.00"), D("0.7E+1"), D("70E-1")]
    assert len({fp({"id": v}) for v in same}) == 1
    assert len({fp({"id": v}) for v in [0, -0 * 1, D("0"), D("0.00"), D("-0"), D("-0.0"), D("0E+5")]}) == 1
    assert fp({"id": D("1.10")}) == fp({"id": D("1.1")}) != fp({"id": D("1.11")})
    assert fp({"id": 10**30}) == fp({"id": D(10**30)}) != fp({"id": 10**30 + 1})
    assert fp({"id": 100}) == fp({"id": D("1E+2")}) != fp({"id": 10})


def test_booleans_bytes_and_text_are_different_types():
    prints = [fp({"id": v}) for v in [True, 1, "1", "True", b"1", False, 0, "0", "False"]]
    assert prints[1] == fp({"id": D(1)})
    assert len(set(prints)) == len(prints)
    assert fp({"id": b"a"}) != fp({"id": "a"}) != fp({"id": b"A"})


def test_strings_are_compared_exactly():
    assert len({fp({"name": s}) for s in ["a", "A", "a ", " a", "a\n", "é", "é"]}) == 7
    assert fp({"name": "日本語 \U0001F600"}) == fp({"name": "日本語 \U0001F600"})


def test_datetimes_are_normalised_to_utc_instants():
    plus9 = timezone(timedelta(hours=9))
    minus5 = timezone(-timedelta(hours=5))
    instant = [datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
               datetime(2025, 6, 1, 21, 0, tzinfo=plus9),
               datetime(2025, 6, 1, 7, 0, tzinfo=minus5)]
    assert len({fp({"id": 1, "name": t}) for t in instant}) == 1
    assert fp({"name": instant[0]}) != fp({"name": instant[0] + timedelta(microseconds=1)})
    assert fp({"name": instant[0]}) != fp({"name": instant[0] + timedelta(hours=1)})


def test_dates_datetimes_and_text_are_distinct():
    day = date(2025, 1, 2)
    midnight = datetime(2025, 1, 2, tzinfo=timezone.utc)
    prints = [fp({"name": v}) for v in [day, midnight, "2025-01-02", "2025-01-02T00:00:00+00:00"]]
    assert len(set(prints)) == 4


def test_duplicate_field_names_are_rejected():
    with pytest.raises(ValueError):
        fp({"id": 1}, ["id", "name", "id"])


@pytest.mark.parametrize("bad, exc", [
    (datetime(2025, 1, 1), ValueError),             # naive
    (D("NaN"), ValueError), (D("Infinity"), ValueError),
    (1.5, TypeError), ([1], TypeError), ({"a": 1}, TypeError), ((1,), TypeError), (object(), TypeError),
])
def test_unsupported_values_raise(bad, exc):
    with pytest.raises(exc):
        fp({"id": bad})


def test_unselected_unsupported_values_are_ignored():
    assert fp({"id": 1, "blob": [1, 2], "f": 1.5}, ["id"]) == fp({"id": 1}, ["id"])


def test_equal_digest_iff_equal_canonical_form_on_random_records():
    rng = random.Random(37)
    alphabet = ["", "a", "b", "|", "=", ",", '"', "a|b", "None", "\x00", "é", "1"]
    pool = [None, 0, 1, 2, D("1.0"), D("2.00"), D("-0"), True, False, b"a", b"", datetime(2025, 1, 1, tzinfo=timezone.utc),
            date(2025, 1, 1)] + alphabet
    names = ["a", "b", "c", "a|b", "b=c"]

    def canon(rec):
        out = []
        for n in sorted(names):
            v = rec.get(n)
            if v is None:
                continue
            if isinstance(v, bool):
                out.append((n, "bool", v))
            elif isinstance(v, (int, D)):
                out.append((n, "num", D(v)))
            elif isinstance(v, datetime):
                out.append((n, "ts", v.astimezone(timezone.utc)))
            else:
                out.append((n, type(v).__name__, v))
        return tuple(out)

    recs = [{n: rng.choice(pool) for n in rng.sample(names, rng.randint(0, 3))} for _ in range(400)]
    digest = {}
    for r in recs:
        c = canon(r)
        d = fp(r, names)
        assert digest.setdefault(c, d) == d                 # equal canonical form -> equal digest
    assert len(set(digest.values())) == len(digest)         # different canonical form -> different digest
    # ... and the same through shuffled key order / reversed field order
    for r in recs[:50]:
        items = list(r.items())
        rng.shuffle(items)
        assert fp(dict(items), names[::-1]) == fp(r, names)
