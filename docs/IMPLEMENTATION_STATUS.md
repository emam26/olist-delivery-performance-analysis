# Implementation status

Last updated: 2026-11-04

## Evidence categories

- **Implemented:** source files have been written and statically reviewed.
- **Pending re-verification:** a prior result exists, but code changed afterward.
- **NOT RUN:** no execution evidence has been supplied for this checkpoint.
- **Verified:** reserved for a check whose non-secret output the operator has
  supplied and whose scope is recorded.

## Current status

| Area | Implementation | Verification |
|---|---|---|
| Python 3.13.13 environment | Implemented | Verified by user before current edits |
| Project/development dependencies | Implemented | Installed successfully before current edits |
| Ruff lint and format | Current files edited | Pending re-verification; prior checks passed |
| Offline unit tests | Tests added/edited | Pending re-verification; prior result was 48 passed |
| SQL Server integration test | Explicitly opt-in | Prior offline run deselected one SQL Server test; live test NOT RUN |
| Six-file dataset contracts | Implemented | NOT RUN against real CSV files |
| Offline inventory and hashes | Implemented | NOT RUN |
| SQL Server database objects | Snapshot-aware ordered scripts implemented | NOT DEPLOYED / NOT RUN |
| Transactional/idempotent loader | Per-file transactions plus atomic snapshot activation implemented | Pending unit re-verification; live SQL load NOT RUN |
| Analytical and reporting views | Implemented | NOT RUN |
| SQL data-quality procedure | Implemented | NOT RUN |
| Independent metric reconciliation | Implemented | NOT RUN |
| Dashboard CSV export | Validation-gated provenance export implemented | NOT RUN |
| Power BI model/measures/four-page specification | Documented | Desktop build and reconciliation NOT RUN |
| Empirical findings | Template only | No findings claimed |

## Implemented safeguards

- Local credentials and generated data are Git-ignored by default.
- ODBC values are escaped and the password is excluded from object representations.
- Source files are read but never rewritten.
- File inventory records byte count, row count, and SHA-256 identity.
- SQL loading is atomic per file and successful source hashes are idempotent.
- A changed file set is not visible until all six source hashes form one successful
  snapshot; a failed refresh leaves the prior snapshot active.
- Failure provenance is written only after rollback.
- Staging preserves source text and row lineage.
- Delivery, duration, review, seller, and category grains are explicit.
- Missing values remain null; zero is not fabricated.
- SQL/Python/Power BI reconciliation is required before publication.

## Checks still required

1. Confirm the six manually acquired files and their exact headers/hashes.
2. Re-run Ruff and the offline unit tests after the current edits.
3. Create the dedicated SQL Server database and deploy numbered scripts.
4. Run SQL-marked integration checks against a dedicated test database.
5. Inventory and load the real CSV files; record the active snapshot manifest.
6. Run logged SQL validation and independent metric reconciliation.
7. Export/import dashboard data and complete Power BI reconciliation.
8. Populate findings only from those verified artifacts.

No statement in this document implies that a command, SQL script, test, source
download, database connection, or dashboard refresh has been executed by Codex.
