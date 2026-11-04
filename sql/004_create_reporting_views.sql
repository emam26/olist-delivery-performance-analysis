/* Dashboard-facing reporting views. Rates are decimals from 0 to 1. */

SET NOCOUNT ON;
IF OBJECT_ID(N'analytics.vw_order_delivery', N'V') IS NULL
    THROW 51000, 'Run 003_create_analytical_views.sql first.', 1;
GO

CREATE OR ALTER VIEW reporting.vw_order_delivery_detail
AS
SELECT d.order_id, d.customer_state, d.purchase_month, d.order_status,
       d.is_delivered, d.is_delivery_eligible, d.is_late, d.is_duration_eligible,
       d.delivery_duration_hours, d.days_late,
       r.review_score AS selected_review_score,
       d.delivery_exclusion_reason, d.duration_exclusion_reason,
       d.exclusion_reason
FROM analytics.vw_order_delivery AS d
LEFT JOIN analytics.vw_order_review_selected AS r ON r.order_id = d.order_id;
GO

CREATE OR ALTER VIEW reporting.vw_delivery_overview
AS
WITH duration_window AS
(
    SELECT PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER () AS median_delivery_hours,
           PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER () AS p90_delivery_hours,
           PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER () AS p95_delivery_hours
    FROM analytics.vw_order_delivery
    WHERE is_duration_eligible = 1
),
duration_stats AS
(
    SELECT MAX(median_delivery_hours) AS median_delivery_hours,
           MAX(p90_delivery_hours) AS p90_delivery_hours,
           MAX(p95_delivery_hours) AS p95_delivery_hours
    FROM duration_window
),
totals AS
(
    SELECT COUNT_BIG(*) AS source_order_count,
           SUM(CASE WHEN LOWER(LTRIM(RTRIM(order_status))) = N'delivered'
                    THEN CONVERT(bigint, 1) ELSE 0 END) AS delivered_order_count,
           SUM(CASE WHEN is_delivery_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
               AS eligible_order_count,
           SUM(CASE WHEN is_delivery_eligible = 1 AND is_late = 0
                    THEN CONVERT(bigint, 1) ELSE 0 END) AS on_time_order_count,
           SUM(CASE WHEN is_delivery_eligible = 1 AND is_late = 1
                    THEN CONVERT(bigint, 1) ELSE 0 END) AS late_order_count,
           SUM(CASE WHEN is_duration_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
               AS duration_eligible_order_count,
           AVG(CASE WHEN is_duration_eligible = 1
                    THEN CONVERT(decimal(18, 4), delivery_duration_hours) END)
               AS average_delivery_hours,
           AVG(CASE WHEN is_late = 1 THEN CONVERT(decimal(18, 4), days_late) END)
               AS average_days_late
    FROM analytics.vw_order_delivery
)
SELECT t.source_order_count, t.delivered_order_count, t.eligible_order_count,
       t.source_order_count - t.eligible_order_count
           AS delivery_status_excluded_order_count,
       t.on_time_order_count,
       t.late_order_count,
       CAST(t.on_time_order_count * 1.0 / NULLIF(t.eligible_order_count, 0)
            AS decimal(18, 6)) AS on_time_delivery_rate,
       CAST(t.late_order_count * 1.0 / NULLIF(t.eligible_order_count, 0)
            AS decimal(18, 6)) AS late_delivery_rate,
       t.duration_eligible_order_count,
       t.source_order_count - t.duration_eligible_order_count
           AS duration_excluded_order_count,
       t.average_delivery_hours,
       CAST(s.median_delivery_hours AS decimal(18, 4)) AS median_delivery_hours,
       CAST(s.p90_delivery_hours AS decimal(18, 4)) AS p90_delivery_hours,
       CAST(s.p95_delivery_hours AS decimal(18, 4)) AS p95_delivery_hours,
       t.average_days_late
FROM totals AS t
CROSS JOIN duration_stats AS s;
GO

CREATE OR ALTER VIEW reporting.vw_monthly_delivery
AS
WITH base AS
(
    SELECT * FROM analytics.vw_order_delivery WHERE purchase_month IS NOT NULL
),
duration_window AS
(
    SELECT purchase_month,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY purchase_month) AS median_delivery_hours,
           PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY purchase_month) AS p90_delivery_hours,
           PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY purchase_month) AS p95_delivery_hours
    FROM base
    WHERE is_duration_eligible = 1
),
duration_stats AS
(
    SELECT purchase_month, MAX(median_delivery_hours) AS median_delivery_hours,
           MAX(p90_delivery_hours) AS p90_delivery_hours,
           MAX(p95_delivery_hours) AS p95_delivery_hours
    FROM duration_window
    GROUP BY purchase_month
)
SELECT b.purchase_month,
       COUNT_BIG(*) AS source_order_count,
       SUM(CASE WHEN LOWER(LTRIM(RTRIM(b.order_status))) = N'delivered'
                THEN CONVERT(bigint, 1) ELSE 0 END) AS delivered_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS eligible_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 0 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS delivery_status_excluded_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 0
                THEN CONVERT(bigint, 1) ELSE 0 END) AS on_time_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 1
                THEN CONVERT(bigint, 1) ELSE 0 END) AS late_order_count,
       CAST(SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 0 THEN 1.0 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN b.is_delivery_eligible = 1 THEN 1.0 ELSE 0 END), 0)
            AS decimal(18, 6)) AS on_time_delivery_rate,
       CAST(SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 1 THEN 1.0 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN b.is_delivery_eligible = 1 THEN 1.0 ELSE 0 END), 0)
            AS decimal(18, 6)) AS late_delivery_rate,
       SUM(CASE WHEN b.is_duration_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS duration_eligible_order_count,
       SUM(CASE WHEN b.is_duration_eligible = 0 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS duration_excluded_order_count,
       AVG(CASE WHEN b.is_duration_eligible = 1 THEN b.delivery_duration_hours END)
           AS average_delivery_hours,
       CAST(MAX(s.median_delivery_hours) AS decimal(18, 4)) AS median_delivery_hours,
       CAST(MAX(s.p90_delivery_hours) AS decimal(18, 4)) AS p90_delivery_hours,
       CAST(MAX(s.p95_delivery_hours) AS decimal(18, 4)) AS p95_delivery_hours
FROM base AS b
LEFT JOIN duration_stats AS s ON s.purchase_month = b.purchase_month
GROUP BY b.purchase_month;
GO

CREATE OR ALTER VIEW reporting.vw_state_delivery
AS
WITH base AS
(
    SELECT * FROM analytics.vw_order_delivery
    WHERE customer_state IS NOT NULL
),
duration_window AS
(
    SELECT customer_state,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY customer_state) AS median_delivery_hours,
           PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY customer_state) AS p90_delivery_hours
    FROM base
    WHERE is_duration_eligible = 1
),
duration_stats AS
(
    SELECT customer_state, MAX(median_delivery_hours) AS median_delivery_hours,
           MAX(p90_delivery_hours) AS p90_delivery_hours
    FROM duration_window GROUP BY customer_state
)
SELECT b.customer_state, COUNT_BIG(*) AS source_order_count,
       SUM(CASE WHEN LOWER(LTRIM(RTRIM(b.order_status))) = N'delivered'
                THEN CONVERT(bigint, 1) ELSE 0 END) AS delivered_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS eligible_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 0 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS delivery_status_excluded_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 0
                THEN CONVERT(bigint, 1) ELSE 0 END) AS on_time_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 1
                THEN CONVERT(bigint, 1) ELSE 0 END) AS late_order_count,
       CAST(SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 0 THEN 1.0 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN b.is_delivery_eligible = 1 THEN 1.0 ELSE 0 END), 0)
            AS decimal(18, 6)) AS on_time_delivery_rate,
       CAST(SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 1 THEN 1.0 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN b.is_delivery_eligible = 1 THEN 1.0 ELSE 0 END), 0)
            AS decimal(18, 6)) AS late_delivery_rate,
       SUM(CASE WHEN b.is_duration_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS duration_eligible_order_count,
       SUM(CASE WHEN b.is_duration_eligible = 0 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS duration_excluded_order_count,
       AVG(CASE WHEN b.is_duration_eligible = 1 THEN b.delivery_duration_hours END)
           AS average_delivery_hours,
       CAST(MAX(s.median_delivery_hours) AS decimal(18, 4)) AS median_delivery_hours,
       CAST(MAX(s.p90_delivery_hours) AS decimal(18, 4)) AS p90_delivery_hours
FROM base AS b
LEFT JOIN duration_stats AS s ON s.customer_state = b.customer_state
GROUP BY b.customer_state;
GO

CREATE OR ALTER VIEW reporting.vw_seller_delivery
AS
WITH base AS
(
    SELECT b.order_id, b.seller_id, s.seller_state, d.order_status,
           d.is_delivery_eligible, d.is_late, d.is_duration_eligible,
           d.delivery_duration_hours
    FROM analytics.vw_order_seller_bridge AS b
    INNER JOIN analytics.vw_order_delivery AS d ON d.order_id = b.order_id
    LEFT JOIN analytics.vw_sellers_canonical AS s ON s.seller_id = b.seller_id
),
duration_window AS
(
    SELECT seller_id,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY seller_id) AS median_delivery_hours,
           PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY seller_id) AS p90_delivery_hours
    FROM base WHERE is_duration_eligible = 1
),
duration_stats AS
(
    SELECT seller_id, MAX(median_delivery_hours) AS median_delivery_hours,
           MAX(p90_delivery_hours) AS p90_delivery_hours
    FROM duration_window GROUP BY seller_id
)
SELECT b.seller_id, MAX(b.seller_state) AS seller_state,
       COUNT_BIG(*) AS source_order_count,
       SUM(CASE WHEN LOWER(LTRIM(RTRIM(b.order_status))) = N'delivered'
                THEN CONVERT(bigint, 1) ELSE 0 END) AS delivered_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS eligible_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 0 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS delivery_status_excluded_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 0
                THEN CONVERT(bigint, 1) ELSE 0 END) AS on_time_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 1
                THEN CONVERT(bigint, 1) ELSE 0 END) AS late_order_count,
       CAST(SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 0 THEN 1.0 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN b.is_delivery_eligible = 1 THEN 1.0 ELSE 0 END), 0)
            AS decimal(18, 6)) AS on_time_delivery_rate,
       CAST(SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 1 THEN 1.0 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN b.is_delivery_eligible = 1 THEN 1.0 ELSE 0 END), 0)
            AS decimal(18, 6)) AS late_delivery_rate,
       SUM(CASE WHEN b.is_duration_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS duration_eligible_order_count,
       SUM(CASE WHEN b.is_duration_eligible = 0 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS duration_excluded_order_count,
       AVG(CASE WHEN b.is_duration_eligible = 1 THEN b.delivery_duration_hours END)
           AS average_delivery_hours,
       CAST(MAX(s.median_delivery_hours) AS decimal(18, 4)) AS median_delivery_hours,
       CAST(MAX(s.p90_delivery_hours) AS decimal(18, 4)) AS p90_delivery_hours
FROM base AS b
LEFT JOIN duration_stats AS s ON s.seller_id = b.seller_id
GROUP BY b.seller_id;
GO

CREATE OR ALTER VIEW reporting.vw_category_delivery
AS
WITH base AS
(
    SELECT b.order_id, b.product_category_name, d.order_status,
           d.is_delivery_eligible, d.is_late, d.is_duration_eligible,
           d.delivery_duration_hours
    FROM analytics.vw_order_category_bridge AS b
    INNER JOIN analytics.vw_order_delivery AS d ON d.order_id = b.order_id
),
duration_window AS
(
    SELECT product_category_name,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY product_category_name) AS median_delivery_hours,
           PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY product_category_name) AS p90_delivery_hours
    FROM base WHERE is_duration_eligible = 1
),
duration_stats AS
(
    SELECT product_category_name, MAX(median_delivery_hours) AS median_delivery_hours,
           MAX(p90_delivery_hours) AS p90_delivery_hours
    FROM duration_window GROUP BY product_category_name
)
SELECT b.product_category_name, COUNT_BIG(*) AS source_order_count,
       SUM(CASE WHEN LOWER(LTRIM(RTRIM(b.order_status))) = N'delivered'
                THEN CONVERT(bigint, 1) ELSE 0 END) AS delivered_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS eligible_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 0 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS delivery_status_excluded_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 0
                THEN CONVERT(bigint, 1) ELSE 0 END) AS on_time_order_count,
       SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 1
                THEN CONVERT(bigint, 1) ELSE 0 END) AS late_order_count,
       CAST(SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 0 THEN 1.0 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN b.is_delivery_eligible = 1 THEN 1.0 ELSE 0 END), 0)
            AS decimal(18, 6)) AS on_time_delivery_rate,
       CAST(SUM(CASE WHEN b.is_delivery_eligible = 1 AND b.is_late = 1 THEN 1.0 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN b.is_delivery_eligible = 1 THEN 1.0 ELSE 0 END), 0)
            AS decimal(18, 6)) AS late_delivery_rate,
       SUM(CASE WHEN b.is_duration_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS duration_eligible_order_count,
       SUM(CASE WHEN b.is_duration_eligible = 0 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS duration_excluded_order_count,
       AVG(CASE WHEN b.is_duration_eligible = 1 THEN b.delivery_duration_hours END)
           AS average_delivery_hours,
       CAST(MAX(s.median_delivery_hours) AS decimal(18, 4)) AS median_delivery_hours,
       CAST(MAX(s.p90_delivery_hours) AS decimal(18, 4)) AS p90_delivery_hours
FROM base AS b
LEFT JOIN duration_stats AS s ON s.product_category_name = b.product_category_name
GROUP BY b.product_category_name;
GO

CREATE OR ALTER VIEW reporting.vw_review_delivery_distribution
AS
WITH eligible AS
(
    SELECT d.order_id, CASE WHEN d.is_late = 1 THEN N'Late' ELSE N'On Time' END
               AS delivery_class,
           r.review_score
    FROM analytics.vw_order_delivery AS d
    LEFT JOIN analytics.vw_order_review_selected AS r ON r.order_id = d.order_id
    WHERE d.is_delivery_eligible = 1
),
class_summary AS
(
    SELECT delivery_class,
           SUM(CASE WHEN review_score IS NULL THEN CONVERT(bigint, 1) ELSE 0 END)
               AS orders_without_usable_review
    FROM eligible GROUP BY delivery_class
),
scores AS
(
    SELECT review_score
    FROM (VALUES (1), (2), (3), (4), (5)) AS score_values (review_score)
)
SELECT c.delivery_class, s.review_score, COUNT_BIG(e.order_id) AS review_count,
       c.orders_without_usable_review
FROM class_summary AS c
CROSS JOIN scores AS s
LEFT JOIN eligible AS e
    ON e.delivery_class = c.delivery_class AND e.review_score = s.review_score
GROUP BY c.delivery_class, s.review_score, c.orders_without_usable_review;
GO

CREATE OR ALTER VIEW reporting.vw_current_source_provenance
AS
SELECT dataset_snapshot_id, source_manifest_sha256, dataset_name,
       load_batch_id, source_filename, source_sha256,
       expected_row_count, inserted_row_count, completed_at_utc
FROM analytics.vw_current_snapshot_batches;
GO

CREATE OR ALTER VIEW reporting.vw_latest_validation_results
AS
WITH current_snapshot AS
(
    SELECT MAX(dataset_snapshot_id) AS dataset_snapshot_id
    FROM analytics.vw_current_snapshot_batches
),
latest AS
(
    SELECT MAX(r.validation_run_id) AS validation_run_id
    FROM audit.validation_runs AS r
    INNER JOIN current_snapshot AS s
        ON s.dataset_snapshot_id = r.dataset_snapshot_id
    WHERE r.completed_at_utc IS NOT NULL
)
SELECT r.validation_run_id, r.dataset_snapshot_id,
       s.source_manifest_sha256, r.status AS run_status, r.started_at_utc,
       r.completed_at_utc, d.check_id, d.status AS check_status,
       d.observed_value, d.expected_value, d.message
FROM audit.validation_runs AS r
INNER JOIN audit.dataset_snapshots AS s
    ON s.dataset_snapshot_id = r.dataset_snapshot_id
INNER JOIN audit.validation_results AS d
    ON d.validation_run_id = r.validation_run_id
WHERE r.validation_run_id = (SELECT validation_run_id FROM latest);
GO
