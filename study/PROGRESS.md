# How progress tracking works

Your history lives in **`study/progress.json`**. It is committed to git by default, so it
follows you between machines. Add it to `.gitignore` if you'd rather keep it private.

## What gets recorded

| action | recorded |
|---|---|
| `python -m lab check <ID>` on your practice file | one check entry: timestamp, status (`passed`, `failed`, `error`, `incomplete`, `not_attempted`), duration |
| `python -m lab check-all` | the same for every *attempted* exercise (untouched stubs are not recorded) |
| `python -m lab progress log <ID> --minutes 18 --confidence 4 --notes "missed the tie rule"` | a self-report: date, minutes, confidence 1–5, notes |
| `lab check --file <other file>`, `lab verify`, `lab solution` | **nothing**: only your practice file counts |

Only `passed` means complete:

- an untouched stub is `not_attempted`;
- SQL that runs but returns the wrong rows is `failed`;
- Python tests skipped because PostgreSQL is down are `incomplete`;
- a pass followed by a later failure shows as `regressed (failed)`.

## Spaced repetition

`python -m lab progress` lists what is due today. `python -m lab session --minutes 45 --mix
sql,python` builds a session from that list:

1. **Due reviews** first, the most overdue first.
2. Then **unfinished attempts** (failed or error).
3. Then **new exercises** in curriculum order, alternating SQL and Python. Exercises whose
   prerequisites you haven't passed yet go last.

When something becomes due again:

| situation | next review |
|---|---|
| last check not passed | tomorrow |
| passed, latest confidence 1–2 | tomorrow |
| passed, confidence 3 (or none logged) | in 4 days, doubled for every further passing review (max 60) |
| passed, confidence 4 / 5 | 7 / 14 days, doubled per review |
| your logged minutes > 1.5 × the exercise's interview time | within 2 days, regardless of confidence (speed matters in interviews) |

**Log honestly.** If you peeked at a hint or solution, use confidence ≤ 2 so the exercise comes
back tomorrow.

## Resetting

| goal | command |
|---|---|
| retry one exercise from a blank file | `python -m lab reset-attempts SQL-021 --confirm` |
| …keeping a copy of your old attempt | `python -m lab reset-attempts SQL-021 --keep-history --confirm` (copies to `study/attempt_history/<timestamp>/`) |
| blank out a whole topic | `python -m lab reset-attempts --topic gaps_islands --keep-history --confirm` |
| start everything over | `python -m lab reset-attempts --all --keep-history --confirm` |
| also forget the history | add `--clear-progress`, or `python -m lab progress clear --confirm` |

Without `--confirm`, `reset-attempts` only shows what it would do. Clearing progress never
touches practice files, and resetting practice files keeps progress unless you ask otherwise.

## Session notes

Keep free-form notes in `study/session_notes/`. It is gitignored apart from a placeholder.
Good things to record:

- the clarifying questions you forgot;
- the edge case that bit you;
- the plan node you misread;
- one sentence on how you'd explain it next time.
