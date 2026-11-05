# Architecture

## Objective and boundary

The project creates a reproducible, descriptive analysis of delivery performance in
the public Olist e-commerce dataset. It does not operate an Olist production system,
predict future deliveries, or identify causal effects. Snapshot-specific evidence is
recorded in `docs/ANALYSIS_FINDINGS.md`; every new source, model, or visual change
still requires the relevant manual-runbook verification before it is treated as
observed runtime evidence.

## Data flow

```text
Manually acquired source CSV files
            |
            v
Offline inventory (headers, rows, hashes, structural checks)
            |
            v
SQL Server raw staging tables + per-file audit.load_batches
            |
            v
Six-file audit.dataset_snapshots activation
            |
            v
Typed/canonical analytical views
            |
            +--> independent Python metric reconciliation
            |
            v
Reporting views --> Power BI or immutable CSV export + manifest
```

The source CSV files are immutable inputs. Staging preserves source text and source
row numbers; analytical views perform type conversion and deterministic record
selection without rewriting the files.

## Components

### Python package

- `config.py` validates local paths and SQL Server settings and builds an
  escaped ODBC Driver 18 connection string.
- `datasets.py` defines the exact six-file source contract.
- `inventory.py` performs offline file-level and cross-file inspection.
- `load_data.py` verifies inventory hashes, loads one file atomically, reuses an
  already successful dataset/hash pair, and activates complete source snapshots.
- `metrics.py` independently defines delivery classification and duration metrics.
- `validation.py` combines logged SQL quality checks with cross-engine metric
  reconciliation.
- `export.py` holds the active snapshot stable, requires a completed non-failed SQL
  validation for it, and produces dashboard CSVs plus a provenance manifest without
  overwriting a prior export.
- `statistics.py` contains explicitly descriptive summary helpers.

### SQL Server

- `audit` records load and validation provenance.
- `stg` stores raw source values as text, plus technical lineage fields.
- `analytics` exposes typed, canonical order-, item-, review-, and bridge-level
  views.
- `reporting` exposes stable grains for dashboard use.

The SQL scripts are ordered and rerunnable. They do not silently drop deployed
objects or source records.

### Power BI

Power BI consumes stable reporting views or one manifest-bound CSV export. The
order-level detail table supports global cards and filters. Seller and category
tables remain disconnected because their distinct order attributions are
many-to-many and not additive to the overall order total.

## Transaction and recovery semantics

Each source file is one SQL transaction:

1. verify the inventory hash and record source identity;
2. insert raw rows with batch and row lineage;
3. recheck the file hash to detect a change during reading;
4. mark the load batch successful;
5. commit once.

An exception rolls back all staging and in-transaction audit changes for that
attempt. A separate, post-rollback transaction records safe failure provenance.
Retrying the same file is safe: only a successful `(dataset_name, source_sha256)`
pair causes an idempotent skip. A failed attempt does not masquerade as loaded data.

The six files are published as a second-level transaction boundary. The loader
computes a deterministic manifest hash from the six dataset names, filenames, row
counts, and source hashes. It can reuse successful per-file batches, but analytical
views switch only after all six batch mappings are committed to one successful
`audit.dataset_snapshots` row. If loading or activation fails, the previous complete
snapshot remains current. Validation runs are tied to a snapshot ID, and dashboard
export holds that snapshot stable for the duration of the read.

## Deterministic analytical semantics

- The main grain is one canonical order.
- Customer geography joins through `customer_id`; `customer_unique_id` is not the
  order foreign key.
- Duplicate source keys are retained in staging, surfaced by quality checks, and
  resolved deterministically only in analytical views.
- Review analysis selects one usable review per order using explicit timestamp and
  key ordering.
- Seller and product-category bridges contain distinct order-group pairs.
- Late status compares actual and estimated **calendar dates**.
- Duration eligibility is independent of delivery-status eligibility.
- Missing timestamps and scores remain null; they are never replaced by zero.

## Security and privacy

Secrets live only in a local ignored `.env`. Connection strings and passwords must
not be logged, printed, committed, or embedded in exports. SQL statements use
parameters for data values. Object identifiers are selected only from controlled
dataset/view specifications.

The public data still receives normal handling: preserve attribution, avoid
attempted re-identification, and expose only fields needed for the analysis.

## Threats to validity

- This public dataset reflects a historical marketplace sample, not current Olist
  operations or all Brazilian e-commerce.
- Missing delivery timestamps may be informative rather than random.
- Purchase month can confound seasonal, operational, and cohort effects.
- Seller/category attribution duplicates multi-group orders across groups.
- Review availability and review score are selected outcomes with multiple
  confounders.
- Geographical differences may reflect distance, logistics coverage, product mix,
  and customer composition.

Consequently, the supported claims are descriptive, conditional on the documented
cohorts and data-quality results.
