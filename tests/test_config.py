from __future__ import annotations

from pathlib import Path

import pytest

from olist_delivery.config import (
    ConfigurationError,
    build_odbc_connection_string,
    load_settings,
    safe_database_error,
)


def _environment() -> dict[str, str]:
    return {
        "SQL_SERVER_HOST": "sql.example.test",
        "SQL_SERVER_PORT": "1433",
        "SQL_SERVER_DATABASE": "OlistDeliveryAnalytics",
        "SQL_SERVER_USER": "olist_loader",
        "SQL_SERVER_PASSWORD": "not-a-real-password",
        "SQL_SERVER_DRIVER": "ODBC Driver 18 for SQL Server",
        "SQL_SERVER_ENCRYPT": "yes",
        "SQL_SERVER_TRUST_CERTIFICATE": "yes",
        "SQL_SERVER_TIMEOUT_SECONDS": "15",
        "RAW_DATA_DIRECTORY": "data/raw",
        "PROCESSED_DATA_DIRECTORY": "data/processed",
        "REPORTS_DIRECTORY": "reports",
    }


def test_load_settings_resolves_project_paths(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path, environ=_environment())

    assert settings.raw_data_directory == (tmp_path / "data/raw").resolve()
    assert settings.processed_data_directory == (tmp_path / "data/processed").resolve()
    assert settings.database.port == 1433
    assert settings.database.timeout_seconds == 15


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SQL_SERVER_HOST", ""),
        ("SQL_SERVER_DATABASE", "  "),
        ("SQL_SERVER_USER", ""),
        ("SQL_SERVER_PASSWORD", ""),
        ("SQL_SERVER_PORT", "not-an-integer"),
        ("SQL_SERVER_TIMEOUT_SECONDS", "0"),
    ],
)
def test_load_settings_rejects_missing_or_invalid_database_values(
    tmp_path: Path,
    name: str,
    value: str,
) -> None:
    environment = _environment()
    environment[name] = value

    with pytest.raises(ConfigurationError):
        load_settings(project_root=tmp_path, environ=environment)


def test_connection_string_escapes_values_and_keeps_password_out_of_repr(
    tmp_path: Path,
) -> None:
    environment = _environment()
    environment["SQL_SERVER_PASSWORD"] = "semi;brace}secret"
    settings = load_settings(project_root=tmp_path, environ=environment)

    connection_string = build_odbc_connection_string(settings.database)

    assert "PWD={semi;brace}}secret}" in connection_string
    assert "semi;brace}secret" not in repr(settings.database)
    assert "Encrypt={yes}" in connection_string


def test_database_error_redaction_removes_password_fragments() -> None:
    error = RuntimeError("Login failed; PWD={not-a-real-password}; state=28000")

    safe_message = safe_database_error(error)

    assert "not-a-real-password" not in safe_message
    assert "<redacted>" in safe_message
