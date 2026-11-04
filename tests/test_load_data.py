from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

import olist_delivery.load_data as load_data_module
from olist_delivery.datasets import DATASET_SPECS
from olist_delivery.inventory import build_inventory
from olist_delivery.load_data import (
    CsvValidationError,
    DatasetLoadError,
    LoadOutcome,
    SqlServerDatasetLoader,
    load_required_files,
)


def _spec(name: str):
    return next(spec for spec in DATASET_SPECS if spec.name == name)


class _Cursor:
    def __init__(self, *, fail_insert: bool = False) -> None:
        self.fail_insert = fail_insert
        self.fast_executemany = False
        self.inserted: list[tuple[Any, ...]] = []

    def execute(self, statement: str, parameters: tuple[Any, ...] = ()) -> _Cursor:
        del statement, parameters
        return self

    def executemany(self, statement: str, rows: list[tuple[Any, ...]]) -> _Cursor:
        del statement
        if self.fail_insert:
            raise RuntimeError("synthetic insert failure; PWD={secret}")
        self.inserted.extend(rows)
        return self

    def fetchone(self) -> tuple[int] | None:
        return None

    def nextset(self) -> bool:
        return False


class _Connection:
    def __init__(self, *, fail_insert: bool = False) -> None:
        self.cursor_instance = _Cursor(fail_insert=fail_insert)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> _Cursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _ControlledLoader(SqlServerDatasetLoader):
    def __init__(
        self,
        connection: _Connection,
        *,
        existing_batch: int | None = None,
    ) -> None:
        super().__init__(connection)
        self.existing_batch = existing_batch
        self.failed_messages: list[str] = []

    def _successful_batch(self, *args: object, **kwargs: object) -> int | None:
        del args, kwargs
        return self.existing_batch

    def _start_batch(self, *args: object, **kwargs: object) -> int:
        del args, kwargs
        return 101

    def _record_failed_batch(self, *args: object, **kwargs: object) -> None:
        message = kwargs.get("error_message")
        if message is None and args:
            message = args[-1]
        self.failed_messages.append(str(message or ""))


def _write_orders(path: Path, *, wrong_header: bool = False) -> None:
    spec = _spec("orders")
    columns = list(spec.columns)
    if wrong_header:
        columns[-1] = "unexpected_column"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        row = {column: f"value-{index}" for index, column in enumerate(columns)}
        writer.writerow(row)


def _write_all_sources(directory: Path) -> None:
    directory.mkdir()
    for spec in DATASET_SPECS:
        with (directory / spec.filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=spec.columns)
            writer.writeheader()
            writer.writerow({column: f"{spec.name}-{column}" for column in spec.columns})


def test_successful_source_hash_is_idempotently_skipped(tmp_path: Path) -> None:
    source_path = tmp_path / "orders.csv"
    _write_orders(source_path)
    connection = _Connection()
    loader = _ControlledLoader(connection, existing_batch=77)

    result = loader.load_dataset(_spec("orders"), source_path)

    assert result.status == "skipped"
    assert result.load_batch_id == 77
    assert connection.commits == 0
    assert connection.rollbacks == 0
    assert connection.cursor_instance.inserted == []


def test_successful_file_is_inserted_and_committed_once(tmp_path: Path) -> None:
    source_path = tmp_path / "orders.csv"
    _write_orders(source_path)
    connection = _Connection()
    loader = _ControlledLoader(connection)

    result = loader.load_dataset(_spec("orders"), source_path)

    assert result.status == "succeeded"
    assert result.load_batch_id == 101
    assert result.inserted_row_count == 1
    assert len(connection.cursor_instance.inserted) == 1
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_duplicate_business_keys_are_preserved_in_raw_staging(tmp_path: Path) -> None:
    source_path = tmp_path / "orders.csv"
    _write_orders(source_path)
    spec = _spec("orders")
    with source_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=spec.columns)
        writer.writerow({column: f"value-{index}" for index, column in enumerate(spec.columns)})
    connection = _Connection()
    loader = _ControlledLoader(connection)

    result = loader.load_dataset(spec, source_path)

    assert result.inserted_row_count == 2
    assert len(connection.cursor_instance.inserted) == 2


def test_transaction_failure_rolls_back_then_records_safe_provenance(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "orders.csv"
    _write_orders(source_path)
    connection = _Connection(fail_insert=True)
    loader = _ControlledLoader(connection)

    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        loader.load_dataset(_spec("orders"), source_path)

    assert connection.rollbacks >= 1
    assert connection.cursor_instance.inserted == []
    assert loader.failed_messages
    assert all("secret" not in message for message in loader.failed_messages)


def test_inventory_row_count_mismatch_rolls_back_batch(tmp_path: Path) -> None:
    source_path = tmp_path / "orders.csv"
    _write_orders(source_path)
    connection = _Connection()
    loader = _ControlledLoader(connection)

    with pytest.raises(RuntimeError, match="row-count mismatch"):
        loader.load_dataset(
            _spec("orders"),
            source_path,
            expected_row_count=2,
        )

    assert connection.commits == 0
    assert connection.rollbacks >= 1
    assert loader.failed_messages


def test_header_mismatch_fails_before_database_mutation(tmp_path: Path) -> None:
    source_path = tmp_path / "orders.csv"
    _write_orders(source_path, wrong_header=True)
    connection = _Connection()
    loader = _ControlledLoader(connection)

    with pytest.raises(CsvValidationError, match="header"):
        loader.load_dataset(_spec("orders"), source_path)

    assert connection.commits == 0
    assert connection.cursor_instance.inserted == []


def test_inventory_hash_mismatch_fails_before_database_mutation(tmp_path: Path) -> None:
    source_path = tmp_path / "orders.csv"
    _write_orders(source_path)
    connection = _Connection()
    loader = _ControlledLoader(connection)

    with pytest.raises(CsvValidationError, match="hash changed"):
        loader.load_dataset(
            _spec("orders"),
            source_path,
            expected_sha256="0" * 64,
        )

    assert connection.commits == 0
    assert connection.rollbacks == 0
    assert connection.cursor_instance.inserted == []


def test_complete_snapshot_activates_only_after_all_six_batches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_directory = tmp_path / "raw"
    _write_all_sources(raw_directory)
    inventory = build_inventory(raw_directory)
    events: list[str] = []

    class _SnapshotLoader:
        def __init__(self, connection: object, batch_size: int) -> None:
            del connection, batch_size

        def _successful_snapshot(self, source_manifest_sha256: str) -> None:
            assert len(source_manifest_sha256) == 64
            return None

        def _start_snapshot(self, source_manifest_sha256: str, dataset_count: int) -> int:
            assert len(source_manifest_sha256) == 64
            assert dataset_count == 6
            events.append("start")
            return 50

        def load_dataset(
            self,
            spec: Any,
            path: Path,
            *,
            expected_row_count: int,
            expected_sha256: str,
        ) -> LoadOutcome:
            assert path.is_file()
            events.append(spec.name)
            return LoadOutcome(
                spec.name,
                path.name,
                "succeeded",
                len(events),
                expected_row_count,
                expected_row_count,
                expected_sha256,
            )

        def _activate_snapshot(
            self,
            dataset_snapshot_id: int,
            outcomes: list[LoadOutcome],
        ) -> None:
            assert dataset_snapshot_id == 50
            assert len(outcomes) == 6
            assert events == ["start", *(spec.name for spec in DATASET_SPECS)]
            events.append("activate")

    monkeypatch.setattr(load_data_module, "SqlServerDatasetLoader", _SnapshotLoader)

    outcomes = load_required_files(
        _Connection(),
        raw_directory,
        inventory,
        batch_size=100,
    )

    assert len(outcomes) == 6
    assert events[-1] == "activate"


def test_failed_refresh_records_snapshot_failure_without_activation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_directory = tmp_path / "raw"
    _write_all_sources(raw_directory)
    inventory = build_inventory(raw_directory)
    events: list[str] = []

    class _FailingSnapshotLoader:
        def __init__(self, connection: object, batch_size: int) -> None:
            del connection, batch_size

        def _successful_snapshot(self, source_manifest_sha256: str) -> None:
            del source_manifest_sha256
            return None

        def _start_snapshot(self, source_manifest_sha256: str, dataset_count: int) -> int:
            del source_manifest_sha256, dataset_count
            events.append("start")
            return 60

        def load_dataset(self, spec: Any, path: Path, **kwargs: Any) -> LoadOutcome:
            del path, kwargs
            events.append(spec.name)
            if spec.name == "products":
                raise DatasetLoadError("synthetic refresh failure")
            return LoadOutcome(spec.name, spec.filename, "skipped", 1, 1, 0, "a" * 64)

        def _record_failed_snapshot(self, snapshot_id: int, message: str) -> None:
            assert snapshot_id == 60
            assert "synthetic refresh failure" in message
            events.append("failed")

        def _activate_snapshot(self, *args: object) -> None:
            del args
            events.append("activate")

    monkeypatch.setattr(
        load_data_module,
        "SqlServerDatasetLoader",
        _FailingSnapshotLoader,
    )
    connection = _Connection()

    with pytest.raises(DatasetLoadError, match="synthetic refresh failure"):
        load_required_files(connection, raw_directory, inventory, batch_size=100)

    assert events[-1] == "failed"
    assert "activate" not in events
    assert connection.rollbacks >= 1
