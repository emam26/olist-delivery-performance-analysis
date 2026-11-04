from __future__ import annotations

import json
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
