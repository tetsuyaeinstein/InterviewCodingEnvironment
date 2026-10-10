"""Seed profile definitions. Fixture rows are identical in every profile; only the
pseudo-random generated volume changes."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    n_customers: int            # generated customers (ids 1001..)
    n_stores: int               # total stores incl. fixture stores 1-5
    n_products: int             # total products incl. fixture products 1-10
    n_transactions: int         # generated transactions (ids 100001..)
    n_events: int               # generated customer_events (approx.)
    n_accounts: int             # generated ledger accounts
    ledger_per_account: int     # average ledger entries per generated account
    n_devices: int              # generated kiosk / terminal devices
    availability_products: int  # products tracked in store_product_availability
    warning: str | None = None


PROFILES: dict[str, Profile] = {
    "small": Profile("small", 2_000, 40, 200, 20_000, 30_000, 500, 80, 60, 60),
    "medium": Profile("medium", 20_000, 120, 600, 250_000, 200_000, 3_000, 60, 150, 100),
    "large": Profile(
        "large", 100_000, 300, 1_500, 1_500_000, 600_000, 10_000, 50, 300, 150,
        warning=("The large profile generates ~1.5M transactions / ~3.7M lines and several "
                 "million other rows. Expect a few minutes of CPU time and ~2-3 GB of disk "
                 "in the Docker volume."),
    ),
}
