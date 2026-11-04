"""Render Python inventory findings and optionally run SQL Server validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from olist_delivery.data_quality import (
    ValidationFinding,
    overall_status,
    render_validation_summary,
    write_validation_json,
)
from olist_delivery.database import database_connection, safe_database_error
from olist_delivery.validation import inventory_findings, run_sql_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory-report",
        type=Path,
        default=Path("reports/inventory/inventory.json"),
    )
    parser.add_argument("--output", type=Path, default=Path("reports/validation.json"))
    parser.add_argument("--summary", type=Path, default=Path("reports/validation.md"))
    parser.add_argument("--sqlserver", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _sql_findings(rows: tuple[object, ...]) -> tuple[ValidationFinding, ...]:
    return tuple(
        ValidationFinding(
            check_id=f"sql.{row[0]}",
            status=str(row[1]).lower(),  # type: ignore[arg-type]
            observed_value=str(row[2] or ""),
            expected_value=str(row[3] or ""),
            message=str(row[4]),
        )
        for row in rows
    )


def main() -> int:
    args = build_parser().parse_args()
    try:
        inventory = json.loads(args.inventory_report.read_text(encoding="utf-8"))
        findings = list(inventory_findings(inventory))
        if args.sqlserver:
            with database_connection() as connection:
                findings.extend(_sql_findings(run_sql_validation(connection, fail_on_warning=False)))
        else:
            findings.append(
                ValidationFinding(
                    "sql.validation",
                    "not_evaluated",
                    "not run",
                    "manual SQL Server validation",
                    "pass --sqlserver only after SQL objects and staging loads exist",
                )
            )
        write_validation_json(findings, args.output, overwrite=args.overwrite)
        summary = render_validation_summary(findings)
        if args.summary.exists() and not args.overwrite:
            raise FileExistsError(f"validation summary already exists: {args.summary}")
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(summary, encoding="utf-8")
    except Exception as exc:
        print(f"Validation failed: {safe_database_error(exc)}")
        return 1
    status = overall_status(findings)
    print(summary, end="")
    print(f"Validation status: {status}")
    if status == "failed" or (args.strict and status != "passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
