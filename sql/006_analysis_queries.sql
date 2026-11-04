/*
Read-only analytical queries. Execute manually after validation passes.

Rates are proportions from 0 to 1. Purchase month is the temporal convention.
Seller and category rows use attributed bridge grains and cannot be summed to
reconstruct the global order total when orders span multiple groups.
*/

SET NOCOUNT ON;
DECLARE @MinimumGroupSize int = 30;

/* Reproducibility context. All six rows must share one snapshot and manifest. */
SELECT dataset_snapshot_id, source_manifest_sha256, dataset_name,
       load_batch_id, source_filename, source_sha256,
       expected_row_count, inserted_row_count, completed_at_utc
FROM reporting.vw_current_source_provenance
ORDER BY dataset_name;

/* Publication gate. Review every failed or warning check before interpretation. */
SELECT validation_run_id, dataset_snapshot_id, source_manifest_sha256,
       run_status, completed_at_utc, check_id, check_status,
       observed_value, expected_value, message
FROM reporting.vw_latest_validation_results
ORDER BY check_id;

/* Q1-Q3: Overall delivery performance.
   Grain: one summary row. Cohorts and exclusions come from order-level views. */
SELECT source_order_count, delivered_order_count, eligible_order_count,
       delivery_status_excluded_order_count, on_time_order_count,
       late_order_count, on_time_delivery_rate, late_delivery_rate,
       duration_eligible_order_count, duration_excluded_order_count,
       average_delivery_hours,
       median_delivery_hours, p90_delivery_hours, p95_delivery_hours,
       average_days_late
FROM reporting.vw_delivery_overview;

/* Exclusion audit. Grain: one row per cohort and explicit reason. */
SELECT N'delivery_status' AS cohort,
       COALESCE(delivery_exclusion_reason, N'eligible') AS exclusion_reason,
       COUNT_BIG(*) AS order_count
FROM analytics.vw_order_delivery
GROUP BY COALESCE(delivery_exclusion_reason, N'eligible')
UNION ALL
SELECT N'duration', COALESCE(duration_exclusion_reason, N'eligible'), COUNT_BIG(*)
FROM analytics.vw_order_delivery
GROUP BY COALESCE(duration_exclusion_reason, N'eligible')
ORDER BY cohort, order_count DESC, exclusion_reason;

/* Duration distribution. Grain: one row per explicit elapsed-day bucket. */
SELECT CASE
           WHEN delivery_duration_hours < 24 THEN N'00: <1 day'
           WHEN delivery_duration_hours < 72 THEN N'01: 1-<3 days'
           WHEN delivery_duration_hours < 168 THEN N'02: 3-<7 days'
           WHEN delivery_duration_hours < 336 THEN N'03: 7-<14 days'
           WHEN delivery_duration_hours < 720 THEN N'04: 14-<30 days'
           ELSE N'05: 30+ days'
       END AS duration_bucket,
       COUNT_BIG(*) AS duration_eligible_order_count
FROM analytics.vw_order_delivery
WHERE is_duration_eligible = 1
GROUP BY CASE
             WHEN delivery_duration_hours < 24 THEN N'00: <1 day'
             WHEN delivery_duration_hours < 72 THEN N'01: 1-<3 days'
             WHEN delivery_duration_hours < 168 THEN N'02: 3-<7 days'
             WHEN delivery_duration_hours < 336 THEN N'03: 7-<14 days'
             WHEN delivery_duration_hours < 720 THEN N'04: 14-<30 days'
             ELSE N'05: 30+ days'
         END
ORDER BY duration_bucket;

/* Q4: Monthly pattern based on purchase month, not delivery month. */
SELECT purchase_month, source_order_count, delivered_order_count,
       eligible_order_count, delivery_status_excluded_order_count,
       on_time_order_count, late_order_count, on_time_delivery_rate,
       late_delivery_rate, duration_eligible_order_count,
       duration_excluded_order_count, average_delivery_hours,
       median_delivery_hours, p90_delivery_hours, p95_delivery_hours
FROM reporting.vw_monthly_delivery
ORDER BY purchase_month;

/* Q4: Customer-state comparison. customer_id is the order-specific join key. */
SELECT customer_state, source_order_count, delivered_order_count,
       eligible_order_count, delivery_status_excluded_order_count,
       on_time_order_count, late_order_count, on_time_delivery_rate,
       late_delivery_rate, duration_eligible_order_count,
       duration_excluded_order_count, average_delivery_hours,
       median_delivery_hours, p90_delivery_hours
FROM reporting.vw_state_delivery
WHERE eligible_order_count >= @MinimumGroupSize
ORDER BY late_delivery_rate DESC, eligible_order_count DESC, customer_state;

/* Q5: Seller attribution. Multi-seller orders appear once for each seller. */
SELECT seller_id, seller_state, source_order_count, delivered_order_count,
       eligible_order_count, delivery_status_excluded_order_count,
       on_time_order_count, late_order_count, on_time_delivery_rate,
       late_delivery_rate, duration_eligible_order_count,
       duration_excluded_order_count, average_delivery_hours,
       median_delivery_hours, p90_delivery_hours
FROM reporting.vw_seller_delivery
WHERE eligible_order_count >= @MinimumGroupSize
ORDER BY late_delivery_rate DESC, eligible_order_count DESC, seller_id;

/* Q5: Category attribution. Multi-category orders appear once for each category. */
SELECT product_category_name, source_order_count, delivered_order_count,
       eligible_order_count, delivery_status_excluded_order_count,
       on_time_order_count, late_order_count, on_time_delivery_rate,
       late_delivery_rate, duration_eligible_order_count,
       duration_excluded_order_count, average_delivery_hours,
       median_delivery_hours, p90_delivery_hours
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
