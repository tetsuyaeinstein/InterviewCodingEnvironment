"""`python -m lab ...` — the canonical, cross-platform interface to the interview lab."""
from __future__ import annotations

import argparse
import ast
import filecmp
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from . import exercise_catalog as catalog
from . import progress
from .config import PY_DIR, ROOT, SQL_DIR, STUDY_DIR, rel

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
_STYLE = {"passed": "32", "failed": "31", "error": "31", "not_attempted": "33", "incomplete": "33", "new": "90"}


def paint(text: str, status: str) -> str:
    code = _STYLE.get(status.split()[0] if status else "", "")
    return f"\033[{code}m{text}\033[0m" if _COLOR and code else text


LABEL = {"passed": "PASSED", "failed": "FAILED", "error": "ERROR", "not_attempted": "NOT ATTEMPTED",
         "incomplete": "INCOMPLETE"}


def _table(headers, rows) -> str:
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    out = ["  ".join(h.ljust(w) for h, w in zip(headers, widths)), "  ".join("-" * w for w in widths)]
    out += ["  ".join(c.ljust(w) for c, w in zip(r, widths)) for r in rows]
    return "\n".join(out)


def _exercise(ident: str) -> catalog.Exercise:
    return catalog.get(ident)


# ---------------------------------------------------------------------------
# db
# ---------------------------------------------------------------------------
def cmd_db(args) -> int:
    from . import db
    try:
        if args.db_cmd == "status":
            return db.status()
        if args.db_cmd == "migrate":
            return db.migrate()
        if args.db_cmd == "seed":
            return db.seed(args.size, assume_yes=args.yes)
        if args.db_cmd == "reset":
            return db.reset(args.confirm, args.size)
    except db.LabDBError as e:
        print(e)
        return 1
    return 2


# ---------------------------------------------------------------------------
# browsing
# ---------------------------------------------------------------------------
def cmd_list(args) -> int:
    exs = catalog.filter_exercises(args.lang, args.topic, args.difficulty, args.tag)
    states = progress.summary(catalog.load_catalog())
    rows = []
    for ex in exs:
        st = states[ex.id]["status"]
        rows.append([ex.id, ex.title[:58], ex.area, ex.difficulty, f"{ex.estimated_minutes}m",
                     ex.validation_mode, paint(st, st)])
    if not rows:
        print("No exercises match those filters.")
        return 1
    print(_table(["ID", "Title", "Topic", "Level", "Time", "Mode", "Status"], rows))
    by = Counter(ex.difficulty for ex in exs)
    print(f"\n{len(exs)} exercise(s): " + ", ".join(f"{by[d]} {d}" for d in catalog.DIFFICULTIES if by[d])
          + "   |   python -m lab show <ID>")
    return 0


def cmd_show(args) -> int:
    ex = _exercise(args.id)
    if not ex.question_path.exists():
        print(f"Question file missing: {rel(ex.question_path)}")
        return 1
    print(ex.question_path.read_text(encoding="utf-8").rstrip())
    print("\n" + "-" * 78)
    print(f"{ex.id} | {ex.difficulty} | ~{ex.estimated_minutes} min | mode: {ex.validation_mode}"
          + (f" | prerequisites: {', '.join(ex.prerequisites)}" if ex.prerequisites else ""))
    print(f"Edit : {rel(ex.practice_path)}")
    print(f"Check: python -m lab check {ex.id}" + ("     Run: python -m lab run " + ex.id if ex.lang == "sql" else ""))
    print(f"Stuck? python -m lab hint {ex.id} --level 1   (answers: python -m lab solution {ex.id} — only after trying!)")
    return 0


def cmd_hint(args) -> int:
    ex = _exercise(args.id)
    if not ex.hint_path.exists():
        print("No hints recorded for this exercise.")
        return 1
    text = ex.hint_path.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^##\s*Hint\s*(\d)\s*$", text)
    hints = {int(parts[i]): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    for level in range(1, args.level + 1):
        if level in hints:
            print(f"Hint {level}: {hints[level]}\n")
    if args.level < max(hints or {0: ""}):
        print(f"(more: python -m lab hint {ex.id} --level {args.level + 1})")
    return 0


# ---------------------------------------------------------------------------
# practice: run / check / check-all
# ---------------------------------------------------------------------------
def _resolve_file(ex: catalog.Exercise, file: str | None) -> Path:
    if not file:
        return ex.practice_path
    p = Path(file)
    return p if p.is_absolute() else (Path.cwd() / p)


def cmd_run(args) -> int:
    if not args.id and not args.file:
        print("Usage: python -m lab run SQL-NNN  (or --file path/to/SQL-NNN.sql)")
        return 2
    ex = _exercise(args.id or Path(args.file).name)
    if ex.lang != "sql":
        print(f"`run` executes SQL practice files. For Python use: python -m lab check {ex.id}")
        return 2
    from .sql_validator import run_for_display
    text, code = run_for_display(ex, _resolve_file(ex, args.file))
    print(text)
    return code


def _print_result(ex: catalog.Exercise, res, verbose: bool = True) -> None:
    label = LABEL.get(res.status, res.status.upper())
    print(f"{ex.id}  {ex.title}  [{ex.lang} / {ex.validation_mode}]")
    if res.file:
        print(f"  file   : {rel(res.file)}")
    print(f"  result : {paint(label, res.status)}  ({res.elapsed_s:.2f}s)")
    for m in res.messages:
        print("  " + m.replace("\n", "\n  "))
    if verbose:
        for d in res.details:
            print("\n" + d)
    if res.status == "not_attempted":
        print(f"\n  Open the question with: python -m lab show {ex.id}")
    elif res.status == "passed":
        print(f"\n  Nice. Log it: python -m lab progress log {ex.id} --minutes <m> --confidence <1-5>"
              f"\n  Compare approaches: python -m lab solution {ex.id}" + (" --alt" if ex.has_alt else ""))


def _is_practice(ex: catalog.Exercise, file: Path | None) -> bool:
    if file is None:
        return True
    try:
        return file.exists() and ex.practice_path.exists() and os.path.samefile(file, ex.practice_path)
    except OSError:
        return False


def check_one(ex: catalog.Exercise, file: Path | None, record: bool = True, verbose: bool = True):
    practice = _is_practice(ex, file)
    if ex.lang == "sql":
        from .sql_validator import check
        res = check(ex, file)
    else:
        from .py_checker import check
        res = check(ex, "practice", None if practice else file)
    if record and practice:
        progress.record_check(ex.id, res.status, res.elapsed_s)
    return res


def cmd_check(args) -> int:
    ident = args.id
    file = args.file
    if not ident and not file:
        print("Usage: python -m lab check <ID>  (or --file path/to/attempt)")
        return 2
    if file and not ident:
        ident = Path(file).name
    ex = _exercise(ident)
    path = _resolve_file(ex, file)
    if file and "_alt" in path.stem and ex.lang == "python" and "solutions" in path.parts:
        pass  # checking an alternative reference solution file explicitly is allowed
    res = check_one(ex, path, record=not args.no_record)
    _print_result(ex, res)
    return 0 if res.status == "passed" else 1


def cmd_check_all(args) -> int:
    exs = catalog.filter_exercises(args.lang, args.topic)
    results = {}
    sql_ex = [e for e in exs if e.lang == "sql"]
    py_ex = [e for e in exs if e.lang == "python"]
    if sql_ex:
        from .sql_validator import check
        print(f"Checking {len(sql_ex)} SQL practice file(s) ...", flush=True)
        for ex in sql_ex:
            results[ex.id] = check(ex)
    if py_ex:
        from .py_checker import check_many
        print(f"Running pytest for {len(py_ex)} Python practice file(s) ...", flush=True)
        results.update(check_many(py_ex, "practice"))
    for ex_id, r in results.items():
        if r.status != "not_attempted":
            progress.record_check(ex_id, r.status, r.elapsed_s, source="check-all")
    _summarise(exs, results, show_attempted=True)
    return 0


def _summarise(exs, results, show_attempted=False, title="Summary by category") -> None:
    by_topic = defaultdict(Counter)
    for ex in exs:
        by_topic[(ex.lang, ex.topic)][results[ex.id].status] += 1
    statuses = ["passed", "failed", "error", "incomplete", "not_attempted"]
    rows = [[lang, topic] + [c[s] for s in statuses] for (lang, topic), c in by_topic.items()]
    tot = Counter()
    for c in by_topic.values():
        tot.update(c)
    rows.append(["TOTAL", ""] + [tot[s] for s in statuses])
    print(f"\n{title}")
    print(_table(["Lang", "Topic", "Passed", "Failed", "Error", "Incomplete", "Not attempted"], rows))
    if show_attempted:
        attempted = [(ex, results[ex.id]) for ex in exs if results[ex.id].status != "not_attempted"]
        if attempted:
            print("\nAttempted exercises:")
            for ex, r in attempted:
                print(f"  {ex.id:8s} {paint(LABEL[r.status], r.status):<14s} {r.messages[0].splitlines()[0][:90]}")


# ---------------------------------------------------------------------------
# reference material
# ---------------------------------------------------------------------------
def cmd_solution(args) -> int:
    ex = _exercise(args.id)
    paths = [ex.solution_path(alt=args.alt)]
    if args.explain:
        paths.append(ex.explanation_path)
    if args.alt and not paths[0].exists():
        print(f"{ex.id} has no alternative solution file ({rel(paths[0])}).")
        return 1
    for p in paths:
        print(f"===== {rel(p)} =====")
        if not args.path_only:
            print(p.read_text(encoding="utf-8").rstrip() if p.exists() else "(missing)")
        print()
    extra = []
    if not args.alt and ex.has_alt:
        extra.append(f"--alt for the alternative approach")
    if not args.explain:
        extra.append("--explain for the explanation, trade-offs and follow-ups")
    if extra:
        print("Also available: " + "; ".join(extra))
    return 0


def cmd_verify(args) -> int:
    """Run every reference (and alternative) solution through the real validators, and confirm
    that untouched practice stubs are NOT reported as passing."""
    if args.ids:
        exs = [_exercise(i) for i in args.ids]
    else:
        exs = catalog.filter_exercises(args.lang, args.topic)
    failures = 0
    rows = []
    sql_ex = [e for e in exs if e.lang == "sql"]
    py_ex = [e for e in exs if e.lang == "python"]
    if sql_ex:
        from .sql_validator import check
        for ex in sql_ex:
            for alt in (False, True):
                p = ex.solution_path(alt)
                if not p.exists():
                    if not alt:
                        rows.append([ex.id, "solution", "MISSING"]); failures += 1
                    continue
                r = check(ex, p)
                ok = r.status == "passed"
                failures += not ok
                rows.append([ex.id, p.name, paint(LABEL.get(r.status, r.status), r.status)
                             + ("" if ok else "  " + r.messages[0].splitlines()[0][:80])])
                if not ok and args.verbose:
                    print("\n".join(r.messages))
            stub = check(ex, ex.stub_path if ex.stub_path.exists() else ex.practice_path)
            if stub.status == "passed":
                failures += 1
                rows.append([ex.id, "stub", paint("STUB PASSES (bug)", "failed")])
    if py_ex:
        from .py_checker import check_many
        for impl in ("solution", "solution_alt"):
            targets = [e for e in py_ex if impl == "solution" or e.has_alt]
            for ex_id, r in check_many(targets, impl).items():
                ok = r.status == "passed"
                failures += not ok
                rows.append([ex_id, impl, paint(LABEL.get(r.status, r.status), r.status)
                             + ("" if ok else "  " + " | ".join(r.messages)[:100])])
        stub_targets = [e for e in py_ex if e.stub_path.exists()]
        for ex in stub_targets:  # every pristine stub must be cleanly NOT ATTEMPTED (no test passes on it)
            from .py_checker import check as py_check
            r = py_check(ex, "practice", ex.stub_path, show_output=False)
            if r.status != "not_attempted":
                failures += 1
                rows.append([ex.id, "stub", paint(f"STUB IS {LABEL.get(r.status, r.status)} (tests must fail with "
                                                  f"NotImplementedError on the stub)", "failed") + "  " + r.messages[0][:60]])
    rows.sort(key=lambda r: (r[0][:2] != "SQ", r[0], r[1]))
    print(_table(["Exercise", "Implementation", "Result"], rows))
    n_ok = sum(1 for r in rows if "PASSED" in r[2])
    print(f"\nReference implementations passing: {n_ok}/{len(rows)}. Failures: {failures}.")
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# progress / session / reset
# ---------------------------------------------------------------------------
def cmd_progress(args) -> int:
    cat = catalog.load_catalog()
    if args.progress_cmd == "log":
        ex = _exercise(args.id)
        entry = progress.log_session(ex.id, args.minutes, args.confidence, args.notes)
        st = progress.summary(cat)[ex.id]
        print(f"Logged {ex.id}: {entry}. Next review: {st['next_due']} ({st.get('reason', '')})")
        return 0
    if args.progress_cmd == "clear":
        if not args.confirm:
            print("Refusing to clear progress history without --confirm (practice files are never touched).")
            return 2
        n = progress.clear([_exercise(i).id for i in args.ids] if args.ids else None)
        print(f"Cleared progress for {n} exercise(s). Practice files untouched.")
        return 0
    states = progress.summary(cat)
    by = defaultdict(Counter)
    for ex_id, ex in cat.items():
        st = states[ex_id]
        key = "passed" if st["status"] == "passed" else "new" if st["status"] == "new" else "attempted"
        by[(ex.lang, ex.topic)][key] += 1
    rows = [[lang, topic, c["passed"], c["attempted"], c["new"]] for (lang, topic), c in sorted(by.items())]
    print(_table(["Lang", "Topic", "Passed", "Attempted (not passed)", "New"], rows))
    today = date.today()
    due = [(ex_id, st) for ex_id, st in states.items() if st["next_due"] and st["next_due"] <= today]
    print(f"\nDue for review today ({len(due)}):")
    for ex_id, st in sorted(due, key=lambda t: t[1]["next_due"]):
        print(f"  {ex_id:8s} {cat[ex_id].title[:55]:55s} {st['reason']}")
    total_passed = sum(1 for s in states.values() if s["status"] == "passed")
    print(f"\n{total_passed}/{len(cat)} exercises currently passing. Data: {rel(progress.PROGRESS_FILE)}")
    return 0


def cmd_session(args) -> int:
    langs = [x.strip().lower() for x in args.mix.split(",") if x.strip()]
    langs = ["python" if x in ("py", "python") else "sql" for x in langs]
    cat = catalog.load_catalog()
    plan = progress.plan_session(cat, args.minutes, langs)
    if not plan:
        print("Nothing to schedule - everything is passed and not yet due. Try a timed mock (study/8_WEEK_PLAN.md).")
        return 0
    print(f"Suggested {args.minutes}-minute session ({', '.join(langs)}), start with a 10-minute typing warm-up:")
    total = 0
    for i, (ex, why) in enumerate(plan, 1):
        total += ex.estimated_minutes
        print(f"  {i}. {ex.id:8s} ~{ex.estimated_minutes:>2}m  {ex.difficulty:6s} {ex.title[:52]:52s} [{why}]")
    print(f"Planned: {total} min. For each: python -m lab show <ID>  ->  edit practice file  ->  python -m lab check <ID>")
    print("Time yourself; afterwards: python -m lab progress log <ID> --minutes <m> --confidence <1-5> --notes \"...\"")
    return 0


def _select(args) -> list[catalog.Exercise]:
    if args.all:
        return list(catalog.load_catalog().values())
    if args.topic:
        return catalog.filter_exercises(None, args.topic)
    return [_exercise(i) for i in args.ids]


def cmd_reset_attempts(args) -> int:
    exs = _select(args)
    if not exs:
        print("Choose exercises: IDs, --topic <name> or --all.")
        return 2
    changed = [ex for ex in exs if ex.practice_path.exists() and ex.stub_path.exists()
               and not filecmp.cmp(ex.practice_path, ex.stub_path, shallow=False)]
    missing = [ex for ex in exs if not ex.practice_path.exists()]
    if not args.confirm:
        print(f"Would reset {len(changed)} edited practice file(s) and restore {len(missing)} missing one(s). "
              "Add --confirm to do it" + (" (with --keep-history to archive your attempts first)." if changed else "."))
        for ex in changed[:20]:
            print(f"  {rel(ex.practice_path)}")
        return 2
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    hist = STUDY_DIR / "attempt_history" / stamp
    for ex in changed:
        if args.keep_history:
            dest = hist / ex.practice_path.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ex.practice_path, dest)
        shutil.copyfile(ex.stub_path, ex.practice_path)
    for ex in missing:
        ex.practice_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ex.stub_path, ex.practice_path)
    msg = f"Reset {len(changed)} practice file(s); restored {len(missing)} missing."
    if args.keep_history and changed:
        msg += f" Previous attempts archived under {rel(hist)}."
    if args.clear_progress:
        n = progress.clear([ex.id for ex in exs])
        msg += f" Cleared progress history for {n} exercise(s)."
    else:
        msg += " Progress history kept (use --clear-progress to drop it)."
    print(msg)
    return 0


# ---------------------------------------------------------------------------
# dev (maintainer) commands
# ---------------------------------------------------------------------------
def cmd_dev(args) -> int:
    if args.dev_cmd == "snapshot":
        return _dev_snapshot(args)
    if args.dev_cmd == "build-banks":
        return _dev_build_banks()
    if args.dev_cmd == "lint":
        return _dev_lint(args.ids)
    if args.dev_cmd == "gen-sql-stubs":
        return _dev_gen_sql_stubs(args.ids)
    if args.dev_cmd == "sync-stubs":
        n = 0
        for ex in catalog.load_catalog().values():
            if ex.stub_path.exists() and not ex.practice_path.exists():
                ex.practice_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ex.stub_path, ex.practice_path)
                n += 1
        print(f"Created {n} missing practice file(s) from stubs.")
        return 0
    return 2


_SQL_RULES = {
    "query": "ONE read-only SELECT/WITH statement (PostgreSQL 17). Output columns exactly as specified.",
    "modeling": "ONE read-only SELECT/WITH statement + fill in the RATIONALE comment block (>= 30 words).",
    "plan": "Write the query WITHOUT the EXPLAIN keyword - `lab check` runs EXPLAIN (ANALYZE, BUFFERS) for you.",
    "plan_sandbox": "Runs in a disposable sandbox schema (rolled back). You may CREATE INDEX / ANALYZE first; "
                    "the LAST statement must be the SELECT being analysed (no EXPLAIN keyword).",
    "mutation": "Your statements run in a disposable sandbox schema that is rolled back afterwards. "
                "Write the DML/DDL only - no BEGIN/COMMIT.",
}


def render_sql_stub(ex: catalog.Exercise) -> str:
    mode = ex.validation_mode
    key = "plan_sandbox" if mode == "plan" and ex.check.get("sandbox") else mode
    tables = ", ".join(ex.meta.get("tables") or []) or "(see question)"
    output = ", ".join(ex.meta.get("output") or []) or "(see question)"
    sandbox = ex.meta.get("sandbox_tables")
    lines = [
        "-- " + "=" * 77,
        f"-- {ex.id} | {ex.title}",
        f"-- Level: {ex.difficulty} | Target time: ~{ex.estimated_minutes} min | Mode: {mode}",
        f"-- Question: {rel(ex.question_path)}   (python -m lab show {ex.id})",
        f"-- Tables  : {tables}",
    ]
    if sandbox:
        lines.append(f"-- Sandbox : {', '.join(sandbox)}  (created for you inside the sandbox schema)")
    lines += [
        f"-- Output  : {output}" if mode != "mutation" else f"-- Graded  : final state of {output}",
        f"-- Run     : python -m lab run {ex.id}        Check: python -m lab check {ex.id}",
        f"-- Rules   : {_SQL_RULES[key]}",
        "-- " + "=" * 77,
        "",
        "-- >>> Write your answer below this line >>>",
        "",
        "",
        "",
        "-- <<< end of answer <<<",
        "",
    ]
    if mode == "modeling":
        lines += ["-- RATIONALE:", "--", "--", ""]
    return "\n".join(lines)


def _dev_gen_sql_stubs(ids: list[str] | None = None) -> int:
    n_new = n_upd = 0
    wanted = {catalog.normalize_id(i) for i in ids} if ids else None
    for ex in catalog.load_catalog().values():
        if ex.lang != "sql" or (wanted and ex.id not in wanted):
            continue
        text = render_sql_stub(ex)
        old_stub = ex.stub_path.read_text(encoding="utf-8") if ex.stub_path.exists() else None
        ex.stub_path.parent.mkdir(parents=True, exist_ok=True)
        ex.stub_path.write_text(text, encoding="utf-8", newline="\n")
        practice = ex.practice_path
        if not practice.exists() or (old_stub is not None and practice.read_text(encoding="utf-8") == old_stub):
            practice.parent.mkdir(parents=True, exist_ok=True)
            n_new += not practice.exists()
            n_upd += practice.exists()
            practice.write_text(text, encoding="utf-8", newline="\n")
    print(f"SQL stubs regenerated; practice files created: {n_new}, refreshed (unedited): {n_upd}.")
    return 0


def _dev_snapshot(args) -> int:
    from .sql_validator import _Abort, current_seed, write_snapshot
    seed = current_seed()
    if not seed or seed.get("profile") != "small":
        print("Snapshots must be taken on the SMALL seed: python -m lab db seed --size small")
        return 2
    exs = [e for e in catalog.load_catalog().values() if e.lang == "sql"] if args.all else [_exercise(i) for i in args.ids]
    bad = 0
    for ex in exs:
        if ex.check.get("compare", "exact") != "exact":
            print(f"  {ex.id}: compare={ex.check.get('compare')} (no snapshot needed)")
            continue
        try:
            canon = write_snapshot(ex, seed)
            note = "" if canon.rows else "  WARNING: empty result - fixtures must make the expected output non-empty"
            bad += not canon.rows
            print(f"  {ex.id}: {len(canon.rows):,} rows -> {rel(ex.expected_path)}{note}")
        except _Abort as e:
            bad += 1
            print(f"  {ex.id}: FAILED to snapshot: {e.message}")
    return 1 if bad else 0


def _dev_build_banks() -> int:
    cat = catalog.load_catalog()
    for lang, base, topics, title in (("sql", SQL_DIR, catalog.SQL_TOPICS, "SQL"), ("python", PY_DIR, catalog.PY_TOPICS, "Python")):
        exs = [e for e in cat.values() if e.lang == lang]
        diff = Counter(e.difficulty for e in exs)
        lines = [f"# {title} Question Bank", "",
                 "<!-- Generated by `python -m lab dev build-banks` from the catalog. Do not edit by hand. -->", "",
                 f"{len(exs)} exercises - {diff['easy']} easy / {diff['medium']} medium / {diff['hard']} hard. "
                 "This index contains **no answers or hints**.", "",
                 "Workflow: `python -m lab show <ID>` -> edit the practice file -> `python -m lab check <ID>`"
                 + (" (or `python -m lab run <ID>` to just execute)" if lang == "sql" else "") + ".", ""]
        for topic in topics:
            tex = [e for e in exs if e.topic == topic]
            if not tex:
                continue
            lines += [f"## {topic.replace('_', ' ', 1).replace('_', ' ').title()}", "",
                      "| ID | Question | Level | Time | Mode | Tags |", "|---|---|---|---|---|---|"]
            for e in tex:
                qrel = e.question_path.relative_to(base).as_posix()
                mode = e.validation_mode + (" + postgres" if lang == "python" and e.requires_postgres else "")
                lines.append(f"| [{e.id}]({qrel}) | {e.title} | {e.difficulty} | {e.estimated_minutes} min | {mode} | "
                             f"{', '.join(e.tags)} |")
            lines.append("")
        (base / "QUESTION_BANK.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote {rel(base / 'QUESTION_BANK.md')} ({len(exs)} exercises)")
    return 0


def _stub_is_clean(path: Path) -> list[str]:
    """A Python stub may contain only imports, docstrings, signatures, constants and `raise NotImplementedError`."""
    issues = []
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def body_ok(body) -> bool:
        stmts = [s for s in body if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant))]
        return all(isinstance(s, (ast.Raise, ast.Pass)) for s in stmts) and any(isinstance(s, ast.Raise) for s in stmts)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("__") and node.name not in ("__init__", "__call__", "__iter__", "__next__",
                                                                "__enter__", "__exit__", "__len__", "__contains__"):
                continue
            if not body_ok(node.body):
                issues.append(f"{rel(path)}: function {node.name}() has an implementation (stubs must only raise NotImplementedError)")
    return issues


def _dev_lint(ids: list[str] | None = None) -> int:
    from .sql_runner import is_blank
    cat = catalog.load_catalog()
    wanted = {catalog.normalize_id(i) for i in ids} if ids else None
    issues = []
    for ex in cat.values():
        if wanted and ex.id not in wanted:
            continue
        required = [ex.question_path, ex.hint_path, ex.stub_path, ex.practice_path, ex.solution_path(), ex.explanation_path]
        required += [ex.test_path] if ex.lang == "python" else []
        if ex.lang == "sql" and ex.check.get("compare", "exact") == "exact":
            required.append(ex.expected_path)
        if ex.lang == "sql" and ex.validation_mode in ("plan", "modeling"):
            required.append(ex.rubric_path)
        issues += [f"{ex.id}: missing {rel(p)}" for p in required if not p.exists()]
        if ex.question_path.exists():
            q = ex.question_path.read_text(encoding="utf-8")
            if re.search(r"```\s*sql", q, re.I) and ex.lang == "sql":
                issues.append(f"{ex.id}: question contains a ```sql block (possible answer leak)")
            if re.search(r"(?m)^#+\s*Hint", q):
                issues.append(f"{ex.id}: question contains hints (move them to {rel(ex.hint_path)})")
        if ex.lang == "sql" and ex.stub_path.exists() and not is_blank(ex.stub_path.read_text(encoding="utf-8")):
            issues.append(f"{ex.id}: SQL stub contains executable SQL")
        if ex.lang == "python" and ex.stub_path.exists():
            issues += _stub_is_clean(ex.stub_path)
    n_alt = Counter(ex.lang for ex in cat.values() if ex.has_alt)
    diff = Counter(ex.difficulty for ex in cat.values())
    print(f"Catalog: {sum(1 for e in cat.values() if e.lang == 'sql')} SQL + "
          f"{sum(1 for e in cat.values() if e.lang == 'python')} Python exercises; "
          f"alternative solutions: {n_alt['sql']} SQL, {n_alt['python']} Python; "
          f"difficulty: {dict(diff)}")
    for i in issues:
        print("  " + i)
    print("lint: OK" if not issues else f"lint: {len(issues)} issue(s)")
    return 1 if issues else 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m lab", description="Senior Data Engineer interview lab")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("db", help="database: status | migrate | seed | reset")
    dsub = d.add_subparsers(dest="db_cmd", required=True)
    dsub.add_parser("status", help="connectivity, migrations, seed profile")
    dsub.add_parser("migrate", help="apply idempotent migrations and ensure lab roles")
    s = dsub.add_parser("seed", help="full deterministic reseed (TRUNCATE + load)")
    s.add_argument("--size", choices=["small", "medium", "large"], default="small")
    s.add_argument("--yes", action="store_true", help="confirm the large profile")
    r = dsub.add_parser("reset", help="drop + recreate all lab tables in the LOCAL db, migrate and seed")
    r.add_argument("--confirm", action="store_true")
    r.add_argument("--size", choices=["small", "medium", "large"], default="small")
    d.set_defaults(func=cmd_db)

    ls = sub.add_parser("list", help="browse exercises")
    ls.add_argument("lang", nargs="?", choices=["sql", "python"])
    ls.add_argument("--topic")
    ls.add_argument("--difficulty", choices=catalog.DIFFICULTIES)
    ls.add_argument("--tag")
    ls.set_defaults(func=cmd_list)

    sh = sub.add_parser("show", help="print a question (no hints, no answers)")
    sh.add_argument("id")
    sh.set_defaults(func=cmd_show)

    h = sub.add_parser("hint", help="progressive hints")
    h.add_argument("id")
    h.add_argument("--level", type=int, default=1, choices=[1, 2, 3])
    h.set_defaults(func=cmd_hint)

    ru = sub.add_parser("run", help="execute your SQL practice file and show the result")
    ru.add_argument("id", nargs="?")
    ru.add_argument("--file", help="run a different file for this exercise (ID inferred from the name if omitted)")
    ru.set_defaults(func=cmd_run)

    c = sub.add_parser("check", help="grade your practice attempt")
    c.add_argument("id", nargs="?")
    c.add_argument("--file", help="grade a different file (e.g. the VS Code current file)")
    c.add_argument("--no-record", action="store_true", help="do not record in study/progress.json")
    c.set_defaults(func=cmd_check)

    ca = sub.add_parser("check-all", help="grade every practice file; summary by category")
    ca.add_argument("--lang", choices=["sql", "python"])
    ca.add_argument("--topic")
    ca.set_defaults(func=cmd_check_all)

    so = sub.add_parser("solution", help="show reference solution (opt-in spoiler)")
    so.add_argument("id")
    so.add_argument("--alt", action="store_true", help="alternative approach")
    so.add_argument("--explain", action="store_true", help="also print the explanation")
    so.add_argument("--path-only", action="store_true")
    so.set_defaults(func=cmd_solution)

    v = sub.add_parser("verify", help="verify reference solutions pass and stubs do not")
    v.add_argument("ids", nargs="*")
    v.add_argument("--lang", choices=["sql", "python"])
    v.add_argument("--topic")
    v.add_argument("--all", action="store_true", help="(default when no IDs are given)")
    v.add_argument("--verbose", action="store_true")
    v.set_defaults(func=cmd_verify)

    pr = sub.add_parser("progress", help="progress summary, logging and history")
    psub = pr.add_subparsers(dest="progress_cmd")
    lg = psub.add_parser("log", help="record minutes / confidence / notes for an exercise")
    lg.add_argument("id")
    lg.add_argument("--minutes", type=float)
    lg.add_argument("--confidence", type=int, choices=[1, 2, 3, 4, 5])
    lg.add_argument("--notes")
    cl = psub.add_parser("clear", help="clear progress history (never touches practice files)")
    cl.add_argument("ids", nargs="*")
    cl.add_argument("--confirm", action="store_true")
    pr.set_defaults(func=cmd_progress)

    se = sub.add_parser("session", help="suggest a practice session")
    se.add_argument("--minutes", type=int, default=45)
    se.add_argument("--mix", default="sql,python")
    se.set_defaults(func=cmd_session)

    ra = sub.add_parser("reset-attempts", help="restore practice files to empty stubs")
    ra.add_argument("ids", nargs="*")
    ra.add_argument("--topic")
    ra.add_argument("--all", action="store_true")
    ra.add_argument("--keep-history", action="store_true", help="archive current attempts to study/attempt_history/")
    ra.add_argument("--clear-progress", action="store_true", help="also drop progress history for these exercises")
    ra.add_argument("--confirm", action="store_true")
    ra.set_defaults(func=cmd_reset_attempts)

    dv = sub.add_parser("dev", help="maintainer tools: snapshot | build-banks | lint | sync-stubs")
    dsub2 = dv.add_subparsers(dest="dev_cmd", required=True)
    sn = dsub2.add_parser("snapshot", help="regenerate expected results from reference solutions (small seed)")
    sn.add_argument("ids", nargs="*")
    sn.add_argument("--all", action="store_true")
    dsub2.add_parser("build-banks", help="regenerate sql/ and python/ QUESTION_BANK.md")
    li = dsub2.add_parser("lint", help="check completeness and answer leakage")
    li.add_argument("ids", nargs="*")
    dsub2.add_parser("sync-stubs", help="create missing practice files from stubs")
    gs = dsub2.add_parser("gen-sql-stubs", help="(re)generate SQL stubs from catalog metadata; never overwrites edited practice files")
    gs.add_argument("ids", nargs="*")
    dv.set_defaults(func=cmd_dev)
    return p


def main(argv: list[str] | None = None) -> int:
    if os.name == "nt":  # make the Windows console render UTF-8 question files correctly
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except (AttributeError, OSError):
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except catalog.CatalogError as e:
        print(e)
        return 2
    except KeyboardInterrupt:
        return 130
