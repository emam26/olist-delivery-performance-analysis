# Implementation status

Last updated: 2026-11-04

## Evidence categories

- **Implemented:** source files have been written and statically reviewed.
- **NOT RUN:** no execution evidence has been supplied.
- **Verified:** reserved for a check whose non-secret output the operator has
  supplied and whose scope is recorded.

## Current status

| Area | Implementation | Verification |
|---|---|---|
| Python project/configuration | Implemented | NOT RUN |
| Six-file dataset contracts | Implemented | NOT RUN against real CSV files |
| Offline inventory and hashes | Implemented | NOT RUN |
| SQL Server database objects | Implemented as ordered scripts | NOT DEPLOYED / NOT RUN |
| Transactional/idempotent loader | Implemented | Unit tests NOT RUN; live SQL load NOT RUN |
| Analytical and reporting views | Implemented | NOT RUN |
| SQL data-quality procedure | Implemented | NOT RUN |
| Independent metric reconciliation | Implemented | NOT RUN |
| Dashboard CSV export | Implemented | NOT RUN |
| Unit/integration-style tests | Implemented | NOT RUN |
| Power BI model/measures/specification | Documented | Desktop build and reconciliation NOT RUN |
| Empirical findings | Template only | No findings claimed |

## Implemented safeguards

- Local credentials and generated data are Git-ignored by default.
- ODBC values are escaped and the password is excluded from object representations.
- Source files are read but never rewritten.
- File inventory records byte count, row count, and SHA-256 identity.
- SQL loading is atomic per file and successful source hashes are idempotent.
- Failure provenance is written only after rollback.
- Staging preserves source text and row lineage.
- Delivery, duration, review, seller, and category grains are explicit.
- Missing values remain null; zero is not fabricated.
- SQL/Python/Power BI reconciliation is required before publication.

## Checks still required

1. Confirm the six manually acquired files and their exact headers/hashes.
2. Create a dedicated environment and install the project.
3. Run Ruff and the offline unit tests.
4. Create the dedicated SQL Server database and deploy numbered scripts.
5. Run SQL-marked integration checks against a dedicated test database.
6. Inventory and load the real CSV files.
7. Run logged SQL validation and independent metric reconciliation.
8. Export/import dashboard data and complete Power BI reconciliation.
9. Populate findings only from those verified artifacts.

No statement in this document implies that a command, SQL script, test, source
download, database connection, or dashboard refresh has been executed by Codex.
