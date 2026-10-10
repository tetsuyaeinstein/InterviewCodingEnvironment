"""Shared helpers and constants for the deterministic seed.

Determinism rules used throughout the seed code:
  * every random stream is a ``random.Random`` seeded with a *string* (sha512-based, stable
    across runs and platforms, unaffected by PYTHONHASHSEED);
  * only +, -, *, / and comparisons are used on floats (no libm transcendental functions,
    whose last-bit results can differ between platforms);
  * money is always ``decimal.Decimal`` quantized to cents;
  * no timestamp depends on the wall clock.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

UTC = timezone.utc
SEED_VERSION = 1

#: Business data covers [START, END) in UTC.
START = datetime(2024, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 1, tzinfo=UTC)
#: Sentinel used by dim_customer_scd2 for open-ended rows.
SCD2_OPEN_END = datetime(9999, 12, 31, tzinfo=UTC)

CENT = Decimal("0.01")


def money(value) -> Decimal:
    """Quantize to cents. Floats go through ``repr`` -> str so results are platform-stable."""
    if isinstance(value, float):
        value = repr(value)
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def ts(y: int, m: int, d: int, h: int = 15, mi: int = 0, s: int = 0, us: int = 0) -> datetime:
    """UTC timestamp helper used by the fixtures (default 15:00 UTC)."""
    return datetime(y, m, d, h, mi, s, us, tzinfo=UTC)


def rng_for(profile_seed: str, domain: str) -> random.Random:
    """Independent RNG stream per domain so adding a domain never shifts another."""
    return random.Random(f"de-lab:v{SEED_VERSION}:{profile_seed}:{domain}")


def rand_ts(rng: random.Random, lo: datetime, hi: datetime) -> datetime:
    """Uniform timestamp in [lo, hi) with one-second resolution."""
    span = int((hi - lo).total_seconds())
    return lo + timedelta(seconds=rng.randrange(max(span, 1)))


def daterange(d0: date, d1: date):
    """Dates in [d0, d1)."""
    d = d0
    while d < d1:
        yield d
        d += timedelta(days=1)


class Txn:
    """Builder for a fixture transaction header + its lines (gross derived from lines)."""

    __slots__ = ("transaction_id", "customer_id", "store_id", "transaction_ts", "status",
                 "payment_method", "source_system", "ingested_at", "lines")

    VOUCHER_PRODUCT_ID = 7  # open-price product without price history

    def __init__(self, transaction_id, customer_id, store_id, transaction_ts, amount=None, *,
                 status="COMPLETED", lines=None, payment="CARD", ingest_delay=timedelta(minutes=5),
                 ingested_at=None, source_system=None):
        self.transaction_id = transaction_id
        self.customer_id = customer_id
        self.store_id = store_id
        self.transaction_ts = transaction_ts
        self.status = status
        self.payment_method = payment
        self.source_system = source_system or "POS"
        self.ingested_at = ingested_at or (transaction_ts + ingest_delay)
        if lines is None:
            if amount is None:
                raise ValueError("either amount or lines is required")
            lines = [(self.VOUCHER_PRODUCT_ID, 1, money(amount), Decimal("0.00"))]
        # lines: (product_id, quantity, unit_price, discount)
        self.lines = [(p, q, money(u), money(dsc)) for (p, q, u, dsc) in lines]

    @property
    def gross_amount(self) -> Decimal:
        return sum((q * u - dsc for (_, q, u, dsc) in self.lines), Decimal("0.00"))

    def header_row(self):
        return (self.transaction_id, self.customer_id, self.store_id, self.transaction_ts,
                self.gross_amount, "USD", self.status, self.payment_method, self.source_system,
                self.ingested_at)

    def item_rows(self):
        return [(self.transaction_id, i + 1, p, q, u, dsc) for i, (p, q, u, dsc) in enumerate(self.lines)]
