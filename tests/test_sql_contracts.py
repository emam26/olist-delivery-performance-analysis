from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_DIRECTORY = PROJECT_ROOT / "sql"


@pytest.mark.parametrize(
    "filename",
    [
        "000_create_database.sql",
        "001_create_schemas.sql",
        "002_create_staging_tables.sql",
        "003_create_analytical_views.sql",
        "004_create_reporting_views.sql",
        "005_data_quality_checks.sql",
        "006_analysis_queries.sql",
        "007_create_database_roles.sql",
    ],
)
def test_numbered_sql_script_exists(filename: str) -> None:
    assert (SQL_DIRECTORY / filename).is_file()


def test_analytical_sql_uses_calendar_date_delivery_classification() -> None:
    sql = (SQL_DIRECTORY / "003_create_analytical_views.sql").read_text(encoding="utf-8")
    normalized = " ".join(sql.upper().split())

    assert "ORDER_DELIVERED_CUSTOMER" in normalized
    assert "ORDER_ESTIMATED_DELIVERY" in normalized
    assert "AS IS_LATE" in normalized
    assert "LOWER(LTRIM(RTRIM(O.ORDER_STATUS))) = N'DELIVERED'" in normalized
    assert "COALESCE(LOWER(LTRIM(RTRIM(O.ORDER_STATUS))), N'') <> N'DELIVERED'" in normalized
    assert (
        "CAST(O.ORDER_DELIVERED_CUSTOMER_TIMESTAMP AS DATE) > "
        "CAST(O.ORDER_ESTIMATED_DELIVERY_TIMESTAMP AS DATE)"
    ) in normalized


def test_analytical_sql_preserves_seconds_in_delivery_duration() -> None:
    sql = (SQL_DIRECTORY / "003_create_analytical_views.sql").read_text(encoding="utf-8")
    normalized = " ".join(sql.upper().split())

    assert "DATEDIFF_BIG(SECOND, O.ORDER_PURCHASE_TIMESTAMP" in normalized
    assert "O.ORDER_DELIVERED_CUSTOMER_TIMESTAMP) / 3600.0" in normalized
    assert "DATEDIFF_BIG(MINUTE" not in normalized


def test_reporting_sql_uses_continuous_percentiles() -> None:
    sql = (SQL_DIRECTORY / "004_create_reporting_views.sql").read_text(encoding="utf-8")
    normalized = sql.upper()

    percentiles = set(
        re.findall(
            r"PERCENTILE_CONT\(\s*(0\.\d+)\s*\)\s+WITHIN GROUP\s*"
            r"\(\s*ORDER BY\s+DELIVERY_DURATION_HOURS\s*\)",
            normalized,
        )
    )
    assert {"0.50", "0.90", "0.95"} <= percentiles
    assert normalized.count("WHERE IS_DURATION_ELIGIBLE = 1") >= 5


def test_transactional_sql_scripts_enable_transaction_abort() -> None:
    for filename in (
        "001_create_schemas.sql",
        "002_create_staging_tables.sql",
        "005_data_quality_checks.sql",
        "007_create_database_roles.sql",
    ):
        sql = (SQL_DIRECTORY / filename).read_text(encoding="utf-8").upper()
        assert "SET XACT_ABORT ON" in sql, filename


def test_analytical_views_activate_one_complete_dataset_snapshot() -> None:
    schema_sql = (SQL_DIRECTORY / "001_create_schemas.sql").read_text(encoding="utf-8").upper()
    view_sql = (SQL_DIRECTORY / "003_create_analytical_views.sql").read_text(encoding="utf-8")
    normalized = " ".join(view_sql.upper().split())

    assert "AUDIT.DATASET_SNAPSHOTS" in schema_sql
    assert "AUDIT.DATASET_SNAPSHOT_BATCHES" in schema_sql
    assert "ANALYTICS.VW_CURRENT_SNAPSHOT_BATCHES" in normalized
    assert "MAX(LOAD_BATCH_ID)" not in normalized
    for dataset in ("orders", "order_items", "customers", "sellers", "products", "reviews"):
        assert f"WHERE DATASET_NAME = N'{dataset.upper()}'" in normalized


def test_grouped_duration_statistics_keep_independent_eligibility_cohort() -> None:
    sql = (SQL_DIRECTORY / "004_create_reporting_views.sql").read_text(encoding="utf-8")
    normalized = " ".join(sql.upper().split())

    for view_name in ("VW_STATE_DELIVERY", "VW_SELLER_DELIVERY", "VW_CATEGORY_DELIVERY"):
        section = normalized.split(f"CREATE OR ALTER VIEW REPORTING.{view_name}", maxsplit=1)[1]
        section = section.split(" GO ", maxsplit=1)[0]
        assert "WHERE IS_DURATION_ELIGIBLE = 1" in section
        assert "WHERE D.IS_DELIVERY_ELIGIBLE = 1" not in section
