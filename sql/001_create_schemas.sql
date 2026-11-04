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

    IF OBJECT_ID(N'audit.validation_runs', N'U') IS NULL
    BEGIN
        CREATE TABLE audit.validation_runs
        (
            validation_run_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_validation_runs PRIMARY KEY,
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
                CHECK (completed_at_utc IS NULL OR completed_at_utc >= started_at_utc)
        );
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
