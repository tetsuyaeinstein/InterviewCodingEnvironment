"""PY-038 - Bounded producer / worker / consumer pipeline with backpressure.

Question: python/questions/04_streaming_reliability/PY-038.md   (python -m lab show PY-038)
Check   : python -m lab check PY-038
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


def run_pipeline(items: Iterable[Any],
                 transform: Callable[[Any], Any],
                 consumer: Callable[[Any], Any],
                 *,
                 max_in_flight: int,
                 workers: int = 1) -> int:
    """Pull ``items`` lazily, ``transform`` them on ``workers`` threads, feed ``consumer`` serially
    and in input order, never holding more than ``max_in_flight`` items between "pulled from
    ``items``" and "finished by ``consumer``". Returns the number of items consumed.

    The first failure in input order (a source, transform or consumer error) is re-raised to the
    caller after every thread has stopped. See the question for the exact contract.
    """
    raise NotImplementedError
