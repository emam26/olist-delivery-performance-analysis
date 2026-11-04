from __future__ import annotations

import os

import pytest

from olist_delivery.config import load_settings
from olist_delivery.database import database_connection

pytestmark = [
    pytest.mark.sqlserver,
    pytest.mark.skipif(
        os.getenv("RUN_SQLSERVER_TESTS") != "1",
        reason="Set RUN_SQLSERVER_TESTS=1 for the dedicated SQL Server test database.",
    ),
]


def test_required_database_objects_are_deployed() -> None:
    settings = load_settings()

    with database_connection(settings.database) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                SUM(CASE WHEN schemas.[name] = N'stg' AND objects.[type] = 'U'
                    THEN 1 ELSE 0 END) AS staging_tables,
                SUM(CASE WHEN schemas.[name] = N'analytics' AND objects.[type] = 'V'
                    THEN 1 ELSE 0 END) AS analytical_views,
                SUM(CASE WHEN schemas.[name] = N'reporting' AND objects.[type] = 'V'
                    THEN 1 ELSE 0 END) AS reporting_views,
                SUM(CASE WHEN schemas.[name] = N'audit' AND objects.[type] = 'P'
                    THEN 1 ELSE 0 END) AS audit_procedures
            FROM sys.objects AS objects
            JOIN sys.schemas AS schemas
                ON schemas.[schema_id] = objects.[schema_id]
            WHERE schemas.[name] IN (N'audit', N'stg', N'analytics', N'reporting');
            """
        )
        row = cursor.fetchone()

    assert row is not None
    assert row.staging_tables == 6
    assert row.analytical_views >= 1
    assert row.reporting_views >= 1
    assert row.audit_procedures >= 1
