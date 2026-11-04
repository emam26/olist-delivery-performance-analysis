"""Minimal managed pyodbc connections for explicit SQL Server operations."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pyodbc

from .config import DatabaseSettings, build_connection_string, load_database_settings


def safe_database_error(error: BaseException) -> str:
    """Redact common password forms from a database exception."""

    message = re.sub(
        r"(?i)(pwd|password)\s*=\s*(?:\{(?:[^}]|}})*}|[^;\s]+)",
        r"\1=<redacted>",
        str(error),
    )
    return f"{error.__class__.__name__}: {message}"[:4000]


def connect_database(settings: DatabaseSettings | None = None) -> Any:
    """Open an explicit non-autocommit SQL Server connection."""

    resolved = settings or load_database_settings()
    return pyodbc.connect(build_connection_string(resolved), autocommit=False)


@contextmanager
def database_connection(settings: DatabaseSettings | None = None) -> Iterator[Any]:
    """Close the connection without logging credentials or its connection string."""

    connection = connect_database(settings)
    try:
        yield connection
    finally:
        connection.close()
