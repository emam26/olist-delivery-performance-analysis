"""Render Python inventory findings and optionally run SQL Server validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from olist_delivery.data_quality import (
    ValidationFinding,
    overall_status,
    render_validation_summary,
    write_validation_json,
    write_validation_markdown,
)
from olist_delivery.database import database_connection, safe_database_error
from olist_delivery.validation import inventory_findings, run_sql_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        "--inventory-report",
        type=Path,
        dest="inventory_report",
        default=Path("reports/inventory/inventory.json"),
    )
    parser.add_argument(
        "--json-output",
        "--output",
        type=Path,
        dest="output",
        default=Path("reports/validation.json"),
    )
    parser.add_argument(
        "--markdown-output",
        "--summary",
        type=Path,
        dest="summary",
        default=Path("reports/validation.md"),
    )
    parser.add_argument("--sqlserver", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _sql_findings(rows: tuple[Any, ...]) -> tuple[ValidationFinding, ...]:
    return tuple(
        ValidationFinding(
            check_id=f"sql.{row[1]}",
            severity="Warning" if str(row[2]).lower() == "warning" else "Critical",
            status=str(row[2]),
            observed_value=str(row[3] or ""),
            expected_value=str(row[4] or ""),
            details=str(row[5]),
        )
        for row in rows
    )


def main() -> int:
    args = build_parser().parse_args()
    sql_validation_run_id: int | None = None
    try:
        inventory = json.loads(args.inventory_report.read_text(encoding="utf-8"))
        findings = list(inventory_findings(inventory))
        if args.sqlserver:
            with database_connection() as connection:
                sql_rows = run_sql_validation(connection, fail_on_warning=False)
                findings.extend(_sql_findings(sql_rows))
                if sql_rows:
                    sql_validation_run_id = int(sql_rows[0][0])
        else:
            findings.append(
                ValidationFinding(
                    "sql.validation",
                    "Information",
                    "NotEvaluated",
                    "not run",
                    "manual SQL Server validation",
                    "pass --sqlserver only after SQL objects and staging loads exist",
                )
            )
        write_validation_json(
            findings,
            args.output,
            run_id=sql_validation_run_id,
            overwrite=args.overwrite,
        )
        write_validation_markdown(
            findings,
            args.summary,
            run_id=sql_validation_run_id,
            overwrite=args.overwrite,
        )
        summary = render_validation_summary(findings)
    except Exception as exc:
        print(f"Validation failed: {safe_database_error(exc)}")
        return 1
    status = overall_status(findings)
    print(summary, end="")
    print(f"Validation status: {status}")
    if sql_validation_run_id is not None:
        print(f"SQL validation run ID: {sql_validation_run_id}")
    if status == "failed" or (args.strict and status != "passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
