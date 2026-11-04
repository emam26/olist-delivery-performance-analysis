"""Read-only, deterministic inventory of the six required Olist CSV files."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .datasets import DATASET_SPECS, DATASETS_BY_NAME, DatasetSpec


class InventoryError(RuntimeError):
    """Raised when inventory cannot safely inspect or write its report."""


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without loading it fully into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_timestamp(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _column_values(path: Path, column: str) -> Iterable[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        if column not in (reader.fieldnames or ()):
            return
        for row in reader:
            value = (row.get(column) or "").strip()
            if value:
                yield value


def _orphan_count(path: Path, column: str, parent_ids: set[str]) -> int:
    return sum(1 for value in _column_values(path, column) if value not in parent_ids)


def _item_attribution_counts(
    items_path: Path,
    products_path: Path,
) -> tuple[int, int, set[str]]:
    product_categories: dict[str, str] = {}
    with products_path.open("r", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source, strict=True):
            product_id = (row.get("product_id") or "").strip()
            if product_id:
                product_categories[product_id] = (
                    row.get("product_category_name") or ""
                ).strip() or "(Missing category)"

    sellers_by_order: dict[str, set[str]] = {}
    categories_by_order: dict[str, set[str]] = {}
    item_order_ids: set[str] = set()
    with items_path.open("r", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source, strict=True):
            order_id = (row.get("order_id") or "").strip()
            if not order_id:
                continue
            item_order_ids.add(order_id)
            seller_id = (row.get("seller_id") or "").strip()
            if seller_id:
                sellers_by_order.setdefault(order_id, set()).add(seller_id)
            product_id = (row.get("product_id") or "").strip()
            if product_id:
                category = product_categories.get(product_id, "(Missing category)")
                categories_by_order.setdefault(order_id, set()).add(category)

    multi_seller = sum(len(values) > 1 for values in sellers_by_order.values())
    multi_category = sum(len(values) > 1 for values in categories_by_order.values())
    return multi_seller, multi_category, item_order_ids


def spec_for_dataset(name: str) -> DatasetSpec:
    """Return one known dataset contract with an actionable error."""

    try:
        return DATASETS_BY_NAME[name]
    except KeyError as exc:
        choices = ", ".join(sorted(DATASETS_BY_NAME))
        raise InventoryError(f"unknown dataset {name!r}; expected one of: {choices}") from exc


@dataclass(frozen=True, slots=True)
class InventoryReport:
    """Deterministic inventory evidence for the required source files."""

    status: str
    files: tuple[dict[str, Any], ...]
    relationships: tuple[dict[str, Any], ...]
    report_version: int = 2

    @property
    def dataset_count(self) -> int:
        return len(self.files)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible evidence without exposing source rows."""

        return {
            "report_version": self.report_version,
            "status": self.status,
            "dataset_count": self.dataset_count,
            "files": [dict(item) for item in self.files],
            "relationships": [dict(item) for item in self.relationships],
        }


def _canonical_file_result(path: Path, spec: DatasetSpec) -> dict[str, Any]:
    required_headers = list(spec.columns)
    base: dict[str, Any] = {
        "dataset": spec.name,
        "filename": spec.filename,
        "status": "failed",
        "loadable": False,
        "exists": path.is_file(),
        "byte_count": 0,
        "sha256": "",
        "headers": [],
        "required_headers": required_headers,
        "missing_headers": required_headers,
        "unexpected_headers": [],
        "row_count": 0,
        "missing_values": dict.fromkeys(spec.columns, 0),
        "blank_identifier_count": 0,
        "blank_identifier_counts": dict.fromkeys(spec.required_identifiers, 0),
        "duplicate_natural_key_count": 0,
        "duplicate_natural_key_examples": [],
        "malformed_record_count": 0,
        "malformed_record_examples": [],
        "invalid_timestamp_count": 0,
        "negative_delivery_interval_count": 0,
        "errors": [],
    }
    if not path.is_file():
        base["errors"] = ["required source file is missing"]
        return base

    base["byte_count"] = path.stat().st_size
    base["sha256"] = sha256_file(path)
    seen_keys: set[tuple[str, ...]] = set()
    timestamp_errors = 0
    errors: list[str] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            headers = tuple(reader.fieldnames or ())
            base["headers"] = list(headers)
            missing_headers = sorted(set(spec.columns) - set(headers))
            unexpected_headers = sorted(set(headers) - set(spec.columns))
            base["missing_headers"] = missing_headers
            base["unexpected_headers"] = unexpected_headers
            if missing_headers:
                errors.append("missing required headers: " + ", ".join(missing_headers))
            if unexpected_headers:
                errors.append("unexpected headers: " + ", ".join(unexpected_headers))
            if not missing_headers and not unexpected_headers and headers != spec.columns:
                errors.append("CSV headers are in the wrong order")

            for row_number, row in enumerate(reader, start=2):
                base["row_count"] += 1
                values = [row.get(column) for column in spec.columns]
                malformed = None in row or any(value is None for value in values)
                if malformed:
                    base["malformed_record_count"] += 1
                    if len(base["malformed_record_examples"]) < 10:
                        base["malformed_record_examples"].append(row_number)

                for column, value in zip(spec.columns, values, strict=True):
                    if value is None or not value.strip():
                        base["missing_values"][column] += 1

                for column in spec.required_identifiers:
                    value = row.get(column)
                    if value is None or not value.strip():
                        base["blank_identifier_count"] += 1
                        base["blank_identifier_counts"][column] += 1

                key = tuple((row.get(column) or "").strip() for column in spec.natural_key)
                if malformed:
                    continue
                if key in seen_keys:
                    base["duplicate_natural_key_count"] += 1
                    if len(base["duplicate_natural_key_examples"]) < 10:
                        base["duplicate_natural_key_examples"].append(
                            dict(zip(spec.natural_key, key, strict=True))
                        )
                else:
                    seen_keys.add(key)

                parsed: dict[str, datetime | None] = {}
                for column in spec.timestamp_columns:
                    raw = row.get(column) or ""
                    timestamp = _parse_timestamp(raw)
                    parsed[column] = timestamp
                    if raw.strip() and timestamp is None:
                        timestamp_errors += 1

                if spec.name == "orders":
                    purchase = parsed.get("order_purchase_timestamp")
                    delivered = parsed.get("order_delivered_customer_date")
                    if purchase is not None and delivered is not None and delivered < purchase:
                        base["negative_delivery_interval_count"] += 1
    except (OSError, UnicodeError, csv.Error) as exc:
        errors.append(f"CSV parsing failed near source line {base['row_count'] + 2}: {exc}")
        base["malformed_record_count"] += 1

    base["invalid_timestamp_count"] = timestamp_errors
    if base["malformed_record_count"]:
        errors.append(f"{base['malformed_record_count']} malformed record(s) require inspection")
    if base["duplicate_natural_key_count"]:
        errors.append(
            f"{base['duplicate_natural_key_count']} duplicate row(s) at declared grain "
            f"{spec.natural_key}"
        )
    if base["row_count"] == 0:
        errors.append("source file contains no data records")
    if base["blank_identifier_count"]:
        errors.append(f"{base['blank_identifier_count']} blank required identifier value(s)")
    if timestamp_errors:
        errors.append(f"{timestamp_errors} non-empty timestamp(s) could not be parsed")
    if base["negative_delivery_interval_count"]:
        errors.append(f"{base['negative_delivery_interval_count']} negative delivery interval(s)")
    base["errors"] = errors
    base["loadable"] = not (
        base["missing_headers"]
        or base["unexpected_headers"]
        or base["headers"] != base["required_headers"]
        or base["malformed_record_count"]
        or base["row_count"] == 0
    )
    base["status"] = "failed" if errors or base["missing_headers"] else "passed"
    return base


def _canonical_relationships(data_directory: Path) -> tuple[dict[str, Any], ...]:
    paths = {spec.name: data_directory / spec.filename for spec in DATASET_SPECS}
    if not all(path.is_file() for path in paths.values()):
        return (
            {
                "check_id": "source_relationships",
                "status": "not_evaluated",
                "observed_count": None,
                "message": "all six required files are needed for relationship checks",
            },
        )

    try:
        parent_ids = {
            "orders": set(_column_values(paths["orders"], "order_id")),
            "customers": set(_column_values(paths["customers"], "customer_id")),
            "sellers": set(_column_values(paths["sellers"], "seller_id")),
            "products": set(_column_values(paths["products"], "product_id")),
        }
        checks = (
            ("orders_customer_orphans", "orders", "customer_id", "customers", "failed"),
            ("order_items_order_orphans", "order_items", "order_id", "orders", "failed"),
            ("order_items_seller_orphans", "order_items", "seller_id", "sellers", "warning"),
            (
                "order_items_product_orphans",
                "order_items",
                "product_id",
                "products",
                "warning",
            ),
            ("reviews_order_orphans", "reviews", "order_id", "orders", "warning"),
        )
        results: list[dict[str, Any]] = []
        for check_id, child, column, parent, failure_status in checks:
            observed = _orphan_count(paths[child], column, parent_ids[parent])
            results.append(
                {
                    "check_id": check_id,
                    "status": "passed" if observed == 0 else failure_status,
                    "observed_count": observed,
                    "message": "foreign-key reference check",
                }
            )
        review_counts = Counter(_column_values(paths["reviews"], "order_id"))
        multiple = sum(count > 1 for count in review_counts.values())
        results.append(
            {
                "check_id": "orders_with_multiple_reviews",
                "status": "passed" if multiple == 0 else "warning",
                "observed_count": multiple,
                "message": "multiple reviews are preserved and selected deterministically later",
            }
        )
        multi_seller, multi_category, item_order_ids = _item_attribution_counts(
            paths["order_items"],
            paths["products"],
        )
        orders_without_items = len(parent_ids["orders"] - item_order_ids)
        results.extend(
            (
                {
                    "check_id": "orders_without_items",
                    "status": "passed" if orders_without_items == 0 else "warning",
                    "observed_count": orders_without_items,
                    "message": "orders remain in global KPIs but can lack attribution",
                },
                {
                    "check_id": "multi_seller_orders",
                    "status": "passed",
                    "observed_count": multi_seller,
                    "message": "profiled non-additive order-seller attribution",
                },
                {
                    "check_id": "multi_category_orders",
                    "status": "passed",
                    "observed_count": multi_category,
                    "message": "profiled non-additive order-category attribution",
                },
            )
        )
        return tuple(results)
    except (OSError, UnicodeError, csv.Error) as exc:
        return (
            {
                "check_id": "source_relationships",
                "status": "failed",
                "observed_count": None,
                "message": f"relationship inspection failed: {exc}",
            },
        )


def build_inventory(data_directory: Path) -> InventoryReport:
    """Build deterministic evidence for all required CSV files."""

    files = tuple(
        _canonical_file_result(data_directory / spec.filename, spec) for spec in DATASET_SPECS
    )
    relationships = _canonical_relationships(data_directory)
    if any(item["status"] == "failed" for item in files + relationships):
        status = "failed"
    elif any(item["status"] == "warning" for item in relationships):
        status = "warning"
    else:
        status = "passed"
    return InventoryReport(status, files, relationships)


def inspect_csv_file(path: Path, spec: DatasetSpec) -> dict[str, Any]:
    """Inspect one file using the canonical inventory result schema."""

    return _canonical_file_result(path, spec)


def inventory_dataset(data_directory: Path) -> dict[str, Any]:
    """Compatibility wrapper returning the canonical report as a mapping."""

    return build_inventory(data_directory).to_dict()


def write_inventory_report(
    report: InventoryReport | dict[str, Any],
    destination: Path,
    *,
    overwrite: bool = False,
) -> None:
    """Write deterministic inventory evidence without silent replacement."""

    payload = report.to_dict() if isinstance(report, InventoryReport) else report
    content = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if destination.exists() and not overwrite:
        raise FileExistsError(f"inventory report already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def inventory_summary(report: InventoryReport | dict[str, Any]) -> str:
    """Render a concise human-readable inventory summary."""

    payload = report.to_dict() if isinstance(report, InventoryReport) else report
    lines = [f"Inventory status: {payload['status']}"]
    for item in payload["files"]:
        if not item["exists"]:
            lines.append(f"- {item['filename']}: MISSING")
            continue
        lines.append(
            f"- {item['filename']}: {item['status']}; "
            f"loadable={item.get('loadable', False)}; "
            f"rows={item['row_count']}; bytes={item['byte_count']}"
        )
    for check in payload["relationships"]:
        lines.append(
            f"- {check['check_id']}: {check['status']}; "
            f"count={check.get('observed_count', 'not evaluated')}"
        )
    return "\n".join(lines)
