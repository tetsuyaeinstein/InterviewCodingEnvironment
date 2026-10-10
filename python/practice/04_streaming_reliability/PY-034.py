"""PY-034 - Checkpointed batch processing that survives a crash at any point.

Question: python/questions/04_streaming_reliability/PY-034.md   (python -m lab show PY-034)
Check   : python -m lab check PY-034
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class BadRecord(Exception):
    """Raised by a transform to send one input record to the dead-letter sink."""


@dataclass(frozen=True)
class DeadLetter:
    offset: int          # absolute position of the record in ``source``
    record: Any
    reason: str          # str() of the BadRecord


@dataclass(frozen=True)
class RunReport:
    batches: int         # batches completed (checkpoint saved) by THIS call
    next_offset: int     # the checkpoint value after this call


class BatchSink(Protocol):
    """Durable, batch-addressed output. Writing a batch_id again REPLACES that batch's rows."""

    def write(self, batch_id: int, rows: list) -> None:
        raise NotImplementedError


class CheckpointStore(Protocol):
    """Durable cell holding the offset of the first input record NOT yet fully processed."""

    def load(self) -> int:
        """Return the saved offset (0 if nothing was ever saved)."""
        raise NotImplementedError

    def save(self, offset: int) -> None:
        raise NotImplementedError


def run_batches(source: Sequence[Any],
                transform: Callable[[Any], Iterable[Any]],
                sink: BatchSink,
                dead_letters: BatchSink,
                checkpoint: CheckpointStore,
                *,
                batch_size: int,
                max_batches: int | None = None) -> RunReport:
    """Process ``source`` from the checkpoint onwards in batches of ``batch_size`` input records.

    Must be safe to call again after a crash at ANY point (including inside the sink or
    checkpoint calls): the final sinks must hold every output exactly once. See the question.
    """
    raise NotImplementedError
