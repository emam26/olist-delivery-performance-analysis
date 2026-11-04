# Methodology

## Research questions

The implementation supports these descriptive questions:

1. What proportion of delivery-eligible orders arrived on or before the estimated
   delivery date?
2. How long did duration-eligible orders take from purchase to customer delivery?
3. How did those metrics vary by purchase month, customer state, attributed seller,
   and attributed product category?
4. How were selected review scores distributed across observed delivery outcomes?

The fourth question is associational. The design cannot isolate a causal effect of
delivery timing on reviews.

## Source and study population

The input is the Brazilian E-Commerce Public Dataset by Olist as manually acquired
from the source named in the repository README. Six files are required: orders,
order items, customers, sellers, products, and order reviews.

The full source population is retained in raw staging. Every reported metric states
its eligibility rule and denominator; records are not silently discarded.

## Units of analysis

The primary unit is the order (`order_id`). Order-item, seller, category, and review
data are collapsed or bridged explicitly before joining to the order-level outcome.
This prevents accidental fan-out from changing global order counts.

Customer geography is joined by `customer_id`, the foreign key in the order file.
`customer_unique_id` describes a customer across orders but is not used for that
join.

## Delivery classification

An order is delivery-status eligible when its normalized status is `delivered` and
both `order_delivered_customer_date` and `order_estimated_delivery_date` parse as
valid timestamps.

The comparison uses calendar dates:

- **On Time:** actual delivery date is less than or equal to estimated delivery
  date.
- **Late:** actual delivery date is greater than estimated delivery date.
- **Excluded:** either required timestamp is missing or invalid.

Comparing dates avoids classifying an order as late solely because it arrived later
in the day on the estimated date.

`days_early_or_late = actual delivery date - estimated delivery date`; negative
values indicate early delivery, zero indicates the estimated date, and positive
values indicate late delivery.

## Delivery duration

Duration eligibility is evaluated independently. An order is eligible when purchase
and customer-delivery timestamps parse and delivery is not earlier than purchase.

`delivery_duration_days` is the elapsed timestamp interval divided by 86,400
seconds. It is not rounded to calendar days. Average, median, P90, and P95 are
reported for this cohort. Invalid or negative intervals remain excluded and visible
through reason counts.

The SQL analytical and reporting views store the same duration as
`delivery_duration_hours`; Python and Power BI convert that field to fractional
days when presenting the documented day-based KPIs.

## Canonical records and duplicates

Raw staging retains every source row. Quality checks count duplicated natural keys.
Analytical views select a deterministic canonical row from the latest successful
load using source-row ordering. This makes reruns reproducible but does not make a
duplicate source key benign; unexpected duplication remains a validation finding.

For reviews, one usable record per order is selected by a documented ordering that
prioritizes a valid score and then the latest answer/creation timestamp with stable
key and source-row tie-breakers. All review rows remain available for audit.

## Seller and category attribution

Seller and category analyses use distinct bridges:

- one row per `(order_id, seller_id)`;
- one row per `(order_id, product_category_name)`.

An order with multiple sellers or categories contributes once to each applicable
group. Group rows therefore answer an attribution question and are not additive to
the global order population. Rankings apply a minimum eligible group size of 30 by
default; the threshold is configurable at presentation time and must be displayed.

## Review-score analysis

Review score is analyzed only when the selected score is an integer from 1 through
5. Outputs include group denominators, delivery metrics, and—where calculated—95%
Wilson intervals for binomial on-time proportions.

No causal language is warranted. Plausible confounders include product quality,
seller service, communication, price, customer expectations, geography, and the
decision to submit or update a review.

## Missingness and exclusions

Missing values remain null. In particular, absent delivery timestamps, review
scores, categories, and derived durations are never imputed as zero. Reports expose
all-order, eligible, and excluded counts so that changing denominators are visible.

Missingness should be profiled by order status and purchase period before drawing
substantive conclusions. A complete-case estimate may be biased when missingness is
related to fulfillment status or cohort age.

## Reconciliation and uncertainty

Core counts and metrics are calculated independently in Python and SQL Server.
Counts must match exactly; floating-point values must match within a documented
tolerance. Power BI must then reconcile to the validated SQL/Python outputs.

Percentiles use a continuous interpolation definition (`PERCENTILE_CONT` in SQL).
Rates should be accompanied by denominators. Small group rankings are suppressed or
flagged, and confidence intervals should be considered when comparisons are close.

## Reproducibility boundary

Reproducibility requires the exact source-file hashes, code version, SQL object
definitions, load-batch IDs, validation run ID, and export manifest. The repository
does not contain the source CSV data, credentials, generated reports, or a fabricated
result narrative.
