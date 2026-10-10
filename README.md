# Senior Data Engineer Interview Lab

A local, keyboard-first practice environment for **SQL (PostgreSQL 17)** and **Python** interview
problems:

- **110 exercises** (60 SQL + 50 Python), from entry level to senior/lead depth.
- A Dockerized database with deterministic, fictitious retail/finance data and hand-crafted edge cases.
- Graders that check **correctness**, not just "it ran".
- Reference solutions (often two approaches) with explanations you open only when you choose.
- Spaced-repetition progress tracking, an 8-week plan and interview playbooks.

Nothing leaves your machine: no cloud, no accounts, and all data is synthetic.

> New here? **[QUICKSTART.md](QUICKSTART.md)** gets you from clone to first exercise in about 5 minutes.

## Setup

Prerequisites: Docker Desktop (Compose v2), Python 3.12+, and VS Code (recommended).

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1                 # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install -e ".[dev]"
Copy-Item .env.example .env                  # local-only credentials; optional (defaults match)
docker compose up -d                         # PostgreSQL 17 on localhost:5433
python -m lab db migrate
python -m lab db seed --size small           # ~10 s, deterministic
python -m lab db status
```

If script activation is blocked and you can't change the policy, skip activation and call the
venv interpreter directly: `.\.venv\Scripts\python.exe -m lab db status`. Every command in this
README works that way.

### macOS / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
docker compose up -d
python -m lab db migrate
python -m lab db seed --size small
python -m lab db status
```

`make` is optional (`make up seed check ID=SQL-021`). The Python CLI is the canonical interface.

## Daily practice loop

```bash
python -m lab session --minutes 45 --mix sql,python   # what to do today (due reviews first)
python -m lab list sql --difficulty medium            # browse; also: --topic <name>, --tag <tag>
python -m lab list python --topic algorithms
python -m lab show SQL-021                            # question only: no hints, no answer
#   edit sql/practice/03_gaps_islands_time/SQL-021.sql
python -m lab run SQL-021                             # execute your SQL, see rows or a readable error
python -m lab check SQL-021                           # grade it: diff of missing/unexpected rows + edge cases
python -m lab hint SQL-021 --level 1                  # progressive hints (1-3) if stuck
python -m lab solution SQL-021                        # reference answer (spoiler, opt-in); --alt; --explain
python -m lab progress log SQL-021 --minutes 18 --confidence 4 --notes "forgot DISTINCT first"
python -m lab progress                                # summary + what's due

python -m lab show PY-012                             # Python works the same way
#   edit python/practice/02_algorithms/PY-012.py
python -m lab check PY-012                            # runs pytest against YOUR practice file
python -m lab solution PY-012 --alt
python -m lab check-all                               # everything, summarised by category
```

In VS Code, **Ctrl+Shift+B** runs *Lab: check current file* on whatever practice file is open.
Other tasks (run current SQL file, show question, hint, session, DB start/seed) are under
*Terminal → Run Task…*

### What the graders do

| result | meaning |
|---|---|
| `PASSED` | correct columns, types and rows (or all tests), plus every hand-written edge-case assertion |
| `FAILED` | it ran but is wrong: you see missing/unexpected rows, an order or type mismatch, or failing tests and which edge case broke |
| `ERROR` | SQL error (with line, column and caret) / Python syntax or collection error / disallowed statement |
| `NOT ATTEMPTED` | untouched stub: never counted as done |
| `INCOMPLETE` | some tests skipped (e.g. PostgreSQL not running): never counted as done |

SQL validation modes:

- **query:** your single `SELECT` runs as a read-only role with a timeout. The result is compared
  as a multiset (duplicates matter), or as an ordered list when the question requires an order.
- **mutation:** your DML runs in a throw-away `lab_sb_*` schema that is always rolled back; the
  final table state is graded.
- **plan:** results are checked, `EXPLAIN (ANALYZE, BUFFERS)` is captured, and objective plan
  facts are checked. Interpretation is graded by you against a rubric.
- **modeling:** query plus your written `-- RATIONALE:` block, with a rubric.

## Where things live

| you want… | look in |
|---|---|
| the question (no answers) | `sql/questions/<topic>/SQL-NNN.md`, `python/questions/<topic>/PY-NNN.md`, indexed in `sql/QUESTION_BANK.md` and `python/QUESTION_BANK.md` |
| **the file you edit** | `sql/practice/<topic>/SQL-NNN.sql`, `python/practice/<topic>/PY-NNN.py` |
| hints | `sql/hints/…`, `python/hints/…` (or `lab hint`) |
| reference solutions | `sql/solutions/…/SQL-NNN.sql` (+ `_alt.sql`), `python/solutions/…/PY-NNN.py` (+ `_alt.py`) |
| explanations, trade-offs, follow-ups | `sql/explanations/…`, `python/explanations/…` |
| how answers are checked | `sql/checks/` (catalog, expected results, adversarial assertions, rubrics), `python/tests/` |
| the data | `database/DATA_DICTIONARY.md` (tables, conventions, **fixture catalogue**), `database/migrations/`, `database/seed/` |
| study material | `study/8_WEEK_PLAN.md`, `study/INTERVIEW_PLAYBOOK.md`, `study/SQL_POSTGRES_VS_SQLSERVER.md`, `study/COMMON_PITFALLS.md`, `study/PERFORMANCE_CHECKLIST.md`, `study/PROGRESS.md` |
| extending the bank | `docs/AUTHORING.md` |

Spoiler protection:

- `lab show` prints only the question.
- VS Code search and Quick Open exclude solutions, explanations, hints and checks
  (`.vscode/settings.json`).
- Tests import **your** practice file. Reference code is only imported by `lab verify`, and
  nothing ever copies answers into practice files.

## Database

| command | what it does |
|---|---|
| `docker compose up -d` | start PostgreSQL 17 (`de-lab-postgres`, port **5433**, named volume, health check) |
| `python -m lab db status` | connectivity, migrations, roles, seed profile and checksum |
| `python -m lab db migrate` | apply idempotent migrations; create/update the `lab_grader` and `lab_practice` roles |
| `python -m lab db seed --size small` | full deterministic reload (TRUNCATE + COPY in one transaction): ~21k transactions |
| `python -m lab db seed --size medium` | ~250k transactions, for EXPLAIN/indexing practice (about 1–2 min) |
| `python -m lab db seed --size large --yes` | ~1.5M transactions; opt-in, several minutes, a few GB of disk |
| `python -m lab db reset --confirm` | guarded: local host only, lab DB only. Drops/recreates the lab schema, migrates and seeds small. |

Same profile, same data: the seed uses fixed RNG seeds, a fixed calendar (2024–2025) and fixed
IDs. Nothing depends on today's date. `lab db status` prints a checksum you can compare across
runs. Hand-written edge-case fixtures (customers 1–99, stores 1–5, …) are identical in every
profile.

Expected results are snapshots taken on the **small** profile. On medium/large, `lab check` compares against the reference solution run live. The hand-written edge-case assertions about the fixture customers/stores still apply; the few that quote numbers from the small profile's *generated* data are marked `profile: small` and skipped on other profiles. All 108 SQL reference files and the PostgreSQL-backed Python exercises were verified on both small and medium; a sample (SQL-001/021/041/053/055/059, PY-042/044) also on large.

**Connecting from VS Code:** install the recommended *SQLTools* + *SQLTools PostgreSQL* extensions.
The connection **"Interview Lab (practice, read-only)"** is preconfigured in
`.vscode/settings.json` (localhost:5433, db `interview_lab`, user `lab_practice`). Open any `.sql`
file and run the selection with SQLTools. The credentials in `.env.example` are local-only and
protect only this disposable container.

Roles:

- `lab_practice` is SELECT-only, with read-only sessions. Use it for exploration.
- `lab_grader` can only create disposable sandbox schemas.
- The superuser `lab_admin` is used only by migrate, seed and reset.

## Resetting your work

| goal | command |
|---|---|
| retry an exercise with a blank file, archiving the old attempt | `python -m lab reset-attempts SQL-021 --keep-history --confirm` |
| blank a topic | `python -m lab reset-attempts --topic cdc --keep-history --confirm` |
| everything | `python -m lab reset-attempts --all --keep-history --confirm` |
| clear history too | add `--clear-progress` (or `python -m lab progress clear --confirm`) |
| fresh database | `python -m lab db seed --size small` (or `python -m lab db reset --confirm`) |

Practice files are never overwritten without `--confirm`. Progress history is kept unless you
ask to clear it. See `study/PROGRESS.md` for the spaced-repetition rules.

## Quality checks

```bash
python -m pytest -q             # the lab's self-tests (seed determinism, validators, CLI, leakage)
python -m lab verify            # every reference + alternative solution passes; every stub is NOT ATTEMPTED
python -m lab dev lint          # completeness and answer-leakage checks
python -m lab dev build-banks   # regenerate QUESTION_BANK.md files from the catalog
```

`LAB_SELFTEST_RESEED=1 python -m pytest tests/test_seed_integrity.py` also re-seeds twice and
compares checksums.

## Dependencies and locking

Runtime dependencies are `psycopg[binary]` 3, `PyYAML`, `python-dotenv` and `tzdata`; `pytest`
is a dev dependency (`pyproject.toml`). For a byte-for-byte reproducible environment, install the
pinned set: `python -m pip install -r requirements.lock && python -m pip install -e . --no-deps`.
Regenerate the lock with `python -m pip freeze --exclude-editable > requirements.lock`.

## Troubleshooting

| symptom | fix |
|---|---|
| `Cannot connect to PostgreSQL at localhost:5433` | `docker compose up -d`; wait for `docker compose ps` to show *healthy*; check nothing else uses 5433 (change `LAB_DB_PORT` in `.env` and restart compose) |
| `password authentication failed for user lab_practice` | `python -m lab db migrate` (creates/updates the roles from `.env`) |
| `relation ... does not exist` | `python -m lab db migrate` then `python -m lab db seed --size small` |
| Python tests `INCOMPLETE` | the integration tests need the DB; start it and seed |
| garbled characters in Windows PowerShell 5.1 | use Windows Terminal or the VS Code terminal; the CLI switches the console to UTF-8 |
