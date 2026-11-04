"""Non-overwriting exports from validated SQL reporting views for Power BI."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ExportSpec:
    """One reporting export with explicit columns and deterministic ordering."""

    filename: str
    view: str
    columns: tuple[str, ...]
    order_by: tuple[str, ...]


EXPORT_SPECS: tuple[ExportSpec, ...] = (
    ExportSpec(
        "order_delivery.csv",
        "reporting.vw_order_delivery_detail",
        (
            "order_id",
            "customer_state",
            "purchase_month",
            "order_status",
            "is_delivered",
            "is_delivery_eligible",
            "is_late",
            "is_duration_eligible",
            "delivery_duration_hours",
            "days_late",
            "selected_review_score",
            "delivery_exclusion_reason",
            "duration_exclusion_reason",
            "exclusion_reason",
        ),
        ("order_id",),
    ),
    ExportSpec(
        "monthly_delivery.csv",
        "reporting.vw_monthly_delivery",
        (
            "purchase_month",
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
        ),
        ("purchase_month",),
    ),
    ExportSpec(
        "regional_delivery.csv",
        "reporting.vw_state_delivery",
        (
            "customer_state",
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
        ),
        ("customer_state",),
    ),
    ExportSpec(
        "seller_delivery.csv",
        "reporting.vw_seller_delivery",
        (
            "seller_id",
            "seller_state",
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
        ),
        ("seller_id",),
    ),
    ExportSpec(
        "category_delivery.csv",
        "reporting.vw_category_delivery",
        (
            "product_category_name",
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
        ),
        ("product_category_name",),
    ),
    ExportSpec(
        "review_delivery.csv",
        "reporting.vw_review_delivery_distribution",
        ("delivery_class", "review_score", "review_count", "orders_without_usable_review"),
        ("delivery_class", "review_score"),
    ),
    ExportSpec(
        "source_provenance.csv",
        "reporting.vw_current_source_provenance",
        (
            "dataset_snapshot_id",
            "source_manifest_sha256",
            "dataset_name",
            "load_batch_id",
            "source_filename",
            "source_sha256",
            "expected_row_count",
            "inserted_row_count",
            "completed_at_utc",
        ),
        ("dataset_name",),
    ),
    ExportSpec(
        "validation_results.csv",
        "reporting.vw_latest_validation_results",
        (
            "validation_run_id",
            "dataset_snapshot_id",
            "source_manifest_sha256",
            "run_status",
            "started_at_utc",
            "completed_at_utc",
            "check_id",
            "check_status",
            "observed_value",
            "expected_value",
            "message",
        ),
        ("check_id",),
    ),
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_export_context(connection: Any) -> dict[str, Any]:
    cursor = connection.cursor()
    cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    cursor.execute(
        """
        SELECT TOP (1) dataset_snapshot_id, source_manifest_sha256
        FROM audit.dataset_snapshots AS snapshots WITH (HOLDLOCK)
        WHERE status = 'Succeeded' AND dataset_count = 6
          AND (SELECT COUNT_BIG(*)
               FROM audit.dataset_snapshot_batches AS mappings
               INNER JOIN audit.load_batches AS batches
                   ON batches.load_batch_id = mappings.load_batch_id
                  AND batches.dataset_name = mappings.dataset_name
                  AND batches.source_sha256 = mappings.source_sha256
                  AND batches.status = 'Succeeded'
               WHERE mappings.dataset_snapshot_id = snapshots.dataset_snapshot_id) = 6
        ORDER BY dataset_snapshot_id DESC
        """
    )
    snapshot = cursor.fetchone()
    if snapshot is None:
        raise RuntimeError("no successful complete dataset snapshot is available for export")

    cursor.execute(
        """
        SELECT TOP (1) validation_run_id, status, completed_at_utc
        FROM audit.validation_runs
        WHERE dataset_snapshot_id = ? AND completed_at_utc IS NOT NULL
        ORDER BY validation_run_id DESC
        """,
        (int(snapshot[0]),),
    )
    validation = cursor.fetchone()
    if validation is None:
        raise RuntimeError("the current dataset snapshot has no completed SQL validation run")
    validation_status = str(validation[1])
    if validation_status not in {"Passed", "Warning"}:
        raise RuntimeError(
            f"the current dataset snapshot is not exportable; validation status={validation_status}"
        )
    return {
        "dataset_snapshot_id": int(snapshot[0]),
        "source_manifest_sha256": str(snapshot[1]),
        "validation_run_id": int(validation[0]),
        "validation_status": validation_status,
        "validation_completed_at_utc": str(validation[2]),
    }


def export_reporting_views(connection: Any, output_directory: Path) -> Path:
    """Export all configured views and provenance without overwriting a run."""

    if output_directory.exists():
        raise FileExistsError(f"export directory already exists: {output_directory}")
    try:
        context = _validated_export_context(connection)
        output_directory.mkdir(parents=True)
        manifest: dict[str, Any] = {
            "exported_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "provenance": context,
            "files": [],
        }
        for spec in EXPORT_SPECS:
            columns = ", ".join(spec.columns)
            ordering = ", ".join(spec.order_by)
            cursor = connection.cursor()
            cursor.execute(f"SELECT {columns} FROM {spec.view} ORDER BY {ordering}")
            destination = output_directory / spec.filename
            with destination.open("w", encoding="utf-8", newline="") as target:
                writer = csv.writer(target)
                writer.writerow(spec.columns)
                row_count = 0
                for row in cursor:
                    writer.writerow(tuple(row))
                    row_count += 1
            manifest["files"].append(
                {
                    "filename": spec.filename,
                    "source_view": spec.view,
                    "row_count": row_count,
                    "sha256": _file_sha256(destination),
                    "grain_warning": (
                        "seller/category totals are attributed bridge counts and are not additive "
                        "to the global order total"
                        if "seller" in spec.filename or "category" in spec.filename
                        else None
                    ),
                }
            )
        connection.rollback()
        manifest_path = output_directory / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest_path
    except Exception:
        # Preserve partial files for diagnosis; never mislabel the directory as complete.
        connection.rollback()
        raise
