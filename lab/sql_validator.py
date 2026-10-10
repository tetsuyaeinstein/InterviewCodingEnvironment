"""SQL exercise validation.

Modes (catalog field ``validation_mode``):
  query     one read-only statement as lab_practice; exact column names + type categories,
            row multiset (or ordered list when check.ordered) compared to the expected result.
  mutation  statements run as lab_grader inside a disposable lab_sb_* schema after the
            catalog ``setup`` SQL; the ``verify`` query's result is compared; always rolled back.
            ``runs: 2`` executes the attempt twice (idempotency).
  plan      result checked like query mode, then EXPLAIN (ANALYZE, BUFFERS) is captured and
            objective plan facts are checked; interpretation is graded manually via a rubric.
  modeling  query mode + a written "-- RATIONALE:" comment block, graded with a rubric.

Expected results: sql/checks/expected/<ID>.json is a canonical snapshot taken from the reference
solution on the SMALL seed. If the database holds a different seed (medium/large), the reference
solution is executed live instead. Independent hand-written assertions in
sql/checks/adversarial/<ID>.yaml are always evaluated.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import psycopg
import yaml

from . import db
from .exercise_catalog import Exercise
from .sql_runner import (QueryResult, ResultTooLarge, Statement, comment_text, execute, format_db_error,
                         format_table, is_blank, split_statements)

PASSED, FAILED, NOT_ATTEMPTED, ERROR, INCOMPLETE = "passed", "failed", "not_attempted", "error", "incomplete"

NUMBER_TYPES = {"int2", "int4", "int8", "numeric", "float4", "float8", "oid", "money"}
TEXT_TYPES = {"text", "varchar", "bpchar", "name", "char", "citext", "unknown"}
CATEGORY = {"date": "date", "timestamptz": "timestamptz", "timestamp": "timestamp", "bool": "boolean",
            "json": "json", "jsonb": "json", "interval": "interval", "time": "time", "uuid": "text"}
DEFAULT_DECIMALS = 6
WRITE_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP", "ALTER", "TRUNCATE", "UPSERT", "REPLACE"}

FORBIDDEN_ALWAYS = re.compile(
    r"^\s*(BEGIN|START|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|END|ABORT|PREPARE|DISCARD|RESET|LISTEN|NOTIFY|"
    r"SET\s+(SESSION\s+AUTHORIZATION|ROLE)|SET\s+(LOCAL\s+)?(search_path|role|session_authorization)\b|"
    r"ALTER\s+(SYSTEM|ROLE|DATABASE|DEFAULT)|CREATE\s+(DATABASE|ROLE|USER|EXTENSION)|DROP\s+(DATABASE|SCHEMA|ROLE|OWNED)|"
    r"GRANT|REVOKE|COPY|DO|CALL|VACUUM|CHECKPOINT|LOAD|SECURITY|REASSIGN)\b",
    re.IGNORECASE)


def category(type_name: str) -> str:
    if type_name in NUMBER_TYPES:
        return "number"
    if type_name in TEXT_TYPES:
        return "text"
    if type_name.startswith("_"):
        return "array"
    return CATEGORY.get(type_name, type_name)


def canon_value(v, cat: str, decimals: int):
    """Canonical, JSON-serialisable representation used for comparison and snapshots."""
    if v is None:
        return None
    if cat == "number":
        try:
            d = Decimal(repr(v)) if isinstance(v, float) else Decimal(str(v))
            return f"{d.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP):.{decimals}f}"
        except (InvalidOperation, ValueError):
            return str(v)
    if cat == "timestamptz" and isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if cat == "boolean" or isinstance(v, bool):
        return "true" if v else "false"
    if cat == "json":
        return json.dumps(v, sort_keys=True, separators=(",", ":"))
    if cat == "interval" and isinstance(v, timedelta):
        return f"{Decimal(str(v.total_seconds())).quantize(Decimal('0.000001')):.6f}s"
    if isinstance(v, (list, tuple)):
        return json.dumps([str(x) if x is not None else None for x in v])
    return str(v)


def canon_literal(v, cat: str, decimals: int):
    """Canonicalise a value written by hand in an adversarial YAML file."""
    if v is None:
        return None
    if cat == "number":
        return canon_value(Decimal(str(v)), cat, decimals)
    if cat == "timestamptz":
        if isinstance(v, datetime):
            return canon_value(v if v.tzinfo else v.replace(tzinfo=timezone.utc), cat, decimals)
        return canon_value(datetime.fromisoformat(str(v).replace("Z", "+00:00")), cat, decimals)
    if cat == "date":
        return v.isoformat() if isinstance(v, date) else str(v)
    if cat == "boolean":
        return "true" if (v is True or str(v).lower() in ("true", "t", "1")) else "false"
    if cat == "json":
        return json.dumps(v, sort_keys=True, separators=(",", ":"))
    return str(v)


@dataclass
class Canon:
    columns: list[str]
    categories: list[str]
    rows: list[tuple]

    @classmethod
    def from_result(cls, res: QueryResult, decimals: int) -> "Canon":
        cats = [category(t) for t in res.type_names]
        rows = [tuple(canon_value(v, c, decimals) for v, c in zip(r, cats)) for r in res.rows]
        return cls(res.columns, cats, rows)

    def to_json(self) -> dict:
        return {"columns": [{"name": n, "category": c} for n, c in zip(self.columns, self.categories)],
                "rows": [list(r) for r in self.rows]}

    @classmethod
    def from_json(cls, data: dict) -> "Canon":
        return cls([c["name"] for c in data["columns"]], [c["category"] for c in data["columns"]],
                   [tuple(r) for r in data["rows"]])


@dataclass
class CheckResult:
    exercise_id: str
    status: str
    elapsed_s: float = 0.0
    messages: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)   # long text (plans, rubrics)
    file: Path | None = None
    expected_source: str = ""

    @property
    def passed(self) -> bool:
        return self.status == PASSED


class _Abort(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# ---------------------------------------------------------------------------
# Running an attempt (shared by run / check / verify / snapshot)
# ---------------------------------------------------------------------------
@dataclass
class Execution:
    result: QueryResult | None          # result of the graded query (query/plan/modeling) or verify query (mutation)
    plan: str = ""
    assertion_failures: list[str] = field(default_factory=list)
    sandbox_results: list[QueryResult] = field(default_factory=list)


def _decimals(ex: Exercise) -> int:
    return int(ex.check.get("decimals", DEFAULT_DECIMALS))


def _guard(ex: Exercise, statements: list[Statement]) -> None:
    mode = ex.validation_mode
    for st in statements:
        code = st.code
        if FORBIDDEN_ALWAYS.match(code):
            raise _Abort(ERROR, f"Statement not allowed in the lab runner: {code.split()[0].upper()} ... "
                                "(transaction control, roles, COPY, DO blocks and schema drops are managed by the grader)")
        if mode in ("query", "modeling") and st.keyword in WRITE_KEYWORDS:
            raise _Abort(ERROR, f"This is a read-only query exercise: write a single SELECT/WITH statement (found {st.keyword}).")
        if mode == "plan" and st.keyword == "SET" and not re.match(r"SET\s+LOCAL\s+(enable_\w+|work_mem|random_page_cost|jit)\b", code, re.I):
            raise _Abort(ERROR, "Only SET LOCAL enable_* / work_mem / random_page_cost / jit are allowed in plan exercises.")


def _strip_explain(text: str) -> str:
    return re.sub(r"^\s*EXPLAIN\s*(\([^)]*\)\s*)?(ANALYZE\s+)?(VERBOSE\s+)?", "", text, flags=re.IGNORECASE)


def run_attempt(ex: Exercise, source: str, path: Path | None, *, with_plan: bool = False,
                evaluate_assertions: bool = True) -> Execution:
    """Execute SQL text for an exercise according to its mode. Raises _Abort on user errors."""
    statements = split_statements(source)
    if not statements:
        raise _Abort(NOT_ATTEMPTED, "Practice file is empty (only comments). Write your SQL below the marker and re-run.")
    _guard(ex, statements)
    mode = ex.validation_mode
    cfg = ex.check
    decimals = _decimals(ex)
    use_sandbox = mode == "mutation" or (mode == "plan" and cfg.get("sandbox", False))

    if mode in ("query", "modeling") and len(statements) != 1:
        raise _Abort(ERROR, f"Query exercises expect exactly ONE statement; found {len(statements)}. "
                            "Combine steps with CTEs (WITH ...).")

    current: Statement | None = None
    try:
        if not use_sandbox:
            with db.connect("practice") as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                *prelude, final = statements
                for st in prelude:  # only SET LOCAL enable_* reaches here (plan mode)
                    current = st
                    conn.execute(st.text)
                current = final
                text = _strip_explain(final.text) if mode == "plan" else final.text
                res = execute(conn, text)
                if not res.has_result:
                    raise _Abort(ERROR, "The statement did not return a result set.")
                exe = Execution(res)
                if with_plan:
                    exe.plan = _explain(conn, text)
                if evaluate_assertions:
                    exe.assertion_failures = _sql_assertions(conn, ex, final.text, decimals)
                conn.rollback()
                return exe
        # sandboxed: mutation, or plan exercises that create indexes/tables
        with db.connect("grader") as conn:
            with db.sandbox(conn, ex.id.replace("-", "").lower()):
                for setup_sql in _as_list(cfg.get("setup")):
                    current = None
                    conn.execute(setup_sql)
                runs = int(cfg.get("runs", 1)) if mode == "mutation" else 1
                exe = Execution(None)
                last_res = None
                for _ in range(runs):
                    for st in statements:
                        current = st
                        last_res = execute(conn, _strip_explain(st.text) if mode == "plan" and st is statements[-1] else st.text)
                        exe.sandbox_results.append(last_res)
                current = None
                if mode == "mutation":
                    verify_sql = cfg.get("verify")
                    if not verify_sql:
                        raise _Abort(ERROR, f"{ex.id}: catalog check.verify is missing")
                    exe.result = execute(conn, verify_sql)
                    if evaluate_assertions:
                        exe.assertion_failures = _sql_assertions(conn, ex, None, decimals)
                else:
                    if last_res is None or not last_res.has_result:
                        raise _Abort(ERROR, "The last statement must be the SELECT query being analysed.")
                    exe.result = last_res
                    if with_plan:
                        exe.plan = _explain(conn, _strip_explain(statements[-1].text))
                    if evaluate_assertions:
                        exe.assertion_failures = _sql_assertions(conn, ex, statements[-1].text, decimals)
                return exe
    except _Abort:
        raise
    except ResultTooLarge as e:
        raise _Abort(FAILED, str(e)) from e
    except db.LabDBError as e:
        raise _Abort(ERROR, str(e)) from e
    except psycopg.Error as e:
        raise _Abort(ERROR, format_db_error(e, source, current, path)) from e


def _as_list(v) -> list[str]:
    if not v:
        return []
    return [v] if isinstance(v, str) else list(v)


def _explain(conn, text: str) -> str:
    rows = conn.execute("EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT) " + text).fetchall()
    return "\n".join(r[0] for r in rows)


# ---------------------------------------------------------------------------
# Expected results
# ---------------------------------------------------------------------------
def load_snapshot(ex: Exercise) -> dict | None:
    if not ex.expected_path.exists():
        return None
    return json.loads(ex.expected_path.read_text(encoding="utf-8"))


def current_seed() -> dict | None:
    try:
        with db.connect("practice") as conn:
            return db.seed_info(conn)
    except db.LabDBError:
        return None


def reference_canon(ex: Exercise) -> Canon:
    path = ex.solution_path()
    exe = run_attempt(ex, path.read_text(encoding="utf-8"), path, evaluate_assertions=False)
    return Canon.from_result(exe.result, _decimals(ex))


def expected_canon(ex: Exercise, seed: dict | None) -> tuple[Canon, str]:
    snap = load_snapshot(ex)
    if snap and seed and snap.get("seed_checksum") == seed.get("checksum"):
        return Canon.from_json(snap), f"snapshot ({snap.get('seed_profile')} seed)"
    if not ex.solution_path().exists():
        raise _Abort(ERROR, f"No expected snapshot matches the current seed and no reference solution exists for {ex.id}.")
    why = "no snapshot" if not snap else f"snapshot is for the {snap.get('seed_profile')} seed"
    return reference_canon(ex), f"reference solution on live data ({why})"


def write_snapshot(ex: Exercise, seed: dict) -> Canon:
    canon = reference_canon(ex)
    data = {"id": ex.id, "generated_from": ex.solution_path().name, "seed_profile": seed["profile"],
            "seed_version": seed["seed_version"], "seed_checksum": seed["checksum"],
            "ordered": bool(ex.check.get("ordered", False)), "decimals": _decimals(ex), **canon.to_json()}
    ex.expected_path.parent.mkdir(parents=True, exist_ok=True)
    ex.expected_path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return canon


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------
def _display(v):
    """Human-friendly rendering of a canonical value (drops padding zeros of numbers)."""
    if isinstance(v, str) and re.fullmatch(r"-?\d+\.\d+", v):
        v = v.rstrip("0").rstrip(".")
        return "0" if v in ("-0", "") else v
    return v


def _fmt_rows(columns, rows, limit=10) -> str:
    return format_table(columns, [tuple(_display(v) for v in r) for r in rows], max_rows=limit)


def compare(expected: Canon, actual: Canon, ordered: bool) -> list[str]:
    problems: list[str] = []
    if [c.lower() for c in actual.columns] != [c.lower() for c in expected.columns]:
        problems.append("Column names/order differ.\n"
                        f"  expected: {', '.join(expected.columns)}\n"
                        f"  actual  : {', '.join(actual.columns)}")
        return problems
    type_issues = [f"  {n}: expected {e}, got {a}" for n, e, a in zip(expected.columns, expected.categories, actual.categories)
                   if e != a and not (a == "unknown" or e == "unknown")]
    if type_issues:
        problems.append("Column types differ (type categories):\n" + "\n".join(type_issues))
        return problems
    if not actual.rows:
        problems.append(f"Your query returned 0 rows; expected {len(expected.rows):,}. An empty result never passes.")
        return problems
    if ordered:
        if actual.rows != expected.rows:
            idx = next((i for i, (a, e) in enumerate(zip(actual.rows, expected.rows)) if a != e),
                       min(len(actual.rows), len(expected.rows)))
            msg = [f"Ordered result differs (row counts: expected {len(expected.rows):,}, actual {len(actual.rows):,}); "
                   f"first difference at row {idx + 1}."]
            lo = max(0, idx - 1)
            msg.append("  expected rows around there:\n" + _indent(_fmt_rows(expected.columns, expected.rows[lo:idx + 3])))
            msg.append("  actual rows around there:\n" + _indent(_fmt_rows(actual.columns, actual.rows[lo:idx + 3])))
            if Counter(actual.rows) == Counter(expected.rows):
                msg.append("  (same rows, wrong ORDER BY - this exercise specifies the output order)")
            problems.append("\n".join(msg))
        return problems
    exp_c, act_c = Counter(expected.rows), Counter(actual.rows)
    if exp_c != act_c:
        missing = list((exp_c - act_c).elements())
        extra = list((act_c - exp_c).elements())
        msg = [f"Rows differ: expected {len(expected.rows):,} rows, got {len(actual.rows):,} "
               f"({len(missing):,} missing, {len(extra):,} unexpected)."]
        if missing:
            msg.append("  missing (expected but not returned):\n" + _indent(_fmt_rows(expected.columns, sorted(missing, key=_sort_key))))
        if extra:
            msg.append("  unexpected (returned but not expected):\n" + _indent(_fmt_rows(actual.columns, sorted(extra, key=_sort_key))))
        dupes = [r for r, n in act_c.items() if n > 1 and n > exp_c.get(r, 0)]
        if dupes:
            msg.append(f"  hint: {len(dupes)} row(s) appear more often than expected - check for join fan-out or missing de-duplication.")
        problems.append("\n".join(msg))
    return problems


def _sort_key(row):
    out = []
    for v in row:
        if v is None:
            out.append((0, Decimal(0), ""))
        elif isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v):
            out.append((1, Decimal(v), ""))
        else:
            out.append((2, Decimal(0), str(v)))
    return tuple(out)


def _indent(text: str, pad: str = "    ") -> str:
    return "\n".join(pad + line for line in text.splitlines())


# ---------------------------------------------------------------------------
# Adversarial assertions
# ---------------------------------------------------------------------------
def load_assertions(ex: Exercise) -> list[dict]:
    if not ex.adversarial_path.exists():
        return []
    data = yaml.safe_load(ex.adversarial_path.read_text(encoding="utf-8")) or {}
    return list(data.get("assertions") or [])


def _sql_assertions(conn, ex: Exercise, student_sql: str | None, decimals: int) -> list[str]:
    failures = []
    for a in load_assertions(ex):
        if "sql" not in a:
            continue
        text = a["sql"]
        if "{student}" in text:
            if student_sql is None:
                continue
            text = text.replace("{student}", "\n" + _strip_explain(student_sql) + "\n")
        try:
            conn.execute("SAVEPOINT lab_assert")
            row = conn.execute(text).fetchone()
            conn.execute("RELEASE SAVEPOINT lab_assert")
            ok = bool(row and row[0] is True)
        except psycopg.Error as e:
            conn.execute("ROLLBACK TO SAVEPOINT lab_assert")
            failures.append(f"{a.get('name', 'assertion')}  (could not evaluate: {e.diag.message_primary})")
            continue
        if not ok:
            failures.append(a.get("name", "assertion"))
    return failures


def python_assertions(ex: Exercise, actual: Canon) -> list[str]:
    failures = []
    decimals = _decimals(ex)
    cols = [c.lower() for c in actual.columns]

    def matches(row, where: dict) -> bool:
        for k, v in where.items():
            k = k.lower()
            if k not in cols:
                return False
            i = cols.index(k)
            if row[i] != canon_literal(v, actual.categories[i], decimals):
                return False
        return True

    for a in load_assertions(ex):
        if "sql" in a:
            continue
        name = a.get("name", "assertion")
        if "absent" in a:
            if any(matches(r, a["absent"]) for r in actual.rows):
                failures.append(name)
            continue
        where = a.get("present") or a.get("row") or {}
        hits = [r for r in actual.rows if matches(r, where)]
        if "count" in a and len(hits) != int(a["count"]):
            failures.append(f"{name}  (matching rows: {len(hits)}, expected {a['count']})")
            continue
        if not hits:
            failures.append(name)
            continue
        if "expect" in a:
            if not any(matches(r, a["expect"]) for r in hits):
                got = ", ".join(f"{k}={_display(r[cols.index(k.lower())]) if k.lower() in cols else '?'}"
                                for r in hits[:1] for k in a["expect"])
                failures.append(f"{name}  (got {got})")
    return failures


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def check(ex: Exercise, path: Path | None = None) -> CheckResult:
    path = path or ex.practice_path
    t0 = time.perf_counter()
    res = CheckResult(ex.id, ERROR, file=path)
    try:
        if not path.exists():
            raise _Abort(ERROR, f"File not found: {path}")
        source = path.read_text(encoding="utf-8")
        if is_blank(source):
            raise _Abort(NOT_ATTEMPTED, "Practice file is empty (only comments). Write your SQL below the marker and re-run.")
        cfg = ex.check
        exe = run_attempt(ex, source, path, with_plan=ex.validation_mode == "plan")
        decimals = _decimals(ex)
        actual = Canon.from_result(exe.result, decimals)
        seed = current_seed()
        problems: list[str] = []
        if cfg.get("compare", "exact") == "exact":
            expected, res.expected_source = expected_canon(ex, seed)
            problems += compare(expected, actual, bool(cfg.get("ordered", False)))
        else:  # 'columns_only': graded by column contract + assertions (e.g. hash values)
            expected_cols = cfg.get("columns") or []
            if expected_cols and [c.lower() for c in actual.columns] != [c.lower() for c in expected_cols]:
                problems.append(f"Column names/order differ.\n  expected: {', '.join(expected_cols)}\n  actual  : {', '.join(actual.columns)}")
            if not actual.rows:
                problems.append("Your query returned 0 rows. An empty result never passes.")
            res.expected_source = "column contract + assertions"
        failures = exe.assertion_failures + python_assertions(ex, actual)
        if failures:
            problems.append("Edge-case checks failed:\n" + "\n".join(f"  - {f}" for f in failures))
        problems += _pattern_checks(ex, source)
        if ex.validation_mode == "plan":
            problems += _plan_checks(ex, exe.plan, res)
        if ex.validation_mode == "modeling":
            problems += _rationale_check(ex, source)
        if ex.validation_mode in ("plan", "modeling") and ex.rubric_path.exists():
            res.details.append("Manual rubric (self-assess; not auto-graded):\n" + ex.rubric_path.read_text(encoding="utf-8"))
        res.messages = problems
        res.status = FAILED if problems else PASSED
        if res.status == PASSED:
            res.messages = [f"{len(actual.rows):,} row(s) match the expected result"
                            + (f" (compared against {res.expected_source})" if res.expected_source else "")
                            + (f"; {len(load_assertions(ex))} edge-case assertion(s) passed" if load_assertions(ex) else "")]
    except _Abort as e:
        res.status, res.messages = e.status, [e.message]
    res.elapsed_s = time.perf_counter() - t0
    return res


def _pattern_checks(ex: Exercise, source: str) -> list[str]:
    from .sql_runner import strip_comments
    code = strip_comments(source)
    out = []
    for rule in ex.check.get("forbid_patterns") or []:
        if re.search(rule["pattern"], code, re.IGNORECASE | re.DOTALL):
            out.append(f"Requirement not met: {rule['message']}")
    for rule in ex.check.get("require_patterns") or []:
        if not re.search(rule["pattern"], code, re.IGNORECASE | re.DOTALL):
            out.append(f"Requirement not met: {rule['message']}")
    return out


def _plan_checks(ex: Exercise, plan: str, res: CheckResult) -> list[str]:
    problems = []
    lines = []
    for rule in ex.check.get("plan_expect") or []:
        found = re.search(rule["pattern"], plan, re.IGNORECASE | re.MULTILINE) is not None
        ok = (not found) if rule.get("absent") else found
        sev = rule.get("severity", "required")
        lines.append(f"  [{'ok' if ok else 'MISSING' if sev == 'required' else 'note'}] {rule['name']}")
        if not ok and sev == "required":
            problems.append(f"Plan check failed: {rule['name']}")
    res.details.insert(0, "EXPLAIN (ANALYZE, BUFFERS) of your final query:\n" + _indent(plan, "  "))
    if lines:
        res.details.insert(1, "Objective plan facts:\n" + "\n".join(lines))
    return problems


def _rationale_check(ex: Exercise, source: str) -> list[str]:
    text = comment_text(source)
    m = re.search(r"RATIONALE:(.*)", text, re.IGNORECASE | re.DOTALL)
    words = re.findall(r"[A-Za-z0-9]+", m.group(1)) if m else []
    need = int(ex.check.get("min_rationale_words", 30))
    if len(words) < need:
        return [f"Write your design rationale in the '-- RATIONALE:' comment block (at least {need} words; found {len(words)})."]
    return []


def run_for_display(ex: Exercise, path: Path | None = None) -> tuple[str, int]:
    """`lab run`: execute and print results (no grading). Returns (text, exit_code)."""
    path = path or ex.practice_path
    from .config import settings, rel
    if not path.exists():
        return f"File not found: {path}", 1
    source = path.read_text(encoding="utf-8")
    header = f"Running {rel(path)} [{ex.id}, mode={ex.validation_mode}]"
    try:
        t0 = time.perf_counter()
        exe = run_attempt(ex, source, path, with_plan=ex.validation_mode == "plan", evaluate_assertions=False)
        elapsed = (time.perf_counter() - t0) * 1000
    except _Abort as e:
        return f"{header}\n{e.message}", 0 if e.status == NOT_ATTEMPTED else 1
    out = [header]
    if ex.validation_mode == "mutation":
        out.append(f"Executed in a rolled-back sandbox. State of `verify` query after your statements ({elapsed:.0f} ms):")
    else:
        out.append(f"Result ({elapsed:.0f} ms):")
    r = exe.result
    out.append(format_table(r.columns, r.rows, settings().max_display_rows, r.type_names))
    if exe.plan:
        out.append("\nEXPLAIN (ANALYZE, BUFFERS):\n" + exe.plan)
    return "\n".join(out), 0
