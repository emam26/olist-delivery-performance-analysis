/* Analytical views. Every view uses the latest successful batch per dataset. */

SET NOCOUNT ON;
IF OBJECT_ID(N'stg.orders', N'U') IS NULL
    THROW 51000, 'Run staging-table creation and load successful batches first.', 1;
GO

CREATE OR ALTER VIEW analytics.vw_current_orders_raw
AS
WITH latest AS
(
    SELECT MAX(load_batch_id) AS load_batch_id
    FROM audit.load_batches
    WHERE dataset_name = N'orders' AND status = 'Succeeded'
)
SELECT source_row_number, order_id, customer_id, order_status,
       order_purchase_timestamp, order_approved_at,
       order_delivered_carrier_date, order_delivered_customer_date,
       order_estimated_delivery_date, source_row_sha256
FROM stg.orders
WHERE load_batch_id = (SELECT load_batch_id FROM latest);
GO

CREATE OR ALTER VIEW analytics.vw_current_items_raw
AS
WITH latest AS
(
    SELECT MAX(load_batch_id) AS load_batch_id
    FROM audit.load_batches
    WHERE dataset_name = N'order_items' AND status = 'Succeeded'
)
SELECT source_row_number, order_id, order_item_id, product_id, seller_id,
       shipping_limit_date, price, freight_value, source_row_sha256
FROM stg.order_items
WHERE load_batch_id = (SELECT load_batch_id FROM latest);
GO

CREATE OR ALTER VIEW analytics.vw_current_customers_raw
AS
WITH latest AS
(
    SELECT MAX(load_batch_id) AS load_batch_id
    FROM audit.load_batches
    WHERE dataset_name = N'customers' AND status = 'Succeeded'
)
SELECT source_row_number, customer_id, customer_unique_id,
       customer_zip_code_prefix, customer_city, customer_state, source_row_sha256
FROM stg.customers
WHERE load_batch_id = (SELECT load_batch_id FROM latest);
GO

CREATE OR ALTER VIEW analytics.vw_current_sellers_raw
AS
WITH latest AS
(
    SELECT MAX(load_batch_id) AS load_batch_id
    FROM audit.load_batches
    WHERE dataset_name = N'sellers' AND status = 'Succeeded'
)
SELECT source_row_number, seller_id, seller_zip_code_prefix,
       seller_city, seller_state, source_row_sha256
FROM stg.sellers
WHERE load_batch_id = (SELECT load_batch_id FROM latest);
GO

CREATE OR ALTER VIEW analytics.vw_current_products_raw
AS
WITH latest AS
(
    SELECT MAX(load_batch_id) AS load_batch_id
    FROM audit.load_batches
    WHERE dataset_name = N'products' AND status = 'Succeeded'
)
SELECT source_row_number, product_id, product_category_name,
       product_name_lenght, product_description_lenght, product_photos_qty,
       product_weight_g, product_length_cm, product_height_cm, product_width_cm,
       source_row_sha256
FROM stg.products
WHERE load_batch_id = (SELECT load_batch_id FROM latest);
GO

CREATE OR ALTER VIEW analytics.vw_current_reviews_raw
AS
WITH latest AS
(
    SELECT MAX(load_batch_id) AS load_batch_id
    FROM audit.load_batches
    WHERE dataset_name = N'reviews' AND status = 'Succeeded'
)
SELECT source_row_number, review_id, order_id, review_score,
       review_comment_title, review_comment_message,
       review_creation_date, review_answer_timestamp, source_row_sha256
FROM stg.reviews
WHERE load_batch_id = (SELECT load_batch_id FROM latest);
GO

CREATE OR ALTER VIEW analytics.vw_orders_typed
AS
WITH ranked AS
(
    SELECT *,
           COUNT_BIG(*) OVER (PARTITION BY order_id) AS source_order_duplicate_count,
           ROW_NUMBER() OVER
           (
               PARTITION BY order_id
               ORDER BY source_row_number, source_row_sha256
           ) AS canonical_row_number
    FROM analytics.vw_current_orders_raw
)
SELECT order_id, customer_id, order_status,
       TRY_CONVERT(datetime2(0), NULLIF(order_purchase_timestamp, N''), 120)
           AS order_purchase_timestamp,
       TRY_CONVERT(datetime2(0), NULLIF(order_approved_at, N''), 120)
           AS order_approved_at,
       TRY_CONVERT(datetime2(0), NULLIF(order_delivered_carrier_date, N''), 120)
           AS order_delivered_carrier_timestamp,
       TRY_CONVERT(datetime2(0), NULLIF(order_delivered_customer_date, N''), 120)
           AS order_delivered_customer_timestamp,
       TRY_CONVERT(datetime2(0), NULLIF(order_estimated_delivery_date, N''), 120)
           AS order_estimated_delivery_timestamp,
       order_purchase_timestamp AS order_purchase_timestamp_raw,
       order_delivered_customer_date AS order_delivered_customer_timestamp_raw,
       order_estimated_delivery_date AS order_estimated_delivery_timestamp_raw,
       source_order_duplicate_count,
       source_row_number,
       source_row_sha256
FROM ranked
WHERE canonical_row_number = 1;
GO

CREATE OR ALTER VIEW analytics.vw_customers_canonical
AS
WITH ranked AS
(
    SELECT *,
           COUNT_BIG(*) OVER (PARTITION BY customer_id) AS source_customer_duplicate_count,
           ROW_NUMBER() OVER
           (
               PARTITION BY customer_id
               ORDER BY source_row_number, source_row_sha256
           ) AS canonical_row_number
    FROM analytics.vw_current_customers_raw
)
SELECT customer_id, customer_unique_id, customer_zip_code_prefix,
       customer_city, customer_state, source_customer_duplicate_count
FROM ranked
WHERE canonical_row_number = 1;
GO

CREATE OR ALTER VIEW analytics.vw_sellers_canonical
AS
WITH ranked AS
(
    SELECT *, ROW_NUMBER() OVER
    (
        PARTITION BY seller_id ORDER BY source_row_number, source_row_sha256
    ) AS canonical_row_number
    FROM analytics.vw_current_sellers_raw
)
SELECT seller_id, seller_zip_code_prefix, seller_city, seller_state
FROM ranked
WHERE canonical_row_number = 1;
GO

CREATE OR ALTER VIEW analytics.vw_products_canonical
AS
WITH ranked AS
(
    SELECT *, ROW_NUMBER() OVER
    (
        PARTITION BY product_id ORDER BY source_row_number, source_row_sha256
    ) AS canonical_row_number
    FROM analytics.vw_current_products_raw
)
SELECT product_id, NULLIF(LTRIM(RTRIM(product_category_name)), N'') AS product_category_name,
       TRY_CONVERT(int, NULLIF(product_name_lenght, N'')) AS product_name_length,
       TRY_CONVERT(int, NULLIF(product_description_lenght, N'')) AS product_description_length,
       TRY_CONVERT(int, NULLIF(product_photos_qty, N'')) AS product_photos_qty,
       TRY_CONVERT(decimal(18, 3), NULLIF(product_weight_g, N'')) AS product_weight_g,
       TRY_CONVERT(decimal(18, 3), NULLIF(product_length_cm, N'')) AS product_length_cm,
       TRY_CONVERT(decimal(18, 3), NULLIF(product_height_cm, N'')) AS product_height_cm,
       TRY_CONVERT(decimal(18, 3), NULLIF(product_width_cm, N'')) AS product_width_cm
FROM ranked
WHERE canonical_row_number = 1;
GO

CREATE OR ALTER VIEW analytics.vw_order_items
AS
SELECT source_row_number, order_id,
       TRY_CONVERT(int, NULLIF(order_item_id, N'')) AS order_item_id,
       product_id, seller_id,
       TRY_CONVERT(datetime2(0), NULLIF(shipping_limit_date, N''), 120)
           AS shipping_limit_timestamp,
       TRY_CONVERT(decimal(18, 2), NULLIF(price, N'')) AS price,
       TRY_CONVERT(decimal(18, 2), NULLIF(freight_value, N'')) AS freight_value,
       COUNT_BIG(*) OVER (PARTITION BY order_id, order_item_id)
           AS source_item_duplicate_count,
       source_row_sha256
FROM analytics.vw_current_items_raw;
GO

CREATE OR ALTER VIEW analytics.vw_reviews_all
AS
SELECT source_row_number, review_id, order_id,
       TRY_CONVERT(int, NULLIF(review_score, N'')) AS review_score,
       review_comment_title, review_comment_message,
       TRY_CONVERT(datetime2(0), NULLIF(review_creation_date, N''), 120)
           AS review_creation_timestamp,
       TRY_CONVERT(datetime2(0), NULLIF(review_answer_timestamp, N''), 120)
           AS review_answer_timestamp,
       COUNT_BIG(*) OVER (PARTITION BY order_id) AS source_review_count,
       source_row_sha256
FROM analytics.vw_current_reviews_raw;
GO

CREATE OR ALTER VIEW analytics.vw_order_review_selected
AS
WITH ranked AS
(
    SELECT *, ROW_NUMBER() OVER
    (
        PARTITION BY order_id
        ORDER BY
            CASE WHEN review_score BETWEEN 1 AND 5 THEN 0 ELSE 1 END,
            review_answer_timestamp DESC,
            review_creation_timestamp DESC,
            review_id DESC,
            source_row_number DESC
    ) AS selection_rank
    FROM analytics.vw_reviews_all
)
SELECT order_id, review_id, review_score, review_comment_title,
       review_comment_message, review_creation_timestamp,
       review_answer_timestamp, source_review_count
FROM ranked
WHERE selection_rank = 1 AND review_score BETWEEN 1 AND 5;
GO

CREATE OR ALTER VIEW analytics.vw_order_delivery
AS
SELECT o.order_id, o.customer_id, c.customer_unique_id, c.customer_state,
       o.order_status, o.order_purchase_timestamp,
       o.order_delivered_customer_timestamp,
       o.order_estimated_delivery_timestamp,
       CASE WHEN o.order_purchase_timestamp IS NULL THEN NULL
            ELSE DATEFROMPARTS(YEAR(o.order_purchase_timestamp),
                               MONTH(o.order_purchase_timestamp), 1) END AS purchase_month,
       CAST(CASE WHEN LOWER(LTRIM(RTRIM(o.order_status))) = N'delivered'
                     AND o.order_delivered_customer_timestamp IS NOT NULL
                     AND o.order_estimated_delivery_timestamp IS NOT NULL
                 THEN 1 ELSE 0 END AS bit) AS is_delivery_eligible,
       CAST(CASE WHEN LOWER(LTRIM(RTRIM(o.order_status))) = N'delivered'
                     AND o.order_delivered_customer_timestamp IS NOT NULL
                     AND o.order_estimated_delivery_timestamp IS NOT NULL
                 THEN CASE WHEN CAST(o.order_delivered_customer_timestamp AS date)
                                    > CAST(o.order_estimated_delivery_timestamp AS date)
                                THEN 1 ELSE 0 END
                 ELSE NULL END AS bit) AS is_late,
       CAST(CASE WHEN o.order_purchase_timestamp IS NOT NULL
                     AND o.order_delivered_customer_timestamp IS NOT NULL
                     AND o.order_delivered_customer_timestamp >= o.order_purchase_timestamp
                 THEN 1 ELSE 0 END AS bit) AS is_duration_eligible,
       CASE WHEN o.order_purchase_timestamp IS NOT NULL
                 AND o.order_delivered_customer_timestamp IS NOT NULL
                 AND o.order_delivered_customer_timestamp >= o.order_purchase_timestamp
            THEN CAST(DATEDIFF_BIG(MINUTE, o.order_purchase_timestamp,
                                   o.order_delivered_customer_timestamp) / 60.0
                      AS decimal(18, 4)) END AS delivery_duration_hours,
       CASE WHEN o.order_delivered_customer_timestamp IS NOT NULL
                 AND o.order_estimated_delivery_timestamp IS NOT NULL
                 AND CAST(o.order_delivered_customer_timestamp AS date)
                     > CAST(o.order_estimated_delivery_timestamp AS date)
            THEN DATEDIFF(DAY, CAST(o.order_estimated_delivery_timestamp AS date),
                               CAST(o.order_delivered_customer_timestamp AS date)) END
            AS days_late,
       CASE
           WHEN LOWER(LTRIM(RTRIM(o.order_status))) <> N'delivered' THEN N'status_not_delivered'
           WHEN o.order_delivered_customer_timestamp IS NULL
               THEN N'missing_or_invalid_actual_delivery'
           WHEN o.order_estimated_delivery_timestamp IS NULL
               THEN N'missing_or_invalid_estimated_delivery'
           WHEN o.order_purchase_timestamp IS NULL
               THEN N'missing_or_invalid_purchase_timestamp'
           WHEN o.order_delivered_customer_timestamp < o.order_purchase_timestamp
               THEN N'negative_delivery_interval'
           ELSE NULL
       END AS exclusion_reason,
       o.source_order_duplicate_count,
       CAST(CASE WHEN c.customer_id IS NULL THEN 1 ELSE 0 END AS bit) AS missing_customer,
       c.source_customer_duplicate_count
FROM analytics.vw_orders_typed AS o
LEFT JOIN analytics.vw_customers_canonical AS c ON c.customer_id = o.customer_id;
GO

CREATE OR ALTER VIEW analytics.vw_order_seller_bridge
AS
SELECT DISTINCT order_id, seller_id
FROM analytics.vw_order_items
WHERE NULLIF(LTRIM(RTRIM(order_id)), N'') IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(seller_id)), N'') IS NOT NULL;
GO

CREATE OR ALTER VIEW analytics.vw_order_category_bridge
AS
SELECT DISTINCT i.order_id, p.product_category_name
FROM analytics.vw_order_items AS i
INNER JOIN analytics.vw_products_canonical AS p ON p.product_id = i.product_id
WHERE NULLIF(LTRIM(RTRIM(i.order_id)), N'') IS NOT NULL
  AND p.product_category_name IS NOT NULL;
GO
