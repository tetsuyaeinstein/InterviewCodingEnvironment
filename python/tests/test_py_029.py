"""Tests for PY-029 (imports your practice file by default; see _loader.py)."""
import csv
import math
import os
import random
import tracemalloc
from decimal import Decimal

import pytest

from _loader import load

mod = load("PY-029")


@pytest.fixture
def env(tmp_path):
    (tmp_path / "in").mkdir()
    (tmp_path / "out").mkdir()
    (tmp_path / "work").mkdir()
    return tmp_path


def write_csv(path, header, rows, bom=False):
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def test_sorts_and_creates_runs_in_the_work_dir(env):
    rng = random.Random(29)
    rows = [[f"k{rng.randint(0, 999):03d}", str(i), "x" * rng.randint(0, 20)] for i in range(3000)]
    src = write_csv(env / "in" / "data.csv", ["key", "seq", "pad"], rows)
    runs = []

    def on_run(path):
        assert path.parent.resolve() == (env / "work").resolve(), "runs must be written to work_dir"
        assert path.exists() and path.stat().st_size > 0, "callback must see a complete run file"
        runs.append(path)

    n = mod.external_sort_csv(src, env / "out" / "sorted.csv", "key", max_records_in_memory=50,
                              work_dir=env / "work", on_run_written=on_run)
    assert n == 3000
    assert len(runs) == math.ceil(3000 / 50), "expected one run per 50 records"
    out = read_csv(env / "out" / "sorted.csv")
    assert out[0] == ["key", "seq", "pad"]
    assert out[1:] == sorted(rows, key=lambda r: r[0])        # sorted() is stable: ties in input order
    assert os.listdir(env / "work") == [], "run files must be deleted"
    assert os.listdir(env / "out") == ["sorted.csv"]


def test_stable_for_equal_keys_across_runs(env):
    rows = [[k, str(i)] for i, k in enumerate(["b", "a", "b", "a", "c", "a", "b"] * 30)]
    src = write_csv(env / "in" / "d.csv", ["k", "seq"], rows)
    mod.external_sort_csv(src, env / "out" / "s.csv", "k", max_records_in_memory=4, work_dir=env / "work")
    out = read_csv(env / "out" / "s.csv")[1:]
    assert out == sorted(rows, key=lambda r: r[0])


def test_numeric_keys(env):
    rows = [["10", "a"], ["9", "b"], ["-1", "c"], ["1.50", "d"], ["1.5", "e"], [" 2 ", "f"], ["100", "g"]]
    src = write_csv(env / "in" / "d.csv", ["amount", "tag"], rows)
    mod.external_sort_csv(src, env / "out" / "s.csv", "amount", max_records_in_memory=2,
                          work_dir=env / "work", numeric=True)
    assert [r[1] for r in read_csv(env / "out" / "s.csv")[1:]] == ["c", "d", "e", "f", "b", "a", "g"]


def test_string_keys_use_code_point_order(env):
    rows = [["b"], ["B"], ["a"], ["10"], ["9"], ["é"], [""]]
    src = write_csv(env / "in" / "d.csv", ["k"], rows)
    mod.external_sort_csv(src, env / "out" / "s.csv", "k", max_records_in_memory=3, work_dir=env / "work")
    assert [r[0] for r in read_csv(env / "out" / "s.csv")[1:]] == ["", "10", "9", "B", "a", "b", "é"]


def test_quoted_commas_and_newlines_survive_runs(env):
    rows = [["3", "plain"], ["1", "has, comma"], ["2", "multi\nline \"quoted\""], ["0", ""]]
    src = write_csv(env / "in" / "d.csv", ["id", "note"], rows, bom=True)
    n = mod.external_sort_csv(src, env / "out" / "s.csv", "id", max_records_in_memory=1, work_dir=env / "work")
    assert n == 4
    assert read_csv(env / "out" / "s.csv") == [["id", "note"], ["0", ""], ["1", "has, comma"],
                                              ["2", "multi\nline \"quoted\""], ["3", "plain"]]


def test_header_only_and_empty_file(env):
    src = write_csv(env / "in" / "h.csv", ["a", "b"], [])
    calls = []
    assert mod.external_sort_csv(src, env / "out" / "s.csv", "a", max_records_in_memory=10,
                                 work_dir=env / "work", on_run_written=calls.append) == 0
    assert read_csv(env / "out" / "s.csv") == [["a", "b"]] and calls == []
    empty = env / "in" / "e.csv"
    empty.write_bytes(b"")
    with pytest.raises(ValueError):
        mod.external_sort_csv(empty, env / "out" / "e.csv", "a", max_records_in_memory=10, work_dir=env / "work")


def test_invalid_arguments(env):
    src = write_csv(env / "in" / "d.csv", ["a"], [["1"]])
    with pytest.raises(ValueError):
        mod.external_sort_csv(src, env / "out" / "s.csv", "missing", max_records_in_memory=10, work_dir=env / "work")
    with pytest.raises(ValueError):
        mod.external_sort_csv(src, env / "out" / "s.csv", "a", max_records_in_memory=0, work_dir=env / "work")
    assert os.listdir(env / "work") == [] and os.listdir(env / "out") == []


def test_failure_midway_cleans_up_and_leaves_destination_untouched(env):
    rows = [[str(i), "x"] for i in range(2000)]
    rows[1500][0] = "not-a-number"
    src = write_csv(env / "in" / "d.csv", ["n", "x"], rows)
    dest = env / "out" / "s.csv"
    dest.write_text("previous result")
    runs = []
    with pytest.raises(ValueError):
        mod.external_sort_csv(src, dest, "n", max_records_in_memory=100, work_dir=env / "work",
                              numeric=True, on_run_written=runs.append)
    assert len(runs) >= 10, "runs should have been spilled before the bad row was reached"
    assert os.listdir(env / "work") == [], "run files left behind after an error"
    assert dest.read_text() == "previous result"
    assert os.listdir(env / "out") == ["s.csv"]


def test_exception_from_callback_cleans_up(env):
    src = write_csv(env / "in" / "d.csv", ["n"], [[str(i)] for i in range(100)])

    class Stop(Exception):
        pass

    seen = []

    def on_run(path):
        seen.append(path)
        if len(seen) == 3:
            raise Stop()

    with pytest.raises(Stop):
        mod.external_sort_csv(src, env / "out" / "s.csv", "n", max_records_in_memory=10,
                              work_dir=env / "work", on_run_written=on_run)
    assert os.listdir(env / "work") == [] and os.listdir(env / "out") == []


def test_memory_is_bounded_by_the_run_size(env):
    rng = random.Random(7)
    n = 4000
    rows = [[f"{rng.randint(0, 10**9):010d}", "p" * 5000] for _ in range(n)]
    src = write_csv(env / "in" / "big.csv", ["key", "payload"], rows)   # ~20 MB
    del rows
    count = []
    tracemalloc.start()
    try:
        written = mod.external_sort_csv(src, env / "out" / "s.csv", "key", max_records_in_memory=200,
                                        work_dir=env / "work", on_run_written=lambda p: count.append(p))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert written == n and len(count) == n // 200
    assert peak < 6_000_000, f"peak traced memory {peak / 1e6:.1f} MB for a ~20 MB file with 200-record runs"
    keys = [r[0] for r in read_csv(env / "out" / "s.csv")[1:]]
    assert keys == sorted(keys) and len(keys) == n
