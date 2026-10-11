# Quickstart (about 5 minutes)

## 1. Install and start (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1          # blocked? use .\.venv\Scripts\python.exe instead of python below
python -m pip install -e ".[dev]"
docker compose up -d
python -m lab db migrate
python -m lab db seed --size small
python -m lab db status               # expect: migrations 4 applied, profile=small, read-only = on
```

macOS / Linux: `python3.12 -m venv .venv && source .venv/bin/activate`, then the same commands.

## 2. Your first SQL exercise

```powershell
python -m lab show SQL-021
code sql\practice\03_gaps_islands_time\SQL-021.sql     # type your query below the marker
python -m lab run SQL-021                              # look at your rows
python -m lab check SQL-021                            # graded: PASSED / FAILED with a diff
```

## 3. Your first Python exercise

```powershell
python -m lab show PY-012
code python\practice\02_algorithms\PY-012.py           # replace `raise NotImplementedError`
python -m lab check PY-012
```

## 4. A PostgreSQL integration exercise

```powershell
python -m lab show PY-041
code python\practice\05_database_integrations\PY-041.py
python -m lab check PY-041                             # needs the container running
```

## 5. After it passes

```powershell
python -m lab solution SQL-021 --explain               # compare with the reference + read follow-ups
python -m lab solution SQL-021 --alt                   # a genuinely different approach
python -m lab progress log SQL-021 --minutes 20 --confidence 3
python -m lab session --minutes 45 --mix sql,python    # tomorrow: start here
```

In VS Code:

- Accept the recommended extensions.
- Open a practice file and press **Ctrl+Shift+B** to check it.
- Use *Terminal → Run Task…* for everything else.

The study plan is in `study/8_WEEK_PLAN.md`. For the full daily routine, how time is (and is not) measured, and environment management, see `PRACTICE_GUIDE.md`.
