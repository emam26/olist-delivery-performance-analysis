"""Calculate core KPIs independently from the orders CSV and optionally reconcile SQL."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from pathlib import Path

from olist_delivery.database import database_connection, safe_database_error
from olist_delivery.datasets import DATASETS_BY_NAME
from olist_delivery.metrics import aggregate_delivery_metrics
from olist_delivery.serialization import dumps_report_json
from olist_delivery.validation import reconcile_metric_values

RECONCILIATION_KEYS = (
    "source_order_count",
    "delivered_order_count",
    "eligible_order_count",
    "delivery_status_excluded_order_count",
    "on_time_order_count",
    "late_order_count",
    "on_time_delivery_rate",
    "late_delivery_rate",
    "duration_eligible_order_count",
    "duration_excluded_order_count",
    "average_delivery_hours",
    "median_delivery_hours",
    "p90_delivery_hours",
    "p95_delivery_hours",
    "average_days_late",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--orders-csv",
        type=Path,
        default=Path("data/raw/olist_orders_dataset.csv"),
    )
    parser.add_argument(
        "--json-output",
        "--output",
        type=Path,
        dest="output",
        default=Path("reports/metric_validation.json"),
    )
    parser.add_argument("--sqlserver", action="store_true")
    return parser


def _orders(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        required = set(DATASETS_BY_NAME["orders"].columns)
        missing = sorted(required - set(reader.fieldnames or ()))
        if missing:
            raise ValueError(f"orders CSV is missing required headers: {missing}")
        return list(reader)


def _sql_metrics(connection: object) -> dict[str, object]:
    cursor = connection.cursor()  # type: ignore[attr-defined]
    cursor.execute(
        "SELECT " + ", ".join(RECONCILIATION_KEYS) + " FROM reporting.vw_delivery_overview"
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("reporting.vw_delivery_overview returned no row")
    return dict(zip(RECONCILIATION_KEYS, row, strict=True))


def main() -> int:
    args = build_parser().parse_args()
    try:
        python_metrics = aggregate_delivery_metrics(_orders(args.orders_csv))
        report: dict[str, object] = {"python_metrics": python_metrics}
        failed = False
        if args.sqlserver:
            with database_connection() as connection:
                sql_metrics = _sql_metrics(connection)
            findings = reconcile_metric_values(python_metrics, sql_metrics, tolerance=1e-4)
            report["sql_metrics"] = sql_metrics
            report["reconciliation"] = [asdict(finding) for finding in findings]
            failed = any(finding.status.lower() == "failed" for finding in findings)
            report["status"] = "failed" if failed else "passed"
        else:
            report["status"] = "not_evaluated"
            report["sql_reconciliation"] = "NOT RUN"
        if args.output.exists():
            raise FileExistsError(f"metric report already exists: {args.output}")
        serialized_report = dumps_report_json(report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized_report + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"Metric validation failed: {safe_database_error(exc)}")
        return 1
    print(serialized_report)
    print(f"Metric validation report: {args.output}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
