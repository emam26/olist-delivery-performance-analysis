"""Python and SQL validation orchestration without conflating warning and success."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .data_quality import ValidationFinding


def _valid_sha256(value: Any) -> bool:
    text = str(value).lower()
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


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
                    ("Passed" if item.get("headers") == item.get("required_headers") else "Failed"),
                    str(item.get("headers", [])),
                    str(item.get("required_headers", [])),
                    "required CSV header contract",
                ),
                ValidationFinding(
                    f"source.{dataset}.checksum",
                    "Critical",
                    "Passed" if _valid_sha256(item.get("sha256", "")) else "Failed",
                    str(item.get("sha256", "")),
                    "64-character SHA-256",
                    "source identity used for load and snapshot provenance",
                ),
                ValidationFinding(
                    f"source.{dataset}.row_count",
                    "Critical",
                    "Passed" if int(item.get("row_count", 0)) > 0 else "Failed",
                    str(item.get("row_count", 0)),
                    "at least 1 data row",
                    "empty required datasets cannot support analysis",
                ),
                ValidationFinding(
                    f"source.{dataset}.required_identifiers",
                    "Critical",
                    "Passed" if item.get("blank_identifier_count", 0) == 0 else "Failed",
                    str(item.get("blank_identifier_count", 0)),
                    "0 blank identifier values",
                    str(item.get("blank_identifier_counts", {})),
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
                ValidationFinding(
                    f"source.{dataset}.timestamp_parse",
                    "Critical",
                    "Passed" if item.get("invalid_timestamp_count", 0) == 0 else "Failed",
                    str(item.get("invalid_timestamp_count", 0)),
                    "0 invalid non-empty timestamps",
                    "invalid timestamp text remains source evidence, never a zero date",
                ),
                ValidationFinding(
                    f"source.{dataset}.missing_values",
                    "Warning",
                    ("Warning" if sum(item.get("missing_values", {}).values()) > 0 else "Passed"),
                    str(sum(item.get("missing_values", {}).values())),
                    "profiled; no hidden imputation",
                    str(item.get("missing_values", {})),
                ),
                ValidationFinding(
                    f"source.{dataset}.negative_delivery_intervals",
                    "Warning",
                    (
                        "Warning"
                        if item.get("negative_delivery_interval_count", 0) > 0
                        else "Passed"
                    ),
                    str(item.get("negative_delivery_interval_count", 0)),
                    "0 preferred",
                    "negative intervals are excluded from duration KPIs",
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
            agrees = math.isclose(
                float(python_value),
                float(sql_value),
                rel_tol=0.0,
                abs_tol=tolerance,
            )
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
