from __future__ import annotations

import json
from decimal import Decimal

import pytest

from olist_delivery.serialization import dumps_report_json


def test_report_json_preserves_sql_decimal_values_in_nested_payloads() -> None:
    report = {
        "sql_metrics": {
            "count": Decimal("12"),
            "missing": None,
            "nested": {
                "negative": Decimal("-1.2500"),
                "precise": Decimal("0.123456789012345678901234567890"),
                "rate": Decimal("0.750000"),
            },
        },
        "status": "passed",
    }

    payload = json.loads(dumps_report_json(report))

    assert payload["sql_metrics"]["count"] == 12
    assert isinstance(payload["sql_metrics"]["count"], int)
    assert payload["sql_metrics"]["missing"] is None
    assert payload["sql_metrics"]["nested"] == {
        "negative": "-1.2500",
        "precise": "0.123456789012345678901234567890",
        "rate": "0.750000",
    }


def test_report_json_rejects_unexpected_objects() -> None:
    with pytest.raises(TypeError, match="object.*not JSON serializable"):
        dumps_report_json({"unexpected": object()})


def test_report_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="non-finite Decimal"):
        dumps_report_json({"metric": Decimal("NaN")})

    with pytest.raises(ValueError, match="Out of range float values"):
        dumps_report_json({"metric": float("inf")})
