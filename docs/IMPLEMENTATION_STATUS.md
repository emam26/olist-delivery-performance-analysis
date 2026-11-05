# Implementation status

Last updated: 2026-11-05 (snapshot evidence supplied by the operator)

## Evidence categories

- **Implemented:** source files have been written and statically reviewed.
- **Pending re-verification:** a prior result exists, but an affected source file
  changed afterward.
- **NOT RUN:** no execution evidence has been supplied for this checkpoint.
- **Verified:** reserved for a check whose non-secret output the operator has
  supplied and whose scope is recorded.

## Current status

| Area | Implementation | Verification |
|---|---|---|
| Python 3.13.13 environment | Implemented | Verified by user before current edits |
| Project/development dependencies | Implemented | Installed successfully before current edits |
| Ruff lint and format | Current files edited | Operator reports `ruff check .` passed and formatting passed for 45 files |
| Offline unit tests | Offline suite configured; SQL Server test explicitly opt-in | Operator reports 72 passed, 1 deselected |
| Six-file dataset contracts and inventory | Implemented | Snapshot #1 artifacts record the six required files, row counts, and SHA-256 identities |
| SQL Server database objects and snapshot activation | Snapshot-aware ordered scripts implemented | Snapshot #1 is recorded as a complete six-file successful snapshot |
| Transactional/idempotent loader | Per-file transactions plus atomic snapshot activation implemented | Snapshot #1 load/provenance checks passed; a fresh idempotency rerun is not claimed here |
| Analytical and reporting views | Implemented | Snapshot #1 dashboard export records the source reporting views and output hashes |
| SQL data-quality procedure | Implemented | Validation run #1: Warning, no failed checks, three warnings |
| Independent metric reconciliation | Implemented | `reports/metric_reconciliation.json`: 15/15 checks passed |
| Dashboard CSV export | Validation-gated provenance export implemented | Snapshot #1: eight exported CSVs plus manifest |
| Power BI PBIP/PBIR model, measures, four-page layout, and theme | Portfolio refinements prepared | Operator reports Snapshot #1 refresh/render, reconciled Overview cards, and verified State/Category global benchmark totals; navigation, clear-slicer, and post-edit accessibility checks remain unverified |
| Portfolio screenshots | Four Snapshot #1 page captures are present under `docs/images/` and embedded in `README.md` | Content inspected as operator-produced artifacts; replacement captures require the screenshot checklist and privacy review |
| Local Power BI PDF | Operator reports `Olist_Delivery_Analysis.pdf` at the repository root | Local source artifact only; this assignment does not recommend adding it to version control |
| Empirical findings | Evidence-backed documentation | See `docs/ANALYSIS_FINDINGS.md`; Snapshot #1 Q7-Q9 results supplied by the operator |

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

1. Re-run Ruff and the offline unit tests after any future Python, test, or style
   change.
2. Run the opt-in SQL Server integration test only against a dedicated configured
   database if its environment is available.
3. Re-run Q7-Q9 in `sql/006_analysis_queries.sql` after any data or logic change;
   review and record replacement severity, promise-window, and concentration
   outputs before updating published findings.
4. Refresh Power BI after any data/model change and repeat the visual, local-slicer,
   colour, accessibility, and screenshot checks in `powerbi/reconciliation.md`.
5. Create native Desktop navigation and Clear all slicers controls only after their
   definitions have been runtime-verified; they are not currently a verified feature.
6. Obtain human approval of the current screenshots and any public PDF before adding
   or publishing those artifacts; verify they contain no local paths or sensitive
   metadata.

No statement in this document implies that a command, SQL script, test, source
download, database connection, or dashboard refresh has been executed by Codex.
