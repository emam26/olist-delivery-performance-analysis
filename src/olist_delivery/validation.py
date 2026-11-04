"""Python and SQL validation orchestration without conflating warning and success."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .data_quality import ValidationFinding


def inventory_findings(report: Mapping[str, Any]) -> tuple[ValidationFinding, ...]:
    """Translate inventory evidence into stable validation findings."""

    findings: list[ValidationFinding] = []
    for item in report.get("files", []):
        dataset = str(item.get("dataset", "unknown"))
        if not item.get("exists", False):
            findings.append(
                ValidationFinding(
                    f"source.{dataset}.presence",
                    "Critical",
                    "Failed",
                    "missing",
                    "present",
                    str(item.get("errors", ["required file is missing"])[0]),
                )
            )
            continue
        findings.extend(
            (
                ValidationFinding(
                    f"source.{dataset}.headers",
                    "Critical",
                    "Passed" if not item.get("missing_headers") else "Failed",
                    str(item.get("headers", [])),
                    str(item.get("required_headers", [])),
                    "required CSV header contract",
                ),
                ValidationFinding(
                    f"source.{dataset}.declared_grain",
                    "Critical",
                    "Passed" if item.get("duplicate_natural_key_count", 0) == 0 else "Failed",
                    str(item.get("duplicate_natural_key_count", 0)),
                    "0 duplicate rows",
                    "duplicates remain preserved for inspection",
                ),
                ValidationFinding(
                    f"source.{dataset}.malformed_rows",
                    "Critical",
                    "Passed" if item.get("malformed_record_count", 0) == 0 else "Failed",
                    str(item.get("malformed_record_count", 0)),
                    "0 malformed rows",
                    "malformed source records are never silently discarded",
                ),
            )
        )
    for relationship in report.get("relationships", []):
        status = str(relationship.get("status", "not_evaluated")).lower()
        if status not in {"passed", "warning", "failed", "not_evaluated"}:
            status = "failed"
        observed = relationship.get("observed_count", "unknown")
        severity = "Critical" if status == "failed" else "Warning"
        status_name = {
            "passed": "Passed",
            "warning": "Warning",
            "failed": "Failed",
            "not_evaluated": "NotEvaluated",
        }[status]
        findings.append(
            ValidationFinding(
                f"relationship.{relationship['check_id']}",
                severity,
                status_name,
                str(observed),
                "0 or documented source exception",
                str(relationship.get("message", "source relationship check")),
            )
        )
    return tuple(findings)


def run_sql_validation(connection: Any, *, fail_on_warning: bool = False) -> tuple[Any, ...]:
    """Run the installed SQL validation procedure and return its result rows."""

    cursor = connection.cursor()
    cursor.execute("EXEC audit.usp_run_validation @fail_on_warning = ?", (fail_on_warning,))
    rows = tuple(cursor.fetchall())
    connection.commit()
    return rows


def reconcile_metric_values(
    python_values: Mapping[str, Any],
    sql_values: Mapping[str, Any],
    *,
    tolerance: float = 1e-9,
) -> tuple[ValidationFinding, ...]:
    """Compare independently calculated metrics with explicit numeric tolerance."""

    findings = []
    for name in sorted(set(python_values) | set(sql_values)):
        python_value = python_values.get(name)
        sql_value = sql_values.get(name)
        if isinstance(python_value, (int, float)) and isinstance(sql_value, (int, float)):
            agrees = math.isclose(float(python_value), float(sql_value), abs_tol=tolerance)
        else:
            agrees = python_value == sql_value
        findings.append(
            ValidationFinding(
                f"metric.{name}",
                "Critical",
                "Passed" if agrees else "Failed",
                f"python={python_value!r}; sql={sql_value!r}",
                f"agreement within {tolerance}",
                "independent Python-to-SQL reconciliation",
            )
        )
    return tuple(findings)
