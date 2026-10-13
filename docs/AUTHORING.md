# Authoring guide: adding or changing exercises

This guide is for whoever extends the bank (you, or an AI assistant). The rules protect the
practice experience: **questions never leak answers, stubs are empty, validators check
correctness, and every reference solution is verified by the real grader.**

Exemplars to copy the style from:

| kind | exercise | files |
|---|---|---|
| SQL query mode | SQL-021 | `sql/*/03_gaps_islands_time/SQL-021.*` |
| SQL mutation mode | SQL-046 | `sql/*/05_cdc_data_quality/SQL-046.*` |
| Python pure function | PY-012 | `python/*/02_algorithms/PY-012.*` |
| Python + PostgreSQL | PY-041 | `python/*/05_database_integrations/PY-041.*` |

Read `database/DATA_DICTIONARY.md` (tables, conventions, **fixture catalogue**) before writing
SQL questions.

---

## 1. Files per exercise

### SQL exercise `SQL-NNN` in topic folder `<topic>`

| path | content |
|---|---|
| `sql/checks/catalog/<topic>.yaml` | metadata + validation config (one entry in `exercises:`) |
| `sql/questions/<topic>/SQL-NNN.md` | the question: **no hints, no SQL code blocks, no technique names that give it away** |
| `sql/hints/<topic>/SQL-NNN.md` | exactly `## Hint 1`, `## Hint 2`, `## Hint 3` sections, increasingly specific, still no full answer |
| `sql/stubs/<topic>/SQL-NNN.sql` and `sql/practice/<topic>/SQL-NNN.sql` | **generated**: `python -m lab dev gen-sql-stubs SQL-NNN` |
| `sql/solutions/<topic>/SQL-NNN.sql` | working PostgreSQL 17 reference answer, commented |
| `sql/solutions/<topic>/SQL-NNN_alt.sql` | optional genuinely different approach (different technique, not renamed variables) |
| `sql/explanations/<topic>/SQL-NNN.md` | approach, why edge cases matter, complexity/plan, indexes, production notes, SQL Server/Synapse notes, alternatives, **2–4 follow-ups incl. "at 500M rows"** |
| `sql/checks/adversarial/SQL-NNN.yaml` | hand-written assertions derived from the fixture catalogue, independent of the reference |
| `sql/checks/expected/SQL-NNN.json` | **generated**: `python -m lab dev snapshot SQL-NNN` (small seed) |
| `sql/checks/rubrics/SQL-NNN.md` | required for `plan` and `modeling` modes: a checklist the learner self-grades against |

### Python exercise `PY-NNN` in topic folder `<topic>`

| path | content |
|---|---|
| `python/catalog/<topic>.yaml` | metadata |
| `python/questions/<topic>/PY-NNN.md` | contract (signature, types, semantics), examples, corner cases, complexity expectation. **No implementation code.** A signature block is fine. |
| `python/hints/<topic>/PY-NNN.md` | `## Hint 1..3` |
| `python/stubs/<topic>/PY-NNN.py` | module docstring + imports + signatures + docstrings + `raise NotImplementedError` only. Plain data definitions (dataclass / NamedTuple / Enum / exception classes / constants) are allowed when the contract needs them. **No logic, no algorithm hints.** |
| `python/practice/<topic>/PY-NNN.py` | copy of the stub: `python -m lab dev sync-stubs` creates it if missing |
| `python/solutions/<topic>/PY-NNN.py` (+ `_alt.py`) | reference implementation(s), idiomatic, standard library unless the topic is psycopg |
| `python/explanations/<topic>/PY-NNN.md` | approaches compared, big-O, scale-up (millions of records, streaming, late data, memory), 2–4 follow-ups |
| `python/tests/test_py_NNN.py` | pytest tests (see §5) |
| `python/tests/fixtures/PY-NNN/...` | optional input files (CSV/NDJSON) used by tests |

---

## 2. Catalog entries

### SQL (`sql/checks/catalog/<topic>.yaml`)

```yaml
topic: 03_gaps_islands_time            # must match the folder name
exercises:
  - id: SQL-021
    title: Five consecutive purchase days
    difficulty: medium                 # easy | medium | hard
    estimated_minutes: 20              # realistic interview time
    validation_mode: query             # query | mutation | plan | modeling
    requires_database: true
    tables: [transactions]             # shown in the stub header
    output: [customer_id]              # output column names (stub header); mutation: graded table(s)
    sandbox_tables: [...]              # mutation/plan-sandbox only: tables the setup creates
    prerequisites: [SQL-011]
    tags: [gaps-and-islands, window-functions, dates]
    check:
      ordered: false                   # true ONLY if the question mandates ORDER BY
      decimals: 2                      # rounding used for numeric comparison (default 6)
      compare: exact                   # exact (default) | columns_only (graded by columns + assertions)
      columns: [a, b]                  # required when compare: columns_only
      forbid_patterns:                 # regexes on the attempt (comments stripped)
        - {pattern: "::\\s*date", message: "..."}
      require_patterns:
        - {pattern: "ON\\s+CONFLICT", message: "..."}
      # mutation mode (and plan mode with sandbox: true):
      setup: ["CREATE TABLE ...", "INSERT ..."]   # runs as lab_grader in a fresh sandbox schema
      verify: "SELECT ... FROM sandbox_table"     # mutation: the graded result
      runs: 2                                     # mutation: execute the attempt N times (idempotency)
      # plan mode:
      sandbox: true                               # attempt may CREATE INDEX/ANALYZE on sandbox copies
      plan_expect:
        - {name: "...", pattern: "Index Scan", severity: required}   # or advisory; absent: true inverts
      # modeling mode:
      min_rationale_words: 30
```

Notes:

- **Query mode:** one statement only, run as the read-only `lab_practice` role. The expected
  result must be **non-empty** and should be scoped (dates, stores, customers) so it stays
  below about 3,000 rows.
- **Mutation mode:** setup tables live in the sandbox schema (`search_path = sandbox, public`).
  Copy from `public.*` with `CREATE TABLE x AS SELECT ...`, or write explicit `VALUES` so the
  final state is hand-checkable. The grader role cannot modify `public` tables. Everything is
  rolled back.
- **Plan mode:** the attempt's **last** statement is the analysed `SELECT` (written without
  `EXPLAIN`). `lab check` runs `EXPLAIN (ANALYZE, BUFFERS)` on it.
  - Only use `plan_expect` for robust plan facts, e.g. "an Index/Bitmap scan on X",
    "Subplans Removed" / a single partition scanned, no `Seq Scan on big_table`.
  - Prefer `severity: advisory` when a fact depends on statistics.
  - Never grade elapsed time. Put the interpretation questions in the rubric file.
- **Numeric types:** int/bigint/numeric/float all compare as "number", rounded to `decimals`.
  Column **names must match exactly** (case-insensitive), in order.
- The type categories are number, text, date, timestamptz, timestamp, boolean, json, interval.
  Say in the question which one each output column must be.

### Python (`python/catalog/<topic>.yaml`)

```yaml
topic: 02_algorithms
exercises:
  - id: PY-012
    title: Longest window of distinct status codes (sliding window)
    difficulty: medium
    estimated_minutes: 15
    requires_database: false
    requires_postgres: false           # true => tests use pg fixtures and pytest.mark.requires_postgres
    module: python/practice/02_algorithms/PY-012.py
    functions: [longest_unique_substring]   # public names the tests call (classes too)
    prerequisites: []
    tags: [sliding-window, hashing]
```

---

## 3. Adversarial assertions (`sql/checks/adversarial/SQL-NNN.yaml`)

Write these by hand from the fixture catalogue, never by copying the reference output. Each
`name` is shown to the learner **only when it fails**. Describe the case ("customer 6: 6
purchases on only 4 distinct days"), never the technique.

```yaml
assertions:
  - name: "customer 2 (4-day run) is not reported"
    absent: {customer_id: 2}
  - name: "customer 3 appears exactly once"
    present: {customer_id: 3}
    count: 1
  - name: "customer 23 net spend is 90.00"
    row: {customer_id: 23}
    expect: {net_spend: 90.00}
  - name: "query-mode SQL assertion over your result"
    sql: "SELECT count(*) = 0 FROM ({student}) s WHERE s.amount < 0"   # must return one boolean TRUE
  - name: "mutation-mode SQL assertion over sandbox state"
    sql: "SELECT amount = 99.00 FROM txn_current WHERE business_key = 'FX-0010'"
```

- `present` / `absent` / `row` match on the **result columns** (values are normalised like the
  comparison: numbers rounded, timestamps in UTC ISO format such as `2025-06-15T10:00:00+00:00`,
  dates as `YYYY-MM-DD`, booleans `true`/`false`).
- `{student}` is replaced by the attempt's single statement (query/plan modes). It is not
  available in mutation mode, where `sql` assertions run over the sandbox tables instead.
- `compare: columns_only` checks column names, not types. When a type matters, add an
  assertion such as `SELECT bool_and(pg_typeof(x)::text = 'text') FROM ({student}) s`.
- An assertion that quotes numbers from the *generated* data (counts, revenues, "N customers") only holds on
  the small seed: tag it `profile: small` so it is skipped on medium/large. Assertions about hand-written
  fixtures (customers 1-99, stores 1-5, FX-* CDC keys, ...) hold on every profile and need no tag. Check with
  `lab db seed --size medium` then `lab verify --lang sql`.
- Python tests that touch the database must derive expectations from an oracle query (see PY-044) or use only
  fixture rows, never hard-code IDs of generated rows.
- Aim for 4–10 assertions per exercise. Each should target a specific fixture edge case.

---

## 4. Writing a good question (both languages)

- Start from a **business requirement**: who needs it and why. Do not name the technique
  ("use a window function", "use a heap").
- **Open every question with a `## In plain words` section** (directly after the title/meta line, before the
  business context). It is what the interviewer would actually *say*, plus the essentials, so the learner can
  grasp the task in 15 seconds even under pressure. Format (see SQL-003):

  ```markdown
  ## In plain words

  > "<1-3 spoken sentences, the way an interviewer would phrase it; no jargon beyond the domain words>"

  **You return:** <grain, then the columns/return value (SQL: one row per ...; Python: what the function returns)>

  **The fine print, in short:**
  - <up to 3 bullets restating the rules that are easy to miss: statuses, dates/zones, ties, NULLs, inclusive/exclusive>
  ```

  It must agree exactly with the precise requirements below it, never name the technique (no "use a window
  function / heap / LATERAL"), and stay under about 10 lines. `lab dev lint` fails if it is missing.
- Pin down semantics explicitly:
  - grain;
  - which statuses count;
  - inclusive/exclusive date bounds (always give **fixed** dates, never "today");
  - time zone (UTC by default);
  - NULL handling;
  - tie-breaking;
  - duplicates;
  - rounding;
  - output order (or say "any order").
- Give an **output contract** table (column, type, meaning) and an **illustrative** example
  with made-up IDs/values that differ from the real fixture data.
- List the edge cases the learner must handle (what, not how).
- State constraints: one statement, PostgreSQL 17, time/space expectations, input scale.
- Add a short "clarify before you code" list of questions a strong candidate would ask.
- Keep markdown readable in a terminal: tables, short paragraphs.

### Explanation files must include

1. Approach in plain English (with a small worked table where it helps).
2. Why each edge case matters, referencing the fixture IDs.
3. Complexity / query-plan discussion and indexes worth having.
4. The alternative approach(es) and their trade-offs.
5. Production considerations (idempotency, late data, monitoring, correctness checks).
6. SQL Server / Azure Synapse dialect notes (SQL), or library/runtime notes (Python).
7. **Follow-up questions (2–4)**, including what changes at 500 million rows / millions of
   records / streaming.

---

## 5. Python tests

```python
"""Tests for PY-NNN (imports your practice file by default; see _loader.py)."""
import pytest
from _loader import load

mod = load("PY-NNN")              # NEVER import from python/solutions

def test_example_from_question():
    assert mod.func(...) == ...
```

- At least **3 edge-case tests**; typically 6–15 tests. Include adversarial ones: input that
  breaks plausible-but-wrong implementations (ties, duplicates, empty input, NULL/None,
  boundaries, time zones, very large input).
- A randomised comparison against a tiny brute-force oracle written **inside the test** is
  encouraged. Use a seeded `random.Random(n)`.
- **Never swallow `NotImplementedError`.** If a test expects "any exception", write
  `except NotImplementedError: raise` first, or use `pytest.raises(SpecificError)`. On the
  pristine stub **every** test must fail with `NotImplementedError`. `lab verify` enforces this.
- Test names are neutral (`test_ties_are_deterministic`, not `test_use_heap`).
- Determinism: no wall-clock dependence (inject clocks/sleepers), no network, no real sleeping
  longer than about 50 ms. Threads/asyncio tests must be deterministic. Use `tmp_path` for files.
- Performance assertions only where complexity is the point; use generous limits (e.g. < 2 s).
- PostgreSQL tests: `pytestmark = pytest.mark.requires_postgres`.
  - Use the `pg_readonly` fixture (lab_practice, read-only) or `pg_sandbox` (lab_grader with a
    fresh `lab_sb_*` schema first on the `search_path`; create your own tables there).
  - Never write to `public` tables.
  - When Postgres is down these tests skip, and `lab check` reports INCOMPLETE (never passed).

---

## 6. Workflow and commands

```powershell
$env:LAB_NO_PROGRESS = "1"                     # authors: don't pollute study/progress.json
python -m lab dev gen-sql-stubs SQL-NNN         # after writing the catalog entry
python -m lab dev sync-stubs                    # creates missing python/practice files from stubs
python -m lab dev snapshot SQL-NNN              # writes sql/checks/expected/SQL-NNN.json (small seed)
python -m lab verify SQL-NNN PY-NNN             # reference + alt pass; stubs are NOT ATTEMPTED
python -m lab check SQL-NNN --file <wrong.sql>  # prove plausible wrong answers FAIL
python -m lab dev lint SQL-NNN PY-NNN           # completeness + leakage
python -m lab show SQL-NNN                      # read it as the learner will
```

Rules:

- Never run `lab db seed`, `lab db reset` or `lab db migrate`, and never edit `database/` or
  `lab/`. If a question needs fixture data that does not exist, design around the existing
  fixtures, or report the gap.
- Keep scratch files in `.lab_tmp/` (gitignored).
- Prove at least one plausible **wrong** solution fails for each exercise (e.g. missing DISTINCT,
  wrong boundary, ignoring status, fan-out join), and record what you tried.
