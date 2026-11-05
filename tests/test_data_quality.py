from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from olist_delivery.data_quality import (
    ValidationFinding,
    overall_status,
    write_validation_json,
    write_validation_markdown,
)
from olist_delivery.validation import reconcile_metric_values


def _finding(*, severity: str = "Critical", status: str = "Passed") -> ValidationFinding:
    return ValidationFinding(
        check_id="example_check",
        severity=severity,
        status=status,
        observed_value="0",
        expected_value="0",
        details="Synthetic unit-test finding.",
    )


def test_overall_status_blocks_on_failed_critical_check() -> None:
    findings = [
        _finding(),
        _finding(severity="Warning", status="Failed"),
        _finding(severity="Critical", status="Failed"),
    ]

    assert overall_status(findings) == "failed"


def test_warning_failure_does_not_become_a_critical_pass() -> None:
    assert overall_status([_finding(severity="Warning", status="Failed")]) == "warning"


def test_validation_artifacts_are_created_without_overwrite(tmp_path: Path) -> None:
    findings = [_finding()]
    json_path = tmp_path / "validation.json"
    markdown_path = tmp_path / "validation.md"

    write_validation_json(findings, json_path, run_id=7)
    write_validation_markdown(findings, markdown_path, run_id=7)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == 7
    assert payload["status"] == "passed"
    assert "example_check" in markdown_path.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_validation_json(findings, json_path, run_id=7)


def test_metric_reconciliation_uses_absolute_tolerance_only() -> None:
    findings = reconcile_metric_values(
        {"large_metric": 1_000_000_000_000.0},
        {"large_metric": 1_000_000_000_001.0},
        tolerance=1e-4,
    )

    assert findings[0].status == "Failed"


def test_metric_reconciliation_supports_sql_decimal_values_and_nulls() -> None:
    findings = reconcile_metric_values(
        {
            "count": 10,
            "missing": None,
            "negative_average": -1.25,
            "rate": 2 / 3,
        },
        {
            "count": Decimal("10"),
            "missing": None,
            "negative_average": Decimal("-1.2500"),
            "rate": Decimal("0.666667"),
        },
        tolerance=1e-4,
    )

    assert all(finding.status == "Passed" for finding in findings)


def test_metric_reconciliation_detects_decimal_mismatch() -> None:
    findings = reconcile_metric_values(
        {"rate": 0.5},
        {"rate": Decimal("0.5002")},
        tolerance=1e-4,
    )

    assert findings[0].status == "Failed"


def test_metric_reconciliation_distinguishes_null_from_missing_key() -> None:
    findings = reconcile_metric_values(
        {"nullable_metric": None},
        {},
        tolerance=1e-4,
    )

    assert findings[0].status == "Failed"
    assert "sql=<missing key>" in findings[0].observed_value


def test_metric_reconciliation_never_rounds_large_integer_counts_to_a_match() -> None:
    findings = reconcile_metric_values(
        {"count": 9_007_199_254_740_993},
        {"count": Decimal("9007199254740992")},
        tolerance=1.0,
    )

    assert findings[0].status == "Failed"
