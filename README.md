# Olist Delivery Performance Analysis

> Understanding delivery times, late orders, and customer reviews with SQL, Python, and Power BI.

![Status: Dashboard source prepared; Desktop verification pending](https://img.shields.io/badge/status-dashboard%20verification%20pending-yellow)
![Python](https://img.shields.io/badge/language-Python-3776AB?logo=python&logoColor=white)
![SQL Server](https://img.shields.io/badge/database-SQL%20Server-CC2927)
![Power BI](https://img.shields.io/badge/dashboard-Power%20BI-F2C811)

The project addresses a practical question: **where do delivery delays appear in Olist's historical orders, and how do those orders compare with on-time deliveries?** The implementation uses SQL and Python to prepare the data and Power BI to present the findings.

> [!NOTE]
> The Python, SQL Server, export, and reconciliation workflow has been exercised by
> the project operator for dataset snapshot #1. The editable Power BI source has
> not yet been reopened and visually validated in Power BI Desktop. No dashboard
> screenshot or causal business finding is claimed here.

## Purpose

The project is intended to help an analyst answer practical delivery questions: how often orders arrive after the estimated date, how delivery times vary across groups, and whether late orders are associated with different customer review scores.

It is a historical portfolio analysis, not work commissioned by Olist. The findings will describe the supplied data rather than current business performance.

## Data source

The source is the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), published by Olist on Kaggle. The publisher describes approximately 100,000 orders from 2016 to 2018.

Download the files from that source and retain its attribution and license
information. Raw dataset files are not bundled into the repository. Inventory,
load, snapshot, validation, and export artifacts record input filenames, hashes,
and row counts for reproducibility.

The required inputs are orders, order items, customers, sellers, products, and
reviews. Payment data is outside the current analytical scope.

## Questions to answer

- What share of delivered orders arrived on or before the estimated delivery date?
- What are the median and slower-end delivery times?
- How do delivery patterns vary by month and customer state?
- Which sellers or product categories have higher late-delivery rates, with enough orders for a useful comparison?
- How do review-score distributions differ between on-time and late deliveries?
- How many records are excluded from each metric, and why?

The analysis will report group sizes beside rates. Small groups will not be ranked as though they provide equally reliable evidence.

## Workflow

1. Download and inventory the original CSV files.
2. Load them into SQL Server staging tables without silently discarding rows.
3. Use Python and SQL to examine keys, missing values, timestamps, and unmatched references.
4. Create documented analytical tables and views at explicit grains.
5. Activate all six successful source batches as one immutable analytical snapshot.
6. Calculate delivery metrics independently in SQL and Python and reconcile them.
7. Export validated reporting data or import reporting views into Power BI.
8. Refresh the editable PBIP report, reconcile its unfiltered cards to the SQL and
   Python outputs, and capture screenshots only after the publication gate passes.
9. Publish findings only with exclusions, provenance, and limitations.

The core tools are Microsoft SQL Server, T-SQL, Python, pandas, Power BI, and Git.

## Implemented analytical model

| Table or view | Grain and purpose |
| --- | --- |
| Staging tables | Preserve the input records and loading provenance. |
| Order delivery table | One row per order, with delivery eligibility and derived durations. |
| Order-item table | One row per source order item. |
| Order-seller bridge | One row per distinct order and seller, for seller-level delivery comparisons. |
| Order-category bridge | One row per distinct order and category, if category comparisons are included. |
| Order-review view | At most one review record per order under a documented selection rule. |
| Reporting views | Monthly, regional, seller, and review summaries. |

Customer records will be joined using the order's customer key. The dataset's unique-customer identifier can support repeat-customer analysis later, but will not replace the order-specific join key.

Order items and reviews can multiply rows when joined directly to orders. The order-level delivery table will remain the basis of overall order counts. Seller and category summaries will document their separate grains and will not be summed to invent a global order total.

## Metric definitions

| Metric | Implemented definition |
| --- | --- |
| Eligible delivered order | An order marked delivered with valid actual and estimated delivery dates. |
| Late order | Actual delivery calendar date is after the estimated delivery calendar date. |
| On-time delivery rate | Eligible orders delivered on or before their estimated date divided by all eligible orders. |
| Purchase-to-delivery time | Elapsed time between purchase and actual customer delivery for valid, nonnegative intervals. |
| Days late | Positive calendar-date difference between actual and estimated delivery, calculated for late orders. |
| Review comparison | Review-score distributions for on-time and late orders with usable review data. |

Calendar dates will be used for late/on-time classification so a delivery later on the estimated day is not counted as a full late day. Elapsed delivery duration will be calculated separately.

Canceled, unavailable, undelivered, and incomplete orders will be reported separately rather than treated as zero-day deliveries. Missing dates and invalid intervals will have explicit exclusion reasons. Source timestamps without timezone information will not be labeled UTC.

If multiple reviews exist for one order, the analysis will first inspect them and document a deterministic selection rule. It will not assume the relationship is one-to-one.

## Power BI pages

- **Delivery overview:** eligible orders, on-time rate, delivery-time distribution, and monthly patterns.
- **Regions and sellers:** group sizes, late-delivery rates, delivery times, and
  non-additive category context.
- **Customer reviews:** review distributions alongside delivery outcomes.
- **Data quality:** missing fields, exclusions, unmatched records, and reconciliation totals.

The editable PBIP/PBIR source is in [`powerbi/`](powerbi/). It contains four
report pages, a TMDL model with the order-level and disconnected reporting tables,
and denominator-safe measures. Local CSV partitions and the `.pbix` deliverable
remain machine-specific artifacts; they are not portfolio evidence until the
operator refreshes and checks the report in Power BI Desktop.

## Verified snapshot baseline

The operator-reported snapshot #1 baseline contains 99,441 source orders and the
following reconciled overall metrics:

| Metric | Snapshot value |
| --- | ---: |
| Delivered orders | 96,478 |
| Delivery-eligible orders | 96,470 |
| On-time orders | 89,936 |
| Late orders | 6,534 |
| On-time delivery rate | 93.2269% |
| Late delivery rate | 6.7731% |
| Duration-eligible orders | 96,476 |
| Average delivery hours | 301.4089 |
| Median delivery hours | 245.2261 |
| P90 delivery hours | 554.3425 |
| P95 delivery hours | 702.6244 |
| Average days late | 10.6201 |

These are validation references supplied by the operator for snapshot #1, not
claims about current Olist operations. Re-run reconciliation after any refresh.

## Dashboard showcase

Real screenshots are intentionally not included yet. After Power BI Desktop
refresh and reconciliation, capture the four pages listed above using
[`docs/SCREENSHOT_CHECKLIST.md`](docs/SCREENSHOT_CHECKLIST.md), then add only the
resulting image paths here. Until that step, visual insights remain pending
analysis and should not be inferred from the snapshot totals alone.

Pending insight placeholders:

- `[Pending]` Compare monthly on-time performance after checking cohort sizes and
  excluded purchase months.
- `[Pending]` Compare state and seller rankings only after applying the minimum
  eligible-order threshold and disclosing non-additive attribution.
- `[Pending]` Describe review-score differences as associations, not causal effects.

## Validation and completion evidence

Before publishing findings, the project should demonstrate that:

- Input and staging counts reconcile.
- Keys are unique at each declared grain, or exceptions are explained.
- Joins do not inflate the overall order count.
- Every excluded order has an understandable reason.
- SQL results agree with independently checked sample calculations.
- Power BI totals agree with the underlying reporting views.
- A fresh run can reproduce the published outputs from the documented input files.

The operator-reported snapshot #1 evidence includes 446,802 source rows across six
datasets, a successfully activated snapshot, completed SQL data-quality validation,
and reconciled internal delivery KPI counts. Desktop report rendering and visual
filter behavior remain manual verification steps.

## Reproduce from a fresh checkout

```bash
cd /mnt/f/olist-delivery-performance-analysis
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
python -m pytest -q -m "not sqlserver"
```

Then acquire the six source files manually, create a non-overwriting inventory,
configure the ignored `.env`, and follow the SQL Server and Power BI phases in the
[manual runbook](docs/MANUAL_RUNBOOK.md). Database deployment, real-data loading,
metric reconciliation, export, and Power BI refresh/rendering remain
environment-dependent manual steps.

## Interpretation limits

A late order may contain items from multiple sellers. An order-level delivery timestamp does not establish which seller or carrier caused a delay.

Differences between groups and associations with review scores will be described without causal claims. No business adoption, cost saving, or improvement in delivery performance is currently established.

## Current setup

The reproducible Python, SQL Server, validation, and export layers have been
operator-verified for snapshot #1. The editable Power BI source is implemented but
its Desktop refresh, visual bindings, filters, and screenshots remain **NOT
VERIFIED**. Raw data, local exports, credentials, and generated database artifacts
remain outside version control.

Start with the [manual runbook](docs/MANUAL_RUNBOOK.md). The implemented design is
documented in [architecture](docs/ARCHITECTURE.md), [methodology](docs/METHODOLOGY.md),
[KPI definitions](docs/KPI_DEFINITIONS.md), and the
[implementation status](docs/IMPLEMENTATION_STATUS.md). Source CSV files,
credentials, generated reports, and database artifacts are intentionally excluded
from version control.

After all reconciliations are verified, use the
[screenshot checklist](docs/SCREENSHOT_CHECKLIST.md) before adding real dashboard
images to the portfolio.
