"""Tests for PY-026 (imports your practice file by default; see _loader.py)."""
import os
import tracemalloc

import pytest

from _loader import load

mod = load("PY-026")


class Boom(Exception):
    pass


class HardStop(BaseException):
    """Simulates KeyboardInterrupt / SystemExit without disturbing pytest."""


@pytest.fixture
def dirs(tmp_path):
    src_dir, out_dir = tmp_path / "in", tmp_path / "out"
    src_dir.mkdir()
    out_dir.mkdir()
    return src_dir, out_dir


def write(path, data: bytes):
    path.write_bytes(data)
    return path


def test_transforms_lines_and_normalises_line_endings(dirs):
    src_dir, out_dir = dirs
    src = write(src_dir / "a.csv", b"id,name\r\n1,ann\r\n2,bob\r\n")
    dest = out_dir / "a.out"
    n = mod.transform_file_atomically(src, dest, str.upper)
    assert n == 3
    assert dest.read_bytes() == b"ID,NAME\n1,ANN\n2,BOB\n"
    assert sorted(os.listdir(out_dir)) == ["a.out"]


def test_none_drops_lines_and_last_line_without_newline(dirs):
    src_dir, out_dir = dirs
    src = write(src_dir / "a.txt", b"keep 1\ndrop\nkeep 2\nlast")
    dest = out_dir / "b.txt"
    n = mod.transform_file_atomically(str(src), str(dest), lambda s: None if s == "drop" else s)
    assert n == 3
    assert dest.read_bytes() == b"keep 1\nkeep 2\nlast\n"


def test_failure_midway_preserves_existing_destination_and_cleans_up(dirs):
    src_dir, out_dir = dirs
    src = write(src_dir / "a.txt", b"".join(b"line %d\n" % i for i in range(1000)))
    dest = write(out_dir / "report.txt", b"OLD CONTENT\n")
    write(out_dir / "neighbour.txt", b"untouched")

    def transform(line):
        if line == "line 500":
            raise Boom("bad record")
        return line

    with pytest.raises(Boom):
        mod.transform_file_atomically(src, dest, transform)
    assert dest.read_bytes() == b"OLD CONTENT\n"
    assert sorted(os.listdir(out_dir)) == ["neighbour.txt", "report.txt"], "temporary file left behind"


def test_failure_when_destination_did_not_exist(dirs):
    src_dir, out_dir = dirs
    src = write(src_dir / "a.txt", b"a\nb\nc\n")

    def transform(line):
        if line == "b":
            raise Boom(line)
        return line

    with pytest.raises(Boom):
        mod.transform_file_atomically(src, out_dir / "new.txt", transform)
    assert os.listdir(out_dir) == []


def test_base_exceptions_also_clean_up(dirs):
    src_dir, out_dir = dirs
    src = write(src_dir / "a.txt", b"a\nb\n")
    dest = write(out_dir / "d.txt", b"old")

    def transform(line):
        raise HardStop()

    with pytest.raises(HardStop):
        mod.transform_file_atomically(src, dest, transform)
    assert dest.read_bytes() == b"old" and os.listdir(out_dir) == ["d.txt"]


def test_readers_never_see_partial_output_and_temp_lives_next_to_destination(dirs):
    src_dir, out_dir = dirs
    src = write(src_dir / "a.txt", b"".join(b"row %d\n" % i for i in range(5000)))
    dest = write(out_dir / "live.txt", b"v1\n")
    observed = []

    def transform(line):
        if line == "row 4000":   # well past any write buffer
            observed.append((dest.read_bytes(), sorted(os.listdir(out_dir))))
        return line

    assert mod.transform_file_atomically(src, dest, transform) == 5000
    old_bytes, listing = observed[0]
    assert old_bytes == b"v1\n", "the destination was modified before the transform finished"
    assert "live.txt" in listing and len(listing) == 2, \
        f"expected exactly one temporary file next to the destination, saw {listing}"
    assert dest.read_bytes().count(b"\n") == 5000
    assert os.listdir(out_dir) == ["live.txt"]


def test_fsync_happens_before_the_atomic_replace(dirs, monkeypatch):
    src_dir, out_dir = dirs
    src = write(src_dir / "a.txt", b"x\ny\n")
    dest = out_dir / "d.txt"
    events = []
    real_fsync, real_replace = os.fsync, os.replace

    def spy_fsync(fd):
        events.append(("fsync",))
        return real_fsync(fd)

    def spy_replace(a, b, *args, **kw):
        events.append(("replace", os.path.dirname(os.path.abspath(a)), os.path.abspath(b)))
        return real_replace(a, b, *args, **kw)

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "replace", spy_replace)
    mod.transform_file_atomically(src, dest, lambda s: s)
    names = [e[0] for e in events]
    assert "replace" in names, "use os.replace (or Path.replace) for the final rename"
    i = names.index("replace")
    assert "fsync" in names[:i], "data must be fsync'ed before the rename"
    assert events[i][1] == os.path.abspath(out_dir) and events[i][2] == os.path.abspath(dest)
    assert dest.read_bytes() == b"x\ny\n"


def test_in_place_rewrite(dirs):
    src_dir, _ = dirs
    f = write(src_dir / "same.txt", b"a\nb\n")
    assert mod.transform_file_atomically(f, f, lambda s: s * 2) == 2
    assert f.read_bytes() == b"aa\nbb\n"
    assert os.listdir(src_dir) == ["same.txt"]


def test_undecodable_source_midway_leaves_destination_untouched(dirs):
    src_dir, out_dir = dirs
    src = write(src_dir / "a.txt", b"ok line\n" * 20_000 + b"bad \xff\xfe bytes\n")
    dest = write(out_dir / "d.txt", b"previous")
    with pytest.raises(UnicodeDecodeError):
        mod.transform_file_atomically(src, dest, lambda s: s)
    assert dest.read_bytes() == b"previous" and os.listdir(out_dir) == ["d.txt"]


def test_missing_source(dirs):
    src_dir, out_dir = dirs
    dest = write(out_dir / "d.txt", b"previous")
    with pytest.raises(FileNotFoundError):
        mod.transform_file_atomically(src_dir / "nope.txt", dest, lambda s: s)
    assert dest.read_bytes() == b"previous" and os.listdir(out_dir) == ["d.txt"]


def test_non_utf8_encoding_round_trip(dirs):
    src_dir, out_dir = dirs
    src = write(src_dir / "a.txt", "café\nnaïve\n".encode("latin-1"))
    dest = out_dir / "d.txt"
    mod.transform_file_atomically(src, dest, str.upper, encoding="latin-1")
    assert dest.read_bytes() == "CAFÉ\nNAÏVE\n".encode("latin-1")


def test_large_file_is_streamed(dirs):
    src_dir, out_dir = dirs
    src = src_dir / "big.txt"
    with open(src, "wb") as f:
        for i in range(250_000):
            f.write(b"%08d,some payload text to make the file larger\n" % i)
    dest = out_dir / "big.out"
    tracemalloc.start()
    try:
        n = mod.transform_file_atomically(src, dest, lambda s: s[:8])
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert n == 250_000 and dest.stat().st_size == 250_000 * 9
    assert peak < 4_000_000, f"peak traced memory {peak / 1e6:.1f} MB - stream the file, don't read it whole"
