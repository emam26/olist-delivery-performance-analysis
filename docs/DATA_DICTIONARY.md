# Data dictionary

This dictionary describes the implemented source contracts and analytical meaning.
Exact deployed SQL types remain authoritative in the numbered scripts under `sql/`.

## Source files

### Orders — `olist_orders_dataset.csv`

Grain: one source row intended per `order_id`.

| Field | Meaning | Analytical use |
|---|---|---|
| `order_id` | Source order identifier | Primary analytical grain |
| `customer_id` | Order-specific customer identifier | Join to customers; do not substitute `customer_unique_id` |
| `order_status` | Source fulfillment status | Context and missingness profiling; not used alone to infer delivery |
| `order_purchase_timestamp` | Purchase timestamp | Cohort month and duration start |
| `order_approved_at` | Approval timestamp | Context/quality checks |
| `order_delivered_carrier_date` | Carrier handoff timestamp | Context/quality checks |
| `order_delivered_customer_date` | Customer delivery timestamp | Actual delivery date and duration end |
| `order_estimated_delivery_date` | Promised/estimated delivery timestamp | Delivery classification comparator |

### Order items — `olist_order_items_dataset.csv`

Grain: one source row intended per `(order_id, order_item_id)`.

| Field | Meaning | Analytical use |
|---|---|---|
| `order_id` | Parent order | Join to canonical order |
| `order_item_id` | Item sequence within order | Source item key |
| `product_id` | Product identifier | Join to product/category |
| `seller_id` | Seller identifier | Distinct order-seller bridge |
| `shipping_limit_date` | Seller shipping-limit timestamp | Context only in current scope |
| `price` | Item price | Retained, not a delivery KPI |
| `freight_value` | Item freight value | Retained, not a delivery KPI |

### Customers — `olist_customers_dataset.csv`

Grain: one source row intended per `customer_id`.

| Field | Meaning | Analytical use |
|---|---|---|
| `customer_id` | Order-facing customer key | Correct order-to-customer join |
| `customer_unique_id` | Cross-order customer identity | Retained; not the order foreign key |
| `customer_zip_code_prefix` | Customer postal prefix | Retained; not exposed in headline reporting |
| `customer_city` | Customer city | Optional drill-down |
| `customer_state` | Customer state code | Geographic grouping |

### Sellers — `olist_sellers_dataset.csv`

Grain: one source row intended per `seller_id`.

| Field | Meaning | Analytical use |
|---|---|---|
| `seller_id` | Seller identifier | Order-seller attribution |
| `seller_zip_code_prefix` | Seller postal prefix | Context only |
| `seller_city` | Seller city | Context only |
| `seller_state` | Seller state | Context; not customer geography |

### Products — `olist_products_dataset.csv`

Grain: one source row intended per `product_id`. Source spelling is preserved for
the two `*_lenght` columns.

| Field | Meaning | Analytical use |
|---|---|---|
| `product_id` | Product identifier | Item-to-product join |
| `product_category_name` | Source category label | Distinct order-category bridge |
| `product_name_lenght` | Product-name character count | Retained only |
| `product_description_lenght` | Description character count | Retained only |
| `product_photos_qty` | Product photo count | Retained only |
| `product_weight_g` | Weight in grams | Retained only |
| `product_length_cm` | Length in centimeters | Retained only |
| `product_height_cm` | Height in centimeters | Retained only |
| `product_width_cm` | Width in centimeters | Retained only |

### Order reviews — `olist_order_reviews_dataset.csv`

Source grain is review record; multiple rows can refer to one order.

| Field | Meaning | Analytical use |
|---|---|---|
| `review_id` | Source review identifier | Review identity and tie-breaker |
| `order_id` | Reviewed order | Join to canonical order |
| `review_score` | Integer score expected from 1 through 5 | Descriptive grouped analysis |
| `review_comment_title` | Optional title | Retained, not published in KPI views |
| `review_comment_message` | Optional message | Retained, not published in KPI views |
| `review_creation_date` | Review creation timestamp | Deterministic selection/context |
| `review_answer_timestamp` | Review answer/update timestamp | Deterministic selection/context |

## Technical staging lineage

Every `stg.*_raw` table includes:

| Field | Meaning |
|---|---|
| `<table>_raw_id` | SQL identity for physical row lineage |
| `load_batch_id` | Foreign key to `audit.load_batches` |
| `source_row_number` | One-based CSV data-row number |
| `source_sha256` | Hash of the complete source file loaded in that batch |
| source fields | Original CSV text, with empty fields represented as SQL null |

Staging does not enforce business-key uniqueness because duplicate source rows must
remain observable.

## Audit objects

### `audit.load_batches`

One row per load attempt. Principal fields include dataset name, source file name,
source hash, source byte/row counts, status (`Started`, `Succeeded`, or `Failed`),
start/completion UTC timestamps, inserted row count, and safe error text. A filtered
unique index prevents two successful rows for the same dataset/hash pair.

### `audit.validation_runs`

One row per SQL validation execution, including start/completion UTC timestamps,
status, and safe execution message.

### `audit.validation_results`

One row per check in a validation run: check ID, severity, status, observed and
expected values, and details.

## Principal analytical views

### `analytics.vw_order_delivery`

Grain: one canonical order.

| Field | Meaning |
|---|---|
| `order_id` | Canonical order identifier |
| `customer_id` / `customer_unique_id` | Correctly joined customer identifiers |
| `customer_state` | Customer geography |
| `order_status` | Source order status |
| `order_purchase_timestamp` | Typed purchase timestamp |
| `order_purchase_date` / `purchase_month` | Derived date and month |
| `order_delivered_customer_timestamp` | Typed actual-delivery timestamp |
| `order_estimated_delivery_timestamp` | Typed estimate timestamp |
| `delivery_classification` | `On Time`, `Late`, or `Excluded` |
| `delivery_eligible` | 1 only when delivery classification is possible |
| `days_early_or_late` | Signed calendar-day difference |
| `duration_eligible` | 1 only for valid nonnegative purchase-to-delivery interval |
| `delivery_duration_days` | Fractional elapsed days |
| `exclusion_reason` | Actionable reason for an unavailable core metric |
| `selected_review_score` | One deterministic valid score, otherwise null |

### Bridge views

- `analytics.vw_order_seller_bridge`: one distinct `(order_id, seller_id)`.
- `analytics.vw_order_category_bridge`: one distinct
  `(order_id, product_category_name)`.

These grains are unique by design but are not additive across seller or category.

## Reporting views

The `reporting` schema exposes:

- order-delivery detail;
- overall performance;
- purchase-month performance;
- customer-state performance;
- attributed seller performance;
- attributed category performance;
- selected-review-score performance;
- latest validation results.

Each aggregated view includes the relevant all-order, eligible, excluded, on-time,
and late counts so a consumer can verify its denominator.
