"""PY-026 reference solution: temp file in the destination directory + fsync + os.replace.

Why each step:
  * same directory  -> os.replace is a same-volume rename, which is atomic (POSIX rename(2),
                       Windows MoveFileEx with REPLACE_EXISTING); a temp in /tmp could be on
                       another volume and degrade into copy+delete;
  * flush + fsync   -> the new bytes are on disk *before* the rename is, so a crash cannot
                       leave a renamed-but-empty file;
  * close first     -> Windows refuses to replace/unlink files that are still open (this also
                       makes src == dest work);
  * BaseException   -> Ctrl+C / SystemExit also clean up the temp file.
"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Callable


def _fsync_dir(path: str) -> None:
    """Persist the rename itself (POSIX only; directories cannot be opened on Windows)."""
    if os.name == "nt":
        return
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def transform_file_atomically(src: str | os.PathLike[str], dest: str | os.PathLike[str],
                              transform: Callable[[str], str | None], *,
                              encoding: str = "utf-8") -> int:
    dest_path = os.path.abspath(os.fspath(dest))
    dest_dir = os.path.dirname(dest_path)
    written = 0
    with open(src, encoding=encoding) as inp:          # fails before any temp file exists
        fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix="." + os.path.basename(dest_path) + ".",
                                   suffix=".tmp")
        try:
            # newline="\n": never translate to os.linesep (CRLF on Windows)
            with open(fd, "w", encoding=encoding, newline="\n") as out:
                for line in inp:
                    result = transform(line[:-1] if line.endswith("\n") else line)
                    if result is None:
                        continue
                    out.write(result)
                    out.write("\n")
                    written += 1
                out.flush()
                os.fsync(out.fileno())
        except BaseException:
            os.unlink(tmp)                              # `out` is closed by now
            raise
    # the source is closed here, so replacing it in place also works on Windows
    try:
        os.replace(tmp, dest_path)
    except BaseException:
        os.unlink(tmp)
        raise
    _fsync_dir(dest_dir)
    return written
