"""Seed the LARGE profile (~1.5M transactions; opt-in, needs --yes).
Canonical: `python -m lab db seed --size large --yes`."""
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from database.seed.generator import main

    main("large")
