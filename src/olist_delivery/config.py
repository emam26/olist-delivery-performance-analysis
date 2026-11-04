"""Validated local configuration with password-safe SQL Server handling."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when local configuration is missing or unsafe."""


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is required")
    return value


def _positive_int(values: Mapping[str, str], name: str, default: int) -> int:
    raw = values.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive")
    return value


def _yes_no(values: Mapping[str, str], name: str, default: str) -> str:
    value = values.get(name, default).strip().lower()
    if value not in {"yes", "no"}:
        raise ConfigurationError(f"{name} must be 'yes' or 'no'")
    return value


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """SQL Server settings loaded from environment variables."""

    driver: str
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    encrypt: str = "yes"
    trust_certificate: str = "no"


@dataclass(frozen=True, slots=True)
class ProjectSettings:
    """Filesystem and analytical settings independent of database credentials."""

    data_directory: Path
    report_directory: Path
    export_directory: Path
    load_batch_size: int
    minimum_group_size: int


def load_project_settings(
    values: Mapping[str, str] | None = None,
    *,
    load_dotenv_file: bool = True,
) -> ProjectSettings:
    """Load project paths and bounded positive numeric settings."""

    if load_dotenv_file:
        load_dotenv()
    source = os.environ if values is None else values
    return ProjectSettings(
        data_directory=Path(source.get("OLIST_DATA_DIRECTORY", "data/raw")),
        report_directory=Path(source.get("OLIST_REPORT_DIRECTORY", "reports")),
        export_directory=Path(source.get("OLIST_EXPORT_DIRECTORY", "reports/exports")),
        load_batch_size=_positive_int(source, "OLIST_LOAD_BATCH_SIZE", 1000),
        minimum_group_size=_positive_int(source, "OLIST_MIN_GROUP_SIZE", 30),
    )


def load_database_settings(
    values: Mapping[str, str] | None = None,
    *,
    load_dotenv_file: bool = True,
) -> DatabaseSettings:
    """Load SQL Server credentials only when a database operation is requested."""

    if load_dotenv_file:
        load_dotenv()
    source = os.environ if values is None else values
    return DatabaseSettings(
        driver=_required(source, "SQL_SERVER_DRIVER"),
        host=_required(source, "SQL_SERVER_HOST"),
        port=_positive_int(source, "SQL_SERVER_PORT", 1433),
        database=_required(source, "SQL_SERVER_DATABASE"),
        user=_required(source, "SQL_SERVER_USER"),
        password=_required(source, "SQL_SERVER_PASSWORD"),
        encrypt=_yes_no(source, "SQL_SERVER_ENCRYPT", "yes"),
        trust_certificate=_yes_no(source, "SQL_SERVER_TRUST_CERTIFICATE", "no"),
    )


def escape_odbc_value(value: str) -> str:
    """Brace and escape an ODBC value so delimiters cannot alter its meaning."""

    return "{" + value.replace("}", "}}") + "}"


def build_connection_string(settings: DatabaseSettings) -> str:
    """Build an ODBC Driver 18 SQL-authentication string without logging it."""

    server = f"{settings.host},{settings.port}"
    parts = {
        "DRIVER": settings.driver,
        "SERVER": server,
        "DATABASE": settings.database,
        "UID": settings.user,
        "PWD": settings.password,
        "Encrypt": settings.encrypt,
        "TrustServerCertificate": settings.trust_certificate,
    }
    return ";".join(f"{key}={escape_odbc_value(value)}" for key, value in parts.items()) + ";"
