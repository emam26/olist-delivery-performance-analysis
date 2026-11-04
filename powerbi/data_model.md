# Power BI data model

## Recommended source

Use Import mode against the `reporting` SQL Server views. Import is appropriate for
this bounded historical dataset, gives predictable percentile/filter behavior, and
does not imply real-time monitoring. DirectQuery is not recommended for this
portfolio analysis. Record the database, refresh UTC time, dataset snapshot ID,
source-manifest hash, and validation run ID in the report notes.

If SQL Server access is unavailable from Power BI Desktop, use a single immutable
CSV export directory plus its `manifest.json`. Never mix files from different
export directories.

## Tables and grains

| Power BI table | SQL view | Grain | Intended use |
|---|---|---|---|
| Order Delivery | `reporting.vw_order_delivery_detail` | One row per canonical order | Core cards, distributions, drill-through, and independently filtered metrics |
| Monthly Delivery | `reporting.vw_monthly_delivery` | Purchase month | Reconciled time trend |
| State Delivery | `reporting.vw_state_delivery` | Customer state | Geographic comparison |
| Seller Delivery | `reporting.vw_seller_delivery` | Distinct order-seller attribution | Seller comparison only; totals are not additive |
| Category Delivery | `reporting.vw_category_delivery` | Distinct order-category attribution | Product-category comparison only; totals are not additive |
| Review Delivery | `reporting.vw_review_delivery_distribution` | Delivery class and selected review score | Descriptive association only; missing-review count repeats by class |
| Data Quality | `reporting.vw_latest_validation_results` | One validation result per check | Quality-status page and publication gate |
| Source Provenance | `reporting.vw_current_source_provenance` | One row per dataset in the active snapshot | Source hashes and load reconciliation |

## Relationships

Keep all summary, quality, and provenance tables disconnected. They contain values
at different grains; relating them to the order-level table would create ambiguous
filtering and tempting but invalid totals.

Use `Order Delivery[purchase_month]` or the monthly view for the purchase-month
trend. The monthly view may be used directly for the published trend after its
values reconcile with the order-level measures. The export contract does not
include a separate order-purchase-date column.

```DAX
Calendar =
VAR FirstDate = MINX('Order Delivery', 'Order Delivery'[purchase_month])
VAR LastDate = MAXX('Order Delivery', 'Order Delivery'[purchase_month])
RETURN
    ADDCOLUMNS(
        CALENDAR(FirstDate, LastDate),
        "Year", YEAR([Date]),
        "Month Number", MONTH([Date]),
        "Month", FORMAT([Date], "YYYY-MM"),
        "Year Month Sort", YEAR([Date]) * 100 + MONTH([Date])
    )
```

Sort `Calendar[Month]` by `Calendar[Year Month Sort]`.

Create one active, single-direction, many-to-one relationship from
`Order Delivery[purchase_month]` (many) to `Calendar[Date]` (one). Mark `Calendar`
as the date table using `Calendar[Date]`. Do not relate `Monthly Delivery` to the
calendar at the same time; use it as a disconnected reconciled visual source, or
build the monthly visual from `Order Delivery`, but do not mix both approaches in
one visual.

## Import instructions

For SQL Server, choose **Get data > SQL Server**, enter only the confirmed server
and database, select Import, and choose the eight reporting views listed above.
Use the approved read-only identity; do not paste a connection string into report
notes. For CSV mode, choose all eight CSVs from one export directory and verify
their names and hashes against that directory's `manifest.json` before loading.
Never combine files from two export directories.

## Semantic constraints

- `is_late` is interpreted only inside the `is_delivery_eligible = 1` cohort.
- Delivery duration has its own eligibility flag. Do not use delivery-status
  eligibility as a substitute denominator.
- Missing future or incomplete timestamps remain blank, not zero.
- Seller and category outputs use distinct order attribution. A multi-seller or
  multi-category order can appear in more than one group, so group totals must not
  be summed into an overall order count.
- Review analysis uses one deterministic usable review per order. It describes an
  association and does not establish that delivery performance caused the score.
- Apply the documented minimum group-size threshold before ranking sellers,
  categories, states, or review groups.
- Apply the threshold as a visual-level filter on each summary table's
  `eligible_order_count`; the order-level `[Minimum Group Size]` measure is a label,
  not a valid cross-table filter for disconnected summaries.
