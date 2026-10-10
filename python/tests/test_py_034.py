"""Tests for PY-034 (imports your practice file by default; see _loader.py)."""
import random

import pytest

from _loader import load

mod = load("PY-034")


class Crash(BaseException):
    """Simulated process death (BaseException so that `except Exception` cannot hide it)."""


class World:
    """Durable state that outlives crashes: sink, dead-letter sink, checkpoint cell."""

    def __init__(self):
        self.sink = {}
        self.dead = {}
        self.ckpt = 0
        self.log = []          # (kind, argument) of every completed durable operation
        self.loads = 0
        self.ops = 0
        self.crash = None      # (op_index, "before" | "after") for the current attempt

    def begin_attempt(self, crash=None):
        self.ops = 0
        self.crash = crash

    def _op(self, kind, arg, do):
        i = self.ops
        self.ops += 1
        if self.crash == (i, "before"):
            raise Crash()
        do()
        self.log.append((kind, arg))
        if self.crash == (i, "after"):
            raise Crash()

    # the three interfaces -------------------------------------------------
    class _Sink:
        def __init__(self, world, kind, store):
            self.w, self.kind, self.store = world, kind, store

        def write(self, batch_id, rows):
            rows = list(rows)
            self.w._op(self.kind, batch_id, lambda: self.store.__setitem__(batch_id, rows))

    class _Ckpt:
        def __init__(self, world):
            self.w = world

        def load(self):
            self.w.loads += 1
            return self.w.ckpt

        def save(self, offset):
            self.w._op("ckpt", offset, lambda: setattr(self.w, "ckpt", offset))

    def run(self, source, transform, batch_size, **kw):
        return mod.run_batches(source, transform, World._Sink(self, "sink", self.sink),
                               World._Sink(self, "dead", self.dead), World._Ckpt(self),
                               batch_size=batch_size, **kw)

    def rows(self):
        return [r for _, rows in sorted(self.sink.items()) for r in rows]

    def dead_letters(self):
        return [d for _, ds in sorted(self.dead.items()) for d in ds]


def chars(s):
    if s == "!":
        raise mod.BadRecord("bang")
    return list(s)


SOURCE = ["a", "bb", "", "ccc", "!", "dd", "e"]


def expected(source, transform):
    rows, dead = [], []
    for i, rec in enumerate(source):
        try:
            rows.extend(list(transform(rec)))
        except mod.BadRecord as exc:
            dead.append(mod.DeadLetter(i, rec, str(exc)))
    return rows, dead


def count_ops(source, transform, batch_size):
    w = World()
    w.begin_attempt()
    w.run(source, transform, batch_size)
    return w.ops


def run_with_crashes(source, transform, plan):
    """plan: list of (batch_size, crash_point_or_None). A final crash-free run (last batch size) completes."""
    w = World()
    for batch_size, crash in plan:
        w.begin_attempt(crash)
        try:
            w.run(source, transform, batch_size)
        except Crash:
            pass
    w.begin_attempt()
    w.run(source, transform, plan[-1][0])
    return w


def test_example_from_question():
    w = World()
    w.begin_attempt()
    report = w.run(["a", "bb", "", "ccc"], chars, 2)
    assert w.rows() == list("abbccc")
    assert report == mod.RunReport(2, 4) and w.ckpt == 4 and w.dead_letters() == []


def test_per_batch_call_pattern_and_checkpoint_is_the_commit_point():
    w = World()
    w.begin_attempt()
    w.run(SOURCE, chars, 3)                         # batches [0,3) [3,6) [6,7)
    kinds = [k for k, _ in w.log]
    assert kinds == ["sink", "dead", "ckpt"] * 3 or kinds == ["dead", "sink", "ckpt"] * 3
    assert [a for k, a in w.log if k == "ckpt"] == [3, 6, 7]
    assert w.loads == 1


def test_matches_uninterrupted_result_with_dead_letters_at_absolute_offsets():
    w = World()
    w.begin_attempt()
    w.run(SOURCE, chars, 2)
    exp_rows, exp_dead = expected(SOURCE, chars)
    assert w.rows() == exp_rows and w.dead_letters() == exp_dead
    assert exp_dead == [mod.DeadLetter(4, "!", "bang")]


@pytest.mark.parametrize("batch_size", [1, 2, 3, 7, 50])
def test_single_crash_at_every_step_never_loses_or_duplicates(batch_size):
    exp_rows, exp_dead = expected(SOURCE, chars)
    total = count_ops(SOURCE, chars, batch_size)
    for i in range(total):
        for when in ("before", "after"):
            w = run_with_crashes(SOURCE, chars, [(batch_size, (i, when)), (batch_size, None)])
            assert w.rows() == exp_rows, (batch_size, i, when)
            assert w.dead_letters() == exp_dead, (batch_size, i, when)
            assert w.ckpt == len(SOURCE)


def test_two_consecutive_crashes_anywhere():
    exp_rows, exp_dead = expected(SOURCE, chars)
    total = count_ops(SOURCE, chars, 2)
    points = [(i, when) for i in range(total) for when in ("before", "after")]
    for p1 in points:
        for p2 in points[::3]:
            w = run_with_crashes(SOURCE, chars, [(2, p1), (2, p2), (2, None)])
            assert (w.rows(), w.dead_letters()) == (exp_rows, exp_dead), (p1, p2)


def test_restart_with_a_different_batch_size_is_still_exact():
    exp_rows, exp_dead = expected(SOURCE, chars)
    for first in (1, 2, 3, 4, 7):
        for second in (1, 2, 3, 5, 100):
            total = count_ops(SOURCE, chars, first)
            for i in range(total):
                for when in ("before", "after"):
                    w = run_with_crashes(SOURCE, chars, [(first, (i, when)), (second, None)])
                    assert (w.rows(), w.dead_letters()) == (exp_rows, exp_dead), (first, second, i, when)


def test_finished_job_is_a_noop_on_rerun():
    w = World()
    w.begin_attempt()
    w.run(SOURCE, chars, 3)
    before = len(w.log)
    report = w.run(SOURCE, chars, 3)
    assert report == mod.RunReport(0, len(SOURCE)) and len(w.log) == before


def test_transform_may_yield_many_or_no_rows_and_checkpoint_counts_inputs():
    src = [3, 0, 0, 2, 0, 1]
    w = World()
    w.begin_attempt()
    w.run(src, lambda n: [n] * n, 4)
    assert w.rows() == [3, 3, 3, 2, 2, 1]
    assert [a for k, a in w.log if k == "ckpt"] == [4, 6]


def test_bad_record_discards_rows_it_already_yielded():
    def gen(rec):
        yield rec
        if rec == "x":
            raise mod.BadRecord("late failure")
        yield rec.upper()

    w = World()
    w.begin_attempt()
    w.run(["a", "x", "b"], gen, 3)
    assert w.rows() == ["a", "A", "b", "B"]
    assert w.dead_letters() == [mod.DeadLetter(1, "x", "late failure")]


def test_bug_in_transform_leaves_no_trace_of_its_batch_and_resumes_after_the_fix():
    def buggy(rec):
        if rec == "ccc":
            raise ZeroDivisionError("bug")
        return list(rec)

    w = World()
    w.begin_attempt()
    with pytest.raises(ZeroDivisionError):
        w.run(["a", "bb", "", "ccc", "d"], buggy, 2)
    # batch [0,2) committed; batch [2,4) (which contains the bug) wrote nothing
    assert w.ckpt == 2 and w.rows() == list("abb") and len(w.sink) == 1 and len(w.dead) == 1
    w.run(["a", "bb", "", "ccc", "d"], chars, 2)
    assert w.rows() == list("abbcccd") and w.ckpt == 5


def test_max_batches_allows_incremental_runs():
    w = World()
    w.begin_attempt()
    assert w.run(SOURCE, chars, 2, max_batches=0) == mod.RunReport(0, 0) and w.log == []
    assert w.run(SOURCE, chars, 2, max_batches=1) == mod.RunReport(1, 2)
    assert w.run(SOURCE, chars, 2, max_batches=2) == mod.RunReport(2, 6)
    assert w.run(SOURCE, chars, 2) == mod.RunReport(1, 7)
    assert (w.rows(), w.dead_letters()) == expected(SOURCE, chars)


def test_empty_source_and_oversized_batch():
    w = World()
    w.begin_attempt()
    assert w.run([], chars, 5) == mod.RunReport(0, 0) and w.log == []
    assert w.run(["z"], chars, 1000) == mod.RunReport(1, 1) and w.rows() == ["z"]


def test_invalid_arguments_touch_nothing():
    for kw in ({"batch_size": 0}, {"batch_size": -1}, {"batch_size": 2, "max_batches": -1}):
        w = World()
        w.begin_attempt()
        with pytest.raises(ValueError):
            w.run(SOURCE, chars, **kw)
        assert w.log == [] and w.ckpt == 0
    w = World()
    w.ckpt = 99                                      # checkpoint ahead of the data
    w.begin_attempt()
    with pytest.raises(ValueError):
        w.run(SOURCE, chars, 2)
    assert w.log == []
    w.ckpt = -1
    with pytest.raises(ValueError):
        w.run(SOURCE, chars, 2)


def test_randomised_crash_schedules_always_converge_to_the_clean_result():
    rng = random.Random(34)
    for _ in range(150):
        n = rng.randint(0, 14)
        src = [rng.choice(["", "a", "bc", "!", "def"]) for _ in range(n)]
        exp = expected(src, chars)
        plan = []
        for _ in range(rng.randint(1, 4)):
            bs = rng.randint(1, 6)
            plan.append((bs, (rng.randint(0, 3 * ((n // bs) + 1)), rng.choice(["before", "after"]))))
        plan.append((rng.randint(1, 6), None))
        w = run_with_crashes(src, chars, plan)
        assert (w.rows(), w.dead_letters()) == exp, (src, plan)
