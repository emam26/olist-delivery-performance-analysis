"""Shared validation result types and deterministic report rendering."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ValidationStatus = Literal["Passed", "Warning", "Failed", "NotEvaluated"]
ValidationSeverity = Literal["Critical", "Warning", "Information"]

_STATUS_NAMES = {
    "passed": "Passed",
    "warning": "Warning",
    "failed": "Failed",
    "not_evaluated": "NotEvaluated",
    "notevaluated": "NotEvaluated",
}


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """One auditable validation result."""

    check_id: str
    severity: str
    status: str
    observed_value: str
    expected_value: str
    details: str


def _canonical_status(status: str) -> ValidationStatus:
    try:
        return _STATUS_NAMES[status.replace(" ", "").lower()]
    except KeyError as exc:
        raise ValueError(f"unknown validation status: {status}") from exc


def _finding_payload(finding: ValidationFinding) -> dict[str, str]:
    payload = asdict(finding)
    payload["status"] = _canonical_status(finding.status)
    return payload


def overall_status(findings: Iterable[ValidationFinding]) -> str:
    """Aggregate findings without allowing warnings to masquerade as passes."""

    materialized = tuple(findings)
    if any(
        finding.severity.strip().lower() == "critical"
        and _canonical_status(finding.status) == "Failed"
        for finding in materialized
    ):
        return "failed"
    if any(
        _canonical_status(finding.status) in {"Warning", "Failed", "NotEvaluated"}
        for finding in materialized
    ):
        return "warning"
    return "passed"


def write_validation_json(
    findings: Iterable[ValidationFinding],
    destination: Path,
    *,
    run_id: int | None = None,
    overwrite: bool = False,
) -> None:
    """Write stable machine-readable findings without silent replacement."""

    materialized = tuple(findings)
    payload: dict[str, object] = {
        "report_version": 1,
        "status": overall_status(materialized),
        "findings": [_finding_payload(finding) for finding in materialized],
    }
    if run_id is not None:
        payload["run_id"] = run_id
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if destination.exists() and not overwrite:
        raise FileExistsError(f"validation report already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def render_validation_summary(findings: Iterable[ValidationFinding]) -> str:
    """Render a compact human-readable validation table."""

    materialized = tuple(findings)
    lines = [
        f"Validation status: {overall_status(materialized)}",
        "",
        "check_id | severity | status | observed | expected | details",
        "---|---|---|---|---|---",
    ]
    for finding in materialized:
        values = (
            finding.check_id,
            finding.severity,
            _canonical_status(finding.status),
            finding.observed_value,
            finding.expected_value,
            finding.details,
        )
        lines.append(" | ".join(value.replace("|", "\\|") for value in values))
    return "\n".join(lines) + "\n"


def write_validation_markdown(
    findings: Iterable[ValidationFinding],
    destination: Path,
    *,
    run_id: int | None = None,
    overwrite: bool = False,
) -> None:
    """Write a deterministic Markdown validation artifact."""

    content = render_validation_summary(findings)
    if run_id is not None:
        content = f"Run ID: {run_id}\n\n" + content
    if destination.exists() and not overwrite:
        raise FileExistsError(f"validation report already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
