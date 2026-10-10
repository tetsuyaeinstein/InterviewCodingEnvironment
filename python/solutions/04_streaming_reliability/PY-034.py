"""PY-034 reference solution: replace-by-batch-id outputs, then the checkpoint LAST.

Protocol per batch [start, end):
  1. compute rows + dead letters in memory (no side effects; a bug aborts the batch cleanly);
  2. sink.write(start, rows)          - idempotent: batch id = first input offset, replace semantics;
  3. dead_letters.write(start, dls)   - same;
  4. checkpoint.save(end)             - the commit point.

A crash before step 4 leaves the checkpoint at `start`, so the rerun rebuilds the *same* batch
(same id) and overwrites whatever steps 2-3 left behind. After step 4 the batch is never touched
again. This is "at-least-once processing + idempotent sink = effectively-once output".
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class BadRecord(Exception):
    pass


@dataclass(frozen=True)
class DeadLetter:
    offset: int
    record: Any
    reason: str


@dataclass(frozen=True)
class RunReport:
    batches: int
    next_offset: int


class BatchSink(Protocol):
    def write(self, batch_id: int, rows: list) -> None: ...


class CheckpointStore(Protocol):
    def load(self) -> int: ...
    def save(self, offset: int) -> None: ...


def run_batches(source: Sequence[Any],
                transform: Callable[[Any], Iterable[Any]],
                sink: BatchSink,
                dead_letters: BatchSink,
                checkpoint: CheckpointStore,
                *,
                batch_size: int,
                max_batches: int | None = None) -> RunReport:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    if max_batches is not None and max_batches < 0:
        raise ValueError("max_batches must be >= 0")
    offset = checkpoint.load()
    if not isinstance(offset, int) or offset < 0 or offset > len(source):
        raise ValueError(f"checkpoint {offset!r} is outside the source (0..{len(source)})")

    done = 0
    while offset < len(source) and (max_batches is None or done < max_batches):
        end = min(offset + batch_size, len(source))
        rows: list = []
        dead: list[DeadLetter] = []
        for pos in range(offset, end):
            record = source[pos]
            try:
                produced = list(transform(record))      # materialise: a BadRecord mid-way drops all of it
            except BadRecord as exc:
                dead.append(DeadLetter(pos, record, str(exc)))
            else:
                rows.extend(produced)
        sink.write(offset, rows)
        dead_letters.write(offset, dead)
        checkpoint.save(end)                            # commit point, strictly last
        offset = end
        done += 1
    return RunReport(done, offset)
