"""Self-tests for the CLI, catalog integrity, leakage rules and progress tracking."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import pytest

from lab import cli, exercise_catalog, progress


def run(capsys, *argv):
    code = cli.main(list(argv))
    out = capsys.readouterr().out
    return code, out


def test_parser_has_documented_commands():
    parser = cli.build_parser()
    for argv in (["db", "status"], ["db", "migrate"], ["db", "seed", "--size", "medium"], ["db", "reset", "--confirm"],
                 ["list", "sql", "--difficulty", "medium"], ["list", "python", "--topic", "algorithms"],
                 ["show", "SQL-021"], ["run", "SQL-021"], ["check", "PY-012"], ["check-all"],
                 ["solution", "PY-012", "--alt"], ["progress"], ["session", "--minutes", "45", "--mix", "sql,python"],
                 ["verify", "--all"], ["reset-attempts", "--all", "--keep-history", "--confirm"], ["hint", "SQL-021", "--level", "2"]):
        parser.parse_args(argv)


def test_catalog_loads_and_ids_are_consistent():
    cat = exercise_catalog.load_catalog()
    assert cat, "catalog is empty"
    for ex_id, ex in cat.items():
        assert exercise_catalog.normalize_id(ex_id) == ex_id
        assert ex.question_path.exists(), ex.question_path
        prefix = "SQL" if ex.lang == "sql" else "PY"
        assert ex_id.startswith(prefix)


@pytest.mark.parametrize("text, expected", [("sql-21", "SQL-021"), ("SQL_021_alt", "SQL-021"), ("test_py_012", "PY-012"),
                                            ("PY-012.py", "PY-012"), ("nothing", None)])
def test_normalize_id(text, expected):
    assert exercise_catalog.normalize_id(text) == expected


def test_list_and_show_do_not_leak_solutions(capsys, isolated_progress):
    code, out = run(capsys, "list", "sql")
    assert code == 0 and "SQL-021" in out
    for ex in exercise_catalog.load_catalog().values():
        code, out = run(capsys, "show", ex.id)
        assert code == 0
        assert not re.search(r"(?m)^#+\s*Hint", out), f"{ex.id}: hints printed by show"
        sol = ex.solution_path()
        if sol.exists():
            markers = ("SELECT", "JOIN", "OVER (", "GROUP BY", "ON CONFLICT", "PARTITION BY",
                       "return ", "for ", "while ", "yield ")
            body = [ln.strip() for ln in sol.read_text(encoding="utf-8").splitlines()
                    if len(ln.strip()) > 30 and not ln.strip().startswith(("--", "#", '"""'))
                    and any(m in ln for m in markers)]
            leaked = [ln for ln in body if ln in out]
            assert not leaked, f"{ex.id}: solution lines visible in show output: {leaked[:2]}"


def test_hint_is_progressive(capsys):
    code, out = run(capsys, "hint", "SQL-021", "--level", "1")
    assert code == 0 and "Hint 1" in out and "Hint 2" not in out
    code, out = run(capsys, "hint", "SQL-021", "--level", "3")
    assert "Hint 3" in out


def test_practice_stubs_are_clean_and_match_stubs():
    for ex in exercise_catalog.load_catalog().values():
        assert ex.stub_path.exists(), ex.stub_path
        if ex.lang == "python":
            assert cli._stub_is_clean(ex.stub_path) == []


def test_unattempted_stub_is_not_recorded_as_passed(isolated_progress):
    cat = exercise_catalog.load_catalog()
    ex = next(iter(cat.values()))
    progress.record_check(ex.id, "not_attempted", 0.1)
    st = progress.summary(cat)[ex.id]
    assert st["status"] != "passed" and st["passes"] == 0


def test_spaced_repetition_rules():
    today = datetime.now(timezone.utc)
    iso = lambda d: (today - timedelta(days=d)).replace(microsecond=0).isoformat()  # noqa: E731
    failed = {"checks": [{"at": iso(0), "status": "failed"}], "logs": []}
    assert progress.state(failed, 20)["next_due"] == today.date() + timedelta(days=1)
    passed_conf5 = {"checks": [{"at": iso(0), "status": "passed"}], "logs": [{"at": iso(0), "confidence": 5}]}
    assert progress.state(passed_conf5, 20)["next_due"] == today.date() + timedelta(days=14)
    slow = {"checks": [{"at": iso(0), "status": "passed"}], "logs": [{"at": iso(0), "confidence": 5, "minutes": 60}]}
    st = progress.state(slow, 20)
    assert st["next_due"] <= today.date() + timedelta(days=2) and "slow" in st["reason"]
    regressed = {"checks": [{"at": iso(3), "status": "passed"}, {"at": iso(0), "status": "failed"}],
                 "logs": [], "first_passed_at": iso(3)}
    assert progress.state(regressed, 20)["status"].startswith("regressed")


def test_session_plan_respects_budget_and_mix(isolated_progress):
    cat = exercise_catalog.load_catalog()
    plan = progress.plan_session(cat, 45, ["sql", "python"], today=date(2026, 1, 1))
    assert plan and sum(ex.estimated_minutes for ex, _ in plan) <= 45
    if any(e.lang == "python" for e in cat.values()) and any(e.lang == "sql" for e in cat.values()):
        assert {ex.lang for ex, _ in plan} == {"sql", "python"} or len(plan) == 1


def test_progress_log_and_reset_attempts_preserve_history(tmp_path, monkeypatch, capsys, isolated_progress):
    ex = exercise_catalog.get("PY-012")
    original = ex.practice_path.read_text(encoding="utf-8")
    monkeypatch.setattr(cli, "STUDY_DIR", tmp_path)
    try:
        ex.practice_path.write_text(original + "\n# my attempt\n", encoding="utf-8")
        code, _ = run(capsys, "reset-attempts", "PY-012")
        assert code == 2 and "my attempt" in ex.practice_path.read_text(encoding="utf-8")  # dry run
        progress.log_session("PY-012", 12, 4, "felt ok")
        code, out = run(capsys, "reset-attempts", "PY-012", "--keep-history", "--confirm")
        assert code == 0 and "archived" in out
        assert ex.practice_path.read_text(encoding="utf-8") == ex.stub_path.read_text(encoding="utf-8")
        archived = list((tmp_path / "attempt_history").rglob("PY-012.py"))
        assert archived and "my attempt" in archived[0].read_text(encoding="utf-8")
        assert progress.load()["exercises"]["PY-012"]["logs"], "progress history must be kept"
    finally:
        ex.practice_path.write_text(original, encoding="utf-8")


def test_python_check_reports_not_attempted_for_stub(isolated_progress):
    from lab import py_checker
    res = py_checker.check(exercise_catalog.get("PY-012"), "practice", exercise_catalog.get("PY-012").stub_path)
    assert res.status == "not_attempted"
