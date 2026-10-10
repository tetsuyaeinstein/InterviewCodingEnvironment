"""Run Python exercise tests with pytest in a subprocess and classify the outcome.

Tests import the implementation through python/tests/_loader.py:
  LAB_IMPL=practice (default) -> python/practice/<topic>/PY-NNN.py
  LAB_IMPL=solution           -> python/solutions/<topic>/PY-NNN.py      (verify mode only)
  LAB_IMPL=solution_alt       -> python/solutions/<topic>/PY-NNN_alt.py  (verify mode only)
  LAB_IMPL_FILE=<path>        -> explicit file for the matching exercise (lab check --file)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT, TMP_DIR
from .exercise_catalog import Exercise
from .sql_validator import ERROR, FAILED, INCOMPLETE, NOT_ATTEMPTED, PASSED, CheckResult

_TEST_RE = re.compile(r"test_py_(\d{3})")


@dataclass
class Case:
    name: str
    outcome: str        # passed | failed | error | skipped
    message: str = ""


def _run(test_files: list[Path], impl: str, impl_file: Path | None, junit: Path, quiet: bool) -> tuple[int, str]:
    env = os.environ.copy()
    env["LAB_IMPL"] = impl
    env.pop("LAB_IMPL_FILE", None)
    if impl_file:
        env["LAB_IMPL_FILE"] = str(Path(impl_file).resolve())
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, "-m", "pytest", *[str(p) for p in test_files], "-q", "--tb=short", "--no-header",
           "-p", "no:cacheprovider", f"--junitxml={junit}", "-o", "junit_family=xunit2", "-rfE"]
    if quiet:
        cmd.append("--tb=no")
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout + proc.stderr


def _parse(junit: Path) -> dict[str, list[Case]]:
    by_ex: dict[str, list[Case]] = defaultdict(list)
    if not junit.exists():
        return by_ex
    root = ET.parse(junit).getroot()
    for tc in root.iter("testcase"):
        ident = f"{tc.get('classname', '')}.{tc.get('name', '')}"
        m = _TEST_RE.search(ident)
        if not m:
            continue
        ex_id = f"PY-{m.group(1)}"
        outcome, message = "passed", ""
        for child in tc:
            if child.tag in ("failure", "error", "skipped"):
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[child.tag]
                message = (child.get("message") or "") + "\n" + (child.text or "")
                break
        by_ex[ex_id].append(Case(tc.get("name", ""), outcome, message.strip()))
    return by_ex


def classify(cases: list[Case]) -> tuple[str, str]:
    if not cases:
        return ERROR, "No tests were collected (syntax error in the file or test module?)."
    passed = [c for c in cases if c.outcome == "passed"]
    bad = [c for c in cases if c.outcome in ("failed", "error")]
    skipped = [c for c in cases if c.outcome == "skipped"]
    if bad and not passed and all("NotImplementedError" in c.message for c in bad):
        return NOT_ATTEMPTED, f"Not attempted: all {len(bad)} test(s) hit NotImplementedError in the practice stub."
    if any(c.name.startswith("python.tests") or "collection" in c.message.lower() for c in bad if c.outcome == "error") and not passed:
        return ERROR, "Test collection failed (syntax/import error in your file)."
    if bad:
        return FAILED, f"{len(passed)}/{len(cases)} tests passed; {len(bad)} failing."
    if skipped:
        reason = skipped[0].message.splitlines()[0] if skipped[0].message else "skipped"
        return INCOMPLETE, f"{len(passed)} passed, {len(skipped)} skipped ({reason}). Skipped tests never count as passed."
    return PASSED, f"all {len(passed)} tests passed"


def check(ex: Exercise, impl: str = "practice", file: Path | None = None, show_output: bool = True) -> CheckResult:
    TMP_DIR.mkdir(exist_ok=True)
    junit = TMP_DIR / f"junit_{ex.id}_{os.getpid()}.xml"
    t0 = time.perf_counter()
    res = CheckResult(ex.id, ERROR, file=file or (ex.practice_path if impl == "practice" else
                                                   ex.solution_path(alt=impl == "solution_alt")))
    if not ex.test_path.exists():
        res.messages = [f"Test file missing: {ex.test_path}"]
        return res
    if impl == "practice" and not (file or ex.practice_path).exists():
        res.messages = [f"Practice file missing: {file or ex.practice_path}  (restore with: python -m lab reset-attempts {ex.id} --confirm)"]
        return res
    try:
        code, output = _run([ex.test_path], impl, file, junit, quiet=False)
        cases = _parse(junit).get(ex.id, [])
    finally:
        junit.unlink(missing_ok=True)
    res.status, summary = classify(cases)
    res.messages = [summary]
    if res.status in (FAILED, ERROR) and show_output:
        res.details.append(_trim_output(output))
    res.elapsed_s = time.perf_counter() - t0
    return res


def check_many(exercises: list[Exercise], impl: str = "practice") -> dict[str, CheckResult]:
    """One pytest process for many exercises (used by check-all / verify)."""
    TMP_DIR.mkdir(exist_ok=True)
    junit = TMP_DIR / f"junit_all_{impl}_{os.getpid()}.xml"
    files = [ex.test_path for ex in exercises if ex.test_path.exists()]
    t0 = time.perf_counter()
    try:
        _run(files, impl, None, junit, quiet=True) if files else (0, "")
        parsed = _parse(junit)
    finally:
        junit.unlink(missing_ok=True)
    elapsed = time.perf_counter() - t0
    out = {}
    for ex in exercises:
        status, summary = classify(parsed.get(ex.id, [])) if ex.test_path.exists() else (ERROR, "test file missing")
        failing = [c.name for c in parsed.get(ex.id, []) if c.outcome in ("failed", "error")]
        r = CheckResult(ex.id, status, elapsed_s=elapsed / max(len(exercises), 1), messages=[summary])
        if failing and status == FAILED:
            r.messages.append("failing: " + ", ".join(failing[:6]) + (" ..." if len(failing) > 6 else ""))
        out[ex.id] = r
    return out


def _trim_output(output: str, limit: int = 120) -> str:
    lines = [ln for ln in output.splitlines() if not ln.startswith("- generated xml file")]
    if len(lines) > limit:
        lines = lines[:limit] + [f"... ({len(lines) - limit} more lines; run pytest directly for full output)"]
    return "\n".join(lines)
