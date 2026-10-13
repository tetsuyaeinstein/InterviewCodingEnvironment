"""Local progress tracking (study/progress.json) and simple spaced repetition.

Only a *passed* `lab check` marks an exercise complete. `not_attempted`, `error`, `failed` and
`incomplete` (skipped tests) are recorded as attempts but never as completion.

Scheduling (next review date):
  * last check failed/error, or latest self-rated confidence <= 2  -> due again in 1 day
  * passed: base interval by latest confidence (1:1d, 2:2d, 3:4d, 4:7d, 5:14d; default 3)
    doubled for every additional passing review, capped at 60 days
  * solve slower than 1.5x the estimated interview time -> interval capped at 2 days
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import STUDY_DIR

PROGRESS_FILE = STUDY_DIR / "progress.json"
BASE_INTERVAL = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def load(path: Path | None = None) -> dict:
    path = path or PROGRESS_FILE  # resolved at call time so tests can redirect the file
    if not path.exists():
        return {"version": 1, "exercises": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_suffix(".corrupt.json")
        path.replace(backup)
        print(f"warning: {path.name} was unreadable; moved to {backup.name} and started fresh")
        return {"version": 1, "exercises": {}}
    data.setdefault("exercises", {})
    return data


def save(data: dict, path: Path | None = None) -> None:
    path = path or PROGRESS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)  # atomic on Windows and POSIX


def _entry(data: dict, ex_id: str) -> dict:
    return data["exercises"].setdefault(ex_id, {"checks": [], "logs": []})


def record_check(ex_id: str, status: str, elapsed_s: float, source: str = "check") -> None:
    if os.environ.get("LAB_NO_PROGRESS") == "1":
        return
    data = load()
    e = _entry(data, ex_id)
    e["checks"].append({"at": _now().isoformat(), "status": status, "elapsed_s": round(elapsed_s, 2), "source": source})
    e["checks"] = e["checks"][-200:]
    if status == "passed" and not e.get("first_passed_at"):
        e["first_passed_at"] = _now().isoformat()
    save(data)


def log_session(ex_id: str, minutes: float | None, confidence: int | None, notes: str | None) -> dict:
    data = load()
    e = _entry(data, ex_id)
    entry = {"at": _now().isoformat(), "date": date.today().isoformat()}
    if minutes is not None:
        entry["minutes"] = minutes
    if confidence is not None:
        if not 1 <= confidence <= 5:
            raise ValueError("confidence must be 1..5")
        entry["confidence"] = confidence
    if notes:
        entry["notes"] = notes
    e["logs"].append(entry)
    save(data)
    return entry


def clear(ex_ids: list[str] | None = None) -> int:
    data = load()
    if ex_ids is None:
        n = len(data["exercises"])
        data["exercises"] = {}
    else:
        n = sum(1 for i in ex_ids if data["exercises"].pop(i, None) is not None)
    save(data)
    return n


# ---------------------------------------------------------------------------
# Derived state
# ---------------------------------------------------------------------------
def state(entry: dict | None, estimated_minutes: int) -> dict:
    """Summarise one exercise: status, passes, next_due (date) and reason."""
    if not entry or (not entry.get("checks") and not entry.get("logs")):
        return {"status": "new", "passes": 0, "next_due": None, "last": None}
    checks = [c for c in entry.get("checks", []) if c["status"] != "not_attempted"]
    logs = entry.get("logs", [])
    last = checks[-1] if checks else None
    passes = [c for c in checks if c["status"] == "passed"]
    status = "passed" if last and last["status"] == "passed" else (last["status"] if last else "logged")
    if entry.get("first_passed_at") and status != "passed":
        status = f"regressed ({status})"
    last_conf = next((l["confidence"] for l in reversed(logs) if "confidence" in l), None)
    last_minutes = next((l["minutes"] for l in reversed(logs) if "minutes" in l), None)
    last_at = max([c["at"] for c in checks] + [l["at"] for l in logs]) if (checks or logs) else None
    last_day = datetime.fromisoformat(last_at).date() if last_at else date.today()
    if not last or last["status"] != "passed":
        interval, reason = 1, "not passed yet"
    elif last_conf is not None and last_conf <= 2:
        interval, reason = 1, f"low confidence ({last_conf})"
    else:
        interval = BASE_INTERVAL.get(last_conf or 3, 4) * (2 ** max(len(passes) - 1, 0))
        interval, reason = min(interval, 60), f"review ({len(passes)} pass{'es' if len(passes) != 1 else ''})"
        if last_minutes and last_minutes > 1.5 * estimated_minutes:
            interval, reason = min(interval, 2), f"slow solve ({last_minutes:g} min vs {estimated_minutes} est.)"
    return {"status": status, "passes": len(passes), "next_due": last_day + timedelta(days=interval),
            "reason": reason, "last": last_at, "confidence": last_conf}


def summary(catalog: dict) -> dict:
    data = load()
    out = {}
    for ex_id, ex in catalog.items():
        out[ex_id] = state(data["exercises"].get(ex_id), ex.estimated_minutes)
    return out


def plan_session(catalog: dict, minutes: int, langs: list[str], today: date | None = None) -> list[tuple]:
    """Pick due reviews first, then unfinished attempts, then new exercises in curriculum order,
    alternating languages, until the time budget is used."""
    today = today or date.today()
    states = summary(catalog)
    pools: dict[str, list] = {lang: [] for lang in langs}
    for ex_id, ex in catalog.items():
        if ex.lang not in pools:
            continue
        st = states[ex_id]
        prereq_ok = all(states.get(p, {}).get("passes", 0) > 0 or p not in catalog for p in ex.prerequisites)
        if st["status"] == "new":
            rank = (2, ex.number) if prereq_ok else (3, ex.number)
            why = "new" if prereq_ok else f"new (prerequisites {', '.join(ex.prerequisites)} not passed yet)"
        elif st["next_due"] and st["next_due"] <= today:
            rank, why = (0, st["next_due"].toordinal(), ex.number), f"due: {st['reason']}"
        elif st["status"] != "passed":
            rank, why = (1, ex.number), f"in progress ({st['status']})"
        else:
            continue
        pools[ex.lang].append((rank, ex, why))
    for lang in pools:
        pools[lang].sort(key=lambda t: t[0])
    picked, used = [], 0
    while any(pools.values()):
        progressed = False
        for lang in langs:
            if not pools[lang]:
                continue
            rank, ex, why = pools[lang][0]
            if used + ex.estimated_minutes > minutes:
                pools[lang].pop(0)
                continue
            pools[lang].pop(0)
            picked.append((ex, why))
            used += ex.estimated_minutes
            progressed = True
        if not progressed and used >= minutes:
            break
    return picked
