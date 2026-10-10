"""PY-032 - Idempotent event consumer with an atomic state store.

Question: python/questions/04_streaming_reliability/PY-032.md   (python -m lab show PY-032)
Check   : python -m lab check PY-032
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


class ConflictingEvent(Exception):
    """The same event_id was delivered again with a different account or amount."""


class StoreError(Exception):
    """Raised by a store when it cannot complete an operation (the consumer must not hide it)."""


@dataclass(frozen=True)
class Event:
    event_id: str
    account_id: str
    amount: Decimal        # signed: positive = deposit, negative = withdrawal


class StateStore(Protocol):
    """The only persistence the consumer may use."""

    def get(self, key: str, default: Any = None) -> Any:
        """Read one value."""
        raise NotImplementedError

    def commit(self, writes: Mapping[str, Any]) -> None:
        """Atomically apply every write, or none of them (raise StoreError)."""
        raise NotImplementedError


class IdempotentConsumer:
    """Applies each event's effect to account balances at most once per event_id."""

    def __init__(self, store: StateStore) -> None:
        raise NotImplementedError

    def process(self, event: Event) -> str:
        """Return "applied", "rejected" or "duplicate"."""
        raise NotImplementedError

    def balance(self, account_id: str) -> Decimal:
        """Current balance (Decimal('0') for an unknown account), read from the store."""
        raise NotImplementedError
