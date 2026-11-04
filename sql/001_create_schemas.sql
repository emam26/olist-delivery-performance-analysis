/*
Creates non-destructive schemas and audit metadata for the Olist project.

Run manually in the intended project database. This script does not create,
drop, or switch databases and refuses to run in a system database.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_NAME() IN (N'master', N'model', N'msdb', N'tempdb')
    THROW 51000, 'Run this script only in the dedicated Olist project database.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF SCHEMA_ID(N'audit') IS NULL EXEC(N'CREATE SCHEMA audit AUTHORIZATION dbo;');
    IF SCHEMA_ID(N'stg') IS NULL EXEC(N'CREATE SCHEMA stg AUTHORIZATION dbo;');
    IF SCHEMA_ID(N'analytics') IS NULL EXEC(N'CREATE SCHEMA analytics AUTHORIZATION dbo;');
    IF SCHEMA_ID(N'reporting') IS NULL EXEC(N'CREATE SCHEMA reporting AUTHORIZATION dbo;');

    IF OBJECT_ID(N'audit.load_batches', N'U') IS NULL
    BEGIN
        CREATE TABLE audit.load_batches
        (
            load_batch_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_load_batches PRIMARY KEY,
            dataset_name nvarchar(100) NOT NULL,
            source_filename nvarchar(260) NOT NULL,
            source_sha256 char(64) NOT NULL,
            source_byte_count bigint NOT NULL,
            expected_row_count bigint NULL,
            inserted_row_count bigint NOT NULL
                CONSTRAINT DF_load_batches_inserted DEFAULT (0),
            status varchar(20) NOT NULL
                CONSTRAINT DF_load_batches_status DEFAULT ('Started'),
            started_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_load_batches_started DEFAULT (SYSUTCDATETIME()),
            completed_at_utc datetime2(7) NULL,
            error_summary nvarchar(4000) NULL,
            CONSTRAINT CK_load_batches_dataset_not_blank
                CHECK (LEN(LTRIM(RTRIM(dataset_name))) > 0),
            CONSTRAINT CK_load_batches_filename_not_blank
                CHECK (LEN(LTRIM(RTRIM(source_filename))) > 0),
            CONSTRAINT CK_load_batches_sha256_length CHECK (LEN(source_sha256) = 64),
            CONSTRAINT CK_load_batches_byte_count CHECK (source_byte_count >= 0),
            CONSTRAINT CK_load_batches_expected_count
                CHECK (expected_row_count IS NULL OR expected_row_count >= 0),
            CONSTRAINT CK_load_batches_inserted_count CHECK (inserted_row_count >= 0),
            CONSTRAINT CK_load_batches_status
                CHECK (status IN ('Started', 'Succeeded', 'Failed', 'SkippedDuplicate')),
            CONSTRAINT CK_load_batches_completion
                CHECK (completed_at_utc IS NULL OR completed_at_utc >= started_at_utc)
        );
    END;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'audit.load_batches')
          AND name = N'UX_load_batches_succeeded_file'
    )
    BEGIN
        CREATE UNIQUE INDEX UX_load_batches_succeeded_file
            ON audit.load_batches (dataset_name, source_sha256)
            WHERE status = 'Succeeded';
    END;

    IF OBJECT_ID(N'audit.dataset_snapshots', N'U') IS NULL
    BEGIN
        CREATE TABLE audit.dataset_snapshots
        (
            dataset_snapshot_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_dataset_snapshots PRIMARY KEY,
            source_manifest_sha256 char(64) NOT NULL,
            dataset_count int NOT NULL,
            status varchar(20) NOT NULL
                CONSTRAINT DF_dataset_snapshots_status DEFAULT ('Started'),
            started_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_dataset_snapshots_started DEFAULT (SYSUTCDATETIME()),
            completed_at_utc datetime2(7) NULL,
            error_summary nvarchar(4000) NULL,
            CONSTRAINT CK_dataset_snapshots_sha256_length
                CHECK (LEN(source_manifest_sha256) = 64),
            CONSTRAINT CK_dataset_snapshots_dataset_count CHECK (dataset_count > 0),
            CONSTRAINT CK_dataset_snapshots_status
                CHECK (status IN ('Started', 'Succeeded', 'Failed')),
            CONSTRAINT CK_dataset_snapshots_completion
                CHECK (completed_at_utc IS NULL OR completed_at_utc >= started_at_utc)
        );
    END;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'audit.dataset_snapshots')
          AND name = N'UX_dataset_snapshots_succeeded_manifest'
    )
    BEGIN
        CREATE UNIQUE INDEX UX_dataset_snapshots_succeeded_manifest
            ON audit.dataset_snapshots (source_manifest_sha256)
            WHERE status = 'Succeeded';
    END;

    IF OBJECT_ID(N'audit.dataset_snapshot_batches', N'U') IS NULL
    BEGIN
        CREATE TABLE audit.dataset_snapshot_batches
        (
            dataset_snapshot_id bigint NOT NULL,
            dataset_name nvarchar(100) NOT NULL,
            load_batch_id bigint NOT NULL,
            source_sha256 char(64) NOT NULL,
            CONSTRAINT PK_dataset_snapshot_batches
                PRIMARY KEY (dataset_snapshot_id, dataset_name),
            CONSTRAINT UQ_dataset_snapshot_batches_batch
                UNIQUE (dataset_snapshot_id, load_batch_id),
            CONSTRAINT FK_dataset_snapshot_batches_snapshot
                FOREIGN KEY (dataset_snapshot_id)
                REFERENCES audit.dataset_snapshots (dataset_snapshot_id),
            CONSTRAINT FK_dataset_snapshot_batches_load_batch
                FOREIGN KEY (load_batch_id)
                REFERENCES audit.load_batches (load_batch_id),
            CONSTRAINT CK_dataset_snapshot_batches_name_not_blank
                CHECK (LEN(LTRIM(RTRIM(dataset_name))) > 0),
            CONSTRAINT CK_dataset_snapshot_batches_known_dataset
                CHECK (dataset_name IN
                (
                    N'orders', N'order_items', N'customers',
                    N'sellers', N'products', N'reviews'
                )),
            CONSTRAINT CK_dataset_snapshot_batches_sha256_length
                CHECK (LEN(source_sha256) = 64)
        );
    END;

    IF OBJECT_ID(N'audit.validation_runs', N'U') IS NULL
    BEGIN
        CREATE TABLE audit.validation_runs
        (
            validation_run_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_validation_runs PRIMARY KEY,
            dataset_snapshot_id bigint NULL,
            status varchar(20) NOT NULL
                CONSTRAINT DF_validation_runs_status DEFAULT ('Started'),
            fail_on_warning bit NOT NULL,
            started_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_validation_runs_started DEFAULT (SYSUTCDATETIME()),
            completed_at_utc datetime2(7) NULL,
            error_summary nvarchar(4000) NULL,
            CONSTRAINT CK_validation_runs_status
                CHECK (status IN ('Started', 'Passed', 'Warning', 'Failed')),
            CONSTRAINT CK_validation_runs_completion
                CHECK (completed_at_utc IS NULL OR completed_at_utc >= started_at_utc),
            CONSTRAINT FK_validation_runs_snapshot
                FOREIGN KEY (dataset_snapshot_id)
                REFERENCES audit.dataset_snapshots (dataset_snapshot_id)
        );
    END;

    IF COL_LENGTH(N'audit.validation_runs', N'dataset_snapshot_id') IS NULL
        ALTER TABLE audit.validation_runs ADD dataset_snapshot_id bigint NULL;

    IF NOT EXISTS
    (
        SELECT 1 FROM sys.foreign_keys
        WHERE parent_object_id = OBJECT_ID(N'audit.validation_runs')
          AND name = N'FK_validation_runs_snapshot'
    )
    BEGIN
        ALTER TABLE audit.validation_runs WITH CHECK
            ADD CONSTRAINT FK_validation_runs_snapshot
            FOREIGN KEY (dataset_snapshot_id)
            REFERENCES audit.dataset_snapshots (dataset_snapshot_id);
    END;

    IF NOT EXISTS
    (
        SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'audit.validation_runs')
          AND name = N'IX_validation_runs_snapshot'
    )
    BEGIN
        CREATE INDEX IX_validation_runs_snapshot
            ON audit.validation_runs (dataset_snapshot_id, validation_run_id DESC)
            INCLUDE (status, completed_at_utc);
    END;

    IF OBJECT_ID(N'audit.validation_results', N'U') IS NULL
    BEGIN
        CREATE TABLE audit.validation_results
        (
            validation_result_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_validation_results PRIMARY KEY,
            validation_run_id bigint NOT NULL,
            check_id nvarchar(200) NOT NULL,
            status varchar(20) NOT NULL,
            observed_value nvarchar(1000) NULL,
            expected_value nvarchar(1000) NULL,
            message nvarchar(2000) NOT NULL,
            created_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_validation_results_created DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT FK_validation_results_run
                FOREIGN KEY (validation_run_id)
                REFERENCES audit.validation_runs (validation_run_id),
            CONSTRAINT UQ_validation_results_run_check
                UNIQUE (validation_run_id, check_id),
            CONSTRAINT CK_validation_results_status
                CHECK (status IN ('Passed', 'Warning', 'Failed', 'NotEvaluated'))
        );
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
