# Power BI data model

## Recommended source

Use Import mode against the `reporting` SQL Server views. Record the database,
refresh UTC time, and validation run ID in the report notes. Import mode is
appropriate for this bounded public dataset and avoids implying real-time behavior.

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
| Review Delivery | `reporting.vw_review_delivery_distribution` | Selected review score | Descriptive association only |
| Data Quality | `reporting.vw_latest_validation_results` | One validation result per check | Quality-status page and publication gate |

## Relationships

Keep the six summary tables disconnected. They contain metrics at different grains;
relating them to the order-level table would create ambiguous filtering and tempting
but invalid totals.

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
