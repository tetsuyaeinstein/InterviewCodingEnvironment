"""PY-026 - Atomic file-to-file transform (no partial outputs).

Question: python/questions/03_etl_file_processing/PY-026.md   (python -m lab show PY-026)
Check   : python -m lab check PY-026
"""
from __future__ import annotations

import os
from collections.abc import Callable


def transform_file_atomically(src: str | os.PathLike[str], dest: str | os.PathLike[str],
                              transform: Callable[[str], str | None], *,
                              encoding: str = "utf-8") -> int:
    """Stream ``src`` line by line through ``transform`` into ``dest``, atomically.

    Readers of ``dest`` see either the complete old content or the complete new content, never a
    partial file. On any exception ``dest`` is untouched, no temporary file is left behind and
    the exception propagates. Returns the number of lines written.
    """
    raise NotImplementedError
