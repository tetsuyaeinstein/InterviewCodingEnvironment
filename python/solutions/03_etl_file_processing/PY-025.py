"""PY-025 reference solution: one accumulator object per column, updated once per value.

Every statistic is chosen so it can be maintained incrementally (and merged, see the
explanation): counts, a value -> [first value, count] map for distinct/top-k, min/max kept per
type *family* (so a mixed column never triggers a TypeError mid-stream), and an exact Decimal
running sum for the mean.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass
class ColumnProfile:
    name: str
    count: int
    null_count: int
    distinct_count: int
    min: object = None
    max: object = None
    mean: Decimal | None = None
    top_values: list[tuple[object, int]] = field(default_factory=list)
    inferred_type: str = "null"
    types_seen: tuple[str, ...] = ()


def _type_name(v: object) -> str:
    # order matters: bool is an int subclass, datetime is a date subclass
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, (float, Decimal)):
        return "decimal"
    if isinstance(v, str):
        return "str"
    if isinstance(v, datetime):
        return "datetime"
    if isinstance(v, date):
        return "date"
    raise TypeError(f"unsupported value type {type(v).__name__}")


_NUMERIC = {"int", "decimal"}


class _Acc:
    __slots__ = ("non_null", "values", "types", "lo", "hi", "total")

    def __init__(self) -> None:
        self.non_null = 0
        self.values: dict[tuple, list] = {}   # identity -> [first value seen, count]
        self.types: set[str] = set()
        self.lo: dict[str, object] = {}       # family -> min
        self.hi: dict[str, object] = {}       # family -> max
        self.total = Decimal(0)

    def add(self, v: object) -> None:
        t = _type_name(v)
        family = "num" if t in _NUMERIC else t
        self.non_null += 1
        self.types.add(t)
        ident = (family, v)                   # 1 == 1.0 == Decimal('1.00'), but True is not 1
        slot = self.values.get(ident)
        if slot is None:
            self.values[ident] = [v, 1]
        else:
            slot[1] += 1
        if family not in self.lo:
            self.lo[family] = self.hi[family] = v
        else:
            if v < self.lo[family]:
                self.lo[family] = v
            if v > self.hi[family]:
                self.hi[family] = v
        if family == "num":
            self.total += Decimal(repr(v)) if isinstance(v, float) else v

    def finish(self, name: str, rows: int) -> ColumnProfile:
        types = tuple(sorted(self.types))
        if not types:
            inferred = "null"
        elif len(types) == 1:
            inferred = types[0]
        elif set(types) <= _NUMERIC:
            inferred = "decimal"              # int + decimal widen; not flagged as mixed
        else:
            inferred = "mixed"
        families = list(self.lo)
        lo = hi = mean = None
        if inferred != "mixed" and len(families) == 1:
            lo, hi = self.lo[families[0]], self.hi[families[0]]
        if inferred in _NUMERIC:
            mean = self.total / self.non_null
        # stable sort by count desc keeps first-seen order for ties
        ranked = sorted(self.values.values(), key=lambda s: -s[1])[:3]
        return ColumnProfile(name=name, count=rows, null_count=rows - self.non_null,
                             distinct_count=len(self.values), min=lo, max=hi, mean=mean,
                             top_values=[(v, c) for v, c in ranked], inferred_type=inferred,
                             types_seen=types)


def profile_columns(rows: Iterable[Mapping[str, object]]) -> dict[str, ColumnProfile]:
    accs: dict[str, _Acc] = {}
    n = 0
    for row in rows:
        n += 1
        for col, v in row.items():
            acc = accs.get(col)
            if acc is None:
                acc = accs[col] = _Acc()      # rows before this one count as NULL via `n`
            if v is not None:
                acc.add(v)
    return {col: acc.finish(col, n) for col, acc in accs.items()}
