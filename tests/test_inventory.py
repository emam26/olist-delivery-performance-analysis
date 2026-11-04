from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from olist_delivery.datasets import DATASET_SPECS
from olist_delivery.inventory import build_inventory, write_inventory_report


def _spec(name: str):
    return next(spec for spec in DATASET_SPECS if spec.name == name)


def _base_rows() -> dict[str, list[dict[str, str]]]:
    return {
        "orders": [
            {
                "order_id": "order-1",
                "customer_id": "customer-1",
                "order_status": "delivered",
                "order_purchase_timestamp": "2018-01-01 09:00:00",
                "order_approved_at": "2018-01-01 10:00:00",
                "order_delivered_carrier_date": "2018-01-02 10:00:00",
                "order_delivered_customer_date": "2018-01-10 17:00:00",
                "order_estimated_delivery_date": "2018-01-11 00:00:00",
            }
        ],
        "order_items": [
            {
                "order_id": "order-1",
                "order_item_id": "1",
                "product_id": "product-1",
                "seller_id": "seller-1",
                "shipping_limit_date": "2018-01-03 00:00:00",
                "price": "10.00",
                "freight_value": "2.00",
            }
        ],
        "customers": [
            {
                "customer_id": "customer-1",
                "customer_unique_id": "unique-1",
                "customer_zip_code_prefix": "01000",
                "customer_city": "sao paulo",
                "customer_state": "SP",
            }
        ],
        "sellers": [
            {
                "seller_id": "seller-1",
                "seller_zip_code_prefix": "02000",
                "seller_city": "sao paulo",
                "seller_state": "SP",
            }
        ],
        "products": [
            {
                "product_id": "product-1",
                "product_category_name": "books",
                "product_name_lenght": "10",
                "product_description_lenght": "20",
                "product_photos_qty": "1",
                "product_weight_g": "100",
                "product_length_cm": "10",
                "product_height_cm": "5",
                "product_width_cm": "5",
            }
        ],
        "reviews": [
            {
                "review_id": "review-1",
                "order_id": "order-1",
                "review_score": "5",
                "review_comment_title": "",
                "review_comment_message": "",
                "review_creation_date": "2018-01-11 00:00:00",
                "review_answer_timestamp": "2018-01-12 00:00:00",
            }
        ],
    }


def _write_sources(raw_directory: Path, rows: dict[str, list[dict[str, str]]]) -> None:
    raw_directory.mkdir(parents=True)
    for spec in DATASET_SPECS:
        source_path = raw_directory / spec.filename
        with source_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=spec.columns)
            writer.writeheader()
            writer.writerows(rows[spec.name])


def test_inventory_records_hashes_rows_and_headers(tmp_path: Path) -> None:
    raw_directory = tmp_path / "raw"
    _write_sources(raw_directory, _base_rows())

    report = build_inventory(raw_directory)
    payload = report.to_dict()

    assert payload["status"] == "passed"
    assert len(payload["files"]) == 6
    for file_result in payload["files"]:
        assert file_result["row_count"] == 1
        assert len(file_result["sha256"]) == 64
        assert file_result["missing_headers"] == []


def test_inventory_detects_duplicate_natural_key(tmp_path: Path) -> None:
    rows = _base_rows()
    rows["orders"].append(dict(rows["orders"][0]))
    raw_directory = tmp_path / "raw"
    _write_sources(raw_directory, rows)

    payload = build_inventory(raw_directory).to_dict()
    orders = next(
        item for item in payload["files"] if item["dataset"] == "orders"
    )

    assert orders["duplicate_natural_key_count"] == 1
    assert payload["status"] != "passed"


def test_inventory_detects_cross_file_orphan(tmp_path: Path) -> None:
    rows = _base_rows()
    rows["order_items"][0]["product_id"] = "missing-product"
    raw_directory = tmp_path / "raw"
    _write_sources(raw_directory, rows)

    payload = build_inventory(raw_directory).to_dict()

    assert payload["status"] != "passed"
    assert any(
        check["check_id"] == "order_items_product_orphans"
        and check["observed_count"] == 1
        for check in payload["relationships"]
    )


def test_inventory_detects_malformed_csv_record(tmp_path: Path) -> None:
    raw_directory = tmp_path / "raw"
    _write_sources(raw_directory, _base_rows())
    orders_path = raw_directory / _spec("orders").filename
    with orders_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write("too,few,columns\n")

    payload = build_inventory(raw_directory).to_dict()
    orders = next(
        item for item in payload["files"] if item["dataset"] == "orders"
    )

    assert orders["malformed_record_count"] == 1
    assert payload["status"] != "passed"


def test_inventory_detects_negative_delivery_interval(tmp_path: Path) -> None:
    rows = _base_rows()
    rows["orders"][0]["order_purchase_timestamp"] = "2018-01-12 09:00:00"
    raw_directory = tmp_path / "raw"
    _write_sources(raw_directory, rows)

    payload = build_inventory(raw_directory).to_dict()
    orders = next(
        item for item in payload["files"] if item["dataset"] == "orders"
    )

    assert orders["negative_delivery_interval_count"] == 1
    assert payload["status"] != "passed"


def test_inventory_reports_missing_required_file(tmp_path: Path) -> None:
    raw_directory = tmp_path / "raw"
    _write_sources(raw_directory, _base_rows())
    (raw_directory / _spec("reviews").filename).unlink()

    payload = build_inventory(raw_directory).to_dict()
    reviews = next(
        item for item in payload["files"] if item["dataset"] == "reviews"
    )

    assert payload["status"] == "failed"
    assert reviews["exists"] is False


def test_inventory_output_is_deterministic_and_not_overwritten(tmp_path: Path) -> None:
    raw_directory = tmp_path / "raw"
    _write_sources(raw_directory, _base_rows())
    report = build_inventory(raw_directory)
    output_path = tmp_path / "inventory.json"

    write_inventory_report(report, output_path)
    first_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert first_payload == report.to_dict()
    with pytest.raises(FileExistsError):
        write_inventory_report(report, output_path)
