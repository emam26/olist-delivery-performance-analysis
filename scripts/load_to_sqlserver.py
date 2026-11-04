"""Load inventoried Olist CSV files into SQL Server staging tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from olist_delivery.config import load_project_settings
from olist_delivery.database import database_connection, safe_database_error
from olist_delivery.load_data import DatasetLoadError, load_required_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory-report",
        type=Path,
        default=Path("reports/inventory/inventory.json"),
    )
    parser.add_argument("--data-directory", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = load_project_settings()
    data_directory = args.data_directory or settings.data_directory
    try:
        inventory = json.loads(args.inventory_report.read_text(encoding="utf-8"))
        if inventory.get("status") == "failed":
            raise DatasetLoadError("inventory status is failed; resolve source issues first")
        with database_connection() as connection:
            outcomes = load_required_files(
                connection,
                data_directory,
                inventory,
                batch_size=settings.load_batch_size,
            )
    except (OSError, json.JSONDecodeError, DatasetLoadError) as exc:
        print(f"Load blocked or failed: {exc}")
        return 1
    except Exception as exc:
        print(f"Load failed: {safe_database_error(exc)}")
        return 1
    for outcome in outcomes:
        print(
            f"{outcome.dataset}: {outcome.status}; rows={outcome.inserted_row_count}; "
            f"sha256={outcome.source_sha256}"
        )
    print("Staging load completed. Run SQL validation before analysis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
