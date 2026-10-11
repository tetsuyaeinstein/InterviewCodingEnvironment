# Practice guide: how to use this lab, step by step

This is the one document to follow when you sit down to practise. It covers:

1. starting and stopping the environment;
2. the exact loop for one exercise;
3. **how time works (and what is and isn't measured)**;
4. how progress and spaced repetition work;
5. a daily routine and how to pick what to practise;
6. maintaining and troubleshooting the environment.

Commands are shown for PowerShell. On macOS/Linux they are identical after you activate the venv.
Every command works without activating the venv by using `.\.venv\Scripts\python.exe -m lab ...`.

---

## 1. Start of day: get the environment running

### First time only

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
docker compose up -d
python -m lab db migrate
python -m lab db seed --size small
```

### Every later session

1. **Start Docker Desktop** if it isn't running. After a reboot, the database container restarts
   by itself once Docker is up (it is set to `restart: unless-stopped`).
2. Open the project folder in VS Code, open a terminal (Ctrl+`), and activate the venv:
   `.\.venv\Scripts\Activate.ps1`.
3. Confirm everything is healthy:

   ```powershell
   python -m lab db status
   ```

   Good output: `migrations: 4 applied, 0 pending`, `seed: profile=small ...` and
   `practice role: connects OK, read-only sessions = on`. If it can't connect, run
   `docker compose up -d`, wait about 10 seconds, and try again.

### End of day

Nothing needs to be shut down. If you want to free resources, run `docker compose stop` (keeps all
data), and `docker compose up -d` next time. Commit your work if you use git: your attempts live in
`sql/practice/` and `python/practice/`, and your history is in `study/progress.json`.

---

## 2. The loop for one exercise (SQL or Python)

Use a phone or desk timer for **step 3 onward**. The lab does not time you. See section 3.

| # | step | command / action |
|---|---|---|
| 1 | Choose | `python -m lab session --minutes 45 --mix sql,python` suggests what to do. Or browse: `python -m lab list sql --difficulty easy`, `python -m lab list python --topic algorithms`. The **Time** column is the interview target. |
| 2 | Read | `python -m lab show SQL-001`. Only the question appears: no hints, no answers. |
| 3 | **Start your timer.** Clarify out loud | Say what one output row means, and how you'll treat NULLs, ties, duplicates, time zones and boundaries. The question ends with "Clarify before you code" to help. |
| 4 | Explore the data (SQL) | Look at the tables with SQLTools in VS Code, or `python -m lab run SQL-001 --file scratch.sql` with a throwaway query. Details of every table are in `database/DATA_DICTIONARY.md`. |
| 5 | Type your answer | SQL: `sql/practice/<topic>/SQL-NNN.sql`, below the `>>> Write your answer below` marker. Python: `python/practice/<topic>/PY-NNN.py`, replacing `raise NotImplementedError`. Save the file. |
| 6 | Run (SQL only) | `python -m lab run SQL-001` shows your rows or the database error with line and column. For Python, go straight to `check`. |
| 7 | Check | `python -m lab check SQL-001`, or press **Ctrl+Shift+B** in VS Code with the practice file open. Read the feedback (see below), fix, and repeat. |
| 8 | **Stop your timer** when it says `PASSED` | Note the minutes. |
| 9 | Compare | `python -m lab solution SQL-001 --explain`, then `--alt` for a second approach. Answer one follow-up question from the explanation out loud. |
| 10 | Log | `python -m lab progress log SQL-001 --minutes 15 --confidence 3 --notes "what tripped me up"` |

If you're stuck for more than about 10 minutes: `python -m lab hint SQL-001 --level 1`, then
`--level 2`, then `--level 3`. Hints get more specific each time. If you used a hint, log a
lower confidence.

### Reading the result of `lab check`

| result | what it means | what to do |
|---|---|---|
| `PASSED` | Correct columns, types and rows (or all tests), plus every hand-written edge-case check | log it, then read the solution |
| `FAILED` | It ran but is wrong. You see missing and unexpected rows, or an order/type mismatch, or failing tests, plus the **named edge cases** that broke | the names describe the case, not the fix: look the customers up in the data dictionary |
| `ERROR` | SQL error (with line, column and caret), Python syntax error, or a statement that isn't allowed | fix the error and re-run |
| `NOT ATTEMPTED` | The file is still the empty stub | write your answer |
| `INCOMPLETE` | Some Python tests were skipped (usually the database isn't running) | start the database; skipped never counts as passed |

Example of useful `FAILED` output for SQL-001 with an inner join:

```
Rows differ: expected 2,056 rows, got 2,042 (14 missing, 0 unexpected).
  missing: customer 1, 31, 32, 33, ... (all with 0 spend)
Edge-case checks failed:
  - customer 1 (no transactions at all) is present with 0 transactions and 0.00
```

### The four kinds of SQL exercise

| mode | how to write it | how it is graded |
|---|---|---|
| `query` | one `SELECT`/`WITH` statement | rows compared as an unordered set, or an ordered list when the question requires an order |
| `mutation` | your `INSERT`/`UPDATE`/`DELETE`/DDL, in the practice file | runs in a throw-away schema, rolled back afterwards; the final table state is graded |
| `plan` | the query (never type `EXPLAIN`; the lab adds it); sometimes also `CREATE INDEX` | result checked, `EXPLAIN (ANALYZE, BUFFERS)` printed, objective plan facts checked, and **you** grade the interpretation against the printed rubric |
| `modeling` | the query plus a written `-- RATIONALE:` block (30 or more words) | result checked; you self-grade the rationale against the rubric |

Python exercises are all graded by pytest against your practice file. Ones marked `requires_postgres`
also need the database running.

---

## 3. How time works

**The platform does not time your solving. You do.** This is deliberate: nothing runs in the
background, and nothing is secretly measured. There are four different "times" and it matters which is which.

| what | where you see it | what it really is | is it used? |
|---|---|---|---|
| **Target time** | `Time` column in `lab list`, the header of `lab show`, `~20 min` in the question | The estimated interview time for that exercise (for example 10 min for easy SQL-001). A guide, not a limit. | Yes: `lab session` adds up targets to fill your time budget, and "slow" is judged against it |
| **Your solving time** | *you* measure it with a stopwatch, then record it with `lab progress log ... --minutes 15` | What you actually took, including reading and thinking | Yes: see "slow solve" below |
| **Grader run time** | `result : PASSED  (0.18s)` after `lab check`; stored as `elapsed_s` in `study/progress.json` | How long the **checker itself** took to run your query or tests. It is **not** how long you took to write it. | Recorded only. It is not used for scheduling or scoring |
| **Safety timeouts** | SQL statements are cancelled after 15 s (`LAB_STATEMENT_TIMEOUT_MS`); some Python performance tests have their own limits | Protection against runaway queries and quadratic algorithms | A timeout shows as an `ERROR`/`FAILED`; it is not a measure of your speed |

Other points about time:

- `lab session --minutes 45` only chooses exercises whose target times add up to about 45. It
  does not start a clock or enforce anything.
- Python performance tests (for example "O(n), 300k items") check that your algorithm has the
  right complexity. They use generous limits and never grade elapsed time as a ranking.
- SQL plan exercises never grade a query on elapsed time, only on plan facts and results.
- Timestamps in `progress.json` (`"at": ...`) are when you ran `check` or `log`, in UTC. They are
  used to work out "due today".

### A simple way to time yourself

1. Read the question first without the timer (reading is not coding).
2. **Start a timer at "clarify"** and stop it at `PASSED`. Use your phone, a kitchen timer, or any
   stopwatch.
3. Record the minutes with `progress log --minutes N`. Round to the nearest minute.
4. Judge yourself against the target:

   | your time vs target | meaning | what to do |
   |---|---|---|
   | up to the target | interview-ready | confidence 4–5 |
   | up to 1.5x the target | acceptable, a bit slow | confidence 3; redo in a few days |
   | over 1.5x the target | a weak spot. The lab schedules a review **within 2 days** | confidence 1–2; redo from a blank file |

If you'd like automatic timing (for example `lab start SQL-001` that records when you began, so
`check` can suggest the minutes), that can be added. At the moment it is manual on purpose.

---

## 4. Progress and spaced repetition

Your history is in `study/progress.json` (committed to git unless you add it to `.gitignore`).

| you do | it records |
|---|---|
| `lab check <ID>` on your practice file | one entry: time of the check, status, grader run time |
| `lab check-all` | the same for every exercise you have attempted (untouched stubs are not recorded) |
| `lab progress log <ID> --minutes M --confidence C --notes "..."` | your own minutes, confidence (1–5) and notes |
| `lab check --file other.sql`, `lab verify`, `lab solution` | **nothing**: only your own practice files count |

Only `PASSED` counts as done. A pass followed by a later failure shows as `regressed`.

### When an exercise comes back

| situation | next review |
|---|---|
| last check not passed | tomorrow |
| passed, confidence 1–2 | tomorrow |
| passed, confidence 3 (or none logged) | in 4 days, doubling with each extra passing review (max 60) |
| passed, confidence 4 / 5 | 7 / 14 days, doubling with each review |
| logged minutes > 1.5 x target | within 2 days, whatever the confidence |

See what's due: `python -m lab progress`. Start every session with `lab session`, which puts due
reviews first.

**Confidence scale:** 1 = needed the solution or several hints; 2 = got there with hints or many
errors; 3 = solved with a couple of fixes; 4 = solved cleanly; 5 = solved cleanly and fast, and I
could explain the trade-offs.

**Log honestly.** The scheduling is only as good as the confidence and minutes you give it.

---

## 5. A daily routine

| time | activity |
|---|---|
| 10 min | **typing warm-up**: retype this week's key patterns from memory (listed in `study/8_WEEK_PLAN.md`), without copy/paste |
| 30–60 min | `lab session`: due reviews first, then new exercises, a mix of SQL and Python |
| 5 min | for each exercise: read the explanation, answer one follow-up out loud, log it |
| weekend | one **timed mock**: 45 minutes, closed notes, talking aloud, then 30 minutes of error review |

**How to choose what to practise**

- Follow `study/8_WEEK_PLAN.md`: it gives day-by-day exercise IDs for 8 weeks, from SQL foundations
  to mock interviews, with a checkpoint each week.
- Not enough time? Run `python -m lab list sql --difficulty hard` and focus on streaks
  (SQL-021 to 024), SCD2 (SQL-031 to 033), CDC and incremental loads (SQL-041, 046, 047),
  idempotency (SQL-048, PY-032) and streaming/memory problems (PY-021, PY-029, PY-035).
- Weak on a theme? `python -m lab list sql --tag window-functions`, `--tag dates`, and so on.
- Before an interview: one cold mock (for example SQL-011 plus PY-014), then read
  `study/INTERVIEW_PLAYBOOK.md` sections 1 to 4.

---

## 6. Managing the environment

### Everyday commands

| goal | command |
|---|---|
| is everything healthy? | `python -m lab db status` |
| start / stop the database (data kept) | `docker compose up -d` / `docker compose stop` |
| see database logs | `docker compose logs --tail 50 postgres` |
| reload the data (same data every time) | `python -m lab db seed --size small` |
| bigger data for plan/index practice | `python -m lab db seed --size medium` (about 75 s, ~264k transactions); `large --yes` (about 4 min, ~1.6M transactions, a few GB of disk) |
| rebuild the whole lab database | `python -m lab db reset --confirm` |
| remove the database completely (frees disk) | `docker compose down -v` (then repeat the first-time steps from `docker compose up -d`) |

`docker compose down` without `-v` removes the container but **keeps** the data volume.

Seeding is deterministic: the same size always gives the same data and the same checksum, so
your results don't change from day to day. Seeding replaces all lab data. It never touches your
practice files or progress.

Use **small** for normal practice: it is fast and the expected results are snapshotted on it. Use
**medium** for EXPLAIN and index exercises (SQL-051 to 059). On other sizes the grader compares with
the reference solution run live, so a few checks that quote generated-data numbers are skipped.

### Managing your own work

| goal | command |
|---|---|
| retry one exercise from a blank file (archive the old attempt) | `python -m lab reset-attempts SQL-001 --keep-history --confirm` |
| blank a whole topic | `python -m lab reset-attempts --topic cdc --keep-history --confirm` |
| blank everything | `python -m lab reset-attempts --all --keep-history --confirm` |
| also forget progress history | add `--clear-progress`, or `python -m lab progress clear --confirm` |
| see what would be reset first | run the same command without `--confirm` |

Archived attempts go to `study/attempt_history/<timestamp>/` (not committed to git). Resetting never
touches the database, and clearing progress never touches your practice files.

### Updating the lab or moving to another machine

```powershell
git pull
python -m pip install -e ".[dev]"
python -m lab db migrate
python -m lab db seed --size small
```

Your own work is in `sql/practice/`, `python/practice/` and `study/progress.json`. Commit and push
those to carry it with you.

### Changing the database port

Default is 5433, chosen so it doesn't clash with a local PostgreSQL on 5432. To change it: copy
`.env.example` to `.env`, set `LAB_DB_PORT`, run `docker compose up -d` again, and update the port
in the SQLTools connection (`.vscode/settings.json`).

### Check that the lab itself is sound (optional)

```powershell
python -m pytest -q          # the lab's own self-tests
python -m lab verify         # every reference solution passes; every stub is NOT ATTEMPTED
python -m lab dev lint       # completeness and answer-leak checks
```

### Troubleshooting

| symptom | fix |
|---|---|
| `Cannot connect to PostgreSQL at localhost:5433` | start Docker Desktop, then `docker compose up -d`, wait until `docker compose ps` shows *healthy* |
| `password authentication failed` | `python -m lab db migrate` (re-creates the lab roles) |
| `relation ... does not exist` | `python -m lab db migrate`, then `python -m lab db seed --size small` |
| Python test result `INCOMPLETE` | the test needs the database; start it and seed |
| a check seems to hang | a query with a missing join condition or an O(n²) loop. SQL is cancelled after 15 s; Python tests have time guards. Stop it with Ctrl+C and reread the complexity note in the question |
| `.\.venv\Scripts\Activate.ps1` is blocked | use `.\.venv\Scripts\python.exe -m lab ...`, or `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| garbled characters in the terminal | use Windows Terminal or the VS Code terminal |
| "Unknown exercise" | IDs look like `SQL-001` and `PY-012`; `python -m lab list` shows all |

### Where everything is

| you want | location |
|---|---|
| the file you edit | `sql/practice/<topic>/SQL-NNN.sql`, `python/practice/<topic>/PY-NNN.py` |
| the question text | `lab show <ID>` (files in `sql/questions/`, `python/questions/`) |
| the list of all questions | `sql/QUESTION_BANK.md`, `python/QUESTION_BANK.md` |
| answers (open only after trying) | `sql/solutions/`, `python/solutions/`, explanations in `sql/explanations/`, `python/explanations/` |
| table and fixture documentation | `database/DATA_DICTIONARY.md` |
| study plan and playbooks | `study/8_WEEK_PLAN.md`, `study/INTERVIEW_PLAYBOOK.md`, `study/COMMON_PITFALLS.md`, `study/PERFORMANCE_CHECKLIST.md`, `study/SQL_POSTGRES_VS_SQLSERVER.md` |
| progress and spaced-repetition rules | `study/progress.json`, `study/PROGRESS.md` |
