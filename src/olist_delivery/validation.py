"""Python and SQL validation orchestration without conflating warning and success."""

from __future__ import annotations

import math
from typing import Any, Mapping

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
                    "failed",
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
                    "passed" if not item.get("missing_headers") else "failed",
                    str(item.get("headers", [])),
                    str(item.get("required_headers", [])),
                    "required CSV header contract",
                ),
                ValidationFinding(
                    f"source.{dataset}.declared_grain",
                    "passed" if item.get("duplicate_key_rows", 0) == 0 else "failed",
                    str(item.get("duplicate_key_rows", 0)),
                    "0 duplicate rows",
                    "duplicates remain preserved for inspection",
                ),
                ValidationFinding(
                    f"source.{dataset}.malformed_rows",
                    "passed" if item.get("malformed_rows", 0) == 0 else "failed",
                    str(item.get("malformed_rows", 0)),
                    "0 malformed rows",
                    "malformed source records are never silently discarded",
                ),
            )
        )
    for relationship in report.get("relationships", []):
        status = str(relationship.get("status", "not_evaluated"))
        if status not in {"passed", "warning", "failed", "not_evaluated"}:
            status = "failed"
        observed = relationship.get("orphan_rows", relationship.get("order_count", "unknown"))
        findings.append(
            ValidationFinding(
                f"relationship.{relationship['name']}",
                status,  # type: ignore[arg-type]
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
                "passed" if agrees else "failed",
                f"python={python_value!r}; sql={sql_value!r}",
                f"agreement within {tolerance}",
                "independent Python-to-SQL reconciliation",
            )
        )
    return tuple(findings)
