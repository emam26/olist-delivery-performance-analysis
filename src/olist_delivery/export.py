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
            "is_delivery_eligible",
            "is_late",
            "is_duration_eligible",
            "delivery_duration_hours",
            "days_late",
            "selected_review_score",
            "exclusion_reason",
        ),
        ("order_id",),
    ),
    ExportSpec(
        "monthly_delivery.csv",
        "reporting.vw_monthly_delivery",
        (
            "purchase_month",
            "eligible_order_count",
            "on_time_order_count",
            "late_order_count",
            "on_time_delivery_rate",
            "late_delivery_rate",
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
            "eligible_order_count",
            "late_order_count",
            "late_delivery_rate",
            "average_delivery_hours",
            "median_delivery_hours",
        ),
        ("customer_state",),
    ),
    ExportSpec(
        "seller_delivery.csv",
        "reporting.vw_seller_delivery",
        (
            "seller_id",
            "seller_state",
            "eligible_order_count",
            "late_order_count",
            "late_delivery_rate",
            "average_delivery_hours",
            "median_delivery_hours",
        ),
        ("seller_id",),
    ),
    ExportSpec(
        "category_delivery.csv",
        "reporting.vw_category_delivery",
        (
            "product_category_name",
            "eligible_order_count",
            "late_order_count",
            "late_delivery_rate",
            "average_delivery_hours",
            "median_delivery_hours",
        ),
        ("product_category_name",),
    ),
    ExportSpec(
        "review_delivery.csv",
        "reporting.vw_review_delivery_distribution",
        ("delivery_class", "review_score", "review_count", "orders_without_usable_review"),
        ("delivery_class", "review_score"),
    ),
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def export_reporting_views(connection: Any, output_directory: Path) -> Path:
    """Export all configured views and provenance without overwriting a run."""

    if output_directory.exists():
        raise FileExistsError(f"export directory already exists: {output_directory}")
    output_directory.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "exported_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "files": [],
    }
    try:
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
        manifest_path = output_directory / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest_path
    except Exception:
        # Preserve partial files for diagnosis; never mislabel the directory as complete.
        raise
