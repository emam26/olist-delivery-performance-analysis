# Power BI reconciliation checklist

Complete this checklist after every data refresh and before publishing screenshots
or findings. Record actual values in a dated operator note; do not edit expected
results into the repository before they are observed.

## Source and refresh provenance

- Confirm all imported CSV files came from one export directory.
- Compare every CSV row count and SHA-256 hash with `manifest.json`.
- Record the SQL database name, active dataset snapshot ID, source-manifest hash,
  mapped load-batch IDs, validation run ID, and Power BI refresh UTC time.
- Confirm the validation run's snapshot ID equals the active source snapshot ID.
- Confirm no secret-bearing `.env` file or connection string is embedded in an
  exported artifact.

## Grain and count checks

- `order_delivery` row count equals the canonical analytical-order count.
- `DISTINCTCOUNT(order_id)` equals the same order count.
- There are no blank or duplicate order IDs in the order-level table.
- Monthly source-order counts sum to the number of order-level rows with a nonblank
  purchase month; separately disclose orders excluded because purchase month is
  unavailable.
- Seller and category counts are explicitly not expected to sum to the overall
  count because attribution is many-to-many.

## KPI checks

For the unfiltered report, compare Power BI against both the SQL reporting view and
the independent Python validation output:

- all orders;
- delivered orders;
- delivery-eligible orders;
- on-time orders;
- late orders;
- excluded delivery-status orders;
- duration-eligible orders;
- duration-excluded orders;
- on-time and late rates;
- average, median, P90, and P95 delivery duration.

Rates and continuous metrics must reconcile within the documented absolute
tolerance of `1e-4` used by the reconciliation CLI. Counts must
match exactly. `on_time_orders + late_orders` must equal eligible orders.

## Filter behavior

- Select one purchase month and confirm the Page-1 cards and exclusion visuals equal
  that month's reconciled order-level values. Confirm the monthly snapshot visuals
  do not change.
- Confirm each exclusion-reason chart contains nonblank reason groups only and that
  its displayed bars sum exactly to the corresponding exclusion card: 2,971 for
  delivery-status exclusions and 2,965 for duration exclusions on snapshot #1.
- Select a customer state in the Page-2 local slicer and confirm that only the state
  bar, scatter, and state table change. The order-level cards must not change.
- Select a seller state and a product category in their respective local slicers and
  confirm they affect only their own disconnected summary visuals.
- Confirm seller/category visuals do not filter executive cards through an
  accidental relationship.
- Confirm groups below the minimum threshold are excluded from rankings but remain
  available for quality review.
- Confirm the State Median Delivery Hours total and all Category Detail totals are
  blank. The global median and global late rate must be read from `order_delivery`
  KPI measures, never from disconnected summary-table totals.
- Confirm the review legend explicitly maps **Late** to red (`#D85858`) and
  **On Time** to green (`#18866A`).
- Confirm `orders_without_usable_review` is not summed across review-score rows;
  it is repeated class-level context in that summary view.

## Publication gate

Publication is permitted only when:

1. all critical validation checks pass;
2. all order-level counts reconcile exactly;
3. rates and duration statistics reconcile within tolerance;
4. exclusions and non-additive bridge semantics are visible; and
5. findings are labeled as verified observations rather than causal conclusions.

Until then, the dashboard status is **NOT VERIFIED**.
