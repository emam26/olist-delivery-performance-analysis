"""Validated project configuration with password-safe SQL Server handling."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

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


def _path_setting(
    values: Mapping[str, str],
    name: str,
    default: str,
    project_root: Path,
    *aliases: str,
) -> Path:
    raw = values.get(name)
    if raw is None:
        raw = next((values.get(alias) for alias in aliases if values.get(alias)), default)
    path = Path(raw)
    return (path if path.is_absolute() else project_root / path).resolve()


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
    timeout_seconds: int = 30


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved project paths, operational limits, and database settings."""

    project_root: Path
    raw_data_directory: Path
    processed_data_directory: Path
    reports_directory: Path
    database: DatabaseSettings
    load_batch_size: int = 1000
    minimum_group_size: int = 30

    @property
    def data_directory(self) -> Path:
        """Compatibility name for the raw source directory."""

        return self.raw_data_directory

    @property
    def report_directory(self) -> Path:
        """Compatibility name for the reports directory."""

        return self.reports_directory


@dataclass(frozen=True, slots=True)
class ProjectSettings:
    """Legacy split view retained for callers that do not need credentials."""

    data_directory: Path
    report_directory: Path
    export_directory: Path
    load_batch_size: int
    minimum_group_size: int


def load_settings(
    project_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    load_dotenv_file: bool = True,
) -> Settings:
    """Resolve project paths and database settings without opening a connection."""

    if load_dotenv_file and environ is None:
        load_dotenv()
    source = os.environ if environ is None else environ
    root = Path.cwd().resolve() if project_root is None else Path(project_root).resolve()

    database = DatabaseSettings(
        driver=_required(source, "SQL_SERVER_DRIVER"),
        host=_required(source, "SQL_SERVER_HOST"),
        port=_positive_int(source, "SQL_SERVER_PORT", 1433),
        database=_required(source, "SQL_SERVER_DATABASE"),
        user=_required(source, "SQL_SERVER_USER"),
        password=_required(source, "SQL_SERVER_PASSWORD"),
        encrypt=_yes_no(source, "SQL_SERVER_ENCRYPT", "yes"),
        trust_certificate=_yes_no(source, "SQL_SERVER_TRUST_CERTIFICATE", "no"),
        timeout_seconds=_positive_int(source, "SQL_SERVER_TIMEOUT_SECONDS", 30),
    )
    return Settings(
        project_root=root,
        raw_data_directory=_path_setting(
            source,
            "RAW_DATA_DIRECTORY",
            "data/raw",
            root,
            "OLIST_DATA_DIRECTORY",
        ),
        processed_data_directory=_path_setting(
            source,
            "PROCESSED_DATA_DIRECTORY",
            "data/processed",
            root,
        ),
        reports_directory=_path_setting(
            source,
            "REPORTS_DIRECTORY",
            "reports",
            root,
            "OLIST_REPORT_DIRECTORY",
        ),
        database=database,
        load_batch_size=_positive_int(source, "OLIST_LOAD_BATCH_SIZE", 1000),
        minimum_group_size=_positive_int(source, "OLIST_MIN_GROUP_SIZE", 30),
    )


def load_project_settings(
    values: Mapping[str, str] | None = None,
    *,
    load_dotenv_file: bool = True,
) -> ProjectSettings:
    """Load non-secret project settings for compatibility with older scripts."""

    if load_dotenv_file and values is None:
        load_dotenv()
    source = os.environ if values is None else values
    root = Path.cwd().resolve()
    return ProjectSettings(
        data_directory=_path_setting(
            source,
            "RAW_DATA_DIRECTORY",
            "data/raw",
            root,
            "OLIST_DATA_DIRECTORY",
        ),
        report_directory=_path_setting(
            source,
            "REPORTS_DIRECTORY",
            "reports",
            root,
            "OLIST_REPORT_DIRECTORY",
        ),
        export_directory=_path_setting(
            source,
            "OLIST_EXPORT_DIRECTORY",
            "reports/exports",
            root,
        ),
        load_batch_size=_positive_int(source, "OLIST_LOAD_BATCH_SIZE", 1000),
        minimum_group_size=_positive_int(source, "OLIST_MIN_GROUP_SIZE", 30),
    )


def load_database_settings(
    values: Mapping[str, str] | None = None,
    *,
    load_dotenv_file: bool = True,
) -> DatabaseSettings:
    """Load database credentials without opening a connection."""

    return load_settings(
        environ=values,
        load_dotenv_file=load_dotenv_file,
    ).database


def escape_odbc_value(value: str) -> str:
    """Brace and escape an ODBC value so delimiters cannot alter its meaning."""

    return "{" + value.replace("}", "}}") + "}"


def build_odbc_connection_string(settings: DatabaseSettings) -> str:
    """Build an ODBC SQL-authentication string without logging it."""

    server = f"{settings.host},{settings.port}"
    parts = {
        "DRIVER": settings.driver,
        "SERVER": server,
        "DATABASE": settings.database,
        "UID": settings.user,
        "PWD": settings.password,
        "Encrypt": settings.encrypt,
        "TrustServerCertificate": settings.trust_certificate,
        "Connection Timeout": str(settings.timeout_seconds),
    }
    return ";".join(f"{key}={escape_odbc_value(value)}" for key, value in parts.items()) + ";"


def build_connection_string(settings: DatabaseSettings) -> str:
    """Compatibility entry point for the original database module API."""

    return build_odbc_connection_string(settings)


def safe_database_error(error: BaseException) -> str:
    """Redact common password forms from a database exception."""

    message = re.sub(
        r"(?i)((?:pwd|password)\s*=\s*)(\{(?:[^}]|}})*\}|[^;\s]+)",
        r"\1<redacted>",
        str(error),
    )
    return f"{error.__class__.__name__}: {message}"[:4000]
