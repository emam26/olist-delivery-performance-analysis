"""Transactional, duplicate-protected CSV loading into SQL Server staging tables."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .database import safe_database_error
from .datasets import DATASET_SPECS, DatasetSpec
from .inventory import InventoryReport, sha256_file

STAGING_TABLES = {
    "orders": "stg.orders",
    "order_items": "stg.order_items",
    "customers": "stg.customers",
    "sellers": "stg.sellers",
    "products": "stg.products",
    "reviews": "stg.reviews",
}


class DatasetLoadError(RuntimeError):
    """Raised when a source file cannot be loaded without row loss."""


class CsvValidationError(DatasetLoadError):
    """Raised when a source CSV violates its declared contract."""


@dataclass(frozen=True, slots=True)
class LoadOutcome:
    """One file-load outcome."""

    dataset: str
    filename: str
    status: str
    load_batch_id: int | None
    source_row_count: int
    inserted_row_count: int
    source_sha256: str


@dataclass(frozen=True, slots=True)
class _PreparedSource:
    spec: DatasetSpec
    path: Path
    row_count: int
    source_sha256: str


def _source_manifest_sha256(sources: Iterable[_PreparedSource]) -> str:
    payload = [
        {
            "dataset": source.spec.name,
            "filename": source.spec.filename,
            "row_count": source.row_count,
            "source_sha256": source.source_sha256,
        }
        for source in sources
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _prepare_inventory_sources(
    data_directory: Path,
    inventory_report: Mapping[str, Any] | InventoryReport,
) -> tuple[_PreparedSource, ...]:
    payload = (
        inventory_report.to_dict()
        if isinstance(inventory_report, InventoryReport)
        else inventory_report
    )
    files = payload.get("files")
    if not isinstance(files, list):
        raise DatasetLoadError("inventory report has no valid files collection")
    evidence_by_name: dict[str, Mapping[str, Any]] = {}
    for item in files:
        if not isinstance(item, Mapping):
            raise DatasetLoadError("inventory file evidence must be an object")
        dataset = str(item.get("dataset", ""))
        if dataset in evidence_by_name:
            raise DatasetLoadError(f"inventory contains duplicate evidence for {dataset!r}")
        evidence_by_name[dataset] = item

    expected_names = {spec.name for spec in DATASET_SPECS}
    if set(evidence_by_name) != expected_names:
        missing = sorted(expected_names - set(evidence_by_name))
        unexpected = sorted(set(evidence_by_name) - expected_names)
        raise DatasetLoadError(
            f"inventory dataset set is invalid; missing={missing}; unexpected={unexpected}"
        )

    prepared: list[_PreparedSource] = []
    for spec in DATASET_SPECS:
        evidence = evidence_by_name[spec.name]
        loadable = evidence.get("loadable")
        if loadable is not True:
            raise DatasetLoadError(
                f"inventory marks {spec.name} as structurally unloadable; loading is blocked"
            )
        if evidence.get("filename") != spec.filename:
            raise DatasetLoadError(
                f"inventory filename for {spec.name} does not match {spec.filename}"
            )
        try:
            row_count = int(evidence["row_count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DatasetLoadError(f"inventory row count for {spec.name} is invalid") from exc
        source_sha256 = str(evidence.get("sha256", "")).lower()
        if (
            row_count < 0
            or len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)
        ):
            raise DatasetLoadError(f"inventory provenance for {spec.name} is invalid")

        path = data_directory / spec.filename
        _validate_header(path, spec)
        current_sha256 = sha256_file(path)
        if current_sha256 != source_sha256:
            raise DatasetLoadError(
                f"source hash changed after inventory for {spec.filename}; rebuild the inventory"
            )
        prepared.append(_PreparedSource(spec, path, row_count, source_sha256))
    return tuple(prepared)


def _validate_header(path: Path, spec: DatasetSpec) -> None:
    if not path.is_file():
        raise CsvValidationError(f"required source file is missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        try:
            headers = tuple(next(reader))
        except StopIteration as exc:
            raise CsvValidationError(f"source file is empty: {path}") from exc
    if headers != spec.columns:
        missing = sorted(set(spec.columns) - set(headers))
        unexpected = sorted(set(headers) - set(spec.columns))
        raise CsvValidationError(
            f"incorrect CSV header for {spec.filename}; missing={missing}; "
            f"unexpected={unexpected}; "
            "column order must match the documented source contract"
        )


def iter_source_rows(path: Path, spec: DatasetSpec) -> Iterator[tuple[int, tuple[str, ...], str]]:
    """Yield source row number, exact text values, and deterministic row hash."""

    _validate_header(path, spec)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            for source_row_number, row in enumerate(reader, start=2):
                if None in row or any(row.get(column) is None for column in spec.columns):
                    raise CsvValidationError(
                        f"malformed CSV record in {spec.filename} at source line "
                        f"{source_row_number}"
                    )
                values = tuple(row[column] for column in spec.columns)
                canonical = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
                row_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                yield source_row_number, values, row_hash
    except (OSError, UnicodeError, csv.Error) as exc:
        raise DatasetLoadError(f"could not parse {spec.filename}: {exc}") from exc


def _chunks(rows: Iterable[tuple[Any, ...]], size: int) -> Iterator[list[tuple[Any, ...]]]:
    chunk: list[tuple[Any, ...]] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


class SqlServerDatasetLoader:
    """Load one immutable source file in one SQL transaction."""

    def __init__(self, connection: Any, batch_size: int = 1000) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.connection = connection
        self.batch_size = batch_size

    def _successful_batch(self, dataset: str, source_sha256: str) -> int | None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT TOP (1) load_batch_id
            FROM audit.load_batches
            WHERE dataset_name = ? AND source_sha256 = ? AND status = 'Succeeded'
            ORDER BY load_batch_id DESC
            """,
            (dataset, source_sha256),
        )
        row = cursor.fetchone()
        return int(row[0]) if row is not None else None

    def _successful_snapshot(self, source_manifest_sha256: str) -> int | None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT TOP (1) dataset_snapshot_id
            FROM audit.dataset_snapshots
            WHERE source_manifest_sha256 = ? AND status = 'Succeeded'
            ORDER BY dataset_snapshot_id DESC
            """,
            (source_manifest_sha256,),
        )
        row = cursor.fetchone()
        return int(row[0]) if row is not None else None

    def _snapshot_batch_ids(self, dataset_snapshot_id: int) -> dict[str, int]:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT dataset_name, load_batch_id
            FROM audit.dataset_snapshot_batches
            WHERE dataset_snapshot_id = ?
            """,
            (dataset_snapshot_id,),
        )
        return {str(row[0]): int(row[1]) for row in cursor.fetchall()}

    def _start_snapshot(self, source_manifest_sha256: str, dataset_count: int) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO audit.dataset_snapshots
                (source_manifest_sha256, dataset_count, status)
            OUTPUT INSERTED.dataset_snapshot_id
            VALUES (?, ?, 'Started')
            """,
            (source_manifest_sha256, dataset_count),
        )
        row = cursor.fetchone()
        if row is None:
            raise DatasetLoadError("SQL Server did not return a dataset snapshot ID")
        self.connection.commit()
        return int(row[0])

    def _activate_snapshot(
        self,
        dataset_snapshot_id: int,
        outcomes: Iterable[LoadOutcome],
    ) -> None:
        rows = [
            (
                dataset_snapshot_id,
                outcome.dataset,
                outcome.load_batch_id,
                outcome.source_sha256,
            )
            for outcome in outcomes
        ]
        if len(rows) != len(DATASET_SPECS) or any(row[2] is None for row in rows):
            raise DatasetLoadError("a complete snapshot requires one successful batch per dataset")
        cursor = self.connection.cursor()
        cursor.executemany(
            """
            INSERT INTO audit.dataset_snapshot_batches
                (dataset_snapshot_id, dataset_name, load_batch_id, source_sha256)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        cursor.execute(
            """
            UPDATE audit.dataset_snapshots
            SET status = 'Succeeded', completed_at_utc = SYSUTCDATETIME(),
                error_summary = NULL
            WHERE dataset_snapshot_id = ? AND status = 'Started'
            """,
            (dataset_snapshot_id,),
        )
        self.connection.commit()

    def _record_failed_snapshot(
        self,
        dataset_snapshot_id: int,
        error_message: str,
    ) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE audit.dataset_snapshots
            SET status = 'Failed', completed_at_utc = SYSUTCDATETIME(),
                error_summary = ?
            WHERE dataset_snapshot_id = ? AND status = 'Started'
            """,
            (error_message[:4000], dataset_snapshot_id),
        )
        self.connection.commit()

    def _start_batch(
        self,
        spec: DatasetSpec,
        path: Path,
        source_sha256: str,
        source_byte_count: int,
        expected_row_count: int | None,
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO audit.load_batches
            (
                dataset_name, source_filename, source_sha256, source_byte_count,
                expected_row_count, status
            )
            OUTPUT INSERTED.load_batch_id
            VALUES (?, ?, ?, ?, ?, 'Started')
            """,
            (
                spec.name,
                path.name,
                source_sha256,
                source_byte_count,
                expected_row_count,
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise DatasetLoadError("SQL Server did not return a load batch ID")
        return int(row[0])

    def _record_failed_batch(
        self,
        spec: DatasetSpec,
        path: Path,
        source_sha256: str,
        source_byte_count: int,
        expected_row_count: int | None,
        error_message: str,
    ) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO audit.load_batches
            (
                dataset_name, source_filename, source_sha256, source_byte_count,
                expected_row_count, inserted_row_count, status,
                completed_at_utc, error_summary
            )
            VALUES (?, ?, ?, ?, ?, 0, 'Failed', SYSUTCDATETIME(), ?)
            """,
            (
                spec.name,
                path.name,
                source_sha256,
                source_byte_count,
                expected_row_count,
                error_message[:4000],
            ),
        )
        self.connection.commit()

    def load_file(
        self,
        spec: DatasetSpec,
        path: Path,
        *,
        expected_row_count: int | None = None,
        expected_sha256: str | None = None,
    ) -> LoadOutcome:
        """Load a file atomically, or preserve a safe failure record after rollback."""

        _validate_header(path, spec)
        source_sha256 = sha256_file(path)
        if expected_sha256 is not None and source_sha256 != expected_sha256:
            raise CsvValidationError(
                f"source hash changed after inventory for {spec.filename}; rebuild the inventory"
            )
        source_byte_count = path.stat().st_size
        existing_batch = self._successful_batch(spec.name, source_sha256)
        if existing_batch is not None:
            return LoadOutcome(
                spec.name,
                path.name,
                "skipped",
                existing_batch,
                expected_row_count or 0,
                0,
                source_sha256,
            )

        load_batch_id: int | None = None
        inserted = 0
        try:
            self.connection.autocommit = False
            load_batch_id = self._start_batch(
                spec,
                path,
                source_sha256,
                source_byte_count,
                expected_row_count,
            )
            table = STAGING_TABLES[spec.name]
            columns = ", ".join(spec.columns)
            placeholders = ", ".join("?" for _ in range(len(spec.columns) + 3))
            statement = (
                f"INSERT INTO {table} "
                f"(load_batch_id, source_row_number, {columns}, source_row_sha256) "
                f"VALUES ({placeholders})"
            )
            cursor = self.connection.cursor()
            if hasattr(cursor, "fast_executemany"):
                cursor.fast_executemany = True
            rows = (
                (load_batch_id, source_row_number, *values, row_hash)
                for source_row_number, values, row_hash in iter_source_rows(path, spec)
            )
            for chunk in _chunks(rows, self.batch_size):
                cursor.executemany(statement, chunk)
                inserted += len(chunk)

            if sha256_file(path) != source_sha256:
                raise DatasetLoadError(
                    f"source changed while loading {spec.filename}; transaction will roll back"
                )
            if expected_row_count is not None and inserted != expected_row_count:
                raise DatasetLoadError(
                    f"row-count mismatch for {spec.filename}: "
                    f"expected {expected_row_count}, prepared {inserted}"
                )
            cursor.execute(
                """
                UPDATE audit.load_batches
                SET inserted_row_count = ?, status = 'Succeeded',
                    completed_at_utc = SYSUTCDATETIME(), error_summary = NULL
                WHERE load_batch_id = ?
                """,
                (inserted, load_batch_id),
            )
            self.connection.commit()
            return LoadOutcome(
                spec.name,
                path.name,
                "succeeded",
                load_batch_id,
                inserted,
                inserted,
                source_sha256,
            )
        except Exception as exc:
            self.connection.rollback()
            error_summary = safe_database_error(exc)
            try:
                self._record_failed_batch(
                    spec,
                    path,
                    source_sha256,
                    source_byte_count,
                    expected_row_count,
                    error_message=error_summary,
                )
            except Exception:
                self.connection.rollback()
            raise DatasetLoadError(
                f"load failed for {spec.filename}; staging transaction was rolled back; "
                f"{error_summary}"
            ) from exc

    def load_dataset(
        self,
        spec: DatasetSpec,
        path: Path,
        *,
        expected_row_count: int | None = None,
        expected_sha256: str | None = None,
    ) -> LoadOutcome:
        """Load one dataset using the canonical loader method name."""

        return self.load_file(
            spec,
            path,
            expected_row_count=expected_row_count,
            expected_sha256=expected_sha256,
        )


def load_required_files(
    connection: Any,
    data_directory: Path,
    inventory_report: Mapping[str, Any] | InventoryReport,
    *,
    batch_size: int,
) -> tuple[LoadOutcome, ...]:
    """Load all inventoried files and atomically activate their source manifest."""

    sources = _prepare_inventory_sources(data_directory, inventory_report)
    source_manifest_sha256 = _source_manifest_sha256(sources)
    loader = SqlServerDatasetLoader(connection, batch_size)
    existing_snapshot = loader._successful_snapshot(source_manifest_sha256)
    if existing_snapshot is not None:
        batch_ids = loader._snapshot_batch_ids(existing_snapshot)
        if set(batch_ids) != {source.spec.name for source in sources}:
            raise DatasetLoadError(
                f"successful snapshot {existing_snapshot} has an incomplete dataset mapping"
            )
        return tuple(
            LoadOutcome(
                source.spec.name,
                source.path.name,
                "skipped",
                batch_ids[source.spec.name],
                source.row_count,
                0,
                source.source_sha256,
            )
            for source in sources
        )

    dataset_snapshot_id: int | None = None
    outcomes: list[LoadOutcome] = []
    try:
        dataset_snapshot_id = loader._start_snapshot(source_manifest_sha256, len(sources))
        for source in sources:
            outcomes.append(
                loader.load_dataset(
                    source.spec,
                    source.path,
                    expected_row_count=source.row_count,
                    expected_sha256=source.source_sha256,
                )
            )
        loader._activate_snapshot(dataset_snapshot_id, outcomes)
        return tuple(outcomes)
    except Exception as exc:
        connection.rollback()
        safe_message = safe_database_error(exc)
        if dataset_snapshot_id is not None:
            try:
                loader._record_failed_snapshot(dataset_snapshot_id, safe_message)
            except Exception:
                connection.rollback()
        if isinstance(exc, DatasetLoadError):
            raise
        raise DatasetLoadError(
            f"dataset snapshot activation failed; prior successful snapshot remains active; "
            f"{safe_message}"
        ) from exc
