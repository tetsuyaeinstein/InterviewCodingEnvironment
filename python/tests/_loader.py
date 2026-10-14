"""Import the implementation under test.

By default tests import YOUR practice file (python/practice/<topic>/PY-NNN.py).
Verification mode (`python -m lab verify`) sets LAB_IMPL=solution or solution_alt.
`python -m lab check PY-NNN --file <path>` sets LAB_IMPL_FILE for that one exercise.
Reference code is never copied into practice files.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

PY_ROOT = Path(__file__).resolve().parents[1]


def _find(exercise_id: str, impl: str) -> Path:
    override = os.environ.get("LAB_IMPL_FILE")
    if override:
        # `lab check <ID> --file <path>` runs exactly one exercise's tests, so the override applies
        # whatever the file is called (a scratch file such as my_try.py must not be silently ignored).
        path = Path(override)
        if not path.exists():
            raise FileNotFoundError(f"--file {override} does not exist")
        return path
    if impl == "practice":
        folder, name = "practice", f"{exercise_id}.py"
    elif impl == "solution":
        folder, name = "solutions", f"{exercise_id}.py"
    elif impl == "solution_alt":
        folder, name = "solutions", f"{exercise_id}_alt.py"
    else:
        raise ValueError(f"LAB_IMPL must be practice|solution|solution_alt, not {impl!r}")
    matches = sorted((PY_ROOT / folder).glob(f"*/{name}"))
    if not matches:
        raise FileNotFoundError(f"{name} not found under python/{folder}/")
    return matches[0]


def load(exercise_id: str):
    impl = os.environ.get("LAB_IMPL", "practice")
    path = _find(exercise_id, impl)
    mod_name = f"lab_impl_{impl}_{exercise_id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module  # needed for dataclasses / pickling inside the module
    spec.loader.exec_module(module)
    return module
