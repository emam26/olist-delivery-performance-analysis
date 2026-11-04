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

        INSERT audit.validation_runs (status, fail_on_warning)
        VALUES ('Started', @fail_on_warning);
        SET @run_id = CONVERT(bigint, SCOPE_IDENTITY());

        DECLARE @latest_successful_batches bigint =
        (
            SELECT COUNT_BIG(*)
            FROM
            (
                SELECT dataset_name, MAX(load_batch_id) AS load_batch_id
                FROM audit.load_batches
                WHERE status = 'Succeeded'
                GROUP BY dataset_name
            ) AS batches
        );
        INSERT @results VALUES
        (
            N'load.required_successful_batches',
            CASE WHEN @latest_successful_batches = 6 THEN 'Passed' ELSE 'Failed' END,
            CONVERT(nvarchar(1000), @latest_successful_batches), N'6',
            N'Each required dataset needs a successful current load.'
        );

        DECLARE @batch_count_mismatches bigint =
        (
            SELECT COUNT_BIG(*) FROM audit.load_batches
            WHERE status = 'Succeeded'
              AND expected_row_count IS NOT NULL
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
        WITH latest AS
        (
            SELECT dataset_name, MAX(load_batch_id) AS load_batch_id
            FROM audit.load_batches WHERE status = 'Succeeded' GROUP BY dataset_name
        ),
        staged AS
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
        FROM latest AS l
        INNER JOIN audit.load_batches AS b ON b.load_batch_id = l.load_batch_id
        LEFT JOIN staged AS s ON s.load_batch_id = l.load_batch_id
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

        DECLARE @negative_intervals bigint =
        (
            SELECT COUNT_BIG(*) FROM analytics.vw_order_delivery
            WHERE exclusion_reason = N'negative_delivery_interval'
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

        SELECT check_id, status, observed_value, expected_value, message
        FROM audit.validation_results
        WHERE validation_run_id = @run_id
        ORDER BY check_id;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
        INSERT audit.validation_runs
        (
            status, fail_on_warning, completed_at_utc, error_summary
        )
        VALUES
        (
            'Failed', @fail_on_warning, SYSUTCDATETIME(),
            LEFT(CONCAT(ERROR_NUMBER(), N': ', ERROR_MESSAGE()), 4000)
        );
        THROW;
    END CATCH;
END;
GO
