"""PY-032 reference solution: the dedup marker and the effect share ONE atomic commit.

Per event: read the marker; if present compare fingerprints (duplicate or conflict); otherwise
decide (apply / reject on overdraft) and commit {marker, new balance} in a single store.commit().
A crash before the commit leaves nothing behind (redelivery re-applies); a crash after it leaves
both (redelivery is a duplicate). No in-memory cache: the store is the single source of truth,
so a restarted consumer (or a second instance) sees the same dedup state.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


class ConflictingEvent(Exception):
    pass


class StoreError(Exception):
    pass


@dataclass(frozen=True)
class Event:
    event_id: str
    account_id: str
    amount: Decimal


class StateStore(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...
    def commit(self, writes: Mapping[str, Any]) -> None: ...


class IdempotentConsumer:
    def __init__(self, store: StateStore) -> None:
        self._store = store

    @staticmethod
    def _validate(event: Event) -> None:
        if not isinstance(event.event_id, str) or not event.event_id:
            raise ValueError("event_id must be a non-empty string")
        if not isinstance(event.account_id, str) or not event.account_id:
            raise ValueError("account_id must be a non-empty string")
        if not isinstance(event.amount, Decimal) or not event.amount.is_finite() or event.amount == 0:
            raise ValueError(f"amount must be a finite, non-zero Decimal: {event.amount!r}")

    def balance(self, account_id: str) -> Decimal:
        return self._store.get(f"balance:{account_id}", Decimal("0"))

    def process(self, event: Event) -> str:
        self._validate(event)
        marker_key = f"event:{event.event_id}"
        seen = self._store.get(marker_key)
        if seen is not None:
            seen_account, seen_amount, _ = seen
            if seen_account != event.account_id or seen_amount != event.amount:
                raise ConflictingEvent(f"event {event.event_id!r} redelivered with a different payload")
            return "duplicate"
        current = self.balance(event.account_id)
        new_balance = current + event.amount
        if new_balance < 0:
            outcome, writes = "rejected", {}
        else:
            outcome, writes = "applied", {f"balance:{event.account_id}": new_balance}
        writes[marker_key] = (event.account_id, event.amount, outcome)
        self._store.commit(writes)          # the ONLY write: marker + effect together
        return outcome
