"""Export validated SQL reporting views to a new Power BI CSV directory."""

from __future__ import annotations

import argparse
from pathlib import Path

from olist_delivery.database import database_connection, safe_database_error
from olist_delivery.export import export_reporting_views


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory",
        type=Path,
        required=True,
        help="A new directory; existing directories are never overwritten.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        with database_connection() as connection:
            manifest = export_reporting_views(connection, args.output_directory)
    except Exception as exc:
        print(f"Dashboard export failed: {safe_database_error(exc)}")
        return 1
    print(f"Dashboard export succeeded. Manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
