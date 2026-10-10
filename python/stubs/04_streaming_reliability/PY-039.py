"""PY-039 - Classify a batch of messages: unique, exact duplicates, conflicting payloads.

Question: python/questions/04_streaming_reliability/PY-039.md   (python -m lab show PY-039)
Check   : python -m lab check PY-039
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Delivered:
    message_id: str
    payload: dict          # the first-arrival payload for this id
    deliveries: int        # how many times the id was seen (1 for unique)


@dataclass(frozen=True)
class Conflict:
    message_id: str
    payloads: tuple[dict, ...]   # one payload per distinct canonical form, in first-arrival order
    deliveries: int              # total number of times the id was seen


@dataclass(frozen=True)
class Classification:
    unique: list[Delivered]              # ids seen exactly once
    exact_duplicates: list[Delivered]    # ids seen 2+ times, all with the same canonical payload
    conflicts: list[Conflict]            # ids seen with 2+ distinct canonical payloads


def classify_messages(messages: Iterable[tuple[str, Mapping[str, object]]]) -> Classification:
    """Classify ``(message_id, payload)`` pairs. All three lists are sorted by message_id."""
    raise NotImplementedError
