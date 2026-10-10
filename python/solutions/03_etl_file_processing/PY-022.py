"""PY-022 reference solution: a generator that parses one line at a time with a strict json decoder.

- object_pairs_hook detects duplicate keys (json.loads would silently keep the last one);
- parse_float=Decimal keeps 0.1 exact and 1e400 finite; parse_constant rejects NaN/Infinity;
- the quarantine is a caller-owned sink, so records stream out while rejects are collected.
"""
from __future__ import annotations

import json
from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal

INVALID_JSON = "invalid_json"
NOT_AN_OBJECT = "not_an_object"
DUPLICATE_KEY = "duplicate_key"
MISSING_KEYS = "missing_keys"


@dataclass(frozen=True)
class Rejected:
    line_number: int
    raw: str
    reason: str
    detail: str = ""


class _DuplicateKey(ValueError):
    pass


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict:
    obj: dict = {}
    for k, v in pairs:
        if k in obj:
            raise _DuplicateKey(k)
        obj[k] = v
    return obj


def _reject_constant(name: str):
    raise ValueError(f"non-standard JSON constant {name}")


_decoder = json.JSONDecoder(object_pairs_hook=_pairs_hook, parse_float=Decimal,
                            parse_constant=_reject_constant)


def read_ndjson(lines: Iterable[str], required_keys: Collection[str],
                quarantine: list[Rejected]) -> Iterator[dict]:
    required = tuple(required_keys)
    for line_number, line in enumerate(lines, start=1):
        raw = line.rstrip("\r\n")
        text = raw[1:] if line_number == 1 and raw.startswith("﻿") else raw
        if not text.strip():
            continue
        try:
            obj = _decoder.decode(text)        # tolerates surrounding whitespace, nothing else
        except _DuplicateKey as e:
            quarantine.append(Rejected(line_number, raw, DUPLICATE_KEY, f"duplicate key {e.args[0]!r}"))
            continue
        except ValueError as e:                # JSONDecodeError is a ValueError subclass
            quarantine.append(Rejected(line_number, raw, INVALID_JSON, str(e)))
            continue
        except RecursionError:                 # pathologically nested input
            quarantine.append(Rejected(line_number, raw, INVALID_JSON, "nesting too deep"))
            continue
        if not isinstance(obj, dict):
            quarantine.append(Rejected(line_number, raw, NOT_AN_OBJECT, type(obj).__name__))
            continue
        missing = sorted(k for k in required if k not in obj)
        if missing:
            quarantine.append(Rejected(line_number, raw, MISSING_KEYS, ", ".join(missing)))
            continue
        yield obj
