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

## Phase A - offline project and source checks

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

## Phase B - local configuration and SQL Server deployment

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

## Phase C - load and validate

### C1. Load the six inventoried files

Where: WSL Bash, activated environment, project root.

```bash
python scripts/load_to_sqlserver.py \
  --inventory reports/inventory/olist_source_inventory.json
```

Purpose: load each source file atomically, reuse already successful file hashes,
and activate one six-file source snapshot only after every mapping is complete.

Expected pattern: one successful or idempotently skipped result per dataset. Return
dataset name, batch ID, source row count, inserted row count, and status. Stop on the
first failure; preserve its safe message and do not truncate tables. A failed
refresh must leave the prior successful snapshot active.

### C2. Inspect load provenance

Where: SSMS, target database `OlistDeliveryAnalytics`.

```sql
SELECT
    p.dataset_snapshot_id,
    p.source_manifest_sha256,
    p.dataset_name,
    p.load_batch_id,
    p.source_filename,
    p.source_sha256,
    p.expected_row_count,
    p.inserted_row_count,
    p.completed_at_utc
FROM reporting.vw_current_source_provenance AS p
ORDER BY p.dataset_name;
```

Purpose: verify batch identity and status without viewing source rows or secrets.

Expected pattern: one snapshot ID and manifest hash across exactly six rows, with
matching expected/inserted counts. `audit.load_batches` and
`audit.dataset_snapshots` may retain failed historical attempts as provenance.

### C3. Run logged SQL data-quality checks

Where: WSL Bash, activated environment, project root.

```bash
python scripts/validate_data.py \
  --inventory reports/inventory/olist_source_inventory.json \
  --sqlserver \
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
  --orders-csv data/raw/olist_orders_dataset.csv \
  --sqlserver \
  --json-output reports/metric_reconciliation.json
```

Purpose: compare independent Python definitions with SQL analytical outputs.

Expected pattern: exact count agreement, tolerance-bounded numeric agreement, and a
passed overall status. Return the metric comparison summary. Stop if any core metric
differs. In the JSON artifact, fractional SQL decimal metrics are exact base-10
strings, integral decimal values are integers, and SQL nulls are JSON nulls; numeric
reconciliation occurs before this reporting conversion.

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

## Phase D - dashboard handoff

### D1. Export a manifest-bound snapshot

Where: WSL Bash, activated environment, project root.

```bash
python scripts/export_dashboard_data.py \
  --output-directory reports/exports/olist_snapshot_1
```

Purpose: create one non-overwritten CSV set and `manifest.json` for offline Power BI
use.

Expected pattern: eight CSV files plus a manifest containing row counts, SHA-256
hashes, the active snapshot/manifest identity, and validation run/status. Export
must fail before creating a directory when the current snapshot has no completed
Passed or Warning validation run.

The checked-in PBIP partitions point to `reports/exports/olist_snapshot_1`, matching
the operator's current snapshot. If that directory already exists and a new export
is required, use a new directory name and update all eight TMDL partition paths to
that one directory before refreshing Power BI. Never mix files from different
export directories.

### D2. Build and reconcile Power BI manually

Where: Power BI Desktop on Windows.

Action:

1. Open `powerbi/Olist_Delivery_Analysis.pbip` in Power BI Desktop.
2. Confirm all eight CSV partitions resolve to one export directory; update the
   TMDL paths if the local directory is not `reports/exports/olist_snapshot_1`.
3. Refresh the model and confirm **Overview**, **Regions & Sellers**, **Customer
   Experience**, and **Data Quality** load without broken visuals. On an unfiltered
   snapshot #1 report, verify the seven Overview cards show 99,441 total orders,
   96,470 eligible orders, 93.23% on-time rate, 6,534 late orders, and 12.56,
   10.22, and 23.10 days for average, median, and P90 delivery duration.
4. Import `powerbi/Olist_Delivery_Theme.json` if the light-canvas, navy, blue,
   green, amber, and red theme is not already applied. The native page tabs are the
   checked-in navigation. To add persistent navigation, use **Insert > Buttons >
   Navigator > Page navigator**, format it with the theme, copy it to every page,
   and test all four destinations. Confirm the review-distribution legend maps
   **Late** to red and **On Time** to green after theme application.
5. Verify that the state, seller, and category comparison measures suppress groups
   below `eligible_order_count >= 30`. If a visual has been rebuilt from raw summary
   columns, apply that threshold directly to the corresponding disconnected table;
   do not use the order-level threshold measure as a cross-table filter.
6. Confirm the interaction scope: Page-1 order-level slicers affect order cards,
   supporting exclusion cards, and exclusion visuals but not monthly snapshot
   charts. Confirm that the monthly eligible-order volume and tooltip counts are
   visible for interpreting low-volume months, and that delivery-status and duration
   exclusions remain separate cohorts. The reason bars must omit the blank eligible
   group and sum to their respective exclusion cards.
7. Confirm the local interaction scope: the customer-state slicer affects only state
   visuals; the seller-state slicer affects only the seller visual; and the product
   category slicer affects only category visuals. Check chart titles, descending
   late-rate sorting, percentage denominators, null display, review-score class
   behavior, Late/red and On Time/green colors, and the non-additive seller/category
   disclaimers. Confirm State Median Delivery Hours is blank on the total row and
   all Category Detail totals are blank rather than presented as global values.
8. If a reset action is needed, make one page-specific default bookmark at a time:
   clear that page's intended slicers; in **View > Bookmarks**, add a bookmark with
   **Data** and **Current page** enabled and **All visuals** selected; then add a
   blank button and set **Format visual > Action** to that page's bookmark. Test it
   after selecting every local slicer. It must restore only the intended page state;
   do not hand-edit action-button JSON or use one bookmark across disconnected
   summary-table scopes.
9. Follow `powerbi/README.md`, `data_model.md`, `measures.dax`, and
   `dashboard_specification.md`, then complete every item in `reconciliation.md`.

Expected pattern: exact count agreement, tolerance-bounded rates/durations, visible
denominators/exclusions, disconnected seller/category summaries, and no failed
critical validation. Return the reconciliation table and screenshots only after
checking that they contain no credentials or private local paths.

## Phase E - findings and version control

Populate `docs/FINDINGS.md` only from reconciled outputs. Update
`docs/IMPLEMENTATION_STATUS.md` with supplied execution evidence and limitations.
The operator, not Codex, decides when to commit and push. Never commit `.env`, raw
CSV files, generated inventory/validation/export artifacts, database files, or
credentials.
