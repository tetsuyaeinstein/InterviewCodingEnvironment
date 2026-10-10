"""PY-038 reference solution: a slot semaphore bounds the in-flight items; results are re-ordered.

 producer thread : acquire a slot, THEN pull the next item, hand (index, item) to a task queue
                   (backpressure: no free slot -> it simply stops pulling)
 worker threads  : take tasks, run transform, store ("ok"|"err", value) in a dict by index
 caller thread   : consume results strictly in index order, serially; release the slot only when
                   consumer() has returned

Because the slot count is the ONLY limit and every stage holds a slot while it owns an item,
pulled - finished <= max_in_flight at all times, whatever the number of workers, and the reorder
buffer (the results dict) can never grow beyond it either.

Failures are stored as results too, so "the first failure in input order" falls out naturally:
the caller stops at the first failing index, and every earlier item was consumed. All stages poll
a stop event with a short timeout, so nothing can stay blocked after a failure.
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Iterable
from typing import Any

_POLL = 0.01


def run_pipeline(items: Iterable[Any],
                 transform: Callable[[Any], Any],
                 consumer: Callable[[Any], Any],
                 *,
                 max_in_flight: int,
                 workers: int = 1) -> int:
    if max_in_flight < 1 or workers < 1:
        raise ValueError("max_in_flight and workers must be >= 1")

    slots = threading.BoundedSemaphore(max_in_flight)
    tasks: queue.Queue = queue.Queue()
    cond = threading.Condition()
    results: dict[int, tuple[bool, Any]] = {}
    total: list[int | None] = [None]            # number of items, once the source is exhausted
    stop = threading.Event()

    def producer() -> None:
        idx = 0
        try:
            it = iter(items)
            while True:
                while not slots.acquire(timeout=_POLL):
                    if stop.is_set():
                        return
                if stop.is_set():
                    return
                try:
                    item = next(it)
                except StopIteration:
                    slots.release()
                    with cond:
                        total[0] = idx
                        cond.notify_all()
                    return
                tasks.put((idx, item))
                idx += 1
        except BaseException as exc:             # the source itself failed at position idx
            with cond:
                results[idx] = (False, exc)
                total[0] = idx + 1
                cond.notify_all()

    def worker() -> None:
        while not stop.is_set():
            try:
                idx, item = tasks.get(timeout=_POLL)
            except queue.Empty:
                continue
            try:
                outcome: tuple[bool, Any] = (True, transform(item))
            except BaseException as exc:
                outcome = (False, exc)
            with cond:
                results[idx] = outcome
                cond.notify_all()

    threads = [threading.Thread(target=producer, name="pipeline-producer", daemon=True)]
    threads += [threading.Thread(target=worker, name=f"pipeline-worker-{i}", daemon=True) for i in range(workers)]
    for t in threads:
        t.start()

    consumed = 0
    try:
        while True:
            with cond:
                while consumed not in results and not (total[0] is not None and consumed >= total[0]):
                    cond.wait()
                if consumed not in results:
                    break                         # source exhausted and everything consumed
                ok, value = results.pop(consumed)
            if not ok:
                raise value
            consumer(value)
            slots.release()                       # the slot is freed only after the consumer is done
            consumed += 1
    finally:
        stop.set()
        for t in threads:
            t.join()
    return consumed
