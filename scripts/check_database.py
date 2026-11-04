"""Run a read-only SQL Server identity and version check."""

from __future__ import annotations

from olist_delivery.database import database_connection, safe_database_error


def main() -> int:
    try:
        with database_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)),
                       ORIGINAL_LOGIN(), DB_NAME(),
                       CAST(SERVERPROPERTY('Edition') AS nvarchar(256)),
                       CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128))
                """
            )
            row = cursor.fetchone()
    except Exception as exc:
        print(f"Database check failed: {safe_database_error(exc)}")
        return 1
    if row is None:
        print("Database check failed: SQL Server returned no identity row")
        return 1
    print(f"Server: {row[0]}")
    print(f"Login: {row[1]}")
    print(f"Database: {row[2]}")
    print(f"Edition: {row[3]}")
    print(f"Version: {row[4]}")
    print("SQL Server connection check succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
