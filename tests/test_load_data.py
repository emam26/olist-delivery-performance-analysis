from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from olist_delivery.datasets import DATASET_SPECS
from olist_delivery.load_data import CsvValidationError, SqlServerDatasetLoader


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


def test_header_mismatch_fails_before_database_mutation(tmp_path: Path) -> None:
    source_path = tmp_path / "orders.csv"
    _write_orders(source_path, wrong_header=True)
    connection = _Connection()
    loader = _ControlledLoader(connection)

    with pytest.raises(CsvValidationError, match="header"):
        loader.load_dataset(_spec("orders"), source_path)

    assert connection.commits == 0
    assert connection.cursor_instance.inserted == []
