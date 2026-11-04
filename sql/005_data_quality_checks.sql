/* Installs an auditable validation procedure. It does not modify analytical data. */

SET NOCOUNT ON;
IF OBJECT_ID(N'reporting.vw_delivery_overview', N'V') IS NULL
    THROW 51000, 'Run reporting-view creation before installing validation.', 1;
GO

CREATE OR ALTER PROCEDURE audit.usp_run_validation
    @fail_on_warning bit = 0
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @run_id bigint;
    DECLARE @current_snapshot_id bigint;
    DECLARE @results TABLE
    (
        check_id nvarchar(200) NOT NULL PRIMARY KEY,
        status varchar(20) NOT NULL,
        observed_value nvarchar(1000) NULL,
        expected_value nvarchar(1000) NULL,
        message nvarchar(2000) NOT NULL
    );

    BEGIN TRY
        BEGIN TRANSACTION;

        SELECT @current_snapshot_id = MAX(dataset_snapshot_id)
        FROM audit.dataset_snapshots AS s WITH (UPDLOCK, HOLDLOCK)
        WHERE s.status = 'Succeeded'
          AND s.dataset_count = 6
          AND (SELECT COUNT_BIG(*)
               FROM audit.dataset_snapshot_batches AS m
               INNER JOIN audit.load_batches AS b
                   ON b.load_batch_id = m.load_batch_id
                  AND b.dataset_name = m.dataset_name
                  AND b.source_sha256 = m.source_sha256
                  AND b.status = 'Succeeded'
               WHERE m.dataset_snapshot_id = s.dataset_snapshot_id) = 6;

        INSERT audit.validation_runs (dataset_snapshot_id, status, fail_on_warning)
        VALUES (@current_snapshot_id, 'Started', @fail_on_warning);
        SET @run_id = CONVERT(bigint, SCOPE_IDENTITY());

        DECLARE @current_snapshot_batches bigint =
        (
            SELECT COUNT_BIG(*)
            FROM analytics.vw_current_snapshot_batches
        );
        INSERT @results VALUES
        (
            N'load.complete_current_snapshot',
            CASE WHEN @current_snapshot_id IS NOT NULL AND @current_snapshot_batches = 6
                 THEN 'Passed' ELSE 'Failed' END,
            CONCAT(N'snapshot=', @current_snapshot_id,
                   N'; mapped_datasets=', @current_snapshot_batches),
            N'one successful snapshot with 6 mapped datasets',
            N'Analytical views activate all six source versions together.'
        );

        DECLARE @snapshot_mapping_mismatches bigint =
        (
            SELECT COUNT_BIG(*)
            FROM audit.dataset_snapshot_batches AS m
            LEFT JOIN audit.load_batches AS b ON b.load_batch_id = m.load_batch_id
            WHERE m.dataset_snapshot_id = @current_snapshot_id
              AND (b.load_batch_id IS NULL OR b.status <> 'Succeeded'
                   OR b.dataset_name <> m.dataset_name
                   OR b.source_sha256 <> m.source_sha256)
        );
        INSERT @results VALUES
        (
            N'load.snapshot_batch_identity',
            CASE WHEN @snapshot_mapping_mismatches = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @snapshot_mapping_mismatches), N'0 mismatches',
            N'Every current snapshot mapping must match a successful batch name and hash.'
        );

        DECLARE @batch_count_mismatches bigint =
        (
            SELECT COUNT_BIG(*)
            FROM analytics.vw_current_snapshot_batches
            WHERE expected_row_count IS NOT NULL
              AND expected_row_count <> inserted_row_count
        );
        INSERT @results VALUES
        (
            N'load.inventory_to_batch_counts',
            CASE WHEN @batch_count_mismatches = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @batch_count_mismatches), N'0 mismatched batches',
            N'Inventory row counts must equal committed batch row counts.'
        );

        DECLARE @staging_count_mismatches bigint;
        WITH staged AS
        (
            SELECT N'orders' AS dataset_name, load_batch_id, COUNT_BIG(*) AS rows_loaded
            FROM stg.orders GROUP BY load_batch_id
            UNION ALL
            SELECT N'order_items', load_batch_id, COUNT_BIG(*) FROM stg.order_items
            GROUP BY load_batch_id
            UNION ALL
            SELECT N'customers', load_batch_id, COUNT_BIG(*) FROM stg.customers
            GROUP BY load_batch_id
            UNION ALL
            SELECT N'sellers', load_batch_id, COUNT_BIG(*) FROM stg.sellers
            GROUP BY load_batch_id
            UNION ALL
            SELECT N'products', load_batch_id, COUNT_BIG(*) FROM stg.products
            GROUP BY load_batch_id
            UNION ALL
            SELECT N'reviews', load_batch_id, COUNT_BIG(*) FROM stg.reviews
            GROUP BY load_batch_id
        )
        SELECT @staging_count_mismatches = COUNT_BIG(*)
        FROM analytics.vw_current_snapshot_batches AS current_batch
        INNER JOIN audit.load_batches AS b
            ON b.load_batch_id = current_batch.load_batch_id
        LEFT JOIN staged AS s ON s.load_batch_id = current_batch.load_batch_id
        WHERE ISNULL(s.rows_loaded, -1) <> b.inserted_row_count;
        INSERT @results VALUES
        (
            N'load.batch_to_staging_counts',
            CASE WHEN @staging_count_mismatches = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @staging_count_mismatches), N'0 mismatched datasets',
            N'Committed metadata counts must equal physical staging rows.'
        );

        DECLARE @duplicate_orders bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT order_id FROM analytics.vw_current_orders_raw
                GROUP BY order_id HAVING COUNT_BIG(*) > 1
            ) AS duplicates
        );
        INSERT @results VALUES
        (
            N'grain.orders_unique',
            CASE WHEN @duplicate_orders = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @duplicate_orders), N'0 duplicate order IDs',
            N'Canonical selection preserves evidence, but published order grain requires review.'
        );

        DECLARE @duplicate_items bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT order_id, order_item_id FROM analytics.vw_current_items_raw
                GROUP BY order_id, order_item_id HAVING COUNT_BIG(*) > 1
            ) AS duplicates
        );
        INSERT @results VALUES
        (
            N'grain.order_items_unique',
            CASE WHEN @duplicate_items = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @duplicate_items), N'0 duplicate order-item keys',
            N'Order-item grain is (order_id, order_item_id).'
        );

        DECLARE @duplicate_customers bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT customer_id FROM analytics.vw_current_customers_raw
                GROUP BY customer_id HAVING COUNT_BIG(*) > 1
            ) AS duplicates
        );
        INSERT @results VALUES
        (
            N'grain.customers_unique',
            CASE WHEN @duplicate_customers = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @duplicate_customers), N'0 duplicate customer IDs',
            N'Customer grain is one source row per customer_id.'
        );

        DECLARE @duplicate_sellers bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT seller_id FROM analytics.vw_current_sellers_raw
                GROUP BY seller_id HAVING COUNT_BIG(*) > 1
            ) AS duplicates
        );
        INSERT @results VALUES
        (
            N'grain.sellers_unique',
            CASE WHEN @duplicate_sellers = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @duplicate_sellers), N'0 duplicate seller IDs',
            N'Seller grain is one source row per seller_id.'
        );

        DECLARE @duplicate_products bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT product_id FROM analytics.vw_current_products_raw
                GROUP BY product_id HAVING COUNT_BIG(*) > 1
            ) AS duplicates
        );
        INSERT @results VALUES
        (
            N'grain.products_unique',
            CASE WHEN @duplicate_products = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @duplicate_products), N'0 duplicate product IDs',
            N'Product grain is one source row per product_id.'
        );

        DECLARE @duplicate_reviews bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT review_id, order_id FROM analytics.vw_current_reviews_raw
                GROUP BY review_id, order_id HAVING COUNT_BIG(*) > 1
            ) AS duplicates
        );
        INSERT @results VALUES
        (
            N'grain.reviews_unique',
            CASE WHEN @duplicate_reviews = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @duplicate_reviews),
            N'0 duplicate review/order keys',
            N'Review source grain is the composite (review_id, order_id).'
        );

        DECLARE @blank_required_identifiers bigint =
            (SELECT COUNT_BIG(*) FROM analytics.vw_current_orders_raw
             WHERE NULLIF(LTRIM(RTRIM(order_id)), N'') IS NULL
                OR NULLIF(LTRIM(RTRIM(customer_id)), N'') IS NULL)
          + (SELECT COUNT_BIG(*) FROM analytics.vw_current_items_raw
             WHERE NULLIF(LTRIM(RTRIM(order_id)), N'') IS NULL
                OR NULLIF(LTRIM(RTRIM(order_item_id)), N'') IS NULL
                OR NULLIF(LTRIM(RTRIM(product_id)), N'') IS NULL
                OR NULLIF(LTRIM(RTRIM(seller_id)), N'') IS NULL)
          + (SELECT COUNT_BIG(*) FROM analytics.vw_current_customers_raw
             WHERE NULLIF(LTRIM(RTRIM(customer_id)), N'') IS NULL)
          + (SELECT COUNT_BIG(*) FROM analytics.vw_current_sellers_raw
             WHERE NULLIF(LTRIM(RTRIM(seller_id)), N'') IS NULL)
          + (SELECT COUNT_BIG(*) FROM analytics.vw_current_products_raw
             WHERE NULLIF(LTRIM(RTRIM(product_id)), N'') IS NULL)
          + (SELECT COUNT_BIG(*) FROM analytics.vw_current_reviews_raw
             WHERE NULLIF(LTRIM(RTRIM(review_id)), N'') IS NULL
                OR NULLIF(LTRIM(RTRIM(order_id)), N'') IS NULL);
        INSERT @results VALUES
        (
            N'quality.required_identifiers_not_blank',
            CASE WHEN @blank_required_identifiers = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @blank_required_identifiers), N'0 rows',
            N'Required identifiers must be nonblank before canonical joins.'
        );

        DECLARE @orders_missing_customers bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_orders_typed AS o
            LEFT JOIN analytics.vw_customers_canonical AS c ON c.customer_id = o.customer_id
            WHERE c.customer_id IS NULL
        );
        INSERT @results VALUES
        (
            N'relationship.orders_to_customers',
            CASE WHEN @orders_missing_customers = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @orders_missing_customers), N'0 orphan orders',
            N'Orders join customers on the order-specific customer_id.'
        );

        DECLARE @items_missing_orders bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_order_items AS i
            LEFT JOIN analytics.vw_orders_typed AS o ON o.order_id = i.order_id
            WHERE o.order_id IS NULL
        );
        INSERT @results VALUES
        (
            N'relationship.items_to_orders',
            CASE WHEN @items_missing_orders = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @items_missing_orders), N'0 orphan items',
            N'Every item should reference a source order.'
        );

        DECLARE @items_missing_sellers bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_order_items AS i
            LEFT JOIN analytics.vw_sellers_canonical AS s ON s.seller_id = i.seller_id
            WHERE s.seller_id IS NULL
        );
        INSERT @results VALUES
        (
            N'relationship.items_to_sellers',
            CASE WHEN @items_missing_sellers = 0 THEN 'Passed' ELSE 'Warning' END,
            CONVERT(nvarchar(1000), @items_missing_sellers), N'0 orphan item seller IDs',
            N'Orphans do not change global order KPIs but limit seller attribution.'
        );

        DECLARE @items_missing_products bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_order_items AS i
            LEFT JOIN analytics.vw_products_canonical AS p ON p.product_id = i.product_id
            WHERE p.product_id IS NULL
        );
        INSERT @results VALUES
        (
            N'relationship.items_to_products',
            CASE WHEN @items_missing_products = 0 THEN 'Passed' ELSE 'Warning' END,
            CONVERT(nvarchar(1000), @items_missing_products), N'0 orphan item product IDs',
            N'Orphans limit category attribution and remain visible.'
        );

        DECLARE @reviews_missing_orders bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_reviews_all AS r
            LEFT JOIN analytics.vw_orders_typed AS o ON o.order_id = r.order_id
            WHERE o.order_id IS NULL
        );
        INSERT @results VALUES
        (
            N'relationship.reviews_to_orders',
            CASE WHEN @reviews_missing_orders = 0 THEN 'Passed' ELSE 'Warning' END,
            CONVERT(nvarchar(1000), @reviews_missing_orders), N'0 orphan reviews',
            N'Orphan reviews are excluded from order-level review comparisons.'
        );

        DECLARE @invalid_delivery_timestamps bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_orders_typed
            WHERE (NULLIF(order_delivered_customer_timestamp_raw, N'') IS NOT NULL
                   AND order_delivered_customer_timestamp IS NULL)
               OR (NULLIF(order_estimated_delivery_timestamp_raw, N'') IS NOT NULL
                   AND order_estimated_delivery_timestamp IS NULL)
        );
        INSERT @results VALUES
        (
            N'quality.delivery_timestamps_parse',
            CASE WHEN @invalid_delivery_timestamps = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @invalid_delivery_timestamps), N'0 invalid non-empty timestamps',
            N'TRY_CONVERT failures are excluded, never converted to zero dates.'
        );

        DECLARE @invalid_purchase_timestamps bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_orders_typed
            WHERE NULLIF(order_purchase_timestamp_raw, N'') IS NOT NULL
              AND order_purchase_timestamp IS NULL
        );
        INSERT @results VALUES
        (
            N'quality.purchase_timestamps_parse',
            CASE WHEN @invalid_purchase_timestamps = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @invalid_purchase_timestamps),
            N'0 invalid non-empty timestamps',
            N'Invalid purchase timestamps remain NULL and are excluded from duration metrics.'
        );

        DECLARE @missing_delivery_observations bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_order_delivery
            WHERE is_delivery_eligible = 0
        );
        INSERT @results VALUES
        (
            N'quality.delivery_status_exclusions', 'Passed',
            CONVERT(nvarchar(1000), @missing_delivery_observations), N'profiled count',
            N'Non-delivered or missing delivery observations remain explicit exclusions.'
        );

        DECLARE @missing_purchase_timestamps bigint =
            (SELECT COUNT_BIG(*) FROM analytics.vw_orders_typed
             WHERE NULLIF(order_purchase_timestamp_raw, N'') IS NULL);
        DECLARE @missing_actual_delivery_timestamps bigint =
            (SELECT COUNT_BIG(*) FROM analytics.vw_orders_typed
             WHERE NULLIF(order_delivered_customer_timestamp_raw, N'') IS NULL);
        DECLARE @missing_estimated_delivery_timestamps bigint =
            (SELECT COUNT_BIG(*) FROM analytics.vw_orders_typed
             WHERE NULLIF(order_estimated_delivery_timestamp_raw, N'') IS NULL);
        INSERT @results VALUES
        (
            N'missingness.purchase_timestamp', 'Passed',
            CONVERT(nvarchar(1000), @missing_purchase_timestamps), N'profiled count',
            N'Missing purchase timestamps remain NULL and affect duration/month cohorts.'
        );
        INSERT @results VALUES
        (
            N'missingness.actual_delivery_timestamp', 'Passed',
            CONVERT(nvarchar(1000), @missing_actual_delivery_timestamps), N'profiled count',
            N'Missing actual delivery timestamps remain NULL and affect both cohorts.'
        );
        INSERT @results VALUES
        (
            N'missingness.estimated_delivery_timestamp', 'Passed',
            CONVERT(nvarchar(1000), @missing_estimated_delivery_timestamps),
            N'profiled count',
            N'Missing estimated timestamps remain NULL and affect delivery status only.'
        );

        DECLARE @missing_product_categories bigint =
            (SELECT COUNT_BIG(*) FROM analytics.vw_products_canonical
             WHERE product_category_name IS NULL);
        INSERT @results VALUES
        (
            N'missingness.product_category',
            CASE WHEN @missing_product_categories = 0 THEN 'Passed' ELSE 'Warning' END,
            CONVERT(nvarchar(1000), @missing_product_categories), N'0 preferred',
            N'Missing categories are retained under the explicit missing-category label.'
        );

        DECLARE @negative_intervals bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_order_delivery
            WHERE duration_exclusion_reason = N'negative_delivery_interval'
        );
        INSERT @results VALUES
        (
            N'quality.negative_delivery_intervals',
            CASE WHEN @negative_intervals = 0 THEN 'Passed' ELSE 'Warning' END,
            CONVERT(nvarchar(1000), @negative_intervals), N'0 preferred',
            N'Negative intervals are excluded from duration metrics.'
        );

        DECLARE @orders_missing_items bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_orders_typed AS o
            WHERE NOT EXISTS
            (
                SELECT 1 FROM analytics.vw_order_items AS i WHERE i.order_id = o.order_id
            )
        );
        INSERT @results VALUES
        (
            N'relationship.orders_to_items',
            CASE WHEN @orders_missing_items = 0 THEN 'Passed' ELSE 'Warning' END,
            CONVERT(nvarchar(1000), @orders_missing_items), N'0 preferred',
            N'Orders without items remain in global delivery metrics but lack attribution.'
        );

        DECLARE @orders_multiple_reviews bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT order_id FROM analytics.vw_reviews_all
                GROUP BY order_id HAVING COUNT_BIG(*) > 1
            ) AS multiple_reviews
        );
        INSERT @results VALUES
        (
            N'quality.orders_with_multiple_reviews',
            CASE WHEN @orders_multiple_reviews = 0 THEN 'Passed' ELSE 'Warning' END,
            CONVERT(nvarchar(1000), @orders_multiple_reviews), N'documented, not assumed zero',
            N'All reviews remain inspectable; reporting selects one deterministically.'
        );

        DECLARE @missing_review_scores bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_reviews_all
            WHERE review_score IS NULL OR review_score NOT BETWEEN 1 AND 5
        );
        INSERT @results VALUES
        (
            N'quality.missing_or_invalid_review_scores',
            CASE WHEN @missing_review_scores = 0 THEN 'Passed' ELSE 'Warning' END,
            CONVERT(nvarchar(1000), @missing_review_scores), N'0 preferred',
            N'Invalid or missing scores remain unreviewed and are not imputed.'
        );

        DECLARE @multi_seller_orders bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT order_id FROM analytics.vw_order_seller_bridge
                GROUP BY order_id HAVING COUNT_BIG(*) > 1
            ) AS multi_seller
        );
        INSERT @results VALUES
        (
            N'attribution.multi_seller_orders', 'Passed',
            CONVERT(nvarchar(1000), @multi_seller_orders), N'profiled count',
            N'Multi-seller orders are attributed once to each distinct seller and are non-additive.'
        );

        DECLARE @multi_category_orders bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT order_id FROM analytics.vw_order_category_bridge
                GROUP BY order_id HAVING COUNT_BIG(*) > 1
            ) AS multi_category
        );
        INSERT @results VALUES
        (
            N'attribution.multi_category_orders', 'Passed',
            CONVERT(nvarchar(1000), @multi_category_orders), N'profiled count',
            N'Multi-category orders are attributed once to each category and are non-additive.'
        );

        DECLARE @order_delivery_duplicates bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT order_id FROM analytics.vw_order_delivery
                GROUP BY order_id HAVING COUNT_BIG(*) > 1
            ) AS duplicates
        );
        INSERT @results VALUES
        (
            N'grain.order_delivery_unique',
            CASE WHEN @order_delivery_duplicates = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @order_delivery_duplicates), N'0 duplicate order IDs',
            N'Overall KPI view must remain one row per order.'
        );

        DECLARE @seller_bridge_duplicates bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT order_id, seller_id FROM analytics.vw_order_seller_bridge
                GROUP BY order_id, seller_id HAVING COUNT_BIG(*) > 1
            ) AS duplicates
        );
        INSERT @results VALUES
        (
            N'grain.order_seller_bridge_unique',
            CASE WHEN @seller_bridge_duplicates = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @seller_bridge_duplicates), N'0 duplicate bridge keys',
            N'Bridge grain is one row per distinct order and seller.'
        );

        DECLARE @category_bridge_duplicates bigint =
        (
            SELECT COUNT_BIG(*) FROM
            (
                SELECT order_id, product_category_name
                FROM analytics.vw_order_category_bridge
                GROUP BY order_id, product_category_name HAVING COUNT_BIG(*) > 1
            ) AS duplicates
        );
        INSERT @results VALUES
        (
            N'grain.order_category_bridge_unique',
            CASE WHEN @category_bridge_duplicates = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @category_bridge_duplicates), N'0 duplicate bridge keys',
            N'Bridge grain is one row per distinct order and category, including the missing-category label.'
        );

        DECLARE @eligible bigint, @on_time bigint, @late bigint;
        SELECT @eligible = SUM(CASE WHEN is_delivery_eligible = 1 THEN 1 ELSE 0 END),
               @on_time = SUM(CASE WHEN is_delivery_eligible = 1 AND is_late = 0 THEN 1 ELSE 0 END),
               @late = SUM(CASE WHEN is_delivery_eligible = 1 AND is_late = 1 THEN 1 ELSE 0 END)
        FROM analytics.vw_order_delivery;
        INSERT @results VALUES
        (
            N'reconciliation.eligible_equals_on_time_plus_late',
            CASE WHEN ISNULL(@eligible, 0) = ISNULL(@on_time, 0) + ISNULL(@late, 0)
                 THEN 'Passed' ELSE 'Failed' END,
            CONCAT(N'eligible=', @eligible, N'; on_time=', @on_time, N'; late=', @late),
            N'eligible = on_time + late',
            N'Calendar-date classification must be exhaustive for eligible orders.'
        );

        DECLARE @duration_null_violations bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_order_delivery
            WHERE (is_duration_eligible = 0 AND delivery_duration_hours IS NOT NULL)
               OR (is_duration_eligible = 1 AND delivery_duration_hours IS NULL)
        );
        INSERT @results VALUES
        (
            N'quality.duration_null_semantics',
            CASE WHEN @duration_null_violations = 0 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @duration_null_violations), N'0 inconsistent rows',
            N'Missing or invalid durations remain NULL rather than fabricated zeroes.'
        );

        DECLARE @overview_count bigint =
        (
            SELECT source_order_count FROM reporting.vw_delivery_overview
        );
        DECLARE @underlying_count bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_order_delivery
        );
        INSERT @results VALUES
        (
            N'reconciliation.reporting_to_analytical_orders',
            CASE WHEN @overview_count = @underlying_count THEN 'Passed' ELSE 'Failed' END,
            CONCAT(N'reporting=', @overview_count, N'; analytical=', @underlying_count),
            N'equal order counts',
            N'Reporting totals must retain order-level grain.'
        );

        DECLARE @raw_order_count bigint =
            (SELECT COUNT_BIG(*) FROM analytics.vw_current_orders_raw);
        DECLARE @canonical_order_count bigint =
            (SELECT COUNT_BIG(*) FROM analytics.vw_orders_typed);
        INSERT @results VALUES
        (
            N'reconciliation.staging_to_canonical_orders',
            CASE WHEN @raw_order_count = @canonical_order_count
                 THEN 'Passed' ELSE 'Failed' END,
            CONCAT(N'raw=', @raw_order_count, N'; canonical=', @canonical_order_count),
            N'equal when source order IDs are unique',
            N'Canonical selection must not hide order-count multiplication or loss.'
        );

        INSERT audit.validation_results
        (
            validation_run_id, check_id, status, observed_value, expected_value, message
        )
        SELECT @run_id, check_id, status, observed_value, expected_value, message
        FROM @results;

        DECLARE @overall_status varchar(20) =
        (
            SELECT CASE
                WHEN EXISTS (SELECT 1 FROM @results WHERE status = 'Failed') THEN 'Failed'
                WHEN @fail_on_warning = 1
                     AND EXISTS (SELECT 1 FROM @results WHERE status = 'Warning') THEN 'Failed'
                WHEN EXISTS (SELECT 1 FROM @results WHERE status = 'Warning') THEN 'Warning'
                ELSE 'Passed'
            END
        );
        UPDATE audit.validation_runs
        SET status = @overall_status, completed_at_utc = SYSUTCDATETIME()
        WHERE validation_run_id = @run_id;

        COMMIT TRANSACTION;

        SELECT validation_run_id, check_id, status,
               observed_value, expected_value, message
        FROM audit.validation_results
        WHERE validation_run_id = @run_id
        ORDER BY check_id;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
        INSERT audit.validation_runs
        (
            dataset_snapshot_id, status, fail_on_warning,
            completed_at_utc, error_summary
        )
        VALUES
        (
            @current_snapshot_id, 'Failed', @fail_on_warning, SYSUTCDATETIME(),
            LEFT(CONCAT(ERROR_NUMBER(), N': ', ERROR_MESSAGE()), 4000)
        );
        THROW;
    END CATCH;
END;
GO
