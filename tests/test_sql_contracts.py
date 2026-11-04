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
    assert (
        "CAST(O.ORDER_DELIVERED_CUSTOMER_TIMESTAMP AS DATE) > "
        "CAST(O.ORDER_ESTIMATED_DELIVERY_TIMESTAMP AS DATE)"
    ) in normalized


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
