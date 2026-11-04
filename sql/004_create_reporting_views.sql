/* Dashboard-facing reporting views. Rates are decimals from 0 to 1. */

SET NOCOUNT ON;
IF OBJECT_ID(N'analytics.vw_order_delivery', N'V') IS NULL
    THROW 51000, 'Run 003_create_analytical_views.sql first.', 1;
GO

CREATE OR ALTER VIEW reporting.vw_order_delivery_detail
AS
SELECT d.order_id, d.customer_state, d.purchase_month, d.order_status,
       d.is_delivery_eligible, d.is_late, d.is_duration_eligible,
       d.delivery_duration_hours, d.days_late,
       r.review_score AS selected_review_score,
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
SELECT t.source_order_count, t.eligible_order_count, t.on_time_order_count,
       t.late_order_count,
       CAST(t.on_time_order_count * 1.0 / NULLIF(t.eligible_order_count, 0)
            AS decimal(18, 6)) AS on_time_delivery_rate,
       CAST(t.late_order_count * 1.0 / NULLIF(t.eligible_order_count, 0)
            AS decimal(18, 6)) AS late_delivery_rate,
       t.duration_eligible_order_count, t.average_delivery_hours,
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
       SUM(CASE WHEN b.is_delivery_eligible = 1 THEN CONVERT(bigint, 1) ELSE 0 END)
           AS eligible_order_count,
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
WITH eligible AS
(
    SELECT * FROM analytics.vw_order_delivery
    WHERE is_delivery_eligible = 1 AND customer_state IS NOT NULL
),
duration_window AS
(
    SELECT customer_state,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY customer_state) AS median_delivery_hours
    FROM eligible
    WHERE is_duration_eligible = 1
),
duration_stats AS
(
    SELECT customer_state, MAX(median_delivery_hours) AS median_delivery_hours
    FROM duration_window GROUP BY customer_state
)
SELECT e.customer_state, COUNT_BIG(*) AS eligible_order_count,
       SUM(CASE WHEN e.is_late = 1 THEN CONVERT(bigint, 1) ELSE 0 END) AS late_order_count,
       CAST(SUM(CASE WHEN e.is_late = 1 THEN 1.0 ELSE 0 END) / COUNT_BIG(*)
            AS decimal(18, 6)) AS late_delivery_rate,
       AVG(CASE WHEN e.is_duration_eligible = 1 THEN e.delivery_duration_hours END)
           AS average_delivery_hours,
       CAST(MAX(s.median_delivery_hours) AS decimal(18, 4)) AS median_delivery_hours
FROM eligible AS e
LEFT JOIN duration_stats AS s ON s.customer_state = e.customer_state
GROUP BY e.customer_state;
GO

CREATE OR ALTER VIEW reporting.vw_seller_delivery
AS
WITH eligible AS
(
    SELECT b.order_id, b.seller_id, s.seller_state, d.is_late,
           d.is_duration_eligible, d.delivery_duration_hours
    FROM analytics.vw_order_seller_bridge AS b
    INNER JOIN analytics.vw_order_delivery AS d ON d.order_id = b.order_id
    LEFT JOIN analytics.vw_sellers_canonical AS s ON s.seller_id = b.seller_id
    WHERE d.is_delivery_eligible = 1
),
duration_window AS
(
    SELECT seller_id,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY seller_id) AS median_delivery_hours
    FROM eligible WHERE is_duration_eligible = 1
),
duration_stats AS
(
    SELECT seller_id, MAX(median_delivery_hours) AS median_delivery_hours
    FROM duration_window GROUP BY seller_id
)
SELECT e.seller_id, MAX(e.seller_state) AS seller_state,
       COUNT_BIG(*) AS eligible_order_count,
       SUM(CASE WHEN e.is_late = 1 THEN CONVERT(bigint, 1) ELSE 0 END) AS late_order_count,
       CAST(SUM(CASE WHEN e.is_late = 1 THEN 1.0 ELSE 0 END) / COUNT_BIG(*)
            AS decimal(18, 6)) AS late_delivery_rate,
       AVG(CASE WHEN e.is_duration_eligible = 1 THEN e.delivery_duration_hours END)
           AS average_delivery_hours,
       CAST(MAX(s.median_delivery_hours) AS decimal(18, 4)) AS median_delivery_hours
FROM eligible AS e
LEFT JOIN duration_stats AS s ON s.seller_id = e.seller_id
GROUP BY e.seller_id;
GO

CREATE OR ALTER VIEW reporting.vw_category_delivery
AS
WITH eligible AS
(
    SELECT b.order_id, b.product_category_name, d.is_late,
           d.is_duration_eligible, d.delivery_duration_hours
    FROM analytics.vw_order_category_bridge AS b
    INNER JOIN analytics.vw_order_delivery AS d ON d.order_id = b.order_id
    WHERE d.is_delivery_eligible = 1
),
duration_window AS
(
    SELECT product_category_name,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY delivery_duration_hours)
               OVER (PARTITION BY product_category_name) AS median_delivery_hours
    FROM eligible WHERE is_duration_eligible = 1
),
duration_stats AS
(
    SELECT product_category_name, MAX(median_delivery_hours) AS median_delivery_hours
    FROM duration_window GROUP BY product_category_name
)
SELECT e.product_category_name, COUNT_BIG(*) AS eligible_order_count,
       SUM(CASE WHEN e.is_late = 1 THEN CONVERT(bigint, 1) ELSE 0 END) AS late_order_count,
       CAST(SUM(CASE WHEN e.is_late = 1 THEN 1.0 ELSE 0 END) / COUNT_BIG(*)
            AS decimal(18, 6)) AS late_delivery_rate,
       AVG(CASE WHEN e.is_duration_eligible = 1 THEN e.delivery_duration_hours END)
           AS average_delivery_hours,
       CAST(MAX(s.median_delivery_hours) AS decimal(18, 4)) AS median_delivery_hours
FROM eligible AS e
LEFT JOIN duration_stats AS s ON s.product_category_name = e.product_category_name
GROUP BY e.product_category_name;
GO

CREATE OR ALTER VIEW reporting.vw_review_delivery_distribution
AS
WITH eligible AS
(
    SELECT d.order_id, CASE WHEN d.is_late = 1 THEN N'Late' ELSE N'OnTime' END
               AS delivery_class,
           r.review_score
    FROM analytics.vw_order_delivery AS d
    LEFT JOIN analytics.vw_order_review_selected AS r ON r.order_id = d.order_id
    WHERE d.is_delivery_eligible = 1
),
missing AS
(
    SELECT delivery_class,
           SUM(CASE WHEN review_score IS NULL THEN CONVERT(bigint, 1) ELSE 0 END)
               AS orders_without_usable_review
    FROM eligible GROUP BY delivery_class
)
SELECT e.delivery_class, e.review_score, COUNT_BIG(*) AS review_count,
       MAX(m.orders_without_usable_review) AS orders_without_usable_review
FROM eligible AS e
INNER JOIN missing AS m ON m.delivery_class = e.delivery_class
WHERE e.review_score IS NOT NULL
GROUP BY e.delivery_class, e.review_score;
GO

CREATE OR ALTER VIEW reporting.vw_latest_validation_results
AS
WITH latest AS
(
    SELECT MAX(validation_run_id) AS validation_run_id FROM audit.validation_runs
)
SELECT r.validation_run_id, r.status AS run_status, r.started_at_utc,
       r.completed_at_utc, d.check_id, d.status AS check_status,
       d.observed_value, d.expected_value, d.message
FROM audit.validation_runs AS r
INNER JOIN audit.validation_results AS d
    ON d.validation_run_id = r.validation_run_id
WHERE r.validation_run_id = (SELECT validation_run_id FROM latest);
GO
