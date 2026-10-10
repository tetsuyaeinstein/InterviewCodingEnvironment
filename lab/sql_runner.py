"""Execute practice SQL safely and present results / errors readably.

Safety model: `lab run` and query-mode checks connect as the SELECT-only `lab_practice` role
in a read-only transaction with a statement timeout, and the transaction is always rolled back.
Mutation/plan exercises run as `lab_grader` inside a disposable lab_sb_* schema that is rolled back.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from .config import rel

# ---------------------------------------------------------------------------
# Lexing helpers (quotes, dollar-quotes, comments)
# ---------------------------------------------------------------------------
_DOLLAR_TAG = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")


def _scan(text: str):
    """Yield (kind, start, end) segments: 'code', 'comment', 'string'."""
    i, n = 0, len(text)
    code_start = 0
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "-" and nxt == "-":
            if code_start < i:
                yield "code", code_start, i
            j = text.find("\n", i)
            j = n if j == -1 else j
            yield "comment", i, j
            i = code_start = j
            continue
        if c == "/" and nxt == "*":
            if code_start < i:
                yield "code", code_start, i
            depth, j = 1, i + 2
            while j < n and depth:
                if text.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif text.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            yield "comment", i, j
            i = code_start = j
            continue
        if c in ("'", '"'):
            if code_start < i:
                yield "code", code_start, i
            j = i + 1
            while j < n:
                if text[j] == c:
                    if j + 1 < n and text[j + 1] == c:  # doubled quote escape
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            yield "string", i, j
            i = code_start = j
            continue
        if c == "$":
            m = _DOLLAR_TAG.match(text, i)
            if m:
                if code_start < i:
                    yield "code", code_start, i
                tag = m.group(0)
                j = text.find(tag, m.end())
                j = n if j == -1 else j + len(tag)
                yield "string", i, j
                i = code_start = j
                continue
        i += 1
    if code_start < n:
        yield "code", code_start, n


def strip_comments(text: str) -> str:
    return "".join(text[s:e] for kind, s, e in _scan(text) if kind != "comment")


def comment_text(text: str) -> str:
    """Concatenated text of all comments (used to read written rationales)."""
    out = []
    for kind, s, e in _scan(text):
        if kind == "comment":
            chunk = text[s:e]
            chunk = chunk[2:] if chunk.startswith("--") else chunk[2:-2]
            out.append(chunk)
    return "\n".join(out)


def is_blank(text: str) -> bool:
    return strip_comments(text).replace(";", "").strip() == ""


@dataclass
class Statement:
    text: str          # statement text without the terminating semicolon
    offset: int        # character offset of the statement start within the source file

    @property
    def keyword(self) -> str:
        code = strip_comments(self.text).strip()
        m = re.match(r"[A-Za-z]+", code)
        return m.group(0).upper() if m else ""

    @property
    def code(self) -> str:
        return strip_comments(self.text).strip()


def split_statements(text: str) -> list[Statement]:
    """Split on top-level semicolons; drop statements that are only comments/whitespace."""
    stmts: list[Statement] = []
    start = 0
    for kind, s, e in _scan(text):
        if kind != "code":
            continue
        pos = text.find(";", s, e)
        while pos != -1:
            stmts.append(Statement(text[start:pos], start))
            start = pos + 1
            pos = text.find(";", start, e)
    stmts.append(Statement(text[start:], start))
    out = []
    for st in stmts:
        lead = len(st.text) - len(st.text.lstrip())
        st = Statement(st.text.strip(), st.offset + lead)
        if not is_blank(st.text):
            out.append(st)
    return out


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
@dataclass
class QueryResult:
    columns: list[str] = field(default_factory=list)
    type_names: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    has_result: bool = False
    status: str = ""
    elapsed_ms: float = 0.0


_TYPE_CACHE: dict[int, str] = {}


def type_name(conn, oid: int) -> str:
    if oid in _TYPE_CACHE:
        return _TYPE_CACHE[oid]
    info = conn.adapters.types.get(oid)
    name = info.name if info else None
    if name is None:
        row = conn.execute("SELECT typname FROM pg_type WHERE oid = %s", (oid,)).fetchone()
        name = row[0] if row else f"oid:{oid}"
    _TYPE_CACHE[oid] = name
    return name


def execute(conn, text: str, max_rows: int = 200_000) -> QueryResult:
    t0 = time.perf_counter()
    cur = conn.execute(text)
    res = QueryResult(status=cur.statusmessage or "")
    if cur.description:
        res.has_result = True
        res.columns = [d.name for d in cur.description]
        res.type_names = [type_name(conn, d.type_code) for d in cur.description]
        res.rows = cur.fetchmany(max_rows + 1)
        if len(res.rows) > max_rows:
            raise ResultTooLarge(f"Query returned more than {max_rows:,} rows; refine your query.")
    res.elapsed_ms = (time.perf_counter() - t0) * 1000
    return res


class ResultTooLarge(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------
def _cell(v) -> str:
    if v is None:
        return "NULL"
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def format_table(columns: list[str], rows: list, max_rows: int = 50, type_names: list[str] | None = None) -> str:
    if not columns:
        return "(statement returned no result set)"
    shown = [[_cell(v) for v in r] for r in rows[:max_rows]]
    header = [f"{c}" for c in columns]
    widths = [len(h) for h in header]
    if type_names:
        widths = [max(w, len(t)) for w, t in zip(widths, type_names)]
    for r in shown:
        widths = [max(w, len(v)) for w, v in zip(widths, r)]
    line = "-+-".join("-" * w for w in widths)
    out = [" | ".join(h.ljust(w) for h, w in zip(header, widths))]
    if type_names:
        out.append(" | ".join(t.ljust(w) for t, w in zip(type_names, widths)))
    out.append(line)
    for r in shown:
        out.append(" | ".join(v.ljust(w) for v, w in zip(r, widths)))
    extra = len(rows) - len(shown)
    out.append(f"({len(rows):,} row{'s' if len(rows) != 1 else ''}{f'; showing first {len(shown)}' if extra > 0 else ''})")
    return "\n".join(out)


def format_db_error(e: psycopg.Error, source: str, statement: Statement | None, path: Path | None) -> str:
    diag = e.diag
    lines = []
    where = f" in {rel(path)}" if path else ""
    state = f" [SQLSTATE {diag.sqlstate}]" if diag.sqlstate else ""
    lines.append(f"Database error{where}{state}: {diag.message_primary or str(e).strip()}")
    if statement is not None and diag.statement_position:
        try:
            pos = int(diag.statement_position) - 1
            abs_pos = statement.offset + pos
            line_no = source.count("\n", 0, abs_pos) + 1
            line_start = source.rfind("\n", 0, abs_pos) + 1
            line_end = source.find("\n", abs_pos)
            line_end = len(source) if line_end == -1 else line_end
            col = abs_pos - line_start
            lines.append(f"  at line {line_no}, column {col + 1}:")
            lines.append(f"    {source[line_start:line_end]}")
            lines.append(f"    {' ' * col}^")
        except (ValueError, TypeError):
            pass
    if diag.message_detail:
        lines.append(f"  detail: {diag.message_detail}")
    if diag.message_hint:
        lines.append(f"  hint:   {diag.message_hint}")
    if diag.sqlstate == "25006":
        lines.append("  note:   query exercises run read-only; data-changing SQL is only allowed in mutation exercises (sandboxed).")
    if diag.sqlstate == "42501":
        lines.append("  note:   the practice/grader roles cannot modify shared tables; mutation exercises work on sandbox copies.")
    if diag.sqlstate == "57014":
        lines.append("  note:   statement timeout hit (LAB_STATEMENT_TIMEOUT_MS). Look for a missing join predicate / fan-out.")
    return "\n".join(lines)
