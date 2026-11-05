# Dashboard specification

The dashboard is an analytical communication layer over validated reporting views.
It must not introduce new KPI definitions, silently alter denominators, or present
observational associations as causal effects.

The PBIR source contains the core four-page layout, order-level KPI cards, monthly
trend and volume visuals, state/seller/category/review comparisons, and quality and
provenance tables. Power BI Desktop is still required to verify bindings, refresh
the imported partitions, and complete optional histogram and drill-through
enhancements.

## Page 1 - Delivery overview

- Cards: delivered orders, eligible orders, on-time rate, late rate, average
  delivery days, median delivery days, and P90 delivery days.
- Monthly line chart: purchase month on the x-axis; on-time and late rates on a
  shared percentage axis; eligible, excluded, and duration-eligible counts in the
  tooltip. This is a disconnected snapshot summary and is not changed by the
  order-level slicers below.
- Delivery-duration histogram filtered to `is_duration_eligible = 1` (manual
  enhancement; percentile cards and exclusion bars are already specified in PBIR).
- Separate exclusion bars for `delivery_exclusion_reason` and
  `duration_exclusion_reason`; do not conflate the two cohorts.
- Slicers: purchase month, customer state, order status.
- Information panel: metric eligibility definitions, data refresh timestamp, and
  validation status.

The cards must use the `order_delivery` measures. The monthly chart may use the monthly
reporting view only after reconciliation.

## Page 2 - Regions and sellers

- Ranked bar chart: customer state by late-delivery rate.
- Scatter plot: eligible order count versus median delivery days; state as detail.
- Table: state, all orders, eligible orders, on-time rate, late rate, median, P90,
  and excluded orders.
- Comparison measures return values only when eligible orders meet the documented
  minimum group size. Verify the resulting visual-level behavior in Desktop; if a
  visual is rebuilt from raw columns, apply `eligible_order_count >= 30` directly
  to that disconnected summary table.

Use customer state, not seller state, for the regional comparison. Add a seller
scatter and table from `Seller Delivery`, with eligible count, rate, median, and P90
in the tooltip. Add a compact category table from `Category Delivery` and retain
`(Missing category)`. The PBIR comparison measures apply
`eligible_order_count >= 30` separately to each ranked summary and the selected
threshold remains visible.

Display: "Multi-seller and multi-category orders are attributed once to every
applicable group; group rows are not additive to the global order total."

## Page 3 - Customer reviews

- Cards from `order_delivery`: reviewed orders, orders without a usable review, and
  average selected review score.
- Distribution of selected review scores using distinct reviewed orders.
- On-time rate by selected review score, with eligible and reviewed denominators in
  every tooltip (manual tooltip enhancement; the PBIR source includes the review
  distribution visual).
- Late/on-time score comparison from `Review Delivery`. Treat
  `orders_without_usable_review` as a class-level value and never sum its repeated
  value over score rows.
- Persistent subtitle: "Descriptive association; no causal interpretation."

Product quality, service, geography, expectations, and review-selection effects are
plausible confounders.

## Page 4 - Data quality

- Cards: validation status, failed and warning check counts, active snapshot ID,
  validation run ID, and loaded source rows.
- Validation table from `Data Quality`: check ID, check status, observed value,
  expected value, and message.
- Source table from `Source Provenance`: dataset, filename, expected and inserted
  rows, source hash, batch ID, and completion time.
- Exclusion indicators from `order_delivery`: delivery-status excluded, duration
  excluded, and orders without a usable review.
- Methodology panel with KPI definitions and the source-manifest hash.

Any failed check blocks publication. Warnings must be investigated and disclosed.

## Interaction and accessibility requirements

- Use the same on-time and late colors on every page and do not rely on color alone.
- Show denominators in labels or tooltips for every percentage.
- Use descriptive titles that state the grain and time basis.
- Disable cross-highlighting that combines disconnected aggregate tables.
- Include alt text, sufficient contrast, logical tab order, and readable number
  formats.
- Preserve blanks for unavailable metrics; never format missing values as zero.
