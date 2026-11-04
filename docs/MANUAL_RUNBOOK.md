# Manual runbook

This runbook is the only supported execution sequence. Codex has not run any step.
Stop after a failed prerequisite and return only non-secret diagnostics. Do not
continue into SQL loading or dashboard work until the earlier gate is satisfied.

## Local conventions

- WSL project directory: `/mnt/f/olist-delivery-performance-analysis`
- Windows project directory: `F:\olist-delivery-performance-analysis`
- SQL target database: `OlistDeliveryAnalytics`
- Generated inventory: `reports/inventory/`
- Generated validation/export artifacts: `reports/`
- Raw CSV files: local ignored `data/raw/`

If your checkout is elsewhere, replace the project directory only after confirming
its absolute path. Never guess a SQL host, login, or password.

## Phase A — offline project and source checks

### A1. Confirm the checkout

Where: WSL Bash.

```bash
cd /mnt/f/olist-delivery-performance-analysis
pwd
find . -maxdepth 2 -type f | sort
```

Purpose: confirm the intended repository and inspect its bounded file inventory.

Expected pattern: `pwd` prints the exact project path; source, SQL, tests, Power BI,
and documentation files are present. Stop if the path is wrong. Return the file list
only if expected files are missing.

### A2. Create the dedicated Python environment

Where: WSL Bash, project root.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Purpose: isolate dependencies from Conda base and unrelated projects.

Expected pattern: Python reports 3.13 or later and editable installation completes
without dependency errors. Stop and return the Python version and final non-secret
error if creation or installation fails.

### A3. Run static and offline automated checks

Where: WSL Bash, activated project environment, project root.

```bash
ruff check .
ruff format --check .
python -m pytest -q -m "not sqlserver"
```

Purpose: verify lint, formatting, and tests that require neither SQL Server nor the
real source data.

Expected pattern: all three commands exit zero. Return each summary. Stop on the
first failure and do not run automatic fixes until the diagnostic is reviewed.

### A4. Acquire source files manually

Where: browser for acquisition, then Windows Explorer or WSL for placement.

Action: obtain the Brazilian E-Commerce Public Dataset by Olist from the source
identified in the repository README. Review its license/terms. Place exactly these
files in `data/raw/` without editing them:

```text
olist_orders_dataset.csv
olist_order_items_dataset.csv
olist_customers_dataset.csv
olist_sellers_dataset.csv
olist_products_dataset.csv
olist_order_reviews_dataset.csv
```

Purpose: establish immutable local inputs. Do not commit the CSV files or archives.

Expected pattern: all six filenames exist. Stop if the source, license, archive, or
filenames differ; do not rename a semantically different file to force acceptance.

### A5. Build the offline inventory

Where: WSL Bash, activated environment, project root.

```bash
python scripts/inventory_data.py \
  --output reports/inventory/olist_source_inventory.json
```

Purpose: verify headers, rows, hashes, malformed records, duplicates, timestamps,
and cross-file relationships before any database activity.

Expected pattern: a summary for six files, an overall non-failed status, and a new
JSON report path. The command must refuse to overwrite an existing report. Return
the overall status, per-file row counts and SHA-256 hashes, and relationship-check
summary. Do not return raw records.

## Phase B — local configuration and SQL Server deployment

### B1. Create local configuration

Where: WSL Bash, project root.

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` locally and replace placeholders with the confirmed SQL host, database,
runtime login, and password. Keep `OlistDeliveryAnalytics` unless the SQL scripts and
documentation are deliberately changed together.

Purpose: configure the runtime without exposing credentials.

Expected pattern: `.env` exists locally and remains ignored. Do not print or return
its contents.

### B2. Deploy SQL Server

Where: SSMS. Follow `docs/SQL_SERVER_SETUP.md` exactly.

Purpose: create the dedicated database, four schemas, audit/staging objects,
analytical/reporting views, validation procedure, and least-privilege roles.

Expected pattern: no SQL errors and the documented object inventory is present.
Return only the non-secret object-count query output.

### B3. Check Python-to-SQL connectivity

Where: WSL Bash, activated environment, project root.

```bash
python scripts/check_database.py
```

Purpose: confirm ODBC Driver 18 routing/authentication to the target database.

Expected pattern: a concise success message with server, login, database, edition,
and version, but no password or full connection string. Stop if the reported server
or database is not the intended target.

### B4. Run the opt-in SQL Server integration check

Where: WSL Bash, activated environment, project root. Use only the dedicated
development/analysis database configured in the local `.env`.

```bash
RUN_SQLSERVER_TESTS=1 python -m pytest -q -m sqlserver
```

Purpose: confirm that the six staging tables and required analytical, reporting,
and audit objects are visible to the runtime identity.

Expected pattern: the SQL-marked test passes without exposing a connection string.
Stop and return the failing assertion or safe database error if it does not.

## Phase C — load and validate

### C1. Load the six inventoried files

Where: WSL Bash, activated environment, project root.

```bash
python scripts/load_to_sqlserver.py \
  --inventory reports/inventory/olist_source_inventory.json
```

Purpose: load each source file atomically with source hashes and batch provenance.

Expected pattern: one successful or idempotently skipped result per dataset. Return
dataset name, batch ID, source row count, inserted row count, and status. Stop on the
first failure; preserve its safe message and do not truncate tables.

### C2. Inspect load provenance

Where: SSMS, target database `OlistDeliveryAnalytics`.

```sql
SELECT
    load_batch_id,
    dataset_name,
    source_filename,
    source_sha256,
    source_row_count,
    inserted_row_count,
    status,
    started_at_utc,
    completed_at_utc,
    error_message
FROM audit.load_batches
ORDER BY load_batch_id;
```

Purpose: verify batch identity and status without viewing source rows or secrets.

Expected pattern: exactly one latest successful batch per required source hash and
matching source/inserted row counts. Failed historical attempts may remain as valid
provenance.

### C3. Run logged SQL data-quality checks

Where: WSL Bash, activated environment, project root.

```bash
python scripts/validate_data.py \
  --inventory reports/inventory/olist_source_inventory.json \
  --json-output reports/sql_validation.json \
  --markdown-output reports/sql_validation.md
```

Purpose: execute SQL validation, combine it with inventory evidence, and create
reviewable artifacts.

Expected pattern: a validation run ID, zero failed critical checks, and new output
files. Return the status/count summary and any warning check IDs. Stop on a critical
failure.

### C4. Reconcile independent metrics

Where: WSL Bash, activated environment, project root.

```bash
python scripts/validate_metrics.py \
  --json-output reports/metric_reconciliation.json
```

Purpose: compare independent Python definitions with SQL analytical outputs.

Expected pattern: exact count agreement, tolerance-bounded numeric agreement, and a
passed overall status. Return the metric comparison summary. Stop if any core metric
differs.

### C5. Confirm idempotency

Where: WSL Bash, activated environment, project root.

```bash
python scripts/load_to_sqlserver.py \
  --inventory reports/inventory/olist_source_inventory.json
```

Purpose: prove that replaying unchanged file hashes creates no staging duplicates.

Expected pattern: all six datasets report an idempotent skip referencing existing
successful batch IDs. Confirm in SSMS that successful-batch and staging-row counts
did not increase.

## Phase D — dashboard handoff

### D1. Export a manifest-bound snapshot

Where: WSL Bash, activated environment, project root.

```bash
python scripts/export_dashboard_data.py \
  --output-directory reports/exports/olist_dashboard_v1
```

Purpose: create one non-overwritten CSV set and `manifest.json` for offline Power BI
use.

Expected pattern: one CSV per configured reporting view plus a manifest containing
row counts and SHA-256 hashes. Return filenames, row counts, and hashes only.

### D2. Build and reconcile Power BI manually

Where: Power BI Desktop on Windows.

Action: follow `powerbi/README.md`, `data_model.md`, `measures.dax`, and
`dashboard_specification.md`. Then complete every item in `reconciliation.md`.

Expected pattern: exact count agreement, tolerance-bounded rates/durations, visible
denominators/exclusions, disconnected seller/category summaries, and no failed
critical validation. Return the reconciliation table and screenshots only after
checking that they contain no credentials or private local paths.

## Phase E — findings and version control

Populate `docs/FINDINGS.md` only from reconciled outputs. Update
`docs/IMPLEMENTATION_STATUS.md` with supplied execution evidence and limitations.
The operator, not Codex, decides when to commit and push. Never commit `.env`, raw
CSV files, generated inventory/validation/export artifacts, database files, or
credentials.
