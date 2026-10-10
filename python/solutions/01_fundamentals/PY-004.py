"""PY-004 reference solution: iterative depth-first walk with an explicit stack of iterators.

Each stack frame is (key prefix, depth, iterator over that container's children). Keeping the
iterator (rather than pushing all children up front) preserves input order and keeps extra
memory proportional to the depth, not to the width of the payload. No recursion, so a
5,000-level payload cannot hit RecursionError.
"""
from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping
from typing import Any

_DONE = object()


def _is_container(value: Any) -> bool:
    return isinstance(value, (Mapping, list, tuple))


def _children(container: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(container, Mapping):
        for key, value in container.items():
            if not isinstance(key, str):
                raise TypeError(f"mapping keys must be str, got {type(key).__name__}: {key!r}")
            yield key, value
    else:
        for index, value in enumerate(container):
            yield str(index), value


def _emit(out: dict[str, Any], key: str, value: Any) -> None:
    if key in out:
        raise ValueError(f"flattened key collision: {key!r}")
    if isinstance(value, Mapping):
        out[key] = copy.deepcopy(dict(value)) if value else {}
    elif isinstance(value, (list, tuple)):
        out[key] = copy.deepcopy(value) if value else []
    else:
        out[key] = value                      # leaves are stored as-is


def flatten_record(record: Mapping[str, Any], *, sep: str = ".",
                   max_depth: int | None = None) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError(f"record must be a Mapping, got {type(record).__name__}")
    if not isinstance(sep, str) or not sep:
        raise ValueError("sep must be a non-empty string")
    if max_depth is not None and (isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 1):
        raise ValueError(f"max_depth must be None or a positive int, got {max_depth!r}")

    out: dict[str, Any] = {}
    stack: list[tuple[str, int, Iterator[tuple[str, Any]]]] = [("", 0, _children(record))]
    while stack:
        prefix, depth, children = stack[-1]
        child = next(children, _DONE)
        if child is _DONE:
            stack.pop()
            continue
        segment, value = child
        key = segment if depth == 0 else f"{prefix}{sep}{segment}"
        key_depth = depth + 1                 # number of segments in `key`
        expandable = _is_container(value) and len(value) > 0
        if expandable and (max_depth is None or key_depth < max_depth):
            stack.append((key, key_depth, _children(value)))
        else:
            _emit(out, key, value)
    return out
