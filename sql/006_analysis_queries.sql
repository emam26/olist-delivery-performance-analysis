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

/* Q7: Late-delivery severity. Grain: one late, delivery-eligible order.
   Severity is positive calendar days after the estimated delivery date, matching
   the project-wide late classification. The operational bands are descriptive
   reporting bands, not an externally validated service-level taxonomy. */
WITH late_base AS
(
    SELECT customer_state, days_late
    FROM analytics.vw_order_delivery
    WHERE is_delivery_eligible = 1
      AND is_late = 1
      AND days_late IS NOT NULL
),
late_window AS
(
    SELECT days_late,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_late) OVER ()
               AS median_days_late,
           PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY days_late) OVER ()
               AS p90_days_late
    FROM late_base
)
SELECT COUNT_BIG(*) AS late_order_count,
       AVG(CONVERT(decimal(18, 4), days_late)) AS average_days_late,
       CAST(MAX(median_days_late) AS decimal(18, 4)) AS median_days_late,
       CAST(MAX(p90_days_late) AS decimal(18, 4)) AS p90_days_late
FROM late_window;

WITH late_base AS
(
    SELECT CASE
               WHEN days_late = 1 THEN N'01: 1 day late'
               WHEN days_late <= 3 THEN N'02: 2-3 days late'
               WHEN days_late <= 7 THEN N'03: 4-7 days late'
               WHEN days_late <= 14 THEN N'04: 8-14 days late'
               WHEN days_late <= 30 THEN N'05: 15-30 days late'
               ELSE N'06: 31+ days late'
           END AS severity_band
    FROM analytics.vw_order_delivery
    WHERE is_delivery_eligible = 1
      AND is_late = 1
      AND days_late IS NOT NULL
),
totals AS
(
    SELECT COUNT_BIG(*) AS late_order_count
    FROM late_base
)
SELECT severity_band, COUNT_BIG(*) AS late_order_count,
       CAST(COUNT_BIG(*) * 1.0 / NULLIF(MAX(t.late_order_count), 0)
            AS decimal(18, 6)) AS share_of_late_orders
FROM late_base AS b
CROSS JOIN totals AS t
GROUP BY severity_band
ORDER BY severity_band;

/* Compare delay severity only among groups with at least the documented
   eligible-order threshold. State rows are mutually exclusive customer geography. */
WITH state_severity AS
(
    SELECT customer_state, COUNT_BIG(*) AS late_order_count,
           AVG(CONVERT(decimal(18, 4), days_late)) AS average_days_late
    FROM analytics.vw_order_delivery
    WHERE is_delivery_eligible = 1
      AND is_late = 1
      AND days_late IS NOT NULL
    GROUP BY customer_state
)
SELECT s.customer_state, s.eligible_order_count, s.late_order_count,
       s.late_delivery_rate, d.average_days_late
FROM reporting.vw_state_delivery AS s
INNER JOIN state_severity AS d ON d.customer_state = s.customer_state
WHERE s.eligible_order_count >= @MinimumGroupSize
ORDER BY d.average_days_late DESC, s.late_order_count DESC, s.customer_state;

/* Seller rows use the distinct order-seller bridge. They are comparison evidence,
   not a partition of orders and not evidence that a seller caused a delay. */
WITH seller_severity AS
(
    SELECT b.seller_id, COUNT_BIG(*) AS attributed_late_order_count,
           AVG(CONVERT(decimal(18, 4), d.days_late)) AS average_days_late
    FROM analytics.vw_order_seller_bridge AS b
    INNER JOIN analytics.vw_order_delivery AS d ON d.order_id = b.order_id
    WHERE d.is_delivery_eligible = 1
      AND d.is_late = 1
      AND d.days_late IS NOT NULL
    GROUP BY b.seller_id
)
SELECT s.seller_id, s.seller_state, s.eligible_order_count,
       s.late_order_count, s.late_delivery_rate,
       d.attributed_late_order_count, d.average_days_late
FROM reporting.vw_seller_delivery AS s
INNER JOIN seller_severity AS d ON d.seller_id = s.seller_id
WHERE s.eligible_order_count >= @MinimumGroupSize
ORDER BY d.average_days_late DESC, s.late_order_count DESC, s.seller_id;

/* Q8: Estimated-date reliability. Grain: one delivery- and duration-eligible
   order with a nonnegative promised window (purchase to estimated date). The
   early/on-time/late split uses calendar dates so it remains consistent with the
   canonical delivery classification; it does not assume timestamps are UTC. */
WITH promise_base AS
(
    SELECT d.is_late,
           DATEDIFF(DAY, CAST(d.order_estimated_delivery_timestamp AS date),
                    CAST(d.order_delivered_customer_timestamp AS date))
               AS calendar_days_from_promise,
           CAST(DATEDIFF_BIG(SECOND, d.order_purchase_timestamp,
                              d.order_estimated_delivery_timestamp) / 86400.0
                AS decimal(18, 6)) AS promised_window_days,
           CAST(d.delivery_duration_hours / 24.0 AS decimal(18, 6))
               AS actual_delivery_days
    FROM analytics.vw_order_delivery AS d
    WHERE d.is_delivery_eligible = 1
      AND d.is_duration_eligible = 1
      AND d.order_estimated_delivery_timestamp >= d.order_purchase_timestamp
),
promise_window AS
(
    SELECT promised_window_days, actual_delivery_days,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY promised_window_days) OVER ()
               AS median_promised_window_days,
           PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY promised_window_days) OVER ()
               AS p90_promised_window_days
    FROM promise_base
)
SELECT COUNT_BIG(*) AS promise_window_eligible_order_count,
       AVG(promised_window_days) AS average_promised_window_days,
       CAST(MAX(median_promised_window_days) AS decimal(18, 4))
           AS median_promised_window_days,
       CAST(MAX(p90_promised_window_days) AS decimal(18, 4))
           AS p90_promised_window_days,
       AVG(actual_delivery_days) AS average_actual_delivery_days
FROM promise_window;

WITH promise_base AS
(
    SELECT DATEDIFF(DAY, CAST(order_estimated_delivery_timestamp AS date),
                    CAST(order_delivered_customer_timestamp AS date))
               AS calendar_days_from_promise,
           CAST(DATEDIFF_BIG(SECOND, order_purchase_timestamp,
                              order_estimated_delivery_timestamp) / 86400.0
                AS decimal(18, 6)) AS promised_window_days
    FROM analytics.vw_order_delivery
    WHERE is_delivery_eligible = 1
      AND is_duration_eligible = 1
      AND order_estimated_delivery_timestamp >= order_purchase_timestamp
),
bucketed AS
(
    SELECT CASE
               WHEN calendar_days_from_promise < 0 THEN N'Early'
               WHEN calendar_days_from_promise = 0 THEN N'On time'
               ELSE N'Late'
           END AS promise_outcome,
           CASE
               WHEN promised_window_days < 3 THEN N'01: <3 promised days'
               WHEN promised_window_days < 7 THEN N'02: 3-<7 promised days'
               WHEN promised_window_days < 14 THEN N'03: 7-<14 promised days'
               WHEN promised_window_days < 21 THEN N'04: 14-<21 promised days'
               ELSE N'05: 21+ promised days'
           END AS promised_window_band
    FROM promise_base
),
totals AS
(
    SELECT COUNT_BIG(*) AS promise_window_eligible_order_count
    FROM bucketed
)
SELECT promised_window_band, COUNT_BIG(*) AS order_count,
       SUM(CASE WHEN promise_outcome = N'Early' THEN CONVERT(bigint, 1) ELSE 0 END)
           AS early_order_count,
       SUM(CASE WHEN promise_outcome = N'On time' THEN CONVERT(bigint, 1) ELSE 0 END)
           AS on_time_order_count,
       SUM(CASE WHEN promise_outcome = N'Late' THEN CONVERT(bigint, 1) ELSE 0 END)
           AS late_order_count,
       CAST(COUNT_BIG(*) * 1.0 / NULLIF(MAX(t.promise_window_eligible_order_count), 0)
            AS decimal(18, 6)) AS share_of_promise_window_population,
       CAST(SUM(CASE WHEN promise_outcome = N'Late' THEN 1.0 ELSE 0 END)
            / NULLIF(COUNT_BIG(*), 0) AS decimal(18, 6)) AS late_delivery_rate
FROM bucketed AS b
CROSS JOIN totals AS t
GROUP BY promised_window_band
ORDER BY promised_window_band;

/* Q9: Concentration and prioritisation. State percentages share a global,
   mutually exclusive order denominator. Use both late volume and rate; a high
   rate alone is not a priority ranking or causal attribution. */
WITH global_late AS
(
    SELECT COUNT_BIG(*) AS global_late_order_count
    FROM analytics.vw_order_delivery
    WHERE is_delivery_eligible = 1 AND is_late = 1
),
states AS
(
    SELECT customer_state, eligible_order_count, late_order_count, late_delivery_rate,
           SUM(late_order_count) OVER
               (ORDER BY late_order_count DESC, customer_state
                ROWS UNBOUNDED PRECEDING) AS cumulative_late_order_count
    FROM reporting.vw_state_delivery
    WHERE eligible_order_count >= @MinimumGroupSize
)
SELECT s.customer_state, s.eligible_order_count, s.late_order_count,
       s.late_delivery_rate,
       CAST(s.late_order_count * 1.0 / NULLIF(g.global_late_order_count, 0)
            AS decimal(18, 6)) AS share_of_global_late_orders,
       CAST(s.cumulative_late_order_count * 1.0 / NULLIF(g.global_late_order_count, 0)
            AS decimal(18, 6)) AS cumulative_share_of_global_late_orders
FROM states AS s
CROSS JOIN global_late AS g
ORDER BY s.late_order_count DESC, s.customer_state;

/* Seller concentration is explicitly attributed, not distinct-order additive.
   "share_of_global_late_orders" may sum to more than one across sellers when an
   order contains items from multiple sellers. The qualified-attribution shares
   describe only the displayed seller subset after the 30-order threshold. */
WITH global_late AS
(
    SELECT COUNT_BIG(*) AS global_late_order_count
    FROM analytics.vw_order_delivery
    WHERE is_delivery_eligible = 1 AND is_late = 1
),
qualified_sellers AS
(
    SELECT seller_id, seller_state, eligible_order_count, late_order_count,
           late_delivery_rate
    FROM reporting.vw_seller_delivery
    WHERE eligible_order_count >= @MinimumGroupSize
),
ranked_sellers AS
(
    SELECT seller_id, seller_state, eligible_order_count, late_order_count,
           late_delivery_rate,
           SUM(late_order_count) OVER () AS qualified_attributed_late_order_count,
           SUM(late_order_count) OVER
               (ORDER BY late_order_count DESC, seller_id ROWS UNBOUNDED PRECEDING)
               AS cumulative_attributed_late_order_count
    FROM qualified_sellers
)
SELECT s.seller_id, s.seller_state, s.eligible_order_count, s.late_order_count,
       s.late_delivery_rate,
       CAST(s.late_order_count * 1.0 / NULLIF(g.global_late_order_count, 0)
            AS decimal(18, 6)) AS share_of_global_late_orders,
       CAST(s.late_order_count * 1.0
            / NULLIF(s.qualified_attributed_late_order_count, 0) AS decimal(18, 6))
           AS share_of_qualified_seller_attribution,
       CAST(s.cumulative_attributed_late_order_count * 1.0
            / NULLIF(s.qualified_attributed_late_order_count, 0) AS decimal(18, 6))
           AS cumulative_share_of_qualified_seller_attribution
FROM ranked_sellers AS s
CROSS JOIN global_late AS g
ORDER BY s.late_order_count DESC, s.seller_id;

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
