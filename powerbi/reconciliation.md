# Power BI reconciliation checklist

Complete this checklist after every data refresh and before publishing screenshots
or findings. Record actual values in a dated operator note; do not edit expected
results into the repository before they are observed.

## Source and refresh provenance

- Confirm all imported CSV files came from one export directory.
- Compare every CSV byte count and SHA-256 hash with `manifest.json`.
- Record the SQL database name, latest successful load-batch IDs, validation run ID,
  and Power BI refresh UTC time.
- Confirm no secret-bearing `.env` file or connection string is embedded in an
  exported artifact.

## Grain and count checks

- `Order Delivery` row count equals the canonical analytical-order count.
- `DISTINCTCOUNT(order_id)` equals the same order count.
- There are no blank or duplicate order IDs in the order-level table.
- Monthly all-order counts sum to the order-level count.
- Seller and category counts are explicitly not expected to sum to the overall
  count because attribution is many-to-many.

## KPI checks

For the unfiltered report, compare Power BI against both the SQL reporting view and
the independent Python validation output:

- all orders;
- delivery-eligible orders;
- on-time orders;
- late orders;
- excluded delivery-status orders;
- duration-eligible orders;
- on-time and late rates;
- average, median, P90, and P95 delivery duration.

Rates must reconcile within the documented floating-point tolerance. Counts must
match exactly. `on_time_orders + late_orders` must equal eligible orders.

## Filter behavior

- Select one purchase month and confirm cards equal that month's reconciled values.
- Select one state and confirm the state page and order-level measures agree.
- Confirm seller/category visuals do not filter executive cards through an
  accidental relationship.
- Confirm groups below the minimum threshold are excluded from rankings but remain
  available for quality review.

## Publication gate

Publication is permitted only when:

1. all critical validation checks pass;
2. all order-level counts reconcile exactly;
3. rates and duration statistics reconcile within tolerance;
4. exclusions and non-additive bridge semantics are visible; and
5. findings are labeled as verified observations rather than causal conclusions.

Until then, the dashboard status is **NOT VERIFIED**.
