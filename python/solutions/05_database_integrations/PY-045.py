"""PY-045 reference solution: streaming runner with batch flush, poison-row isolation and a summary."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

Extract = Callable[[], Iterable[Any]]
Transform = Callable[[Any], "dict | None"]
Load = Callable[[list[dict]], None]


@dataclass(frozen=True)
class Quarantined:
    position: int
    stage: str
    error: str
    record: Any


@dataclass
class RunSummary:
    read: int = 0
    filtered: int = 0
    loaded: int = 0
    batches: int = 0
    quarantined: list[Quarantined] = field(default_factory=list)


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def run_etl(extract: Extract, transform: Transform, load: Load, *, batch_size: int = 100,
            on_error: str = "quarantine") -> RunSummary:
    if on_error not in ("quarantine", "raise"):
        raise ValueError(f"on_error must be 'quarantine' or 'raise', not {on_error!r}")
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    summary = RunSummary()
    pending: list[tuple[int, dict]] = []   # (position, row)

    def flush() -> None:
        if not pending:
            return
        rows = [row for _, row in pending]
        summary.batches += 1
        try:
            load(rows)
            summary.loaded += len(rows)
        except Exception:
            if on_error == "raise":
                raise
            # Isolate the poison row(s): the batch is atomic, so nothing was stored yet.
            for position, row in pending:
                try:
                    load([row])
                    summary.loaded += 1
                except Exception as exc:
                    summary.quarantined.append(Quarantined(position, "load", _describe(exc), row))
        pending.clear()

    for position, record in enumerate(extract()):
        summary.read += 1
        try:
            row = transform(record)
        except Exception as exc:
            if on_error == "raise":
                raise
            summary.quarantined.append(Quarantined(position, "transform", _describe(exc), record))
            continue
        if row is None:
            summary.filtered += 1
            continue
        pending.append((position, row))
        if len(pending) >= batch_size:
            flush()
    flush()
    summary.quarantined.sort(key=lambda q: q.position)
    return summary
