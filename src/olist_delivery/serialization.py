"""Strict JSON serialization for reports containing SQL Server numeric values."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any


def _report_json_default(value: object) -> int | str:
    if not isinstance(value, Decimal):
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
    if not value.is_finite():
        raise ValueError("non-finite Decimal values are not valid report values")
    if value == value.to_integral_value():
        return int(value)
    return format(value, "f")


def dumps_report_json(payload: Any) -> str:
    """Render deterministic JSON without losing fractional ``Decimal`` precision.

    Integral ``Decimal`` values become JSON integers. Fractional values become
    base-10 strings so their precision and trailing zeros survive JSON parsing.
    Unsupported objects and non-finite numeric values fail explicitly.
    """

    return json.dumps(
        payload,
        allow_nan=False,
        default=_report_json_default,
        indent=2,
        sort_keys=True,
    )
