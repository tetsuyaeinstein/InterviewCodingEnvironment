"""PY-007 reference solution: validate the schema once, then a per-field pipeline
(presence -> null -> coerce -> allowed) whose failures are a private exception carrying the
error code. The row loop catches it, so each field yields at most one error and nothing
data-dependent can escape.
"""
from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

FIELD_TYPES = ("str", "int", "decimal", "bool", "date")
UNKNOWN_FIELD_POLICIES = ("error", "ignore", "keep")


class SchemaError(ValueError):
    """The schema itself is invalid (a configuration bug, not a data problem)."""


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    required: bool = True
    nullable: bool = False
    allowed: Collection[Any] | None = None


@dataclass(frozen=True)
class RowError:
    row_index: int
    field: str | None
    error_code: str
    message: str


class _Invalid(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_INT_RE = re.compile(r"[+-]?\d+", re.ASCII)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)


def _type_error(value: Any, expected: str) -> _Invalid:
    return _Invalid("invalid_type", f"expected {expected}, got {type(value).__name__} {value!r}")


def _to_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    raise _type_error(value, "a string")


def _to_int(value: Any) -> int:
    if isinstance(value, bool):                 # bool is an int subclass: reject first
        raise _type_error(value, "an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if _INT_RE.fullmatch(text):
            return int(text)
        raise _Invalid("invalid_format", f"not an integer: {value!r}")
    raise _type_error(value, "an integer")


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, (bool, float)):        # float: binary rounding already happened
        raise _type_error(value, "a decimal")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except InvalidOperation:
            raise _Invalid("invalid_format", f"not a decimal number: {value!r}") from None
    else:
        raise _type_error(value, "a decimal")
    if not result.is_finite():
        raise _Invalid("invalid_format", f"decimal must be finite: {value!r}")
    return result


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "false"):
            return text == "true"
        raise _Invalid("invalid_format", f"not a boolean (true/false): {value!r}")
    raise _type_error(value, "a boolean")


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):             # datetime is a date subclass: reject first
        raise _type_error(value, "a date (not a datetime)")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if _DATE_RE.fullmatch(text):
            try:
                return date.fromisoformat(text)
            except ValueError:
                pass
        raise _Invalid("invalid_format", f"not a YYYY-MM-DD date: {value!r}")
    raise _type_error(value, "a date")


_COERCERS: dict[str, Callable[[Any], Any]] = {
    "str": _to_str, "int": _to_int, "decimal": _to_decimal, "bool": _to_bool, "date": _to_date,
}


def _allowed_value_ok(ftype: str, v: Any) -> bool:
    if ftype == "str":
        return isinstance(v, str)
    if ftype == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if ftype == "decimal":
        return isinstance(v, Decimal)
    if ftype == "bool":
        return isinstance(v, bool)
    return isinstance(v, date) and not isinstance(v, datetime)


def _check_schema(schema: Sequence[FieldSpec]) -> list[FieldSpec]:
    if isinstance(schema, (str, bytes, Mapping)) or not isinstance(schema, Iterable):
        raise SchemaError("schema must be a sequence of FieldSpec")
    fields = list(schema)
    seen: set[str] = set()
    for spec in fields:
        if not isinstance(spec, FieldSpec):
            raise SchemaError(f"schema entries must be FieldSpec, got {type(spec).__name__}")
        if not isinstance(spec.name, str) or not spec.name:
            raise SchemaError(f"field name must be a non-empty str: {spec.name!r}")
        if spec.name in seen:
            raise SchemaError(f"duplicate field name {spec.name!r}")
        seen.add(spec.name)
        if spec.type not in FIELD_TYPES:
            raise SchemaError(f"{spec.name}: unknown type {spec.type!r}")
        if not isinstance(spec.required, bool) or not isinstance(spec.nullable, bool):
            raise SchemaError(f"{spec.name}: required/nullable must be bool")
        if spec.allowed is not None:
            if isinstance(spec.allowed, (str, bytes)) or not isinstance(spec.allowed, Collection) \
                    or len(spec.allowed) == 0:
                raise SchemaError(f"{spec.name}: allowed must be a non-empty collection of values")
            bad = [v for v in spec.allowed if not _allowed_value_ok(spec.type, v)]
            if bad:
                raise SchemaError(f"{spec.name}: allowed values {bad!r} do not match type {spec.type}")
    return fields


def _validate_field(spec: FieldSpec, value: Any) -> Any:
    is_null = value is None or (spec.type != "str" and isinstance(value, str) and not value.strip())
    if is_null:
        if spec.nullable:
            return None
        raise _Invalid("null_not_allowed", f"{spec.name} must not be null")
    coerced = _COERCERS[spec.type](value)
    if spec.allowed is not None and coerced not in spec.allowed:
        raise _Invalid("not_allowed", f"{coerced!r} is not one of the allowed values")
    return coerced


def validate_rows(rows: Iterable[Any], schema: Sequence[FieldSpec], *,
                  unknown_fields: str = "error") -> tuple[list[dict], list[RowError]]:
    fields = _check_schema(schema)
    if unknown_fields not in UNKNOWN_FIELD_POLICIES:
        raise ValueError(f"unknown_fields must be one of {UNKNOWN_FIELD_POLICIES}, got {unknown_fields!r}")
    names = {spec.name for spec in fields}

    valid: list[dict] = []
    errors: list[RowError] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append(RowError(index, None, "not_a_mapping",
                                   f"row must be a mapping, got {type(row).__name__}"))
            continue
        n_before = len(errors)
        out: dict[Any, Any] = {}
        for spec in fields:
            if spec.name not in row:
                if spec.required:
                    errors.append(RowError(index, spec.name, "missing_required",
                                           f"required field {spec.name!r} is missing"))
                continue
            try:
                out[spec.name] = _validate_field(spec, row[spec.name])
            except _Invalid as bad:
                errors.append(RowError(index, spec.name, bad.code, f"{spec.name}: {bad.message}"))
        unknown = [key for key in row if key not in names]
        if unknown_fields == "error":
            for key in sorted(unknown, key=str):
                errors.append(RowError(index, str(key), "unknown_field", f"unexpected field {key!r}"))
        elif unknown_fields == "keep":
            for key in unknown:
                out[key] = row[key]
        if len(errors) == n_before:
            valid.append(out)
    return valid, errors
