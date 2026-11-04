/*
Read-only analytical queries. Execute manually after validation passes.

Rates are proportions from 0 to 1. Purchase month is the temporal convention.
Seller and category rows use attributed bridge grains and cannot be summed to
reconstruct the global order total when orders span multiple groups.
*/

SET NOCOUNT ON;
DECLARE @MinimumGroupSize int = 30;

/* Q1-Q3: Overall delivery performance.
   Grain: one summary row. Cohorts and exclusions come from order-level views. */
SELECT source_order_count, eligible_order_count, on_time_order_count,
       late_order_count, on_time_delivery_rate, late_delivery_rate,
       duration_eligible_order_count, average_delivery_hours,
       median_delivery_hours, p90_delivery_hours, p95_delivery_hours,
       average_days_late
FROM reporting.vw_delivery_overview;

/* Exclusion audit. Grain: one row per explicit reason, including eligible rows. */
SELECT COALESCE(exclusion_reason, N'none') AS exclusion_reason,
       COUNT_BIG(*) AS order_count
FROM analytics.vw_order_delivery
GROUP BY COALESCE(exclusion_reason, N'none')
ORDER BY order_count DESC, exclusion_reason;

/* Q4: Monthly pattern based on purchase month, not delivery month. */
SELECT purchase_month, eligible_order_count, on_time_order_count, late_order_count,
       on_time_delivery_rate, late_delivery_rate, average_delivery_hours,
       median_delivery_hours, p90_delivery_hours, p95_delivery_hours
FROM reporting.vw_monthly_delivery
ORDER BY purchase_month;

/* Q4: Customer-state comparison. customer_id is the order-specific join key. */
SELECT customer_state, eligible_order_count, late_order_count,
       late_delivery_rate, average_delivery_hours, median_delivery_hours
FROM reporting.vw_state_delivery
WHERE eligible_order_count >= @MinimumGroupSize
ORDER BY late_delivery_rate DESC, eligible_order_count DESC, customer_state;

/* Q5: Seller attribution. Multi-seller orders appear once for each seller. */
SELECT seller_id, seller_state, eligible_order_count, late_order_count,
       late_delivery_rate, average_delivery_hours, median_delivery_hours
FROM reporting.vw_seller_delivery
WHERE eligible_order_count >= @MinimumGroupSize
ORDER BY late_delivery_rate DESC, eligible_order_count DESC, seller_id;

/* Q5: Category attribution. Multi-category orders appear once for each category. */
SELECT product_category_name, eligible_order_count, late_order_count,
       late_delivery_rate, average_delivery_hours, median_delivery_hours
FROM reporting.vw_category_delivery
WHERE eligible_order_count >= @MinimumGroupSize
ORDER BY late_delivery_rate DESC, eligible_order_count DESC, product_category_name;

/* Q6: Review distributions by delivery class. This is association, not causation. */
SELECT delivery_class, review_score, review_count, orders_without_usable_review
FROM reporting.vw_review_delivery_distribution
ORDER BY delivery_class, review_score;

/* Review-selection audit: no usable review and multiple source reviews. */
SELECT
    SUM(CASE WHEN r.order_id IS NULL THEN CONVERT(bigint, 1) ELSE 0 END)
        AS orders_without_usable_review,
    SUM(CASE WHEN r.source_review_count > 1 THEN CONVERT(bigint, 1) ELSE 0 END)
        AS orders_with_multiple_source_reviews,
    COUNT_BIG(*) AS eligible_order_count
FROM analytics.vw_order_delivery AS d
LEFT JOIN analytics.vw_order_review_selected AS r ON r.order_id = d.order_id
WHERE d.is_delivery_eligible = 1;

/* Required reconciliation: eligible classification must be exhaustive. */
SELECT
    SUM(CASE WHEN is_delivery_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
        AS eligible_orders,
    SUM(CASE WHEN is_delivery_eligible = 1 AND is_late = 0
             THEN CONVERT(bigint, 1) ELSE 0 END) AS on_time_orders,
    SUM(CASE WHEN is_delivery_eligible = 1 AND is_late = 1
             THEN CONVERT(bigint, 1) ELSE 0 END) AS late_orders,
    SUM(CASE WHEN is_delivery_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
      - SUM(CASE WHEN is_delivery_eligible = 1 AND is_late IN (0, 1)
                 THEN CONVERT(bigint, 1) ELSE 0 END) AS reconciliation_difference
FROM analytics.vw_order_delivery;
