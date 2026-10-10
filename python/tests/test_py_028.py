"""Tests for PY-028 (imports your practice file by default; see _loader.py)."""
import random
import re
import time
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-028")
H = mod.canonical_row_hash


def canon_oracle(row, exclude=()):
    """Reference canonical form for comparisons (independent of any encoding)."""
    out = {}
    for k, v in row.items():
        if k in exclude or v is None:
            continue
        if isinstance(v, bool):
            out[k] = ("b", v)
        elif isinstance(v, (int, Decimal)):
            out[k] = ("n", Decimal(v))
        else:
            out[k] = ("s", v)
    return out


def test_hash_is_sha256_hex_and_field_order_independent():
    a = H({"id": 1, "name": "Ann", "city": "Oslo"})
    b = H({"city": "Oslo", "id": 1, "name": "Ann"})
    assert a == b and re.fullmatch(r"[0-9a-f]{64}", a)


def test_null_empty_string_and_null_text_are_different_but_absent_equals_null():
    base = {"id": 1}
    assert H({"id": 1, "x": None}) == H(base)
    hashes = {H({"id": 1, "x": v}) for v in (None, "", "NULL", "null", "None", " ")}
    assert len(hashes) == 6


def test_numeric_policy_compares_by_value():
    assert H({"a": Decimal("1.0")}) == H({"a": Decimal("1.00")}) == H({"a": 1}) == H({"a": Decimal("1")})
    assert H({"a": Decimal("-0.00")}) == H({"a": 0}) == H({"a": Decimal("0E+3")})
    assert H({"a": Decimal("100")}) == H({"a": Decimal("1E+2")})
    assert H({"a": Decimal("1.01")}) != H({"a": Decimal("1.00")})
    assert H({"a": Decimal("0.1")}) != H({"a": Decimal("0.01")})


def test_types_are_part_of_the_value():
    assert len({H({"a": True}), H({"a": 1}), H({"a": "1"}), H({"a": "true"}), H({"a": "True"})}) == 5
    assert H({"a": False}) != H({"a": 0})


@pytest.mark.parametrize("r1, r2", [
    ({"a": "x|y", "b": "z"}, {"a": "x", "b": "y|z"}),
    ({"a": "x,y", "b": "z"}, {"a": "x", "b": "y,z"}),
    ({"a": "1", "b": "2"}, {"a": "1\x002", "b": None}),
    ({"ab": "c"}, {"a": "bc"}),
    ({"a": "b=c"}, {"a=b": "c"}),
    ({"a": 'x","b":"y'}, {"a": "x", "b": "y"}),
    ({"a": "x:1:y"}, {"a": "x", "1": "y"}),
    ({"a": ""}, {"": "a"}),
    ({"a": "s1"}, {"a": 1}),
])
def test_no_delimiter_or_concatenation_collisions(r1, r2):
    assert H(r1) != H(r2)


def test_exclude_fields_and_unicode():
    assert H({"id": 1, "loaded_at": "x"}, exclude={"loaded_at"}) == H({"id": 1, "loaded_at": "y"}, exclude={"loaded_at"})
    assert H({"n": "Zoë"}) != H({"n": "Zoë"})   # different code points: no Unicode normalisation


def test_unsupported_values_are_rejected():
    with pytest.raises(TypeError):
        H({"a": 1.5})
    with pytest.raises(TypeError):
        H({"a": [1, 2]})
    with pytest.raises(ValueError):
        H({"a": Decimal("NaN")})


def test_hash_matches_canonical_equality_on_random_rows():
    rng = random.Random(28)
    pool = ["", "|", ",", "a", "a|", "|a", ":", "1", "NULL", '"', "\\", None, 0, 1, Decimal("1.0"),
            Decimal("0.10"), Decimal("0.1"), True, False]
    names = ["a", "b", "a|b", "c"]
    rows = []
    for _ in range(1500):
        rows.append({n: rng.choice(pool) for n in rng.sample(names, rng.randint(0, 4))})
    by_hash = {}
    for row in rows:
        by_hash.setdefault(H(row), []).append(row)
    for group in by_hash.values():
        first = canon_oracle(group[0])
        assert all(canon_oracle(r) == first for r in group), f"collision between {group[:3]}"
    seen = {}
    for row in rows:
        key = tuple(sorted((k, v[0], str(v[1].normalize()) if v[0] == "n" else v[1]) for k, v in canon_oracle(row).items()))
        h = H(row)
        assert seen.setdefault(key, h) == h, f"canonically equal rows hashed differently: {row}"


def test_diff_basic():
    source = [{"id": 1, "name": "Ann", "amt": Decimal("10.00")},
              {"id": 2, "name": "Bob", "amt": Decimal("5.00")},
              {"id": 3, "name": "Cid", "amt": Decimal("7.50")},
              {"id": 5, "name": "Eve", "amt": None}]
    target = [{"id": 3, "name": "Cid", "amt": Decimal("7.5")},          # scale only: unchanged
              {"id": 2, "name": "Bob", "amt": Decimal("5.01")},          # changed amt
              {"id": 4, "name": "Dan", "amt": Decimal("1.00")},          # extra
              {"id": 5, "name": "Eve"}]                                  # absent == None: unchanged
    res = mod.diff_streams(source, target, ["id"])
    assert res.missing == [(1,)]
    assert res.extra == [(4,)]
    assert res.changed == [((2,), ("amt",))]
    assert res.unchanged == 2


def test_changed_fields_cover_both_sides_and_type_changes():
    source = [{"k": "A", "x": "", "y": 1, "z": "same"}, {"k": "B", "flag": True}]
    target = [{"k": "A", "x": None, "y": "1", "z": "same", "w": "new"}, {"k": "B", "flag": 1}]
    res = mod.diff_streams(iter(source), iter(target), ["k"])
    assert res.changed == [(("A",), ("w", "x", "y")), (("B",), ("flag",))]
    assert res.missing == [] and res.extra == [] and res.unchanged == 0


def test_composite_keys_sorted_and_exclude():
    source = [{"s": "S2", "d": "2025-01-02", "v": 1, "ts": "a"}, {"s": "S1", "d": "2025-01-02", "v": 2, "ts": "a"},
              {"s": "S1", "d": "2025-01-01", "v": 3, "ts": "a"}, {"s": "S9", "d": "2025-01-01", "v": 0, "ts": "a"}]
    target = [{"s": "S1", "d": "2025-01-01", "v": 3, "ts": "b"}, {"s": "S1", "d": "2025-01-02", "v": 9, "ts": "b"},
              {"s": "S2", "d": "2025-01-02", "v": 8, "ts": "b"}, {"s": "S0", "d": "2025-01-01", "v": 0, "ts": "b"}]
    res = mod.diff_streams(source, target, ["s", "d"], exclude={"ts"})
    assert res.changed == [(("S1", "2025-01-02"), ("v",)), (("S2", "2025-01-02"), ("v",))]
    assert res.missing == [("S9", "2025-01-01")] and res.extra == [("S0", "2025-01-01")]
    assert res.unchanged == 1


@pytest.mark.parametrize("side", ["source", "target"])
def test_duplicate_keys_raise(side):
    dup = [{"id": 1, "v": 1}, {"id": 1, "v": 1}]
    one = [{"id": 1, "v": 1}]
    with pytest.raises(ValueError):
        if side == "source":
            mod.diff_streams(dup, one, ["id"])
        else:
            mod.diff_streams(one, dup, ["id"])


def test_empty_streams():
    res = mod.diff_streams([], [], ["id"])
    assert (res.missing, res.extra, res.changed, res.unchanged) == ([], [], [], 0)
    res = mod.diff_streams([], [{"id": 2}], ["id"])
    assert res.extra == [(2,)]


def test_diff_matches_brute_force_on_random_data():
    rng = random.Random(2028)
    vals = [None, "", "x", 1, Decimal("1.0"), Decimal("2"), True]
    for _ in range(150):
        src = {k: {"id": k, "a": rng.choice(vals), "b": rng.choice(vals)} for k in rng.sample(range(30), rng.randint(0, 20))}
        tgt = {k: {"id": k, "a": rng.choice(vals), "b": rng.choice(vals)} for k in rng.sample(range(30), rng.randint(0, 20))}
        res = mod.diff_streams(list(src.values()), list(tgt.values()), ["id"])
        assert res.missing == sorted((k,) for k in src.keys() - tgt.keys())
        assert res.extra == sorted((k,) for k in tgt.keys() - src.keys())
        exp_changed = []
        for k in sorted(src.keys() & tgt.keys()):
            a, b = canon_oracle(src[k]), canon_oracle(tgt[k])
            fields = tuple(sorted(f for f in a.keys() | b.keys() if a.get(f) != b.get(f)))
            if fields:
                exp_changed.append(((k,), fields))
        assert res.changed == exp_changed
        assert res.unchanged == len(src.keys() & tgt.keys()) - len(exp_changed)


def test_large_reconciliation_is_fast():
    n = 100_000
    src = ({"id": i, "amt": Decimal(i) / 100, "s": f"row{i}"} for i in range(n))
    tgt = ({"id": i, "amt": Decimal(i) / 100 + (1 if i % 1000 == 0 else 0), "s": f"row{i}"} for i in range(n - 1, 4, -1))
    t0 = time.perf_counter()
    res = mod.diff_streams(src, tgt, ["id"])
    elapsed = time.perf_counter() - t0
    assert res.missing == [(i,) for i in range(5)]
    assert len(res.changed) == n // 1000 - 1 and res.extra == []
    assert elapsed < 6.0, f"took {elapsed:.2f}s"


def test_large_numbers_are_not_rounded_together():
    assert H({"a": 10**30}) != H({"a": 10**30 + 1})
    assert H({"a": Decimal(10**30 + 1)}) != H({"a": Decimal(10**30)})
    assert H({"a": Decimal("1" + "0" * 40)}) == H({"a": 10**40})
