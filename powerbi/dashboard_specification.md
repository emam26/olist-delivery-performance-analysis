# Dashboard specification

The dashboard is an analytical communication layer over validated reporting views.
It must not introduce new KPI definitions, silently alter denominators, or present
observational associations as causal effects.

The PBIR source contains a four-page, 16:9 report with order-level KPI cards,
monthly trend and volume visuals, state/seller/category/review comparisons, and
quality and provenance tables. The project operator reports that the current
snapshot #1 PBIP opens, refreshes, and renders. Power BI Desktop is still required
to revalidate renderings, filters, colors, and optional navigation after any source
or environment change.

## Visual design system

- Canvas: 16:9 with a light neutral background (`#F5F7FA`), white visual surfaces,
  and a compact 20-pixel outer margin.
- Typography: Segoe UI. Page headings are 24pt bold; explanatory text is 11pt;
  visual titles are concise and state the grain, cohort, or filter scope.
- Palette: navy `#14263D` for hierarchy, blue `#315D8C` for neutral series, green
  `#18866A` for on-time performance, amber `#E6A23C` for comparisons that require
  caution, red `#D85858` for late delivery, and gray `#637387` for secondary text.
- Number formats: counts use `#,0`; rates use `0.00%`; delivery-duration cards use
  `0.00` days. Confirm in Desktop that headline cards display no abbreviated units.
- The checked-in `Olist_Delivery_Theme.json` is the reusable theme source. Its
  application to the PBIR must be confirmed in Desktop; it is not represented as a
  synthetic embedded theme reference.

## Navigation

The four PBIR page labels are **Overview**, **Regions & Sellers**, **Customer
Experience**, and **Data Quality**. These labels make native Power BI page tabs a
usable, supported navigation path.

No source-authored page navigator or Clear Slicers action is currently checked in:
the previous generated candidates opened but did not work at runtime. Native
Desktop generation is pending. The next supported step is to create and validate a
Page navigator and a Clear all slicers button on **Overview** in Desktop, save and
close the report, then inspect the resulting PBIR definitions before reproducing
the verified controls elsewhere.

When validated, a **Clear all slicers** button must be described narrowly: it clears
slicer selections on its current page only. It does not clear the Filters pane,
undo a chart selection, or reset disconnected tables on another page. Data Quality
has no slicer and needs no clearing control.

No full-reset bookmarks are checked in. A complete reset needs an intentional,
page-specific saved state and must not imply that an Overview reset controls
disconnected state, seller, category, review, quality, or provenance summaries. If
required, create and validate one Desktop bookmark per page with **Data** and
**Current page** enabled and **All visuals** selected, then attach a blank button
to the matching bookmark.

## Page 1 - Overview

- Headline cards: total orders, delivery-eligible orders, on-time rate, late
  orders, average delivery days, median delivery days, and P90 delivery days.
- Supporting cards: filter-responsive delivery-status and duration exclusion
  counts. These are separate cohorts and are accompanied by their own reason bars;
  neither is a substitute for the other.
- Monthly line chart: purchase month on the x-axis; on-time and late rates on a
  shared percentage axis; eligible, excluded, and duration-eligible counts in the
  tooltip. The adjacent monthly-volume chart exposes the denominator needed to
  interpret low-volume months. No monthly sample-size suppression is applied.
  Both are disconnected snapshot summaries and are not changed by the order-level
  slicers below.
- Separate exclusion bars for `delivery_exclusion_reason` and
  `duration_exclusion_reason`; do not conflate the two cohorts. Eligible orders
  have a null reason by contract, so the bars use reason-specific measures that
  suppress the blank eligible group while retaining order-level slicer context.
  For snapshot #1, delivery reasons reconcile as 2,963
  `status_not_delivered` plus 8 `missing_or_invalid_actual_delivery` = 2,971;
  duration reasons reconcile as 2,965 `missing_or_invalid_actual_delivery` =
  2,965.
- Slicers: purchase month, customer state, order status.
- Page heading and scope note: cards and exclusion visuals are filter-responsive;
  monthly charts are reconciled snapshot summaries.

The cards must use the `order_delivery` measures. The monthly chart may use the monthly
reporting view only after reconciliation.

## Page 2 - Regions & Sellers

- Ranked bar chart: customer state by late-delivery rate.
- Scatter plot: eligible order count versus median delivery hours; state as detail.
- Table: state and eligible-order count, with comparison rates and median duration
  returned only for groups meeting the sample-size threshold. Its Total row is an
  order-level global benchmark, not an aggregation of state summaries: eligible
  orders, late/on-time rates, and median hours use `order_delivery` measures. The
  operator verified the Snapshot #1 values in Desktop: 96,470 eligible orders, a
  6.77% late rate, and approximately 245.23 median delivery hours. Individual state
  values remain state-level; recheck the total after any model or source change.
- Local customer-state slicer: filters only the state bar, scatter, and state table.
- Local seller-state slicer: filters only the seller comparison. It does not filter
  customer-state visuals or order-level cards.
- Comparison measures return values only when eligible orders meet the documented
  minimum group size. Verify the resulting visual-level behavior in Desktop; if a
  visual is rebuilt from raw columns, apply `eligible_order_count >= 30` directly
  to that disconnected summary table.

Use customer state, not seller state, for the regional comparison. The checked-in
seller visual is sorted by late rate and exposes its eligible-order denominator in
the tooltip. It retains full `seller_id` values because the source supplies no
grounded seller name or approved display alias. The PBIR comparison measures apply
`eligible_order_count >= 30` separately to each ranked summary and the selected
threshold remains visible.

Display: "Multi-seller and multi-category orders are attributed once to every
applicable group; group rows are not additive to the global order total."

## Page 3 - Customer Experience

- Cards from `order_delivery`: reviewed orders, orders without a usable review, and
  average selected review score. Their titles disclose that these are all-order
  metrics.
- Distribution of selected review scores using the delivery-eligible,
  selected-review cohort; verify the Late/red and On Time/green series mapping in
  Desktop after refresh.
- On-time rate by selected review score, with the delivery-eligible denominator in
  every tooltip. Do not add the all-order reviewed count to this tooltip because it
  is not the rate denominator.
- The `Review Delivery` chart is a class-by-score distribution. Treat
  `orders_without_usable_review` as a class-level value and never sum its repeated
  value over score rows.
- Local product-category slicer: filters only the category comparison and detail
  table. It does not filter review visuals or order-level cards.
- Persistent subtitle: "Descriptive association; no causal interpretation."

The category detail table's Total row is a clearly labeled order-level benchmark,
not a category roll-up. Category attribution can repeat an order across categories,
so category counts and rates are never summed or averaged for that row. Instead it
uses `order_delivery` measures. The operator verified the Snapshot #1 Total values
in Desktop as 96,470 eligible orders, 6,534 late orders, and a 6.77% late rate.
Individual category rows retain their attributed counts and the 30-eligible-order
rate threshold; recheck the total after any model or source change.

Product quality, service, geography, expectations, and review-selection effects are
plausible confounders.

## Page 4 - Data Quality

- Cards: validation status, failed and warning check counts, active snapshot ID,
  loaded source rows, and the delivery-status/duration exclusions. The failed-check
  measure returns the numeric value `0` when the active validation result contains
  no failed rows; it does not convert missing KPI values into zero.
- Validation table from `Data Quality`: check ID, check status, observed value,
  expected value, and message.
- Source table from `Source Provenance`: dataset, filename, expected and inserted
  rows, source hash, batch ID, and completion time.
- Exclusion indicators from `order_delivery`: delivery-status excluded, duration
  excluded, and orders without a usable review.
- Audit note: source row counts are exact counts. Full source hashes and validation
  messages remain available in the tables and must not be shortened in the model;
  use table scrolling or exported data for complete technical review.

Any failed check blocks publication. Warnings must be investigated and disclosed.

## Interaction and accessibility requirements

- Use the same on-time and late colors on every page and do not rely on color alone.
- Show denominators in labels or tooltips for every percentage.
- Use descriptive titles that state the grain and time basis.
- Keep cross-filtering within the table that supplies a visual. The model does not
  permit order-level slicers to filter disconnected monthly, state, seller,
  category, review, quality, or provenance summaries.
- In Desktop, use **Format > Edit interactions** to confirm the intended local
  behavior: the customer-state slicer affects only state visuals; the seller-state
  slicer affects only the seller visual; and the category slicer affects only
  category visuals. Set interactions to **None** where a disconnected selection
  could otherwise confuse the reader.
- Include alt text, sufficient contrast, logical tab order, and readable number
  formats.
- Preserve blanks for unavailable metrics; never format missing values as zero.

## Desktop checks after source refinement

The report source gives the eight primary charts concise business titles and maps
the `Review Delivery[delivery_class]` values through explicit data-point selectors:
`Late` is `#D85858` and `On Time` is `#18866A`. Confirm both the titles and legend
after refresh. If Desktop does not retain the mapping, select the review chart,
open **Format visual** > **Columns** > **Colors**, turn on **Show all** (or use
**Apply settings to**), and apply those exact colors.

Navigation and clear-slicer controls are pending native Desktop creation and runtime
verification. First create and test them on Overview, save, and close Desktop so
their actual PBIR definitions can be inspected before any source replication. Also
confirm that the ranked state, seller, and category charts sort descending by late
rate and set accessible alt text for visual titles. A full reset remains
Desktop-only until page-specific bookmarks are deliberately created and verified.
