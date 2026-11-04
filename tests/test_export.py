from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from olist_delivery.export import EXPORT_SPECS, export_reporting_views


class _Cursor:
    def __init__(self, validation_status: str) -> None:
        self.validation_status = validation_status
        self.statement = ""

    def execute(self, statement: str, parameters: tuple[Any, ...] = ()) -> _Cursor:
        del parameters
        self.statement = statement
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        if "audit.dataset_snapshots" in self.statement:
            return (12, "a" * 64)
        if "audit.validation_runs" in self.statement:
            return (34, self.validation_status, "2026-01-01 00:00:00")
        return None

    def __iter__(self):
        return iter(())


class _Connection:
    def __init__(self, validation_status: str = "Passed") -> None:
        self.validation_status = validation_status
        self.rollbacks = 0

    def cursor(self) -> _Cursor:
        return _Cursor(self.validation_status)

    def rollback(self) -> None:
        self.rollbacks += 1


def test_export_manifest_records_snapshot_validation_and_file_hashes(tmp_path: Path) -> None:
    output_directory = tmp_path / "export"

    manifest_path = export_reporting_views(_Connection(), output_directory)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["provenance"]["dataset_snapshot_id"] == 12
    assert manifest["provenance"]["validation_run_id"] == 34
    assert manifest["provenance"]["validation_status"] == "Passed"
    assert {item["filename"] for item in manifest["files"]} == {
        spec.filename for spec in EXPORT_SPECS
    }
    assert all(len(item["sha256"]) == 64 for item in manifest["files"])

    with pytest.raises(FileExistsError):
        export_reporting_views(_Connection(), output_directory)


def test_export_refuses_failed_validation_before_creating_directory(tmp_path: Path) -> None:
    output_directory = tmp_path / "export"

    with pytest.raises(RuntimeError, match="validation status=Failed"):
        export_reporting_views(_Connection("Failed"), output_directory)

    assert not output_directory.exists()
