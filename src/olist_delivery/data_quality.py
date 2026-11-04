"""Shared validation result types and deterministic report rendering."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal

ValidationStatus = Literal["passed", "warning", "failed", "not_evaluated"]


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """One auditable validation result."""

    check_id: str
    status: ValidationStatus
    observed_value: str
    expected_value: str
    message: str


def overall_status(findings: Iterable[ValidationFinding]) -> ValidationStatus:
    """Aggregate findings without treating warnings or missing evidence as success."""

    statuses = {finding.status for finding in findings}
    if "failed" in statuses:
        return "failed"
    if "warning" in statuses:
        return "warning"
    if "not_evaluated" in statuses:
        return "not_evaluated"
    return "passed"


def write_validation_json(
    findings: Iterable[ValidationFinding],
    destination: Path,
    *,
    overwrite: bool = False,
) -> None:
    """Write stable machine-readable findings without silent replacement."""

    materialized = tuple(findings)
    payload = {
        "report_version": 1,
        "status": overall_status(materialized),
        "findings": [asdict(finding) for finding in materialized],
    }
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if destination.exists() and destination.read_text(encoding="utf-8") != content:
        if not overwrite:
            raise FileExistsError(f"validation report already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def render_validation_summary(findings: Iterable[ValidationFinding]) -> str:
    """Render a compact human-readable table."""

    materialized = tuple(findings)
    lines = ["check_id | status | observed | expected | message", "---|---|---|---|---"]
    for finding in materialized:
        values = (
            finding.check_id,
            finding.status,
            finding.observed_value,
            finding.expected_value,
            finding.message,
        )
        lines.append(" | ".join(value.replace("|", "\\|") for value in values))
    return "\n".join(lines) + "\n"
