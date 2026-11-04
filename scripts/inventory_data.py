"""Inventory the required Olist CSV files without modifying them."""

from __future__ import annotations

import argparse
from pathlib import Path

from olist_delivery.config import load_project_settings
from olist_delivery.inventory import (
    InventoryError,
    inventory_dataset,
    inventory_summary,
    write_inventory_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-directory", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/inventory/inventory.json"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = load_project_settings()
    data_directory = args.data_directory or settings.data_directory
    try:
        report = inventory_dataset(data_directory)
        write_inventory_report(report, args.output, overwrite=args.overwrite)
    except (InventoryError, OSError) as exc:
        print(f"Inventory failed: {exc}")
        return 1
    print(inventory_summary(report))
    print(f"Inventory report: {args.output}")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
