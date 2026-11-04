# Data-quality framework

## Principles

Validation is a publication gate, not a cosmetic report. The pipeline preserves raw
rows, records source hashes and row lineage, separates critical failures from
warnings, and does not silently repair ambiguous source data.

Every finding records a stable check ID, severity, status, observed value, expected
condition, and actionable details. A failed critical check blocks downstream claims.

## File-level checks

The offline inventory evaluates each required CSV before any SQL connection:

- file presence and readability;
- exact header contract;
- byte count and SHA-256 hash;
- parsed data-row count;
- malformed row count;
- blank required identifiers and duplicate natural keys;
- timestamp parseability for relevant columns;
- negative purchase-to-delivery intervals;
- cross-file orphans for orders, customers, sellers, and products;
- review multiplicity, orders without items, and multi-seller/category attribution.

Inventory output is written to a new path and is not silently overwritten. Source
files are never modified.

The report separates structural loadability from analytical quality status.
Missing files, header mismatch, malformed CSV structure, and empty required files
are not loadable. A structurally readable file with duplicate identifiers, invalid
timestamps, negative intervals, or relationship defects may be staged so its raw
rows remain auditable, but its failed quality findings still block validation,
export, and publication.

## SQL checks

`audit.usp_run_validation` logs and returns checks covering:

- successful load availability and batch/source counts;
- complete six-file snapshot identity and batch/hash mappings;
- raw staging row counts;
- duplicate natural keys;
- order-item/customer/seller/product/review orphans;
- invalid required timestamp text;
- explicit delivery-status and duration exclusion populations;
- negative delivery intervals;
- orders without items;
- multiple source reviews per order and deterministic usable-review selection;
- missing/invalid review scores and multi-seller/category attribution counts;
- uniqueness of canonical order and bridge grains;
- delivery cohort reconciliation and null semantics;
- consistency between analytical and reporting outputs.

The procedure records a validation run even when a validation execution fails, when
SQL Server permits the failure record to be committed safely.

## Severity policy

| Severity | Meaning | Required action |
|---|---|---|
| Critical | Grain, relationship, parsing, or reconciliation failure can invalidate KPIs | Stop; diagnose before reporting |
| Warning | Data limitation or unusual pattern may affect interpretation | Investigate and disclose |
| Information | Provenance or descriptive context | Record for reproducibility |

The expected source may legitimately contain missing optional values. Missingness is
not automatically a failure; hidden denominator changes are.

## Independent metric validation

Python computes the core order metrics from independently parsed records. SQL
computes the same metrics from analytical views. Exact counts and absolute-
tolerance-bounded continuous statistics are compared with relative tolerance set to
zero. This catches semantic drift that a single-engine test would miss.

Power BI is a third reconciliation layer. It must match validated order counts and
rates before publication.

## Tests versus empirical verification

Unit tests use small synthetic records to exercise definitions and failure modes.
They do not demonstrate that the real source data are clean or that SQL Server and
Power BI are configured correctly. Those are separate manual checks in the runbook.

## Handling a failed check

1. Stop dependent loading, export, or publication work.
2. Preserve the inventory, batch ID, validation run ID, and safe error text.
3. Identify whether the issue is source content, file acquisition, configuration,
   code semantics, or SQL deployment.
4. Correct the narrowest root cause without editing raw source files.
5. rerun from the earliest invalidated step and retain both pieces of provenance.

Never suppress a failing check merely to produce a dashboard.
