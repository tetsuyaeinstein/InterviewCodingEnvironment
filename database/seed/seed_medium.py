"""Seed the MEDIUM profile (~250k transactions). Canonical: `python -m lab db seed --size medium`."""
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from database.seed.generator import main

    main("medium")
