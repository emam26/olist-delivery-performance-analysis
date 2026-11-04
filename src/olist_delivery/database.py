"""Minimal managed pyodbc connections for explicit SQL Server operations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pyodbc

from .config import (
    DatabaseSettings,
    build_odbc_connection_string,
    load_database_settings,
    safe_database_error,
)

__all__ = ["connect_database", "database_connection", "safe_database_error"]


def connect_database(settings: DatabaseSettings | None = None) -> Any:
    """Open an explicit non-autocommit SQL Server connection."""

    resolved = settings or load_database_settings()
    return pyodbc.connect(build_odbc_connection_string(resolved), autocommit=False)


@contextmanager
def database_connection(settings: DatabaseSettings | None = None) -> Iterator[Any]:
    """Close the connection without logging credentials or its connection string."""

    connection = connect_database(settings)
    try:
        yield connection
    finally:
        connection.close()
