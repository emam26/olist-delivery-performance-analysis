# SQL Server setup

All actions here are manual. Use a dedicated development/analysis database. Do not
run the scripts in `master`, `model`, `msdb`, `tempdb`, an unrelated application
database, or a production database.

## Prerequisites

- A reachable Microsoft SQL Server instance.
- A confirmed SQL client such as SQL Server Management Studio (SSMS).
- ODBC Driver 18 installed in the environment that will run Python.
- An administrative identity for database/object deployment.
- A separate least-privilege runtime identity for loading and reporting.

Do not put a real password in repository files, command history, screenshots, or
chat. Enter it only into the local ignored `.env` or an approved secret manager.

## 1. Create or confirm the dedicated database

Where: SSMS, connected to the intended SQL Server instance as an authorized
administrator.

Action: review and run `sql/000_create_database.sql`.

Expected pattern: either `Created database [OlistDeliveryAnalytics]` or an explicit
message that it already exists. Stop if the name or server is not the intended one.

## 2. Deploy objects in order

Where: SSMS, with the query window explicitly connected to
`OlistDeliveryAnalytics`.

Run each complete script separately and stop on the first error:

1. `sql/001_create_schemas.sql`
2. `sql/002_create_staging_tables.sql`
3. `sql/003_create_analytical_views.sql`
4. `sql/004_create_reporting_views.sql`
5. `sql/005_data_quality_checks.sql`
6. `sql/006_analysis_queries.sql` — read-only examples; review rather than batch
   deployment if preferred
7. `sql/007_create_database_roles.sql`

Expected pattern: no SQL error and the role script returns permissions for
`olist_loader` and `olist_report_reader`. Script 006 must return empty or populated
result sets depending on whether data have been loaded; it changes no data.

## 3. Map the runtime identity manually

The repository does not create a login because the authentication method and secret
are environment-specific. As an administrator, create or identify the runtime login,
then map it to a database user and add it to the role. Replace the bracketed
placeholder with the already approved login name; never paste a password into this
script.

```sql
USE [OlistDeliveryAnalytics];
GO

CREATE USER [<approved-runtime-login>] FOR LOGIN [<approved-runtime-login>];
ALTER ROLE [olist_loader] ADD MEMBER [<approved-runtime-login>];
```

If the user already exists, omit `CREATE USER`. A read-only Power BI identity should
instead be added to `olist_report_reader`.

## 4. Verify object inventory

Where: SSMS, target database `OlistDeliveryAnalytics`.

```sql
SELECT s.name AS schema_name, o.type_desc, COUNT_BIG(*) AS object_count
FROM sys.objects AS o
JOIN sys.schemas AS s ON s.schema_id = o.schema_id
WHERE s.name IN (N'audit', N'stg', N'analytics', N'reporting')
  AND o.is_ms_shipped = 0
GROUP BY s.name, o.type_desc
ORDER BY s.name, o.type_desc;
```

Expected pattern: objects appear only in the four project schemas. Return this
non-secret output for review. Do not proceed to loading if required schemas, six
staging tables, snapshot audit tables, analytical views, reporting views, or the
validation procedure are missing.

## 5. Connectivity boundary

The Python connection check reports server, login, database, edition, and version.
It must not print the password or full connection string. Connectivity proves only
that authentication and routing work; it does not prove that schema deployment,
loading, validation, or metrics are correct.

## Recovery principles

- A failed file load should leave no staging rows from that transaction.
- Safe failed-attempt provenance may remain in `audit.load_batches`.
- A six-file refresh becomes visible only when `audit.dataset_snapshots` is marked
  `Succeeded` and has six valid mappings. Individual successful batches from an
  interrupted refresh are reusable, but must not replace the prior active snapshot.
- Never delete or truncate data merely to retry; diagnose the batch status and
  source hash first.
- Make a database backup before any operator-authored destructive recovery.
- The supplied scripts contain no automatic reset or drop operation.
