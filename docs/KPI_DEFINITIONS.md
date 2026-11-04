# KPI definitions

All percentages require a visible numerator and denominator. Unless a visual states
otherwise, filters apply before the numerator and denominator are calculated.

| KPI | Definition | Denominator / cohort | Null and exclusion behavior |
|---|---|---|---|
| All orders | Distinct canonical `order_id` count | Canonical orders | Duplicate raw keys are quality findings, not extra orders |
| Delivered orders | Orders whose trimmed, case-normalized status is `delivered` | All orders | Does not imply delivery timestamps are usable |
| Delivery-eligible orders | Delivered orders with valid actual and estimated delivery timestamps | All orders | Missing, invalid, or non-delivered status is excluded |
| On-time orders | Eligible orders where actual calendar date <= estimated calendar date | Delivery-eligible orders | Never inferred from order status alone |
| Late orders | Eligible orders where actual calendar date > estimated calendar date | Delivery-eligible orders | Same-date delivery is on time |
| On-time rate | On-time orders / delivery-eligible orders | Delivery-eligible orders | Null when denominator is zero |
| Late rate | Late orders / delivery-eligible orders | Delivery-eligible orders | Null when denominator is zero |
| Delivery-status excluded orders | All orders - delivery-eligible orders | All orders | Reported as a count and reason distribution |
| Days early or late | Actual delivery date - estimated delivery date in whole calendar days | Delivery-eligible orders | Negative = early; positive = late |
| Duration-eligible orders | Orders with valid purchase and delivery timestamps and nonnegative interval | All orders | Evaluated independently of delivery-status eligibility |
| Duration-excluded orders | All orders - duration-eligible orders | All orders | Reported separately from delivery-status exclusions |
| Delivery duration days | `(delivered timestamp - purchase timestamp) / 86,400 seconds` | Duration-eligible orders | Fractional days retained; invalid/negative is null |
| Average delivery days | Arithmetic mean of delivery duration | Duration-eligible orders | Null when cohort is empty |
| Median delivery days | Continuous 50th percentile | Duration-eligible orders | SQL definition uses `PERCENTILE_CONT(0.50)` |
| P90 / P95 delivery days | Continuous 90th / 95th percentile | Duration-eligible orders | Tail metrics require denominator disclosure |
| Reviewed orders | Orders with one selected valid review score from 1 to 5 | Canonical orders | Missing/invalid review remains unreviewed |
| Average review score | Mean selected review score | Reviewed orders | Descriptive only |

## Grouped KPI rules

- Monthly grouping uses the purchase timestamp's calendar month.
- Geography uses customer state via the order's `customer_id`.
- Seller and category use distinct order-group bridges and are not additive across
  groups.
- Category nulls are retained as `(Missing category)` for transparency.
- Ranked group comparisons require at least 30 delivery-eligible attributed orders
  unless a documented analysis changes the threshold.
- Any changed threshold must be reported alongside the result; it must not be tuned
  to obtain a preferred ranking.

## Required reconciliation identities

For every applicable filter context:

```text
on_time_orders + late_orders = delivery_eligible_orders
delivery_eligible_orders + delivery_status_excluded_orders = all_orders
on_time_rate + late_rate = 1, subject only to numeric tolerance
```

Duration-eligible orders need not equal delivery-eligible orders because the two
cohorts require different timestamp pairs.
