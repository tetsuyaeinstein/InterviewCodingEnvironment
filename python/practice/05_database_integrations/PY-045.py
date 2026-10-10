"""PY-045 - A small extract/transform/load pipeline with injected dependencies.

Question: python/questions/05_database_integrations/PY-045.md   (python -m lab show PY-045)
Check   : python -m lab check PY-045
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

Extract = Callable[[], Iterable[Any]]            # () -> records, in source order
Transform = Callable[[Any], "dict | None"]       # record -> row, or None to filter the record out
Load = Callable[[list[dict]], None]              # batch of rows -> None; atomic: raises => nothing loaded


@dataclass(frozen=True)
class Quarantined:
    position: int          # 0-based index of the record in extraction order
    stage: str             # "transform" or "load"
    error: str             # "<ExceptionType>: <message>"
    record: Any            # the original record (stage "transform") or the transformed row ("load")


@dataclass
class RunSummary:
    read: int = 0                  # records taken from the source
    filtered: int = 0              # transform returned None
    loaded: int = 0                # rows accepted by the sink
    batches: int = 0               # load() calls that contained a full or final batch (not the retries)
    quarantined: list[Quarantined] = field(default_factory=list)


def run_etl(extract: Extract, transform: Transform, load: Load, *, batch_size: int = 100,
            on_error: str = "quarantine") -> RunSummary:
    """Run the pipeline and return the summary. See the question for the exact semantics."""
    raise NotImplementedError
