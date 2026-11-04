/* Raw-text staging. Duplicate and problematic business keys stay inspectable. */

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_NAME() IN (N'master', N'model', N'msdb', N'tempdb')
    THROW 51000, 'Run this script only in the dedicated Olist project database.', 1;
IF OBJECT_ID(N'audit.load_batches', N'U') IS NULL
    THROW 51001, 'Run 001_create_schemas.sql first.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'stg.orders', N'U') IS NULL
    BEGIN
        CREATE TABLE stg.orders
        (
            staging_row_id bigint IDENTITY(1, 1) NOT NULL CONSTRAINT PK_stg_orders PRIMARY KEY,
            load_batch_id bigint NOT NULL,
            source_row_number bigint NOT NULL,
            order_id nvarchar(64) NULL,
            customer_id nvarchar(64) NULL,
            order_status nvarchar(50) NULL,
            order_purchase_timestamp nvarchar(64) NULL,
            order_approved_at nvarchar(64) NULL,
            order_delivered_carrier_date nvarchar(64) NULL,
            order_delivered_customer_date nvarchar(64) NULL,
            order_estimated_delivery_date nvarchar(64) NULL,
            source_row_sha256 char(64) NOT NULL,
            staged_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_stg_orders_staged DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT FK_stg_orders_batch FOREIGN KEY (load_batch_id)
                REFERENCES audit.load_batches (load_batch_id),
            CONSTRAINT UQ_stg_orders_batch_row UNIQUE (load_batch_id, source_row_number)
        );
    END;

    IF OBJECT_ID(N'stg.order_items', N'U') IS NULL
    BEGIN
        CREATE TABLE stg.order_items
        (
            staging_row_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_stg_order_items PRIMARY KEY,
            load_batch_id bigint NOT NULL,
            source_row_number bigint NOT NULL,
            order_id nvarchar(64) NULL,
            order_item_id nvarchar(32) NULL,
            product_id nvarchar(64) NULL,
            seller_id nvarchar(64) NULL,
            shipping_limit_date nvarchar(64) NULL,
            price nvarchar(64) NULL,
            freight_value nvarchar(64) NULL,
            source_row_sha256 char(64) NOT NULL,
            staged_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_stg_order_items_staged DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT FK_stg_order_items_batch FOREIGN KEY (load_batch_id)
                REFERENCES audit.load_batches (load_batch_id),
            CONSTRAINT UQ_stg_order_items_batch_row UNIQUE (load_batch_id, source_row_number)
        );
    END;

    IF OBJECT_ID(N'stg.customers', N'U') IS NULL
    BEGIN
        CREATE TABLE stg.customers
        (
            staging_row_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_stg_customers PRIMARY KEY,
            load_batch_id bigint NOT NULL,
            source_row_number bigint NOT NULL,
            customer_id nvarchar(64) NULL,
            customer_unique_id nvarchar(64) NULL,
            customer_zip_code_prefix nvarchar(32) NULL,
            customer_city nvarchar(200) NULL,
            customer_state nvarchar(16) NULL,
            source_row_sha256 char(64) NOT NULL,
            staged_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_stg_customers_staged DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT FK_stg_customers_batch FOREIGN KEY (load_batch_id)
                REFERENCES audit.load_batches (load_batch_id),
            CONSTRAINT UQ_stg_customers_batch_row UNIQUE (load_batch_id, source_row_number)
        );
    END;

    IF OBJECT_ID(N'stg.sellers', N'U') IS NULL
    BEGIN
        CREATE TABLE stg.sellers
        (
            staging_row_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_stg_sellers PRIMARY KEY,
            load_batch_id bigint NOT NULL,
            source_row_number bigint NOT NULL,
            seller_id nvarchar(64) NULL,
            seller_zip_code_prefix nvarchar(32) NULL,
            seller_city nvarchar(200) NULL,
            seller_state nvarchar(16) NULL,
            source_row_sha256 char(64) NOT NULL,
            staged_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_stg_sellers_staged DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT FK_stg_sellers_batch FOREIGN KEY (load_batch_id)
                REFERENCES audit.load_batches (load_batch_id),
            CONSTRAINT UQ_stg_sellers_batch_row UNIQUE (load_batch_id, source_row_number)
        );
    END;

    IF OBJECT_ID(N'stg.products', N'U') IS NULL
    BEGIN
        CREATE TABLE stg.products
        (
            staging_row_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_stg_products PRIMARY KEY,
            load_batch_id bigint NOT NULL,
            source_row_number bigint NOT NULL,
            product_id nvarchar(64) NULL,
            product_category_name nvarchar(200) NULL,
            product_name_lenght nvarchar(32) NULL,
            product_description_lenght nvarchar(32) NULL,
            product_photos_qty nvarchar(32) NULL,
            product_weight_g nvarchar(32) NULL,
            product_length_cm nvarchar(32) NULL,
            product_height_cm nvarchar(32) NULL,
            product_width_cm nvarchar(32) NULL,
            source_row_sha256 char(64) NOT NULL,
            staged_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_stg_products_staged DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT FK_stg_products_batch FOREIGN KEY (load_batch_id)
                REFERENCES audit.load_batches (load_batch_id),
            CONSTRAINT UQ_stg_products_batch_row UNIQUE (load_batch_id, source_row_number)
        );
    END;

    IF OBJECT_ID(N'stg.reviews', N'U') IS NULL
    BEGIN
        CREATE TABLE stg.reviews
        (
            staging_row_id bigint IDENTITY(1, 1) NOT NULL
                CONSTRAINT PK_stg_reviews PRIMARY KEY,
            load_batch_id bigint NOT NULL,
            source_row_number bigint NOT NULL,
            review_id nvarchar(64) NULL,
            order_id nvarchar(64) NULL,
            review_score nvarchar(32) NULL,
            review_comment_title nvarchar(max) NULL,
            review_comment_message nvarchar(max) NULL,
            review_creation_date nvarchar(64) NULL,
            review_answer_timestamp nvarchar(64) NULL,
            source_row_sha256 char(64) NOT NULL,
            staged_at_utc datetime2(7) NOT NULL
                CONSTRAINT DF_stg_reviews_staged DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT FK_stg_reviews_batch FOREIGN KEY (load_batch_id)
                REFERENCES audit.load_batches (load_batch_id),
            CONSTRAINT UQ_stg_reviews_batch_row UNIQUE (load_batch_id, source_row_number)
        );
    END;

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'stg.orders')
        AND name = N'IX_stg_orders_order_id')
        CREATE INDEX IX_stg_orders_order_id ON stg.orders (order_id, load_batch_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'stg.order_items')
        AND name = N'IX_stg_items_order')
        CREATE INDEX IX_stg_items_order
            ON stg.order_items (order_id, order_item_id, load_batch_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'stg.order_items')
        AND name = N'IX_stg_items_seller')
        CREATE INDEX IX_stg_items_seller ON stg.order_items (seller_id, load_batch_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'stg.customers')
        AND name = N'IX_stg_customers_id')
        CREATE INDEX IX_stg_customers_id ON stg.customers (customer_id, load_batch_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'stg.sellers')
        AND name = N'IX_stg_sellers_id')
        CREATE INDEX IX_stg_sellers_id ON stg.sellers (seller_id, load_batch_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'stg.products')
        AND name = N'IX_stg_products_id')
        CREATE INDEX IX_stg_products_id ON stg.products (product_id, load_batch_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'stg.reviews')
        AND name = N'IX_stg_reviews_order')
        CREATE INDEX IX_stg_reviews_order ON stg.reviews (order_id, load_batch_id);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
