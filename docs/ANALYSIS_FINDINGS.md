# Olist delivery performance: analysis findings

## Evidence status

This is a descriptive analysis of a historical Olist snapshot, not a view of
current operations. It separates three kinds of evidence:

| Status | Meaning in this document |
| --- | --- |
| **Reconciled** | A value is in the snapshot artifacts and the independent Python-to-SQL metric reconciliation recorded a passing result. |
| **Materialized snapshot evidence** | A value is present in the manifest-bound dashboard export, but no new calculation was run for this documentation update. |
| **Pending execution** | The query is implemented and reviewable, but its output has not been supplied. No numerical finding is claimed. |

Snapshot #1 was exported on 2026-11-05 with dataset snapshot ID `1`, validation
run ID `1`, and source-manifest SHA-256
`5529a8b33870405d2947fe7dbbe1f21537803e13eefb2a190411f6672692b0b4`.
The export manifest records eight CSV outputs and their hashes. Generated `reports/`
artifacts are intentionally ignored, so the paths below are evidence locations in a
prepared checkout rather than public repository links.

## Executive summary

- **93.23%** of **96,470** delivery-eligible orders arrived on or before the
  estimated delivery calendar date; **6,534** eligible orders (**6.77%**) arrived
  later. These counts and rates are reconciled between Python and SQL.
- The delivery-time distribution has a meaningful upper tail: the reconciled median
  is **10.22 days** (245.23 hours) while the P90 is **23.10 days** (554.34 hours).
  This is descriptive evidence to monitor slow deliveries, not evidence of a cause.
- Late deliveries are often more than marginal misses: among 6,534 late orders, the
  median delay is **7 calendar days** and the P90 is **22 calendar days**.
- Estimated windows average **23.74 days**, versus **12.56 days** average actual
  duration. The relationship varies by promise-window band and is descriptive, not
  proof of an optimal or causal promise-date policy.
- The snapshot preserves exclusions rather than converting incomplete records to
  zero: **2,971** orders are excluded from delivery-status classification and
  **2,965** from duration statistics.
- In the selected-review, delivery-eligible cohort, the late group has **3,431**
  score-1 reviews and **1,055** score-5 reviews; the on-time group has **5,920**
  score-1 and **55,693** score-5 reviews. This is a strong descriptive difference,
  not a causal estimate of the effect of delivery timing on satisfaction.
- State, seller, and category comparisons are available in the export, but no group
  is treated as a causal explanation. SP and RJ together account for **50.73%** of
  distinct late orders, while seller comparisons remain non-additive at the
  order-seller bridge grain.

## Data and analysis population

### Business question

What do the validated historical Olist records show about delivery timeliness,
delivery duration, and associated customer-review patterns, while keeping
incomplete observations and non-additive group attribution visible?

### Source population and grain

Six source files contribute **446,802** staged records. The primary analytical
grain is one canonical order (`99,441` rows); order items, sellers, categories, and
reviews are separate grains.

| Source | Rows | Role |
| --- | ---: | --- |
| Orders | 99,441 | Canonical order and delivery timestamps |
| Order items | 112,650 | Seller/category attribution bridge input |
| Customers | 99,441 | Order-specific customer geography |
| Sellers | 3,095 | Seller context |
| Products | 32,951 | Product-category context |
| Reviews | 99,224 | Selected-review comparison input |

The source rows and hashes are recorded in
`reports/exports/olist_snapshot_1/source_provenance.csv` and the manifest. The
calculation rules are in
[`metrics.py`](../src/olist_delivery/metrics.py) and
[`003_create_analytical_views.sql`](../sql/003_create_analytical_views.sql).

### Cohorts and definitions

| Cohort or metric | Definition | Snapshot #1 |
| --- | --- | ---: |
| All orders | One canonical order | 99,441 |
| Delivered orders | Source status normalizes to `delivered` | 96,478 |
| Delivery eligible | Delivered, with actual and estimated delivery timestamps | 96,470 |
| On time | Eligible and actual calendar date is on/before estimated calendar date | 89,936 |
| Late | Eligible and actual calendar date is after estimated calendar date | 6,534 |
| Duration eligible | Valid, nonnegative purchase-to-actual-delivery interval | 96,476 |

The delivery-status and duration cohorts are deliberately separate. An order may
have a usable duration but lack an estimated date, so no duration metric is silently
substituted for a delivery-status denominator.

## Overall delivery performance

### Business question

How reliably did the eligible historical orders meet the estimated delivery date,
and how long did valid delivery intervals take?

### Reconciled results

| Metric | Value |
| --- | ---: |
| On-time delivery rate | 93.23% |
| Late delivery rate | 6.77% |
| Average delivery duration | 301.41 hours / 12.56 days |
| Median delivery duration | 245.23 hours / 10.22 days |
| P90 delivery duration | 554.34 hours / 23.10 days |
| P95 delivery duration | 702.62 hours / 29.28 days |
| Average days late, among late orders | 10.62 calendar days |
| Delivery-status exclusions | 2,971 orders |
| Duration exclusions | 2,965 orders |

**Interpretation.** The median-to-P90 gap shows that a headline average alone would
understate the slower portion of valid delivery intervals. The two exclusion counts
must accompany any presentation of rates or durations because they refer to
different eligibility conditions.

**Recommendation.** Use the order-level on-time rate and the duration distribution
together in operational review. Investigate the severe-delay tail after the
severity distribution is generated; do not set a seller or geography target from an
overall average.

**Evidence.** `reports/metric_reconciliation.json` reports all 15 independent
Python-to-SQL checks as `Passed`; `reports/exports/olist_snapshot_1/order_delivery.csv`
is the one-row-per-order dashboard export.

## Trends over time

### Business question

Does the purchase-month series provide stable evidence of changing delivery
performance?

`monthly_delivery.csv` materializes **25** purchase-month cohorts, from September
2016 through October 2018. The two final cohorts contain 16 and 4 source orders,
respectively, and neither has delivery-eligible orders. They are therefore not
rate-comparable with mature cohorts and should not drive a trend narrative.

The monthly table supplies eligible counts, on-time/late counts and rates, and
duration percentiles. No trend slope, seasonal explanation, or best/worst month is
asserted here because that would require a reviewed cohort-level output rather than
a visual impression.

**Recommendation.** In the Overview page, show monthly eligible volume alongside
the rate and flag immature/zero-denominator months. Treat purchase month as a
historical cohort, not as proof of a seasonal mechanism.

**Evidence.** `reports/exports/olist_snapshot_1/monthly_delivery.csv`; the
purchase-month definition is in
[`004_create_reporting_views.sql`](../sql/004_create_reporting_views.sql).

## Regional delivery performance

### Business question

Where do customer-state late rates and late-order volumes warrant further review?

The snapshot provides **27** customer-state rows with mutually exclusive customer
geography, eligible counts, late counts, late rates, and duration statistics. The
dashboard and analysis query apply a minimum eligible-group size of 30 before
comparison. No state ranking is published here without executing and reviewing the
concentration query.

**Recommendation.** Prioritise state follow-up only where both the eligible-volume
denominator and late-order volume justify attention. A high percentage on a small
cohort is not enough evidence for an intervention.

**Limitations.** State is customer geography, not a direct measure of carrier,
distance, product mix, or seller performance.

**Evidence.** `reports/exports/olist_snapshot_1/regional_delivery.csv`;
[`006_analysis_queries.sql`](../sql/006_analysis_queries.sql), Q9 state query
(pending execution).

## Seller performance

### Business question

Which sufficiently large seller-attributed cohorts combine high late volume, late
rate, or delay severity?

The export contains **3,095** distinct seller rows. Each row is a distinct
order-seller attribution, not a partition of orders: **1,278** source orders have
multiple sellers. Seller counts and shares must therefore never be summed into the
global distinct-order total.

**Recommendation.** Use the 30-eligible-order threshold, show the eligible
denominator with the rate, and treat a seller result as a screening signal for
operational investigation rather than evidence that the seller caused the delay.

**Limitations.** An order-level customer-delivery timestamp cannot assign delay to a
specific seller, carrier, or hand-off.

**Evidence.** `reports/exports/olist_snapshot_1/seller_delivery.csv`; the seller
severity and attributed-concentration queries in
[`006_analysis_queries.sql`](../sql/006_analysis_queries.sql) are pending
execution.

## Product category performance

### Business question

Which product-category-attributed cohorts should be compared after enforcing a
minimum denominator?

The export contains **74** categories. A distinct order-category bridge retains
the explicit `(Missing category)` label; **786** orders span multiple categories,
so category rows are non-additive. The State and Category Detail tables display a
global distinct-order benchmark in their total rows rather than a sum or average of
visible summary rows.

**Recommendation.** Use category views to generate product-mix hypotheses, then
validate them with order-, seller-, and geography-aware follow-up. Do not report a
category-table total as a global late rate.

**Limitations.** Product category is a coarse source label. It neither identifies a
shipment's handling requirements nor isolates a causal driver.

**Evidence.** `reports/exports/olist_snapshot_1/category_delivery.csv`,
`reports/sql_validation.json`, and the documented model measures in
[`powerbi/measures.dax`](../powerbi/measures.dax).

## Customer reviews and delivery outcomes

### Business question

How do selected review-score distributions differ between eligible on-time and
late orders?

The review export uses one deterministic usable review per eligible order. It
records 153 late orders and 493 on-time orders without a usable review; those
class-level counts repeat across score rows and must not be summed. Among orders
with a usable selected review, the distribution is materially different:

| Delivery class | Score 1 reviews | Score 5 reviews |
| --- | ---: | ---: |
| Late | 3,431 of 6,381 reviewed (53.77%) | 1,055 |
| On Time | 5,920 of 89,443 reviewed (6.62%) | 55,693 |

**Scope note.** The Customer Experience screenshot's `Orders Without Usable Review`
card is an all-order measure (768 orders). It is not the 646-order
delivery-eligible review-comparison exclusion above, and neither count is the
broader multi-review validation population.

**Interpretation.** The selected-review distributions are associated with delivery
outcome in this historical cohort. They do not show that delivery timing caused a
review score: product quality, price, customer expectations, service recovery, and
review availability are plausible confounders.

**Recommendation.** Use the review chart as a diagnostic prompt. Any intervention
should be evaluated prospectively with appropriate controls rather than inferred
from this descriptive comparison.

**Limitations.** In the delivery-eligible review cohort, 525 orders have multiple
source reviews; the model chooses one usable review deterministically, preserving a
stable order-level grain but not all possible customer feedback. The broader
validation check reports 547 multi-review orders across its own population, so the
two counts must not be substituted for each other.

**Evidence.** `reports/exports/olist_snapshot_1/review_delivery.csv`; review
selection is defined in
[`003_create_analytical_views.sql`](../sql/003_create_analytical_views.sql).

## Delay severity

### Business question

How severe are late deliveries beyond their overall 6.77% frequency, and do
severity patterns differ across adequately sized groups?

Q7 was executed against Snapshot #1 at the late, delivery-eligible order grain:

| Severity metric | Result |
| --- | ---: |
| Late orders | 6,534 |
| Average days late | 10.620140 |
| Median days late | 7 |
| P90 days late | 22 |

The median and P90 show that the late cohort contains more than same-day misses;
the tail remains materially longer than a typical late delivery. The full
severity-band breakdown was not supplied, so no band percentages are reported.

Selected state comparisons retain both volume and rate:

| Customer state | Late orders | Late rate | Average days late |
| --- | ---: | ---: | ---: |
| SP | 1,820 | 4.49% | 8.332967 |
| RJ | 1,495 | 12.11% | 13.522408 |
| AL | 85 | 21.41% | 9.541176 |

**Interpretation.** SP has the largest selected late volume, while RJ combines
substantial late volume with a higher late rate and longer average delay. AL's high
rate is visible but should not be treated as a stable priority ranking without its
denominator and uncertainty context.

**Recommendation.** Focus remediation on combinations of high late volume and high
delay severity—not only a high late rate. The query's seller comparisons remain
screening evidence, not causal attribution.

## Estimated-date reliability

### Business question

Were estimated delivery windows calibrated relative to actual delivery timing?

The core model compares actual and estimated **calendar dates** for the canonical
on-time/late classification. Q8's promise-window population contains 96,470 orders
with valid delivery, duration, and nonnegative purchase-to-estimated windows:

| Promise-window metric | Result |
| --- | ---: |
| Average promised window | 23.736342 days |
| Median promised window | 23.2309 days |
| P90 promised window | 34.2870 days |
| Average actual delivery duration | 12.558217 days |

The calendar-date outcome counts reconcile to the promise-window population:

| Outcome relative to estimated calendar date | Orders |
| --- | ---: |
| Before estimate | 88,644 |
| On estimated date | 1,292 |
| After estimated date | 6,534 |
| **Total** | **96,470** |

| Promised-window band | Late orders / eligible orders | Late rate |
| --- | ---: | ---: |
| <3 days | 49 / 191 | 25.65% |
| 3 to <7 days | 164 / 1,069 | 15.34% |
| 7 to <14 days | 532 / 10,742 | 4.95% |
| 14 to <21 days | 1,730 / 23,304 | 7.42% |
| 21+ days | 4,059 / 61,164 | 6.64% |

**Interpretation.** The smallest promise-window cohorts have the highest observed
late rates, but the pattern is not monotonic across all bands. This historical
descriptive comparison neither proves causal calibration effects nor identifies an
optimal promised window.

**Recommendation.** Review short-window operational cohorts first, then test any
promise-date policy change prospectively with product, geography, and service
factors considered.

## Concentration and prioritisation

### Business question

What share of late volume sits in states or seller-attributed cohorts, while
balancing volume and rate?

Q9 confirms meaningful late-volume concentration at the distinct customer-state
order grain:

| Customer state | Late orders | Share of 6,534 global late orders | Late rate |
| --- | ---: | ---: | ---: |
| SP | 1,820 | 27.85% | 4.49% |
| RJ | 1,495 | 22.88% | 12.11% |
| **SP + RJ** | **3,315** | **50.73%** | — |

The five states with the most late orders account for **69.71%** of distinct global
late orders. SP and RJ therefore merit joint volume-and-rate investigation, but the
data do not identify whether geography, logistics coverage, product mix, seller
mix, or another factor produced the difference.

Seller results use a different, explicitly non-additive grain:

| Seller-attribution result | Result |
| --- | ---: |
| Qualified sellers (at least 30 eligible attributed orders) | 627 |
| Qualified sellers with at least one late attribution | 583 |
| Late seller attributions across qualified sellers | 5,485 |
| Late attributions in the top 10 qualified sellers | 1,027 (18.72%) |
| Seller prefix `4a3ca931` | 1,772 eligible; 172 late; 9.71% late rate |
| Seller prefix `06a2c3af` | 389 eligible; 74 late; 19.02% late rate |

The 5,485 attributed late orders are **not** the global denominator of 6,534
distinct late orders. A multi-seller order can contribute an attribution to more
than one seller, so seller counts, shares, and top-10 concentration cannot be added
or compared as a distinct-order partition.

**Recommendation.** Build a prioritisation list from late volume, eligible
denominator, rate, and severity; then investigate logistics, product mix, and seller
processes rather than treating a state or seller result as causal attribution.

## Data quality and limitations

Snapshot #1's SQL validation contains **36 checks: 33 Passed and 3 Warning**, with
no failed critical check. Its dashboard status is therefore **Warning**, not
failure. The three warning checks presented to the dashboard are:

- 610 products have a missing category label; the category bridge retains an
  explicit missing-category group.
- The broader validation check identifies 547 orders with multiple source reviews;
  one usable review is selected deterministically for the reporting comparison. In
  the narrower delivery-eligible review cohort, the corresponding count is 525.
- 775 orders have no items; they remain in global order metrics but cannot receive
  seller/category attribution.

The wider validation artifact also records source missingness, including 2,965
orders without actual-delivery timestamps. Missing values remain null, never zero.
The snapshot's critical grain, relationship, parsing, cohort-reconciliation, and
Python-to-SQL KPI checks passed in the supplied artifacts.

Additional limits:

- The dataset is historical and public; it is not a current Olist operating feed.
- Customer state is descriptive geography, not a distance or carrier variable.
- Seller/category attribution can repeat multi-group orders.
- Review availability, selection, and score are confounded outcomes.
- The project evaluates associations and distributions, not interventions or
  financial impact.

## Actionable, evidence-bounded recommendations

1. **Operate on both timeliness and tail duration.** Keep the eligible-order rate
   alongside median and P90 duration; the verified median/P90 gap warrants an
   explicit slow-delivery watchlist.
2. **Protect the denominator.** Continue publishing delivery-status and duration
   exclusions separately. Do not turn incomplete timestamps into on-time or
   zero-day records.
3. **Prioritise with Q7–Q9 evidence.** Start with state late volume and rate
   together (notably SP and RJ), and retain the non-additivity warning in every
   seller/category output.
4. **Treat review differences as diagnostic evidence.** Investigate the large
   descriptive distribution difference, then validate candidate changes with a
   prospective evaluation that controls for product, geography, and service factors.
5. **Review promise windows only after calibration output.** Q8 can motivate a
   date-promise review, but the present baseline alone does not establish
   miscalibration.

## Evidence and reproducibility references

| Evidence | Location and use |
| --- | --- |
| Core reconciliation | `reports/metric_reconciliation.json` — 15 Python-to-SQL KPI checks; status `passed` |
| Snapshot validation | `reports/sql_validation.json` and `reports/sql_validation.md` — validation run #1 and quality checks |
| Export identity | `reports/exports/olist_snapshot_1/manifest.json` — snapshot, validation, file rows, hashes, source views |
| Order-level detail | `reports/exports/olist_snapshot_1/order_delivery.csv` — one row per canonical order |
| Summary outputs | `monthly_delivery.csv`, `regional_delivery.csv`, `seller_delivery.csv`, `category_delivery.csv`, and `review_delivery.csv` in the same export directory |
| Metric semantics | [`src/olist_delivery/metrics.py`](../src/olist_delivery/metrics.py) and [`docs/KPI_DEFINITIONS.md`](KPI_DEFINITIONS.md) |
| SQL semantics and further analysis | [`sql/003_create_analytical_views.sql`](../sql/003_create_analytical_views.sql), [`sql/004_create_reporting_views.sql`](../sql/004_create_reporting_views.sql), and [`sql/006_analysis_queries.sql`](../sql/006_analysis_queries.sql); Snapshot #1 Q7-Q9 results supplied by the operator |
| Dashboard scope | [`powerbi/data_model.md`](../powerbi/data_model.md), [`powerbi/dashboard_specification.md`](../powerbi/dashboard_specification.md), and [`powerbi/reconciliation.md`](../powerbi/reconciliation.md) |

### Reproduce or extend the snapshot

Use the full [manual runbook](MANUAL_RUNBOOK.md) for environment setup, inventory,
loading, and SQL deployment. After a fresh successful load, write new artifacts to
new paths because the scripts intentionally refuse overwrites:

```bash
python scripts/validate_data.py \
  --inventory reports/inventory/olist_source_inventory.json \
  --sqlserver \
  --json-output reports/sql_validation_recheck.json \
  --markdown-output reports/sql_validation_recheck.md

python scripts/validate_metrics.py \
  --orders-csv data/raw/olist_orders_dataset.csv \
  --sqlserver \
  --json-output reports/metric_reconciliation_recheck.json

python scripts/export_dashboard_data.py \
  --output-directory reports/exports/olist_snapshot_recheck
```

The supplied Snapshot #1 Q7-Q9 results are integrated above. Re-run the read-only
Q7, Q8, and Q9 blocks in `sql/006_analysis_queries.sql` after any data or logic
change, connected to the validated `OlistDeliveryAnalytics` database. Record the
active snapshot ID, manifest hash, validation run ID, and query output with any
published ranking.
