# Dashboard specification

The dashboard is an analytical communication layer over validated reporting views.
It must not introduce new KPI definitions, silently alter denominators, or present
observational associations as causal effects.

## Page 1 — Executive overview

- Cards: eligible orders, on-time rate, late rate, average delivery days, median
  delivery days, P90 delivery days.
- Monthly line chart: purchase month on the x-axis; on-time and late rates on a
  shared percentage axis; eligible order count in the tooltip.
- Exclusion bar: order counts by `exclusion_reason`.
- Slicers: purchase date, customer state, order status.
- Information panel: metric eligibility definitions, data refresh timestamp, and
  validation status.

The cards must use the order-level measures. The monthly chart may use the monthly
reporting view only after reconciliation.

## Page 2 — Geographic performance

- Ranked bar chart: customer state by on-time rate.
- Scatter plot: eligible order count versus median delivery days; state as detail.
- Table: state, all orders, eligible orders, on-time rate, late rate, median, P90,
  and excluded orders.
- Visual filter: eligible orders at least the documented minimum group size.

Use customer state, not seller state, and label that distinction visibly.

## Page 3 — Seller performance

- Ranked table and scatter plot from `Seller Delivery`.
- Include seller ID, attributed order count, eligible count, on-time rate, median,
  and P90.
- Apply the minimum group-size filter before ranking.
- Display: "Orders with multiple sellers are attributed to each distinct seller;
  seller rows are not additive to the overall order total."

Do not sum seller-level order counts into an executive total.

## Page 4 — Product category performance

- Ranked bar chart and detail table from `Category Delivery`.
- Include an explicit `(Missing category)` label instead of hiding null categories.
- Apply the minimum group-size filter before ranking.
- Display the same non-additivity warning for multi-category orders.

## Page 5 — Reviews and delivery

- Distribution of selected review scores.
- On-time rate and median delivery days by review score.
- Eligible and reviewed denominators in every tooltip.
- Optional Wilson confidence intervals where supplied by a validated export.
- Persistent subtitle: "Descriptive association; no causal interpretation."

Do not imply that late delivery alone caused a low review score. Product quality,
service, customer expectations, and review-selection effects are plausible
confounders.

## Page 6 — Data quality and methodology

- Validation run ID, execution UTC timestamp, and status.
- Table of check ID, severity, status, observed value, expected value, and details.
- Source-file inventory counts and hashes if included in the import notes.
- Metric definitions and exclusion rules.

Any failed critical check blocks publication. Warnings must be explained rather
than hidden.

## Interaction and accessibility requirements

- Use the same on-time and late colors on every page and do not rely on color alone.
- Show denominators in labels or tooltips for every percentage.
- Use descriptive titles that state the grain and time basis.
- Disable cross-highlighting that combines disconnected aggregate tables.
- Include alt text, sufficient contrast, logical tab order, and readable number
  formats.
- Preserve blanks for unavailable metrics; never format missing values as zero.
